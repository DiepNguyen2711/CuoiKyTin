import json
import secrets
from decimal import Decimal

from django.contrib.auth import authenticate
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.core import signing
from django.core.files.storage import FileSystemStorage
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import render
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST

from .models import (
    Category,
    CommentReview,
    Course,
    Follow,
    Notification,
    Transaction,
    User,
    UserBehavior,
    UserProfile,
    Video,
    Wallet,
    WatchSession,
)


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


def _safe_file_url(file_field):
    """Return the served URL for a file field when available."""
    try:
        return file_field.url
    except Exception:
        return ''


def _process_video_purchase(user, video):
    """Unlock a video by moving TC between wallets and marking the session unlocked."""
    session, _ = WatchSession.objects.get_or_create(user=user, video=video)
    if session.is_unlocked:
        return None, _json_error('Bạn đã mua video này rồi!')

    price = video.price_tc
    user_wallet = None

    # Free videos unlock without touching wallets
    if price == 0:
        session.is_unlocked = True
        session.save(update_fields=['is_unlocked'])
        user_wallet = Wallet.objects.filter(user=user).first()
        remaining = user_wallet.balance_tc if user_wallet else Decimal('0.00')
        video_url = _safe_file_url(video.file_url)
        return {'remaining_tc': remaining, 'video_url': video_url, 'videoUrl': video_url}, None

    try:
        with transaction.atomic():
            user_wallet = _lock_wallet(user)
            creator_wallet = _lock_wallet(video.creator)

            if user_wallet.balance_tc < price:
                return None, _json_error('Số dư TC không đủ. Vui lòng nạp thêm!')

            user_wallet.balance_tc -= price
            creator_wallet.balance_tc += price

            user_wallet.save(update_fields=['balance_tc', 'updated_at'])
            creator_wallet.save(update_fields=['balance_tc', 'updated_at'])

            Transaction.objects.create(
                sender=user,
                receiver=video.creator,
                tx_type='SPEND_VIEW',
                amount_tc=price,
                reference_video=video,
                status='SUCCESS',
            )

            session.is_unlocked = True
            session.save(update_fields=['is_unlocked'])
    except Wallet.DoesNotExist:
        return None, _json_error('Ví không tồn tại. Vui lòng liên hệ hỗ trợ.', status=500)
    except Exception as exc:
        return None, _json_error(str(exc), status=500)

    video_url = _safe_file_url(video.file_url)
    return {
        'remaining_tc': user_wallet.balance_tc,
        'video_url': video_url,
        'videoUrl': video_url,
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

    return _json_success({'message': 'Đăng ký thành công! Bạn đã nhận được 5 TC vào ví.', 'token': token}, status=201)

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
        'username': user.username
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

    if not session_id:
        return _json_error('Thiếu session_id!', status=400)

    session = WatchSession.objects.filter(id=session_id, user=user).first()
    if not session:
        return _json_error('Session không tồn tại hoặc không thuộc về bạn!', status=404)

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

    fs = FileSystemStorage()  # Uses MEDIA_ROOT/MEDIA_URL settings
    filename = fs.save(f"videos/{video_file.name}", video_file)
    video_url = fs.url(filename)  # Build served URL for frontend playback

    return _json_success({'message': 'Upload video thành công!', 'video_url': video_url}, status=201)

@require_GET
def api_get_video_detail(request, video_id):
    """API: Fetch video metadata, lock state, and creator info for the viewer."""
    user, auth_error = _require_auth(request)
    if auth_error:
        return auth_error

    try:
        video = Video.objects.get(id=video_id, is_active=True)
    except Video.DoesNotExist:
        return _json_error('Video không tồn tại!', status=404)

    session, _ = WatchSession.objects.get_or_create(user=user, video=video)

    # Auto-unlock free videos on first fetch
    if video.price_tc == 0 and not session.is_unlocked:
        session.is_unlocked = True
        session.save(update_fields=['is_unlocked'])

    locked = not session.is_unlocked
    following = Follow.objects.filter(follower=user, following=video.creator).exists()

    data = {
        'id': video.id,
        'title': video.title,
        'description': video.description,
        'locked': locked,
        'requiredTC': float(video.price_tc),
        'videoUrl': None if locked else _safe_file_url(video.file_url),
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
        video = Video.objects.get(id=video_id, is_active=True)
    except Video.DoesNotExist:
        return _json_error('Video không tồn tại!', status=404)

    payload, error = _process_video_purchase(user, video)
    if error:
        return error

    return _json_success({'message': 'Mở khóa video thành công!', **payload})

@require_GET
def api_get_courses(request):
    """API: Return active courses and categories for catalog display."""
    categories = list(Category.objects.values('id', 'name'))  # Used for filters

    courses = list(
        Course.objects.filter(is_active=True).values(
            'id',
            'title',
            'bundle_price_tc',
            'category__name',
            'instructor__username',
        )
    )

    return _json_success({'categories': categories, 'courses': courses})
    
@csrf_exempt
@require_POST
def api_toggle_follow(request, creator_id=None):
    """API: Toggle follow/unfollow for a creator, blocking self-follow.

    Supports both JSON body (creator_id) and REST-style path parameter.
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

    # A single record represents follow; presence => following
    follow_record = Follow.objects.filter(follower=user, following=creator).first()
    if follow_record:
        follow_record.delete()
        action = 'unfollowed'
    else:
        Follow.objects.create(follower=user, following=creator)
        action = 'followed'

    return _json_success({'action': action})

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
    content = data.get('content')
    rating = data.get('rating')

    try:
        video = Video.objects.get(id=video_id)
    except Video.DoesNotExist:
        return _json_error('Video không tồn tại!', status=404)

    # Create the comment entry (rating may be null)
    CommentReview.objects.create(
        user=user,
        video=video,
        content=content,
        rating=rating,
    )

    if user != video.creator:
        # Notify the creator about new feedback
        Notification.objects.create(
            user=video.creator,
            content=f"🗣️ {user.username} đã bình luận về video '{video.title}' của bạn.",
        )

    return _json_success({'message': 'Đã gửi bình luận!'})

@require_GET
def api_get_notifications(request):
    """API: Fetch recent notifications plus unread count for the current user."""
    user, auth_error = _require_auth(request)
    if auth_error:
        return auth_error

    # Pull latest notifications; limit to keep payload small
    notifs = Notification.objects.filter(user=user).order_by('-created_at')[:20]

    data = [
        {
            'id': n.id,
            'content': n.content,
            'is_read': n.is_read,
            'created_at': n.created_at.strftime("%H:%M %d/%m/%Y"),
        }
        for n in notifs
    ]

    unread_count = Notification.objects.filter(user=user, is_read=False).count()

    return _json_success({'notifications': data, 'unread_count': unread_count})
    
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
            wallet.balance_tc += reward_amount  # Credit TC for watching an ad
            wallet.save(update_fields=['balance_tc', 'updated_at'])

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

    return _json_success({'message': f'Đã cộng {reward_amount} TC vào ví!', 'new_balance': wallet.balance_tc})

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
    """API: Store survey answers for the current user; depends on prior role selection."""
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

    try:
        profile = UserProfile.objects.get(user=user)
        profile.survey_answers = answers  # Persist raw answer list for later recommendations
        profile.save(update_fields=['survey_answers'])
    except UserProfile.DoesNotExist:
        return _json_error('Người dùng chưa chọn vai trò (role) ở bước 1.', status=400)
    except Exception as exc:
        return _json_error(str(exc), status=400)

    return _json_success({'message': 'Lưu khảo sát thành công!'})