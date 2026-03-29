import json
import re
import secrets
import calendar
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import authenticate
from django.contrib.auth.forms import AuthenticationForm, PasswordChangeForm, UserCreationForm
from django.core.cache import cache
from django.core import signing
from django.core.files.storage import default_storage
from django.db import transaction
from django.db.models import Avg, Count, F, Q
from django.http import JsonResponse
from django.shortcuts import render
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST

from .models import (
    Category,
    CommentReview,
    CreatorAccount,
    Course,
    Follow,
    Notification,
    Transaction,
    User,
    UserBehavior,
    UserProfile,
    Video,
    VideoAccess,
    Wallet,
    WatchSession,
    WithdrawalRequest,
)
from .forms import CourseForm, VideoForm


DEFAULT_AVATAR_URL = "https://placehold.co/128x128/e2e8f0/64748b?text=U"


def _json_error(message, status=400):
    """Build a consistent JSON error response.

    Args:
        message: Human-readable error message for the client.
        status: HTTP status code to return (default 400).
    """
    return JsonResponse({'status': 'error', 'message': message}, status=status)


def _json_success(payload=None, status=200):
    """Build a consistent JSON success response with optional payload."""
    data = {'status': 'success'}
    if payload:
        data.update(payload)
    return JsonResponse(data, status=status)


def _tc_to_int(value):
    """Normalize TC values to non-decimal integer for API responses."""
    try:
        return max(0, int(Decimal(str(value))))
    except Exception:
        return 0


def _format_tc_vi(value):
    """Format integer TC with Vietnamese thousands separator using dots."""
    return f"{_tc_to_int(value):,}".replace(',', '.')


def _format_vnd_vi(value):
    """Format integer VND with Vietnamese thousands separator using dots."""
    try:
        return f"{max(0, int(Decimal(str(value)))):,}".replace(',', '.')
    except Exception:
        return '0'


def _profile_balance_tc_int(profile):
    """Read profile TC balance using new field with legacy fallback."""
    if profile is None:
        return 0
    balance_value = profile.balance_tc if profile.balance_tc is not None else profile.wallet_balance
    return _tc_to_int(balance_value)


def _sync_profile_legacy_balance(profile):
    """Mirror decimal balance_tc into legacy wallet_balance integer field."""
    balance_int = _profile_balance_tc_int(profile)
    updates = []
    if profile.wallet_balance != balance_int:
        profile.wallet_balance = balance_int
        updates.append('wallet_balance')
    if profile.balance_tc != Decimal(str(balance_int)):
        profile.balance_tc = Decimal(str(balance_int))
        updates.append('balance_tc')
    if updates:
        profile.save(update_fields=updates)
    return balance_int


def _base_price_minutes(video):
    """Compute base TC price from video duration in minutes unless custom base_price is set."""
    custom = _tc_to_int(getattr(video, 'base_price', 0))
    if custom > 0:
        return custom
    duration = max(0, int(video.duration_seconds or 0))
    return (duration + 30) // 60


def _compute_dynamic_price_tc(video):
    """Dynamic pricing: base from duration + quality bonus from average rating."""
    base_price = _base_price_minutes(video)
    avg_rating = (
        CommentReview.objects.filter(video=video, rating__isnull=False)
        .aggregate(avg=Avg('rating'))
        .get('avg')
    )
    avg_value = float(avg_rating or 0)
    bonus = 0
    if avg_value > 4.8:
        bonus = 5
    elif avg_value > 4.5:
        bonus = 2
    return max(0, base_price + bonus), round(avg_value, 2)


def _parse_json_body(request):
    """Parse request.body as JSON and normalize empty bodies.

    Raises ValueError on invalid JSON so callers can return 400 with details.
    """
    try:
        return json.loads(request.body or '{}')
    except json.JSONDecodeError as exc:
        raise ValueError('Dữ liệu không hợp lệ!') from exc


def _require_auth(request):
    """Guard endpoints using bearer token; returns (user, None) or (None, error)."""
    user = _get_auth_user(request)
    if user:
        return user, None
    return None, _json_error('Vui lòng đăng nhập!', status=401)


def _lock_wallet(user):
    """Lock a user's wallet row for safe balance updates (select_for_update)."""
    return Wallet.objects.select_for_update().get(user=user)


def _issue_token(user):
    """Create a signed bearer token containing the user id and a random nonce."""
    payload = {'uid': user.id, 'nonce': secrets.token_hex(8)}
    return signing.TimestampSigner().sign_object(payload)


def _get_auth_user(request):
    """Extract and verify bearer token; return User or None if invalid/expired."""
    auth_header = request.META.get('HTTP_AUTHORIZATION', '')
    if not auth_header.startswith('Bearer '):
        return None
    raw_token = auth_header.split(' ', 1)[1].strip()
    try:
        data = signing.TimestampSigner().unsign_object(raw_token, max_age=60 * 60 * 24 * 7)  # 7 days
        user_id = data.get('uid')
        return User.objects.filter(id=user_id).first()
    except Exception:
        return None


def _verify_ping_signature(token, max_age_seconds=30):
    """Validate playback ping signature and return payload if valid."""
    signer = signing.TimestampSigner()
    return signer.unsign_object(token, max_age=max_age_seconds)


def _safe_file_url(request, file_field):
    """Return full URL for video file."""
    try:
        if not file_field:
            return ''
        # If already an absolute URL (e.g., Google Drive), return directly
        if isinstance(file_field, str) and file_field.startswith(('http://', 'https://')):
            return file_field
        if hasattr(file_field, 'name') and isinstance(file_field.name, str) and file_field.name.startswith(('http://', 'https://')):
            return file_field.name
        if request:
            return request.build_absolute_uri(file_field.url)
        return file_field.url
    except Exception:
        return ''


def _extract_drive_src(raw_value):
    """Normalize Drive embed input; accept iframe or raw link and return src URL."""
    if not raw_value:
        return ''

    # If an iframe string is passed, pull the src attribute
    src_match = re.search(r'src\s*=\s*["\']([^"\']+)["\']', raw_value)
    if src_match:
        return src_match.group(1).strip()

    # Otherwise, look for a Drive file id and build a preview URL
    id_match = re.search(r"/d/([a-zA-Z0-9_-]+)", raw_value) or re.search(r"id=([a-zA-Z0-9_-]+)", raw_value)
    if id_match:
        return f"https://drive.google.com/file/d/{id_match.group(1)}/preview"

    # Fallback to the provided value
    return raw_value.strip()


def _create_notification(recipient, sender, notification_type, text, link='', video=None):
    """Create a notification row while isolating side effects from main flows."""
    try:
        if not recipient:
            return None
        return Notification.objects.create(
            recipient=recipient,
            sender=sender,
            video=video,
            notification_type=notification_type,
            text=text,
            link=link or '',
        )
    except Exception:
        # Notifications should not break core actions like follow/comment.
        return None


def _get_or_create_profile(user):
    """Get user profile with safe defaults used by profile-centric APIs."""
    return UserProfile.objects.get_or_create(
        user=user,
        defaults={
            'wallet_balance': 5,
            'balance_tc': Decimal('5.00'),
            'notify_comments': True,
            'notify_follows': True,
        },
    )[0]


def _refresh_vip_state(user, profile=None):
    """Keep VIP flags synced between user/profile and auto-expire outdated subscriptions."""
    profile = profile or _get_or_create_profile(user)
    now = timezone.now()

    expiry = profile.vip_expiry or user.vip_expiry
    flagged = bool(profile.is_vip or user.is_vip)
    is_active = bool(flagged and expiry and expiry > now)

    if flagged and expiry and expiry <= now:
        profile.is_vip = False
        profile.vip_expiry = None
        profile.save(update_fields=['is_vip', 'vip_expiry'])
        user.is_vip = False
        user.vip_expiry = None
        user.save(update_fields=['is_vip', 'vip_expiry'])
        return False, None

    updates = []
    if profile.is_vip != bool(user.is_vip):
        profile.is_vip = bool(user.is_vip)
        updates.append('is_vip')
    if profile.vip_expiry != user.vip_expiry:
        profile.vip_expiry = user.vip_expiry
        updates.append('vip_expiry')
    if updates:
        profile.save(update_fields=updates)

    return is_active, expiry


def _get_or_create_creator_account(user):
    """Return creator account row used as pending/available revenue pool."""
    return CreatorAccount.objects.get_or_create(user=user)[0]


def _settle_creator_pending(account):
    """Simple settlement stage: move pending revenue to available balance."""
    if account.pending_vnd > 0:
        account.available_vnd += account.pending_vnd
        account.pending_vnd = Decimal('0.00')
        account.save(update_fields=['available_vnd', 'pending_vnd', 'updated_at'])
    return account


def _add_one_month_safe(dt):
    """Add one calendar month while clamping day to month end when needed."""
    if dt is None:
        return None

    year = dt.year
    month = dt.month + 1
    if month > 12:
        month = 1
        year += 1

    last_day = calendar.monthrange(year, month)[1]
    day = min(dt.day, last_day)
    return dt.replace(year=year, month=month, day=day)


def _profile_avatar_url(request, profile):
    """Build full avatar URL for profile image fields."""
    try:
        if not profile or not profile.avatar:
            return DEFAULT_AVATAR_URL
        if request:
            return request.build_absolute_uri(profile.avatar.url)
        return profile.avatar.url
    except Exception:
        return DEFAULT_AVATAR_URL


def _is_notification_enabled(user, field_name):
    """Check per-user notification preference (defaults to True)."""
    profile = _get_or_create_profile(user)
    return bool(getattr(profile, field_name, True))


def _can_watch_video(user, video):
    """Access rule: owner, free video, purchased access, or active VIP."""
    if not user:
        return False
    if user.id == video.creator_id:
        return True
    if bool(getattr(video, 'is_free', False)):
        return True
    vip_active, _ = _refresh_vip_state(user)
    if vip_active:
        return True
    return VideoAccess.objects.filter(user=user, video=video).exists()


def _is_video_completed(user, video):
    """Determine completion using watch progress against video duration."""
    if not user or not video:
        return False
    required_seconds = max(1, int(video.duration_seconds or 0))
    session = WatchSession.objects.filter(user=user, video=video).first()
    if not session:
        return False
    return int(session.watched_seconds or 0) >= required_seconds


def _prerequisite_gate(user, video):
    """Return whether a user can unlock video based on prerequisite completion."""
    prereq = getattr(video, 'prerequisite_video', None)
    if not prereq:
        return True, None, ''

    if not user:
        return False, prereq.id, prereq.title

    if user.id == video.creator_id:
        return True, prereq.id, prereq.title

    vip_active, _ = _refresh_vip_state(user)
    if vip_active:
        return True, prereq.id, prereq.title

    if _is_video_completed(user, prereq):
        return True, prereq.id, prereq.title

    return False, prereq.id, prereq.title


def _creator_avg_rating(user):
    """Average rating across all creator videos; returns float in [0, 5]."""
    agg = CommentReview.objects.filter(
        video__creator=user,
        rating__isnull=False,
    ).aggregate(avg=Avg('rating'))
    return float(agg.get('avg') or 0)


def _process_video_purchase(user, video):
    """Unlock a specific video for the user with atomic TC deduction and 70/30 split."""
    price_int, avg_rating = _compute_dynamic_price_tc(video)
    if bool(getattr(video, 'is_free', False)):
        price_int = 0
    price = Decimal(str(price_int))

    # Fast path for already-unlocked videos
    if VideoAccess.objects.filter(user=user, video=video).exists():
        video_url = _safe_file_url(None, video.file_url)
        profile = _get_or_create_profile(user)
        remaining_int = _sync_profile_legacy_balance(profile)
        remaining = Decimal(str(remaining_int))
        return {
            'remaining_tc': remaining,
            'remaining_balance': remaining_int,
            'balance': remaining_int,
            'balance_display': f"{_format_tc_vi(remaining_int)} TC",
            'video_url': video_url,
            'videoUrl': video_url,
            'price_tc': price,
            'dynamic_price_tc': price_int,
            'avg_rating': avg_rating,
            'message': 'Video đã được mở khóa trước đó',
        }, None

    did_charge_user = False
    try:
        with transaction.atomic():
            # Create access inside transaction so failures roll back the unlock record
            access, created = VideoAccess.objects.select_for_update().get_or_create(user=user, video=video)
            if not created:
                profile = _get_or_create_profile(user)
                remaining_int = _sync_profile_legacy_balance(profile)
                remaining = Decimal(str(remaining_int))
                video_url = _safe_file_url(None, video.file_url)
                return {
                    'remaining_tc': remaining,
                    'remaining_balance': remaining_int,
                    'balance': remaining_int,
                    'balance_display': f"{_format_tc_vi(remaining_int)} TC",
                    'video_url': video_url,
                    'videoUrl': video_url,
                    'price_tc': price,
                    'dynamic_price_tc': price_int,
                    'avg_rating': avg_rating,
                    'message': 'Video đã được mở khóa trước đó',
                }, None

            vip_active, _ = _refresh_vip_state(user)

            # Free videos (or VIP viewers) are unlocked without balance deduction
            if price > 0 and not vip_active:
                profile = UserProfile.objects.select_for_update().get_or_create(
                    user=user,
                    defaults={'wallet_balance': 5, 'balance_tc': Decimal('5.00')},
                )[0]
                wallet = _lock_wallet(user)
                current_balance = _profile_balance_tc_int(profile)
                if current_balance < price_int:
                    raise ValueError('Số dư TC không đủ để mở khóa video này.')

                next_balance = current_balance - price_int

                UserProfile.objects.filter(pk=profile.pk).update(
                    balance_tc=F('balance_tc') - Decimal(str(price_int)),
                    wallet_balance=F('wallet_balance') - price_int,
                )
                profile.refresh_from_db(fields=['balance_tc', 'wallet_balance'])

                Wallet.objects.filter(pk=wallet.pk).update(balance=F('balance') - Decimal(str(price_int)))
                wallet.refresh_from_db(fields=['balance'])

                Transaction.objects.create(
                    sender=user,
                    receiver=video.creator,
                    tx_type='CONTENT_SALE',
                    amount_tc=price,
                    tc_added=Decimal('0.00'),
                    reference_video=video,
                    status='SUCCESS',
                )

                # Revenue split: 70% to creator pending_vnd (1 TC = 100 VND), 30% kept by platform.
                creator_share_vnd = int(price_int * 0.7 * 100)
                if user.id != video.creator_id and creator_share_vnd > 0:
                    creator_account = CreatorAccount.objects.select_for_update().get_or_create(user=video.creator)[0]
                    CreatorAccount.objects.filter(pk=creator_account.pk).update(
                        pending_vnd=F('pending_vnd') + Decimal(str(creator_share_vnd)),
                        total_earned_vnd=F('total_earned_vnd') + Decimal(str(creator_share_vnd)),
                    )
                    creator_account.refresh_from_db(fields=['pending_vnd', 'total_earned_vnd'])

                    Transaction.objects.create(
                        sender=user,
                        receiver=video.creator,
                        tx_type='CONTENT_SALE',
                        amount_tc=Decimal(str(price_int)),
                        amount_vnd=Decimal(str(creator_share_vnd)),
                        tc_added=Decimal('0.00'),
                        reference_video=video,
                        status='PENDING',
                    )
                did_charge_user = True
            else:
                profile = _get_or_create_profile(user)
                next_balance = _sync_profile_legacy_balance(profile)
                wallet = Wallet.objects.filter(user=user).first()
                if wallet and _tc_to_int(wallet.balance) != next_balance:
                    Wallet.objects.filter(pk=wallet.pk).update(balance=Decimal(str(next_balance)))
                    wallet.refresh_from_db(fields=['balance'])

            session, _ = WatchSession.objects.get_or_create(user=user, video=video)
            if not session.is_unlocked:
                session.is_unlocked = True
                session.save(update_fields=['is_unlocked'])

            # Purchase notifications are only for newly-paid unlocks.
            if did_charge_user:
                buyer_text = f"Bạn đã mở khóa {video.title}. -{price_int} TC"
                _create_notification(
                    recipient=user,
                    sender=video.creator,
                    notification_type=Notification.TYPE_PURCHASE,
                    text=buyer_text,
                    link=f"video-detail.html?id={video.id}",
                    video=video,
                )

                if user.id != video.creator_id:
                    creator_share_vnd = int(price_int * 0.7 * 100)
                    creator_text = f"{user.username} đã mua {video.title}. +{_format_vnd_vi(creator_share_vnd)} VND (Pending)"
                    _create_notification(
                        recipient=video.creator,
                        sender=user,
                        notification_type=Notification.TYPE_PURCHASE,
                        text=creator_text,
                        link=f"video-detail.html?id={video.id}",
                        video=video,
                    )

    except Wallet.DoesNotExist:
        return None, _json_error('Ví không tồn tại.', status=404)
    except ValueError as exc:
        return None, _json_error(str(exc), status=400)
    except Exception as exc:
        return None, _json_error(str(exc), status=500)

    remaining_int = _sync_profile_legacy_balance(profile)
    remaining = Decimal(str(remaining_int))
    video_url = _safe_file_url(None, video.file_url)
    return {
        'remaining_tc': remaining,
        'remaining_balance': remaining_int,
        'balance': remaining_int,
        'balance_display': f"{_format_tc_vi(remaining_int)} TC",
        'video_url': video_url,
        'videoUrl': video_url,
        'price_tc': price,
        'dynamic_price_tc': price_int,
        'avg_rating': avg_rating,
    }, None

def register_view(request):
    """Render and handle the standard Django form-based registration page."""
    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            token = _issue_token(user)
            return _json_success({'token': token}, status=201)
    else:
        form = UserCreationForm()
    return render(request, 'register.html', {'form': form})

def login_view(request):
    """Render and handle the form-based login page."""
    if request.method == 'POST':
        form = AuthenticationForm(data=request.POST)
        if form.is_valid():
            user = form.get_user()
            token = _issue_token(user)
            return _json_success({'token': token})
    else:
        form = AuthenticationForm()
    return render(request, 'login.html', {'form': form})
    return render(request, 'login.html', {'form': form})
  
def create_course(request):
    """Render the frontend page where creators can upload a new course with video."""
    return render(request, 'create_course.html')

@csrf_exempt
@require_POST
def api_register(request):
    """API: Create a new user with basic validation and duplicate checks."""
    try:
        data = _parse_json_body(request)
    except ValueError as exc:
        return _json_error(str(exc), status=400)

    username = data.get('username', '').strip()
    email = data.get('email', '').strip()
    password = data.get('password', '')

    # Basic required-field and length checks to fail fast client-side mistakes
    if not username or not email or not password:
        return _json_error('Vui lòng điền đầy đủ tất cả các trường!')

    if len(password) < 8:
        return _json_error('Mật khẩu phải có ít nhất 8 ký tự!')

    # Enforce uniqueness on email/username to avoid IntegrityErrors
    if User.objects.filter(email=email).exists():
        return _json_error('Email này đã được sử dụng! Vui lòng chọn email khác.')

    if User.objects.filter(username=username).exists():
        return _json_error('Tên người dùng này đã tồn tại! Vui lòng chọn tên khác.')

    try:
        user = User.objects.create_user(username=username, email=email, password=password)
    except Exception as exc:
        return _json_error(f'Lỗi hệ thống: {exc}', status=500)

    token = _issue_token(user)

    return _json_success({'message': 'Đăng ký thành công!', 'token': token}, status=201)

@csrf_exempt
@require_POST
def api_login(request):
    """API: Authenticate a user by email+password and create session."""
    try:
        data = _parse_json_body(request)
    except ValueError as exc:
        return _json_error(str(exc), status=400)

    email = data.get('email', '').strip()
    password = data.get('password', '')

    user_obj = User.objects.filter(email=email).first()
    if not user_obj:
        return _json_error('Email chưa đăng ký!')

    # Authenticate uses username internally, so map email -> username
    user = authenticate(request, username=user_obj.username, password=password)
    if user is None:
        return _json_error('Sai mật khẩu! Vui lòng kiểm tra lại.')

    token = _issue_token(user)
    return _json_success({
        'token': token,
        'username': user.username,
        'user_id': user.id,
    })

@csrf_exempt
@require_GET
def api_get_wallet(request):
    """API: Get wallet balance for the authenticated user."""
    user = _get_auth_user(request)
    if not user:
        return _json_error('Unauthorized', status=401)
    
    try:
        profile = _get_or_create_profile(user)
        wallet, _ = Wallet.objects.get_or_create(user=user)
        balance_int = _sync_profile_legacy_balance(profile)

        # Keep wallet mirrored for legacy code paths.
        if _tc_to_int(wallet.balance) != balance_int:
            wallet.balance = Decimal(str(balance_int))
            wallet.save(update_fields=['balance', 'updated_at'])

        return _json_success({
            'balance': balance_int,
            'balance_tc': balance_int,
            'balance_display': f"{_format_tc_vi(balance_int)} TC",
            'user_id': user.id,
            'username': user.username,
            'email': user.email,
        })
    except Wallet.DoesNotExist:
        return _json_error('Wallet not found', status=404)
    except Exception as e:
        return _json_error(str(e), status=500)

@require_GET
def api_profile(request):
    """API: Return current user's profile plus wallet balances."""
    user, auth_error = _require_auth(request)
    if auth_error:
        return auth_error

    # Profile is the source of truth for balance.
    profile = _get_or_create_profile(user)
    vip_active, vip_expiry = _refresh_vip_state(user, profile)
    wallet, _ = Wallet.objects.get_or_create(user=user)
    creator_account = CreatorAccount.objects.filter(user=user).first()
    balance_int = _sync_profile_legacy_balance(profile)

    # Keep wallet mirror aligned for legacy screens.
    if _tc_to_int(wallet.balance) != balance_int:
        wallet.balance = Decimal(str(balance_int))
        wallet.save(update_fields=['balance', 'updated_at'])

    return _json_success({
        'id': user.id,
        'username': user.username,
        'email': user.email,
        'join_date': user.date_joined.isoformat() if user.date_joined else None,
        'join_date_display': user.date_joined.strftime('%d/%m/%Y') if user.date_joined else None,
        'wallet_balance': balance_int,
        'balance_tc': balance_int,
        'wallet_balance_display': f"{_format_tc_vi(balance_int)} TC",
        'balance': balance_int,
        'balance_display': f"{_format_tc_vi(balance_int)} TC",
        'is_vip': bool(vip_active),
        'vip_expiry': vip_expiry.isoformat() if vip_expiry else None,
        'vip_expiry_display': vip_expiry.strftime('%d/%m/%Y') if vip_expiry else None,
        'creator_available_vnd': _tc_to_int(creator_account.available_vnd) if creator_account else 0,
        'creator_pending_vnd': _tc_to_int(creator_account.pending_vnd) if creator_account else 0,
        'creator_total_earned_vnd': _tc_to_int(creator_account.total_earned_vnd) if creator_account else 0,
        'creator_available_balance': _tc_to_int(creator_account.available_vnd) if creator_account else 0,
        'creator_pending_balance': _tc_to_int(creator_account.pending_vnd) if creator_account else 0,
        'creator_total_earned': _tc_to_int(creator_account.total_earned_vnd) if creator_account else 0,
    })


@require_GET
def api_me(request):
    """API: Return latest profile/user data for global sync on page load."""
    user, auth_error = _require_auth(request)
    if auth_error:
        return auth_error

    profile = _get_or_create_profile(user)
    vip_active, vip_expiry = _refresh_vip_state(user, profile)
    creator_account = CreatorAccount.objects.filter(user=user).first()
    balance_int = _sync_profile_legacy_balance(profile)

    return _json_success({
        'id': user.id,
        'username': user.username,
        'email': user.email,
        'join_date': user.date_joined.isoformat() if user.date_joined else None,
        'join_date_display': user.date_joined.strftime('%d/%m/%Y') if user.date_joined else None,
        'tc_balance': balance_int,
        'balance_tc': balance_int,
        'tc_balance_display': f"{_format_tc_vi(balance_int)} TC",
        'avatar_url': _profile_avatar_url(request, profile),
        'notify_comments': bool(profile.notify_comments),
        'notify_follows': bool(profile.notify_follows),
        'dark_mode': bool(profile.dark_mode),
        'is_vip': bool(vip_active),
        'vip_expiry': vip_expiry.isoformat() if vip_expiry else None,
        'vip_expiry_display': vip_expiry.strftime('%d/%m/%Y') if vip_expiry else None,
        'creator_available_vnd': _tc_to_int(creator_account.available_vnd) if creator_account else 0,
        'creator_pending_vnd': _tc_to_int(creator_account.pending_vnd) if creator_account else 0,
        'creator_total_earned_vnd': _tc_to_int(creator_account.total_earned_vnd) if creator_account else 0,
        'creator_available_balance': _tc_to_int(creator_account.available_vnd) if creator_account else 0,
        'creator_pending_balance': _tc_to_int(creator_account.pending_vnd) if creator_account else 0,
        'creator_total_earned': _tc_to_int(creator_account.total_earned_vnd) if creator_account else 0,
    })


@csrf_exempt
def api_user_settings(request):
    """API: Get or update persisted UI settings for the authenticated user."""
    user, auth_error = _require_auth(request)
    if auth_error:
        return auth_error

    profile = _get_or_create_profile(user)

    if request.method == 'GET':
        return _json_success({
            'dark_mode': bool(profile.dark_mode),
            'notify_comments': bool(profile.notify_comments),
            'notify_follows': bool(profile.notify_follows),
        })

    if request.method in ('PATCH', 'POST'):
        try:
            data = _parse_json_body(request)
        except ValueError as exc:
            return _json_error(str(exc), status=400)

        update_fields = []
        if 'dark_mode' in data:
            profile.dark_mode = bool(data.get('dark_mode'))
            update_fields.append('dark_mode')
        if 'notify_comments' in data:
            profile.notify_comments = bool(data.get('notify_comments'))
            update_fields.append('notify_comments')
        if 'notify_follows' in data:
            profile.notify_follows = bool(data.get('notify_follows'))
            update_fields.append('notify_follows')

        if update_fields:
            profile.save(update_fields=update_fields)

        return _json_success({
            'dark_mode': bool(profile.dark_mode),
            'notify_comments': bool(profile.notify_comments),
            'notify_follows': bool(profile.notify_follows),
        })

    return _json_error('Method not allowed', status=405)


@csrf_exempt
@require_POST
def api_me_change_password(request):
    """API: Change password using Django PasswordChangeForm validation logic."""
    user, auth_error = _require_auth(request)
    if auth_error:
        return auth_error

    try:
        data = _parse_json_body(request)
    except ValueError as exc:
        return _json_error(str(exc), status=400)

    form = PasswordChangeForm(user, data={
        'old_password': data.get('old_password', ''),
        'new_password1': data.get('new_password1', ''),
        'new_password2': data.get('new_password2', ''),
    })
    if not form.is_valid():
        return _json_error(form.errors.as_json(), status=400)

    form.save()
    return _json_success({'message': 'Đổi mật khẩu thành công. Vui lòng đăng nhập lại.'})


@require_GET
def api_check_username(request):
    """API: Check if a username is available."""
    user, auth_error = _require_auth(request)
    if auth_error:
        return auth_error

    username = (request.GET.get('username') or '').strip()
    if not username:
        return _json_error('Thiếu username cần kiểm tra!', status=400)

    exists = User.objects.filter(username__iexact=username).exclude(id=user.id).exists()
    return _json_success({'available': not exists})


@csrf_exempt
@require_POST
def api_me_update_username(request):
    """API: Update current username after availability check."""
    user, auth_error = _require_auth(request)
    if auth_error:
        return auth_error

    try:
        data = _parse_json_body(request)
    except ValueError as exc:
        return _json_error(str(exc), status=400)

    new_username = (data.get('username') or '').strip()
    if len(new_username) < 3:
        return _json_error('Username phải có ít nhất 3 ký tự.', status=400)

    if User.objects.filter(username__iexact=new_username).exclude(id=user.id).exists():
        return _json_error('Username đã tồn tại.', status=409)

    user.username = new_username
    user.save(update_fields=['username'])

    return _json_success({'message': 'Đổi username thành công.', 'username': user.username})


@csrf_exempt
@require_POST
def api_me_upload_avatar(request):
    """API: Update current user's avatar image via AJAX multipart upload."""
    user, auth_error = _require_auth(request)
    if auth_error:
        return auth_error

    avatar = request.FILES.get('avatar')
    if not avatar:
        return _json_error('Thiếu file avatar!', status=400)

    if not str(getattr(avatar, 'content_type', '')).startswith('image/'):
        return _json_error('Avatar phải là file ảnh hợp lệ.', status=400)

    max_size_bytes = 5 * 1024 * 1024
    if int(getattr(avatar, 'size', 0) or 0) > max_size_bytes:
        return _json_error('Ảnh quá lớn. Vui lòng chọn file <= 5MB.', status=400)

    try:
        profile = _get_or_create_profile(user)
        profile.avatar = avatar
        profile.save(update_fields=['avatar'])
    except Exception:
        return _json_error('Không thể lưu avatar. Vui lòng thử lại sau.', status=500)

    return _json_success({
        'message': 'Cập nhật avatar thành công.',
        'avatar_url': _profile_avatar_url(request, profile),
    })


@csrf_exempt
@require_POST
def api_me_remove_avatar(request):
    """API: Remove current avatar and reset profile avatar to default."""
    user, auth_error = _require_auth(request)
    if auth_error:
        return auth_error

    profile = _get_or_create_profile(user)
    old_name = str(getattr(profile.avatar, 'name', '') or '')

    # Reset to empty/default so UI always falls back to safe placeholder.
    profile.avatar = ''
    profile.save(update_fields=['avatar'])

    # Best effort cleanup of uploaded file, skipping known default name.
    if old_name and old_name != 'default.png':
        try:
            default_storage.delete(old_name)
        except Exception:
            pass

    return _json_success({
        'message': 'Đã gỡ avatar, quay về ảnh mặc định.',
        'avatar_url': _profile_avatar_url(request, profile),
    })


@csrf_exempt
@require_POST
def api_me_preferences(request):
    """API: Update profile preferences like notification toggles."""
    user, auth_error = _require_auth(request)
    if auth_error:
        return auth_error

    try:
        data = _parse_json_body(request)
    except ValueError as exc:
        return _json_error(str(exc), status=400)

    profile = _get_or_create_profile(user)

    if 'notify_comments' in data:
        profile.notify_comments = bool(data.get('notify_comments'))
    if 'notify_follows' in data:
        profile.notify_follows = bool(data.get('notify_follows'))

    profile.save(update_fields=['notify_comments', 'notify_follows'])

    return _json_success({
        'notify_comments': bool(profile.notify_comments),
        'notify_follows': bool(profile.notify_follows),
    })

def main_view(request):
    """Serve main page if authenticated; otherwise redirect to login."""
    return _json_error('This endpoint is deprecated in API mode.', status=410)

def user_logout(request):
    """Terminate session then return user to main view."""
    return _json_success({'message': 'Stateless tokens do not require logout. Discard the token client-side.'})

@csrf_exempt
@require_POST
def ping_watch_session(request):
    """API: Increment watched seconds for a watch session heartbeat."""
    user, auth_error = _require_auth(request)
    if auth_error:
        return auth_error

    try:
        data = _parse_json_body(request)
    except ValueError as exc:
        return _json_error(str(exc), status=400)

    session_id = data.get('session_id')
    signature = data.get('signature')

    if not session_id or not signature:
        return _json_error('Thiếu session_id hoặc signature!', status=400)

    session = WatchSession.objects.filter(id=session_id, user=user).first()
    if not session:
        return _json_error('Session không tồn tại hoặc không thuộc về bạn!', status=404)

    # Anti-cheat: enforce >=9s between pings using cached last-seen timestamps
    try:
        payload = _verify_ping_signature(signature)
    except Exception:
        return _json_error('Chữ ký không hợp lệ hoặc đã hết hạn!', status=403)

    # Require signature to be tied to the same user and session
    if payload.get('uid') != user.id or payload.get('sid') != session_id:
        return _json_error('Chữ ký không hợp lệ!', status=403)

    cache_key = f"watch-ping:{user.id}:{session_id}"
    now = timezone.now()
    last_seen = cache.get(cache_key)
    if last_seen and (now - last_seen).total_seconds() < 9:
        return _json_error('Phát hiện spam ping!', status=403)

    cache.set(cache_key, now, timeout=60)

    # Add 10 seconds per heartbeat; UI should call every 10s from player
    session.watched_seconds += 10
    session.save(update_fields=['watched_seconds', 'last_ping_time'])

    return _json_success({'watched_seconds': session.watched_seconds})

@csrf_exempt
@require_POST
def api_upload_video(request):
    """API: Save an uploaded video file and return its served URL."""
    user, auth_error = _require_auth(request)
    if auth_error:
        return auth_error

    if not user.is_creator:
        return _json_error('Chỉ Creator mới được phép tải video lên.', status=403)

    video_file = request.FILES.get('video_file')
    if not video_file:
        return _json_error('Không tìm thấy file video đính kèm!')

    filename = default_storage.save(f"videos/{video_file.name}", video_file)
    video_url = default_storage.url(filename)

    return _json_success({'message': 'Upload video thành công!', 'video_url': video_url}, status=201)


@csrf_exempt
def api_course_list_create(request):
    """List active courses or create a new course (creators only)."""
    if request.method == 'GET':
        q = request.GET.get('q', '').strip()
        category_text = (request.GET.get('category') or '').strip()
        qs = Course.objects.filter(is_deleted=False, is_active=True)
        if q:
            qs = qs.filter(Q(title__icontains=q))
        if category_text:
            qs = qs.filter(category_text__icontains=category_text)
        data = [
            {
                'id': c.id,
                'title': c.title,
                'description': c.description,
                'category': c.category_text,
                'instructor': c.instructor.username,
            }
            for c in qs.order_by('-created_at')
        ]
        return _json_success({'courses': data})

    if request.method == 'POST':
        user, auth_error = _require_auth(request)
        if auth_error:
            return auth_error
        if not user.is_creator:
            return _json_error('Chỉ Creator mới được phép tạo khóa học.', status=403)
        try:
            data = _parse_json_body(request)
        except ValueError as exc:
            return _json_error(str(exc), status=400)

        payload = dict(data)
        payload['category_text'] = (data.get('category_text') or data.get('category') or '').strip()
        form = CourseForm(payload)
        if not form.is_valid():
            return _json_error(form.errors.as_json(), status=400)

        course = form.save(commit=False)
        course.instructor = user
        course.save()

        return _json_success({
            'id': course.id,
            'title': course.title,
            'description': course.description,
        }, status=201)

    return _json_error('Method not allowed', status=405)


@csrf_exempt
def api_course_detail(request, course_id):
    """Retrieve, update, or soft-delete a course."""
    try:
        course = Course.objects.get(id=course_id, is_deleted=False)
    except Course.DoesNotExist:
        return _json_error('Khóa học không tồn tại.', status=404)

    if request.method == 'GET':
        viewer = _get_auth_user(request)
        videos = Video.objects.filter(course=course, is_deleted=False, is_active=True).select_related('prerequisite_video').order_by('created_at')
        unlocked_video_ids = set()
        completed_video_ids = set()
        if viewer:
            unlocked_video_ids = set(
                VideoAccess.objects.filter(user=viewer, video__course=course).values_list('video_id', flat=True)
            )
            course_video_ids = [v.id for v in videos]
            if course_video_ids:
                progress = WatchSession.objects.filter(user=viewer, video_id__in=course_video_ids).values_list('video_id', 'watched_seconds')
                duration_map = {v.id: max(1, int(v.duration_seconds or 0)) for v in videos}
                completed_video_ids = {
                    vid for vid, watched in progress
                    if int(watched or 0) >= int(duration_map.get(vid, 1))
                }

        lessons = []
        viewer_is_vip = False
        if viewer:
            viewer_is_vip, _ = _refresh_vip_state(viewer)
        for lesson in videos:
            duration_seconds = int(lesson.duration_seconds or 0)
            computed_price, _ = _compute_dynamic_price_tc(lesson)
            if lesson.is_free:
                computed_price = 0
            is_unlocked = False
            prerequisite_completed = True
            prerequisite_id = lesson.prerequisite_video_id
            prerequisite_title = lesson.prerequisite_video.title if lesson.prerequisite_video else ''
            if lesson.prerequisite_video_id and viewer:
                prerequisite_completed = lesson.prerequisite_video_id in completed_video_ids
            if lesson.prerequisite_video_id and not viewer:
                prerequisite_completed = False
            if viewer:
                is_owner = lesson.creator_id == viewer.id or course.instructor_id == viewer.id
                is_unlocked = is_owner or viewer_is_vip or lesson.id in unlocked_video_ids or computed_price == 0
                if is_owner or viewer_is_vip or computed_price == 0:
                    prerequisite_completed = True
            # Access means the user can play now; prerequisite only controls unlock eligibility.
            can_access = bool(is_unlocked)
            can_unlock = bool(prerequisite_completed and not is_unlocked)
            lessons.append({
                'id': lesson.id,
                'title': lesson.title,
                'duration_seconds': duration_seconds,
                'price_tc': computed_price,
                'is_free': bool(lesson.is_free),
                'is_unlocked': is_unlocked,
                'prerequisite_id': prerequisite_id,
                'prerequisite_title': prerequisite_title,
                'prerequisite_completed': bool(prerequisite_completed),
                'can_access': can_access,
                'can_unlock': can_unlock,
            })

        return _json_success({
            'id': course.id,
            'title': course.title,
            'description': course.description,
            'category': course.category_text,
            'instructor': course.instructor.username,
            'instructor_id': course.instructor_id,
            'videos': lessons,
        })

    user, auth_error = _require_auth(request)
    if auth_error:
        return auth_error
    if not user.is_creator or course.instructor_id != user.id:
        return _json_error('Chỉ Creator sở hữu khóa học mới được sửa/xóa.', status=403)

    if request.method in ['PUT', 'PATCH']:
        try:
            data = _parse_json_body(request)
        except ValueError as exc:
            return _json_error(str(exc), status=400)
        merged = {field: data.get(field, getattr(course, field)) for field in CourseForm.Meta.fields}
        form = CourseForm(merged, instance=course)
        if not form.is_valid():
            return _json_error(form.errors.as_json(), status=400)
        form.save()
        return _json_success({'message': 'Cập nhật khóa học thành công.'})

    if request.method == 'DELETE':
        course.is_active = False
        course.is_deleted = True
        course.save(update_fields=['is_active', 'is_deleted'])
        return _json_success({'message': 'Đã xóa mềm khóa học.'})

    return _json_error('Method not allowed', status=405)


@csrf_exempt
def api_video_list_create(request):
    """List active videos or create a new video (creators only)."""
    if request.method == 'GET':
        viewer = _get_auth_user(request)
        q = request.GET.get('q', '').strip()
        course_id = request.GET.get('course')
        standalone = request.GET.get('standalone')
        qs = Video.objects.filter(is_deleted=False, is_active=True)
        if q:
            qs = qs.filter(Q(title__icontains=q))
        if course_id:
            qs = qs.filter(course_id=course_id)
        if standalone is not None:
            standalone_flag = str(standalone).lower() in {'1', 'true', 'yes'}
            qs = qs.filter(is_standalone=standalone_flag)
        data = []
        for v in qs.order_by('-created_at'):
            can_watch = _can_watch_video(viewer, v)
            data.append({
                'id': v.id,
                'title': v.title,
                'course': v.course_id,
                'category': v.category.name if v.category else None,
                'price_tc': int(v.price_tc),
                'duration_seconds': v.duration_seconds,
                'creator': v.creator.username,
                'creator_id': v.creator_id,
                'is_standalone': v.is_standalone,
                'is_unlocked': bool(can_watch),
                'thumbnail': _safe_file_url(request, v.thumbnail),
                'file_url': _safe_file_url(request, v.file_url) if can_watch else '',
            })
        return _json_success({'videos': data})

    if request.method == 'POST':
        user, auth_error = _require_auth(request)
        if auth_error:
            return auth_error
        if not user.is_creator:
            return _json_error('Chỉ Creator mới được phép tải video.', status=403)

        form = VideoForm(request.POST)
        if not form.is_valid():
            return _json_error(form.errors.as_json(), status=400)

        video = form.save(commit=False)
        video.creator = user

        upload = request.FILES.get('file_url') or request.FILES.get('video_file')
        if upload:
            stored_name = default_storage.save(f"videos/{upload.name}", upload)
            video.file_url = stored_name
            video.video_file = stored_name

        thumb = request.FILES.get('thumbnail')
        if thumb:
            stored_thumb = default_storage.save(f"thumbnails/{thumb.name}", thumb)
            video.thumbnail = stored_thumb

        video.save()

        return _json_success({'id': video.id, 'title': video.title, 'file_url': _safe_file_url(request, video.file_url)}, status=201)

    return _json_error('Method not allowed', status=405)


@csrf_exempt
def api_video_detail(request, video_id):
    """Retrieve, update, or soft-delete a video."""
    try:
        video = Video.objects.get(id=video_id, is_deleted=False)
    except Video.DoesNotExist:
        return _json_error('Video không tồn tại.', status=404)

    if request.method == 'GET':
        user = _get_auth_user(request)
        can_watch = _can_watch_video(user, video)
        return _json_success({
            'id': video.id,
            'title': video.title,
            'description': video.description,
            'price_tc': int(video.price_tc),
            'course': video.course_id,
            'category': video.category.name if video.category else None,
            'duration_seconds': video.duration_seconds,
            'is_standalone': video.is_standalone,
            'is_locked': not can_watch,
            'file_url': _safe_file_url(request, video.file_url) if can_watch else '',
            'thumbnail': _safe_file_url(request, video.thumbnail),
        })

    user, auth_error = _require_auth(request)
    if auth_error:
        return auth_error
    if not user.is_creator or video.creator_id != user.id:
        return _json_error('Chỉ Creator sở hữu video mới được sửa/xóa.', status=403)

    if request.method in ['PUT', 'PATCH']:
        if request.content_type and request.content_type.startswith('application/json'):
            try:
                payload = _parse_json_body(request)
            except ValueError as exc:
                return _json_error(str(exc), status=400)
            files_payload = {}
        else:
            payload = request.POST
            files_payload = request.FILES

        merged = {field: payload.get(field, getattr(video, field)) for field in VideoForm.Meta.fields}
        form = VideoForm(merged, instance=video)
        if not form.is_valid():
            return _json_error(form.errors.as_json(), status=400)

        video = form.save(commit=False)

        upload = files_payload.get('file_url') or files_payload.get('video_file')
        if upload:
            stored_name = default_storage.save(f"videos/{upload.name}", upload)
            video.file_url = stored_name
            video.video_file = stored_name

        thumb = files_payload.get('thumbnail')
        if thumb:
            stored_thumb = default_storage.save(f"thumbnails/{thumb.name}", thumb)
            video.thumbnail = stored_thumb

        video.save()
        return _json_success({'message': 'Cập nhật video thành công.'})

    if request.method == 'DELETE':
        video.is_active = False
        video.is_deleted = True
        video.save(update_fields=['is_active', 'is_deleted'])
        return _json_success({'message': 'Đã xóa mềm video.'})

    return _json_error('Method not allowed', status=405)


def homepage(request):
    """Public homepage listing active courses with optional search filters."""
    q = request.GET.get('q', '').strip()
    category_text = (request.GET.get('category') or '').strip()
    courses = Course.objects.filter(is_deleted=False, is_active=True)
    if q:
        courses = courses.filter(title__icontains=q)
    if category_text:
        courses = courses.filter(category_text__icontains=category_text)

    categories = Category.objects.all()

    context = {
        'courses': courses.order_by('-created_at'),
        'query': q,
        'category_id': category_text,
        'categories': categories,
    }
    return render(request, 'main.html', context)

@require_GET
def api_get_video_detail(request, video_id):
    """API: Fetch video metadata, lock state, and creator info for the viewer."""
    user, auth_error = _require_auth(request)
    if auth_error:
        return auth_error

    try:
        video = Video.objects.get(id=video_id, is_active=True, is_deleted=False)
    except Video.DoesNotExist:
        return _json_error('Video không tồn tại!', status=404)

    is_owner = user.id == video.creator_id
    vip_active, _ = _refresh_vip_state(user)
    dynamic_price_tc, avg_rating = _compute_dynamic_price_tc(video)
    if video.is_free:
        dynamic_price_tc = 0
    session, _ = WatchSession.objects.get_or_create(user=user, video=video)

    has_access = _can_watch_video(user, video)
    if has_access and not session.is_unlocked:
        session.is_unlocked = True
        session.save(update_fields=['is_unlocked'])

    locked = not has_access
    following = Follow.objects.filter(follower=user, following=video.creator).exists()
    can_unlock_by_prerequisite, prerequisite_id, prerequisite_title = _prerequisite_gate(user, video)
    prerequisite_completed = True
    if prerequisite_id:
        prerequisite_completed = _is_video_completed(user, video.prerequisite_video)
    if is_owner or vip_active or dynamic_price_tc == 0:
        can_unlock_by_prerequisite = True
        prerequisite_completed = True

    data = {
        'id': video.id,
        'title': video.title,
        'description': video.description,
        'locked': locked,
        'is_locked': locked,
        'price_tc': int(dynamic_price_tc),
        'requiredTC': int(dynamic_price_tc),
        'is_owner': is_owner,
        'is_free': bool(video.is_free),
        'is_vip': bool(vip_active),
        'avg_rating': avg_rating,
        'prerequisite_id': prerequisite_id,
        'prerequisite_title': prerequisite_title,
        'prerequisite_completed': bool(prerequisite_completed),
        'can_unlock_by_prerequisite': bool(can_unlock_by_prerequisite),
        'videoUrl': None if locked else _safe_file_url(request, video.file_url),
        'watchSessionId': session.id,
        'creator': {
            'id': video.creator.id,
            'name': video.creator.username,
            'avatar': f"https://ui-avatars.com/api/?name={video.creator.username}",
        },
        'following': following,
    }

    return _json_success(data)

@csrf_exempt
@require_POST
def api_unlock_video(request, video_id):
    """API: Unlock a video using TC and return the playable URL."""
    user, auth_error = _require_auth(request)
    if auth_error:
        return auth_error

    try:
        video = Video.objects.select_related('prerequisite_video').get(id=video_id, is_active=True)
    except Video.DoesNotExist:
        return _json_error('Video không tồn tại!', status=404)

    is_allowed, _, prereq_title = _prerequisite_gate(user, video)
    if not is_allowed:
        return _json_error(f'Bạn cần hoàn thành {prereq_title} để mở khóa bài này!', status=403)

    payload, error = _process_video_purchase(user, video)
    if error:
        return error
    return _json_success({'message': 'Mở khóa video thành công!', **payload})


@csrf_exempt
@require_POST
def api_unlock_video_by_body(request):
    """API: Unlock a video by video_id in JSON body at /api/unlock-video/."""
    user, auth_error = _require_auth(request)
    if auth_error:
        return auth_error

    try:
        data = _parse_json_body(request)
    except ValueError as exc:
        return _json_error(str(exc), status=400)

    video_id = data.get('video_id')
    if not video_id:
        return _json_error('Thiếu video_id!', status=400)

    try:
        video = Video.objects.select_related('prerequisite_video').get(id=video_id, is_active=True, is_deleted=False)
    except Video.DoesNotExist:
        return _json_error('Video không tồn tại!', status=404)

    is_allowed, _, prereq_title = _prerequisite_gate(user, video)
    if not is_allowed:
        return _json_error(f'Bạn cần hoàn thành {prereq_title} để mở khóa bài này!', status=403)

    payload, error = _process_video_purchase(user, video)
    if error:
        return error

    return _json_success({'message': 'Mở khóa video thành công!', **payload})


@require_GET
def api_creator_price_eligibility(request):
    """API: return whether creator can manually override per-video price."""
    user, auth_error = _require_auth(request)
    if auth_error:
        return auth_error

    avg_rating = round(_creator_avg_rating(user), 2)
    eligible = avg_rating > 4.5
    return _json_success({
        'eligible': eligible,
        'avg_rating': avg_rating,
        'min_override_tc': 1,
        'max_override_tc': 5,
    })


@require_GET
def api_get_courses(request):
    """API: Return active courses and categories for catalog display."""
    viewer = _get_auth_user(request)
    categories = list(Category.objects.values('id', 'name'))  # Used for filters

    purchased_course_ids = set()
    if viewer:
        purchased_course_ids = set(
            VideoAccess.objects.filter(user=viewer, video__course__isnull=False)
            .values_list('video__course_id', flat=True)
            .distinct()
        )

    course_qs = (
        Course.objects.filter(is_active=True, is_deleted=False)
        .select_related('instructor')
        .order_by('-created_at')
    )

    courses = [
        {
            'id': course.id,
            'title': course.title,
            'category_text': course.category_text,
            'creator_id': course.instructor_id,
            'creator_name': course.instructor.username,
            'instructor__id': course.instructor_id,
            'instructor__username': course.instructor.username,
            'is_purchased': bool(course.id in purchased_course_ids),
            'created_at': course.created_at.isoformat(),
        }
        for course in course_qs
    ]

    return _json_success({'categories': categories, 'courses': courses})


@require_GET
def api_categories(request):
    """API: Return categories only (id, name) for dropdowns."""
    categories = list(Category.objects.values('id', 'name'))
    return _json_success({'categories': categories})


@require_GET
def api_teachers(request):
    """API: Return ranked teachers (creators) by total views then average rating."""
    user, auth_error = _require_auth(request)
    if auth_error:
        return auth_error

    try:
        teachers_qs = (
            User.objects.filter(uploaded_videos__is_active=True, uploaded_videos__is_deleted=False)
            .distinct()
            .annotate(
                total_views=Count('uploaded_videos__watchsession', distinct=True),
                avg_rating=Avg(
                    'uploaded_videos__comments__rating',
                    filter=Q(uploaded_videos__comments__rating__isnull=False),
                ),
            )
            .order_by('-total_views', '-avg_rating', 'username')
        )

        data = []
        for teacher in teachers_qs:
            profile = _get_or_create_profile(teacher)
            is_following = Follow.objects.filter(follower=user, following=teacher).exists()
            data.append({
                'id': teacher.id,
                'username': teacher.username,
                'avatar_url': _profile_avatar_url(request, profile) or f"https://ui-avatars.com/api/?name={teacher.username}",
                'specialization': profile.specialization or 'Giang vien da linh vuc',
                'bio': profile.bio or 'Chua cap nhat mo ta linh vuc giang day.',
                'total_views': int(teacher.total_views or 0),
                'avg_rating': round(float(teacher.avg_rating or 0), 2),
                'followers_count': Follow.objects.filter(following=teacher).count(),
                'is_following': bool(is_following),
            })

        return _json_success({'teachers': data})
    except Exception as exc:
        return _json_error(f'Khong the tai danh sach giao vien: {exc}', status=500)
    
@csrf_exempt
@require_POST
def api_toggle_follow(request, creator_id=None):
    """API: Toggle follow/unfollow for a creator, blocking self-follow.
    Supports both JSON body (creator_id) and REST-style path parameter.
    The response now returns the boolean follow state and the current follower count
    to allow the frontend to update the UI without reloading.
    All database operations are wrapped to avoid unhandled exceptions.
    """
    user, auth_error = _require_auth(request)
    if auth_error:
        return auth_error

    creator_id_value = creator_id
    if creator_id_value is None:
        try:
            data = _parse_json_body(request)
        except ValueError as exc:
            return _json_error(str(exc), status=400)
        creator_id_value = data.get('creator_id')

    if not creator_id_value:
        return _json_error('Thiếu creator_id!', status=400)

    try:
        creator = User.objects.get(id=creator_id_value)
    except User.DoesNotExist:
        return _json_error('Không tìm thấy Creator này!', status=404)

    if user == creator:
        return _json_error('Bạn không thể tự follow chính mình!')

    try:
        # A single record represents follow; presence => following
        follow_record = Follow.objects.filter(follower=user, following=creator).first()
        if follow_record:
            follow_record.delete()
            is_following = False
        else:
            Follow.objects.create(follower=user, following=creator)
            is_following = True
            if _is_notification_enabled(creator, 'notify_follows'):
                _create_notification(
                    recipient=creator,
                    sender=user,
                    notification_type=Notification.TYPE_FOLLOW,
                    text=f"{user.username} đã theo dõi bạn",
                    link=f"/channel.html?id={user.id}",
                )

        followers_count = Follow.objects.filter(following=creator).count()
    except Exception as exc:
        return _json_error(str(exc), status=500)

    return _json_success({'is_following': is_following, 'followers_count': followers_count})

@csrf_exempt
@require_POST
def api_creator_notify_toggle(request):
    """API: Stub to enable creator notifications; returns success for now."""
    user, auth_error = _require_auth(request)
    if auth_error:
        return auth_error

    # TODO: Persist notification preference once schema supports it.
    return _json_success({'message': 'Đã bật thông báo Creator.'})

@csrf_exempt
@require_POST
def api_purchase_video(request):
    """API: Deduct TC from buyer, credit creator, and unlock the video atomically."""
    user, auth_error = _require_auth(request)
    if auth_error:
        return auth_error

    try:
        data = _parse_json_body(request)
    except ValueError as exc:
        return _json_error(str(exc), status=400)

    video_id = data.get('video_id')

    try:
        video = Video.objects.get(id=video_id, is_active=True)
    except Video.DoesNotExist:
        return _json_error('Video không tồn tại!', status=404)

    payload, error = _process_video_purchase(user, video)
    if error:
        return error

    return _json_success({'message': 'Mua video thành công!', **payload})


@csrf_exempt
@require_POST
def api_recharge_tc(request):
    """API: Recharge TC by paying VND with fixed conversion 10,000 VND = 100 TC."""
    user, auth_error = _require_auth(request)
    if auth_error:
        return auth_error

    try:
        data = _parse_json_body(request)
    except ValueError as exc:
        return _json_error(str(exc), status=400)

    amount_vnd = int(data.get('amount_vnd') or 10000)
    if amount_vnd <= 0 or amount_vnd % 10000 != 0:
        return _json_error('Số tiền nạp phải là bội số của 10.000 VND.', status=400)

    tc_added = amount_vnd // 100

    try:
        with transaction.atomic():
            profile = UserProfile.objects.select_for_update().get_or_create(
                user=user,
                defaults={'wallet_balance': 5, 'balance_tc': Decimal('5.00')},
            )[0]
            wallet, _ = Wallet.objects.select_for_update().get_or_create(user=user)

            UserProfile.objects.filter(pk=profile.pk).update(
                balance_tc=F('balance_tc') + Decimal(str(tc_added)),
                wallet_balance=F('wallet_balance') + tc_added,
            )
            Wallet.objects.filter(pk=wallet.pk).update(balance=F('balance') + Decimal(str(tc_added)))

            profile.refresh_from_db(fields=['balance_tc', 'wallet_balance'])
            new_balance = _profile_balance_tc_int(profile)

            Transaction.objects.create(
                sender=user,
                receiver=user,
                tx_type='RECHARGE',
                amount_tc=Decimal(str(tc_added)),
                amount_vnd=Decimal(str(amount_vnd)),
                tc_added=Decimal(str(tc_added)),
                status='SUCCESS',
            )

            _create_notification(
                recipient=user,
                sender=None,
                notification_type=Notification.TYPE_PURCHASE,
                text=f"Nạp thành công {amount_vnd:,} VND. +{tc_added} TC".replace(',', '.'),
                link='profile.html#wallet',
            )
    except Exception as exc:
        return _json_error(str(exc), status=500)

    return _json_success({
        'message': 'Nạp TC thành công.',
        'balance': new_balance,
        'balance_display': f"{_format_tc_vi(new_balance)} TC",
        'tc_added': tc_added,
        'amount_vnd': amount_vnd,
    })


@csrf_exempt
@require_POST
def api_purchase_vip(request):
    """API: Purchase or renew VIP by charging TC and extending expiry by one month."""
    user, auth_error = _require_auth(request)
    if auth_error:
        return auth_error

    package_price_vnd = Decimal('149000')
    vip_cost_tc = 149

    try:
        with transaction.atomic():
            profile = UserProfile.objects.select_for_update().get_or_create(
                user=user,
                defaults={'wallet_balance': 5, 'balance_tc': Decimal('5.00')},
            )[0]
            wallet, _ = Wallet.objects.select_for_update().get_or_create(user=user)

            balance_int = _sync_profile_legacy_balance(profile)
            if balance_int < vip_cost_tc:
                return _json_error('So du TC khong du de mua/gia han VIP.', status=400)

            now = timezone.now()
            current_expiry = profile.vip_expiry or user.vip_expiry
            is_renewal = bool(current_expiry and current_expiry > now and (profile.is_vip or user.is_vip))
            base_time = current_expiry if current_expiry and current_expiry > now else now
            new_expiry = _add_one_month_safe(base_time)

            new_balance_int = max(0, balance_int - vip_cost_tc)

            profile.is_vip = True
            profile.vip_expiry = new_expiry
            profile.balance_tc = Decimal(str(new_balance_int))
            profile.wallet_balance = new_balance_int
            profile.save(update_fields=['is_vip', 'vip_expiry', 'balance_tc', 'wallet_balance'])

            user.is_vip = True
            user.vip_expiry = new_expiry
            user.save(update_fields=['is_vip', 'vip_expiry'])

            wallet.balance = Decimal(str(new_balance_int))
            wallet.save(update_fields=['balance'])

            Transaction.objects.create(
                sender=user,
                receiver=user,
                tx_type='VIP_PURCHASE',
                amount_tc=Decimal(str(vip_cost_tc)),
                amount_vnd=package_price_vnd,
                tc_added=Decimal('0.00'),
                status='SUCCESS',
            )

            _create_notification(
                recipient=user,
                sender=None,
                notification_type=Notification.TYPE_PURCHASE,
                text=(
                    f"Gia han VIP thanh cong den {new_expiry.strftime('%d/%m/%Y')}"
                    if is_renewal else
                    f"Kich hoat VIP thanh cong den {new_expiry.strftime('%d/%m/%Y')}"
                ),
                link='profile.html#wallet',
            )
    except Exception as exc:
        return _json_error(str(exc), status=500)

    return _json_success({
        'message': 'Gia han VIP thanh cong.' if is_renewal else 'Mua VIP thanh cong.',
        'is_vip': True,
        'is_renewal': is_renewal,
        'vip_cost_tc': vip_cost_tc,
        'balance': new_balance_int,
        'balance_tc': new_balance_int,
        'balance_display': f"{_format_tc_vi(new_balance_int)} TC",
        'vip_expiry': new_expiry.isoformat(),
        'vip_expiry_display': new_expiry.strftime('%d/%m/%Y'),
    })


@csrf_exempt
@require_POST
def api_withdraw_request(request):
    """API: Create a withdrawal request when creator available balance is above threshold."""
    user, auth_error = _require_auth(request)
    if auth_error:
        return auth_error

    try:
        data = _parse_json_body(request)
    except ValueError as exc:
        return _json_error(str(exc), status=400)

    try:
        with transaction.atomic():
            account = CreatorAccount.objects.select_for_update().get_or_create(user=user)[0]

            available_vnd = _tc_to_int(account.available_vnd)
            if available_vnd <= 50000:
                return _json_error('Can toi thieu hon 50.000 VND kha dung de gui yeu cau rut.', status=400)

            requested = data.get('amount_vnd')
            if requested is None:
                withdraw_vnd = available_vnd
            else:
                withdraw_vnd = int(requested)

            if withdraw_vnd <= 50000:
                return _json_error('So tien rut phai lon hon 50.000 VND.', status=400)
            if withdraw_vnd > available_vnd:
                return _json_error('So du kha dung khong du.', status=400)

            CreatorAccount.objects.filter(pk=account.pk).update(
                available_vnd=F('available_vnd') - Decimal(str(withdraw_vnd))
            )
            account.refresh_from_db(fields=['available_vnd'])

            amount_vnd = Decimal(str(withdraw_vnd))
            withdraw_tc = int(withdraw_vnd / 100)
            request_row = WithdrawalRequest.objects.create(
                user=user,
                amount_tc=Decimal(str(withdraw_tc)),
                amount_vnd=amount_vnd,
                status='PENDING',
                note='Auto-generated from profile withdrawal request',
            )

            Transaction.objects.create(
                sender=user,
                receiver=None,
                tx_type='WITHDRAW_VND',
                amount_tc=Decimal(str(withdraw_tc)),
                amount_vnd=amount_vnd,
                tc_added=Decimal('0.00'),
                status='PENDING',
            )

            _create_notification(
                recipient=user,
                sender=None,
                notification_type=Notification.TYPE_PURCHASE,
                text=f"Yeu cau rut {_format_vnd_vi(withdraw_vnd)} VND da duoc tao (ma {request_row.id}).",
                link='profile.html#wallet',
            )
    except Exception as exc:
        return _json_error(str(exc), status=500)

    return _json_success({
        'message': 'Đã gửi yêu cầu rút tiền.',
        'request_id': request_row.id,
        'amount_tc': withdraw_tc,
        'amount_vnd': int(amount_vnd),
        'remaining_available_vnd': _tc_to_int(account.available_vnd),
    })


@csrf_exempt
@require_POST
def api_post_comment(request):
    """API: Create a comment/review and notify the creator if applicable."""
    user, auth_error = _require_auth(request)
    if auth_error:
        return auth_error

    try:
        data = _parse_json_body(request)
    except ValueError as exc:
        return _json_error(str(exc), status=400)

    video_id = data.get('video_id')
    content = (data.get('content') or '').strip()
    rating = data.get('rating')

    try:
        rating_value = int(rating)
    except (TypeError, ValueError):
        return _json_error('Số sao không hợp lệ. Chỉ chấp nhận từ 1 đến 5.', status=400)

    if rating_value < 1 or rating_value > 5:
        return _json_error('Số sao không hợp lệ. Chỉ chấp nhận từ 1 đến 5.', status=400)

    if not content:
        return _json_error('Bạn chưa nhập nội dung bình luận!', status=400)

    try:
        video = Video.objects.get(id=video_id)
    except Video.DoesNotExist:
        return _json_error('Video không tồn tại!', status=404)

    CommentReview.objects.create(
        user=user,
        video=video,
        content=content,
        rating=rating_value,
    )

    if user != video.creator and _is_notification_enabled(video.creator, 'notify_comments'):
        _create_notification(
            recipient=video.creator,
            sender=user,
            notification_type=Notification.TYPE_RATING,
            text=f"{user.username} đã đánh giá {rating_value} sao cho video của bạn",
            link=f"/video-detail.html?id={video.id}",
            video=video,
        )

    return _json_success({'message': 'Đã gửi bình luận!'})

@require_GET
def api_get_notifications(request):
    """API: Fetch recent notifications plus unread count for the current user."""
    user, auth_error = _require_auth(request)
    if auth_error:
        return auth_error

    # Pull latest notifications; limit to keep payload small
    notifs = Notification.objects.filter(recipient=user).select_related('sender', 'video').order_by('-created_at')[:20]

    data = [
        {
            'id': n.id,
            'text': n.text,
            'content': n.text,
            'notification_type': n.notification_type,
            'sender': {
                'id': n.sender_id,
                'username': n.sender.username if n.sender else None,
            },
            'sender_name': n.sender.username if n.sender else 'Hệ thống',
            'video_id': n.video_id,
            'video_title': n.video.title if n.video else None,
            'video_thumbnail': _safe_file_url(request, n.video.thumbnail) if n.video and n.video.thumbnail else '',
            'is_read': n.is_read,
            'created_at': n.created_at.strftime("%H:%M %d/%m/%Y"),
        }
        for n in notifs
    ]

    unread_count = Notification.objects.filter(recipient=user, is_read=False).count()

    return _json_success({'notifications': data, 'unread_count': unread_count})


@csrf_exempt
@require_POST
def mark_notifications_as_read(request):
    """API: Mark all unread notifications as read for current user."""
    user, auth_error = _require_auth(request)
    if auth_error:
        return auth_error

    Notification.objects.filter(recipient=user, is_read=False).update(is_read=True)
    return JsonResponse({'status': 'success'})


@require_GET
def api_video_comments(request, video_id):
    """API: List comments with ratings for one video."""
    comments = CommentReview.objects.filter(video_id=video_id).select_related('user').order_by('-created_at')[:100]
    return JsonResponse([
        {
            'id': c.id,
            'user': c.user.username,
            'comment': c.content,
            'content': c.content,
            'rating': c.rating,
            'created_at': c.created_at.strftime("%H:%M %d/%m/%Y"),
        }
        for c in comments
    ], safe=False)


@csrf_exempt
@require_POST
def api_video_comment(request, video_id):
    """API: Path-style comment endpoint for frontend compatibility."""
    user, auth_error = _require_auth(request)
    if auth_error:
        return auth_error

    try:
        data = _parse_json_body(request)
    except ValueError as exc:
        return _json_error(str(exc), status=400)

    content = (data.get('content') or data.get('comment') or '').strip()
    rating = data.get('rating')

    try:
        rating_value = int(rating)
    except (TypeError, ValueError):
        rating_value = 0

    if rating_value <= 0:
        return _json_error('Bạn phải đánh giá sao trước khi bình luận!', status=400)

    if rating_value < 1 or rating_value > 5:
        return _json_error('Số sao không hợp lệ. Chỉ chấp nhận từ 1 đến 5.', status=400)

    if not content:
        return _json_error('Bạn chưa nhập nội dung bình luận!', status=400)

    try:
        video = Video.objects.get(id=video_id, is_active=True, is_deleted=False)
    except Video.DoesNotExist:
        return _json_error('Video không tồn tại!', status=404)

    CommentReview.objects.create(
        user=user,
        video=video,
        content=content,
        rating=rating_value,
    )

    if user != video.creator and _is_notification_enabled(video.creator, 'notify_comments'):
        _create_notification(
            recipient=video.creator,
            sender=user,
            notification_type=Notification.TYPE_RATING,
            text=f"{user.username} đã đánh giá {rating_value} sao cho video của bạn",
            link=f"/video-detail.html?id={video.id}",
            video=video,
        )

    return _json_success({'message': 'Đã gửi bình luận!'})
    
@csrf_exempt
@require_POST
def api_reward_ads(request):
    """API: Reward TC for ad view with anti-spam timing guard and ledger entry."""
    user, auth_error = _require_auth(request)
    if auth_error:
        return auth_error

    now = timezone.now()

    # Anti-spam: require at least 30 seconds between ad rewards
    last_ad_tx = Transaction.objects.filter(receiver=user, tx_type='EARN_ADS').order_by('-timestamp').first()
    if last_ad_tx and (now - last_ad_tx.timestamp).total_seconds() < 30:
        user.trust_score -= 5
        user.save(update_fields=['trust_score'])
        return _json_error('Phát hiện spam! Bạn xem quảng cáo quá nhanh. Bị trừ 5 điểm uy tín.', status=429)

    reward_amount = Decimal('0.50')

    try:
        with transaction.atomic():
            wallet = _lock_wallet(user)
            profile = UserProfile.objects.select_for_update().get_or_create(
                user=user,
                defaults={'wallet_balance': 5, 'balance_tc': Decimal('5.00')},
            )[0]

            Wallet.objects.filter(pk=wallet.pk).update(balance=F('balance') + reward_amount)
            UserProfile.objects.filter(pk=profile.pk).update(
                balance_tc=F('balance_tc') + reward_amount,
                wallet_balance=F('wallet_balance') + _tc_to_int(reward_amount),
            )
            wallet.refresh_from_db(fields=['balance'])

            Transaction.objects.create(
                receiver=user,
                tx_type='EARN_ADS',
                amount_tc=reward_amount,
                status='SUCCESS',
            )
    except Wallet.DoesNotExist:
        return _json_error('Ví không tồn tại. Vui lòng liên hệ hỗ trợ.', status=500)
    except Exception as exc:
        return _json_error(str(exc), status=500)

    return _json_success({'message': f'Đã cộng {reward_amount} TC vào ví!', 'new_balance': wallet.balance})


@csrf_exempt
@require_POST
def earn_tc(request):
    """API: Add exactly 1 TC for current user and return updated balance."""
    user, auth_error = _require_auth(request)
    if auth_error:
        return auth_error

    try:
        with transaction.atomic():
            profile, _ = UserProfile.objects.select_for_update().get_or_create(
                user=user,
                defaults={'wallet_balance': 5, 'balance_tc': Decimal('5.00')},
            )
            wallet, _ = Wallet.objects.select_for_update().get_or_create(user=user)

            UserProfile.objects.filter(pk=profile.pk).update(
                balance_tc=F('balance_tc') + Decimal('1.00'),
                wallet_balance=F('wallet_balance') + 1,
            )
            Wallet.objects.filter(pk=wallet.pk).update(balance=F('balance') + Decimal('1.00'))
            wallet.refresh_from_db(fields=['balance'])

            Transaction.objects.create(
                receiver=user,
                tx_type='EARN_ADS',
                amount_tc=Decimal('1.00'),
                status='SUCCESS',
            )
    except Exception as exc:
        return _json_error(str(exc), status=500)

    new_balance_int = _tc_to_int(wallet.balance)
    return _json_success({
        'new_balance': new_balance_int,
        'new_balance_display': f"{_format_tc_vi(new_balance_int)} TC",
    })


@csrf_exempt
@require_POST
def reward_ad_view(request):
    """API: Grant 1 TC for a confirmed 30s ad view with simple rate limit."""
    user, auth_error = _require_auth(request)
    if auth_error:
        return auth_error

    cache_key = f"ad-reward-30s:{user.id}"
    now = timezone.now()
    last = cache.get(cache_key)
    if last and (now - last).total_seconds() < 30:
        return _json_error('Bạn đang nhận thưởng quá nhanh, vui lòng đợi.', status=429)

    try:
        with transaction.atomic():
            wallet = Wallet.objects.select_for_update().get(user=user)
            profile = UserProfile.objects.select_for_update().get_or_create(
                user=user,
                defaults={'wallet_balance': 5, 'balance_tc': Decimal('5.00')},
            )[0]

            Wallet.objects.filter(pk=wallet.pk).update(balance=F('balance') + Decimal('1.00'))
            UserProfile.objects.filter(pk=profile.pk).update(
                balance_tc=F('balance_tc') + Decimal('1.00'),
                wallet_balance=F('wallet_balance') + 1,
            )
            wallet.refresh_from_db(fields=['balance'])

            Transaction.objects.create(
                receiver=user,
                tx_type='EARN_ADS',
                amount_tc=Decimal('1.00'),
                status='SUCCESS',
            )
    except Wallet.DoesNotExist:
        return _json_error('Ví không tồn tại. Vui lòng liên hệ hỗ trợ.', status=404)
    except Exception as exc:
        return _json_error(str(exc), status=500)

    cache.set(cache_key, now, timeout=60)

    return _json_success({'message': 'Đã cộng 1 TC sau khi xem quảng cáo 30s!', 'new_balance': wallet.balance})

@csrf_exempt
@require_POST
def api_log_behavior(request):
    """API: Log granular playback interactions for analytics (supports anonymous)."""
    user = _get_auth_user(request)

    try:
        data = _parse_json_body(request)
    except ValueError as exc:
        return _json_error(str(exc), status=400)

    video_id = data.get('video_id')
    event_type = data.get('event_type')
    timestamp_sec = data.get('video_timestamp_seconds', 0)

    try:
        video = Video.objects.get(id=video_id)
    except Video.DoesNotExist:
        return _json_error('Video không tồn tại!', status=404)

    user_agent = request.META.get('HTTP_USER_AGENT', '')[:150]  # Capture lightweight device fingerprint

    UserBehavior.objects.create(
        user=user,
        video=video,
        event_type=event_type,
        video_timestamp_seconds=timestamp_sec,
        device_info=user_agent,
    )

    return _json_success()

@csrf_exempt
@require_POST
def api_select_role(request):
    """API: Save the user's chosen role into their profile."""
    try:
        data = _parse_json_body(request)
    except ValueError as exc:
        return _json_error(str(exc), status=400)

    user, auth_error = _require_auth(request)
    if auth_error:
        email = data.get('email')
        if email:
            user = User.objects.filter(email=email).first()
        if not user:
            return auth_error

    role = data.get('role')

    try:
        profile, _ = UserProfile.objects.get_or_create(user=user)
        profile.role = role  # Overwrite or set the role selection
        profile.save(update_fields=['role'])
    except Exception as exc:
        return _json_error(str(exc), status=400)

    return _json_success({'message': 'Cập nhật role thành công!'})

@csrf_exempt
@require_POST
def api_survey(request):
    """API: Lưu câu trả lời khảo sát; tạo Profile nếu chưa có dựa trên role gửi lên."""
    try:
        data = _parse_json_body(request)
    except ValueError as exc:
        return _json_error(str(exc), status=400)

    user, auth_error = _require_auth(request)
    if auth_error:
        email = data.get('email')
        if email:
            user = User.objects.filter(email=email).first()
        if not user:
            return auth_error

    answers = data.get('answers')
    role = data.get('role')

    try:
        profile, created = UserProfile.objects.update_or_create(
            user=user,
            defaults={
                'role': role if role else 'student', 
                'survey_answers': answers
            }
        )
        
        if not created and role:
            profile.role = role
            profile.save(update_fields=['role', 'survey_answers'])
            
    except Exception as exc:
        return _json_error(str(exc), status=400)
    return _json_success({'message': 'Lưu khảo sát thành công!'})

@csrf_exempt
@require_POST
def api_create_course_with_video(request):
    """API: Create a new course along with a video upload in one shot.

    Expects a multipart/form-data POST with fields:
    - title
    - description
    - category (id)
    - videos_json / videos payload containing per-video duration + pricing data
    - thumbnail (optional image file)

    The newly created course is owned by request.user and a Video linked to
    that course is also created.  Returns {"success": true} on success.
    """
    user, auth_error = _require_auth(request)
    if auth_error:
        return auth_error

    is_json = request.content_type and 'application/json' in request.content_type
    if is_json:
        try:
            payload = _parse_json_body(request)
        except ValueError as exc:
            return _json_error(str(exc), status=400)
        data = payload
        files = {}
    else:
        data = request.POST
        files = request.FILES

    title = (data.get('title') or '').strip()
    description = (data.get('description') or '').strip()
    category_text = (data.get('category_text') or data.get('category') or '').strip()
    videos_json_raw = data.get('videos_json')
    videos_payload_direct = data.get('videos') if is_json else None

    if not title or not description:
        return _json_error('Thiếu dữ liệu cần thiết!', status=400)

    videos_payload = []
    if videos_payload_direct is not None:
        if not isinstance(videos_payload_direct, list) or not videos_payload_direct:
            return _json_error('Danh sách video không hợp lệ!', status=400)
        videos_payload = videos_payload_direct
    elif videos_json_raw:
        try:
            parsed = json.loads(videos_json_raw)
        except Exception:
            return _json_error('videos_json không hợp lệ!', status=400)
        if not isinstance(parsed, list) or not parsed:
            return _json_error('Danh sách video không hợp lệ!', status=400)
        videos_payload = parsed
    else:
        return _json_error('Thiếu danh sách video theo định dạng mới.', status=400)

    form = CourseForm({
        'title': title,
        'description': description,
        'category_text': category_text,
    })

    if not form.is_valid():
        return _json_error(form.errors.as_json(), status=400)

    creator_avg_rating = round(_creator_avg_rating(user), 2)
    creator_can_override = creator_avg_rating > 4.5

    try:
        with transaction.atomic():
            course = form.save(commit=False)
            course.instructor = user
            course.save()

            created = []
            temp_to_video = {}

            for index, item in enumerate(videos_payload):
                v_title = (item.get('title') or title).strip()
                v_description = (item.get('description') or description).strip()
                v_temp_id = (item.get('temp_id') or f'video_{index + 1}').strip()
                v_prereq_temp = item.get('prerequisite_temp_id')
                v_url = _extract_drive_src((item.get('video_url') or '').strip())

                try:
                    v_duration = int(item.get('duration_seconds'))
                    if v_duration <= 0:
                        raise ValueError()
                except Exception:
                    return _json_error(f'duration_seconds không hợp lệ ở video #{index + 1}!', status=400)

                computed_tc = max(1, (v_duration + 59) // 60)
                override_tc = item.get('manual_price_tc')
                base_price_tc = computed_tc

                if override_tc not in (None, '', 'null'):
                    if not creator_can_override:
                        return _json_error('Bạn chưa đủ điều kiện tự đặt giá video.', status=400)
                    try:
                        override_value = int(override_tc)
                    except Exception:
                        return _json_error('Giá tùy chỉnh không hợp lệ.', status=400)
                    if override_value < 1 or override_value > 5:
                        return _json_error('Giá tối đa cho phép là 5 TC', status=400)
                    base_price_tc = override_value

                v_file = files.get(f'video_file_{index}') or files.get(f'video_{index}')
                v_thumb = files.get(f'thumbnail_{index}')

                if not v_file and not v_url:
                    return _json_error(f'Thiếu nguồn video ở mục #{index + 1}!', status=400)

                video = Video(
                    title=v_title,
                    description=v_description,
                    creator=user,
                    course=course,
                    category=course.category,
                    duration_seconds=v_duration,
                    base_price=Decimal(str(base_price_tc)),
                )

                if v_file:
                    stored_name = default_storage.save(f"videos/{v_file.name}", v_file)
                    video.file_url = stored_name
                    video.video_file = stored_name
                else:
                    video.file_url = v_url

                if v_thumb:
                    thumb_name = default_storage.save(f"thumbnails/{v_thumb.name}", v_thumb)
                    video.thumbnail = thumb_name

                video.save()
                temp_to_video[v_temp_id] = video
                created.append((video, v_prereq_temp))

            for video, v_prereq_temp in created:
                if not v_prereq_temp:
                    continue
                prereq_video = temp_to_video.get(str(v_prereq_temp))
                if prereq_video and prereq_video.id != video.id:
                    video.prerequisite_video = prereq_video
                    video.save(update_fields=['prerequisite_video'])

            created_payload = [
                {
                    'id': video.id,
                    'title': video.title,
                    'duration_seconds': int(video.duration_seconds or 0),
                    'price_tc': _tc_to_int(video.base_price),
                    'prerequisite_id': video.prerequisite_video_id,
                }
                for video, _ in created
            ]
    except Exception as exc:
        return _json_error(str(exc), status=500)

    return _json_success({
        'course_id': course.id,
        'creator_id': user.id,
        'channel_id': user.id,
        'videos': created_payload,
        'creator_eligible_price_override': creator_can_override,
        'creator_avg_rating': creator_avg_rating,
        'message': 'Tạo khóa học thành công'
    }, status=201)


@require_GET
def api_channel_detail(request):
    """API: Return information about a creator's channel.

    Query param 'id' must specify the user id of the channel owner.
    Response includes the owner's active courses and follower count.
    """
    user, auth_error = _require_auth(request)
    if auth_error:
        return auth_error

    owner_id = request.GET.get('id')
    if not owner_id:
        return _json_error('Thiếu id kênh!', status=400)

    try:
        owner = User.objects.get(id=owner_id)
    except User.DoesNotExist:
        return _json_error('Người dùng không tồn tại!', status=404)

    owner_profile = _get_or_create_profile(owner)

    # gather courses for owner
    courses = list(
        Course.objects.filter(instructor=owner, is_active=True).values(
            'id', 'title'
        )
    )
    followers_count = Follow.objects.filter(following=owner).count()

    # also indicate whether the requesting user already follows this owner
    is_following = False
    if user:
        is_following = Follow.objects.filter(follower=user, following=owner).exists()

    # collect videos created by owner (useful for channel display)
    videos = []
    try:
        vids = Video.objects.filter(creator=owner, is_active=True)
        for v in vids:
            can_watch = _can_watch_video(user, v)
            videos.append({
                'id': v.id,
                'title': v.title,
                'thumbnail': _safe_file_url(request, v.thumbnail) if v.thumbnail else '',
                'duration_seconds': v.duration_seconds,
                'is_unlocked': bool(can_watch),
                'video_url': _safe_file_url(request, v.file_url) if (can_watch and v.file_url) else '',
            })
    except Exception:
        # on any error, fall back to empty list
        videos = []

    return _json_success({
        'owner': {
            'id': owner.id,
            'username': owner.username,
            'avatar_url': _profile_avatar_url(request, owner_profile) or f"https://ui-avatars.com/api/?name={owner.username}",
            'specialization': owner_profile.specialization or 'Giang vien da linh vuc',
            'bio': owner_profile.bio or 'Chua cap nhat mo ta linh vuc giang day.',
        },
        'courses': courses,
        'followers_count': followers_count,
        'is_following': is_following,
        'videos': videos,
    })
def video_tracking(request):

    if request.method == "POST":

        data = json.loads(request.body)

        video_id = data.get("video_id")
        seconds = data.get("watched_seconds")
        event = data.get("event")

        print("Video:", video_id)
        print("Seconds:", seconds)
        print("Event:", event)

        return JsonResponse({"status":"ok"})

from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from .models import Wallet

@login_required
def earn_reward(request):

    wallet = Wallet.objects.get(user=request.user)

    wallet.tc_balance += 5
    wallet.save()

    return JsonResponse({
        "success": True,
        "tc_balance": wallet.tc_balance
    })