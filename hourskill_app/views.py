import json
import re
import secrets
from decimal import Decimal

from django.contrib.auth import authenticate
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.core.cache import cache
from django.core import signing
from django.core.files.storage import default_storage
from django.db import transaction
from django.db.models import Q
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
from .forms import CourseForm, VideoForm
from .services import process_view_payment


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


def _process_video_purchase(user, video):
    """Unlock a video by moving TC between wallets and marking the session unlocked."""

    session, _ = WatchSession.objects.get_or_create(user=user, video=video)

    if session.is_unlocked:
        video_url = _safe_file_url(None, video.file_url)
        user_wallet = Wallet.objects.filter(user=user).first()
        remaining = user_wallet.balance if user_wallet else Decimal('0.00')

        return {
            'remaining_tc': remaining,
            'video_url': video_url,
            'videoUrl': video_url,
            'message': 'Video đã được mở khóa trước đó'
        }, None

    price = video.price_tc

    # video miễn phí
    if price == 0:
        session.is_unlocked = True
        session.save()

        user_wallet = Wallet.objects.filter(user=user).first()
        remaining = user_wallet.balance if user_wallet else Decimal('0.00')

        video_url = _safe_file_url(None, video.file_url)

        return {
            'remaining_tc': remaining,
            'video_url': video_url,
            'videoUrl': video_url
        }, None

    try:
        paid_amount = process_view_payment(user, video)
        session.is_unlocked = True
        session.save(update_fields=['is_unlocked'])
    except Exception as e:
        return None, _json_error(str(e), status=500)

    video_url = _safe_file_url(None, video.file_url)
    wallet = Wallet.objects.filter(user=user).first()
    remaining = wallet.balance if wallet else Decimal('0.00')

    return {
        'remaining_tc': remaining,
        'video_url': video_url,
        'videoUrl': video_url
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
        wallet = Wallet.objects.get(user=user)
        return _json_success({
            'balance': float(wallet.balance),
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

    # Ensure related rows exist so new users always see 5 TC
    profile, _ = UserProfile.objects.get_or_create(user=user, defaults={'wallet_balance': 5})
    wallet, _ = Wallet.objects.get_or_create(user=user)

    return _json_success({
        'id': user.id,
        'username': user.username,
        'email': user.email,
        'wallet_balance': profile.wallet_balance,
        'balance': float(wallet.balance),
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
        category_id = request.GET.get('category')
        qs = Course.objects.filter(is_deleted=False, is_active=True)
        if q:
            qs = qs.filter(Q(title__icontains=q))
        if category_id:
            qs = qs.filter(category_id=category_id)
        data = [
            {
                'id': c.id,
                'title': c.title,
                'description': c.description,
                'bundle_price_tc': float(c.bundle_price_tc),
                'category': c.category.name if c.category else None,
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

        form = CourseForm(data)
        if not form.is_valid():
            return _json_error(form.errors.as_json(), status=400)

        course = form.save(commit=False)
        course.instructor = user
        course.save()

        return _json_success({
            'id': course.id,
            'title': course.title,
            'description': course.description,
            'bundle_price_tc': float(course.bundle_price_tc),
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
        return _json_success({
            'id': course.id,
            'title': course.title,
            'description': course.description,
            'bundle_price_tc': float(course.bundle_price_tc),
            'category': course.category.name if course.category else None,
            'instructor': course.instructor.username,
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
        q = request.GET.get('q', '').strip()
        course_id = request.GET.get('course')
        qs = Video.objects.filter(is_deleted=False, is_active=True)
        if q:
            qs = qs.filter(Q(title__icontains=q))
        if course_id:
            qs = qs.filter(course_id=course_id)
        data = [
            {
                'id': v.id,
                'title': v.title,
                'course': v.course_id,
                'category': v.category.name if v.category else None,
                'price_tc': float(v.price_tc),
                'duration_seconds': v.duration_seconds,
                'creator': v.creator.username,
                'file_url': _safe_file_url(request, v.file_url),
            }
            for v in qs.order_by('-created_at')
        ]
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
        return _json_success({
            'id': video.id,
            'title': video.title,
            'description': video.description,
            'price_tc': float(video.price_tc),
            'course': video.course_id,
            'category': video.category.name if video.category else None,
            'duration_seconds': video.duration_seconds,
            'file_url': _safe_file_url(request, video.file_url),
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
    category_id = request.GET.get('category')
    courses = Course.objects.filter(is_deleted=False, is_active=True)
    if q:
        courses = courses.filter(title__icontains=q)
    if category_id:
        courses = courses.filter(category_id=category_id)

    categories = Category.objects.all()

    context = {
        'courses': courses.order_by('-created_at'),
        'query': q,
        'category_id': category_id,
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

    is_owner = user.id == video.creator_id or (video.course and video.course.instructor_id == user.id)

    session, _ = WatchSession.objects.get_or_create(user=user, video=video)

    # Owners always see the video unlocked
    if is_owner:
        session.is_unlocked = True
        session.save(update_fields=['is_unlocked'])

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
        'is_owner': is_owner,
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
        video = Video.objects.get(id=video_id, is_active=True)
    except Video.DoesNotExist:
        return _json_error('Video không tồn tại!', status=404)

    payload, error = _process_video_purchase(user, video)
    if error:
        return error
    if payload.get("video_url"):
        payload["videoUrl"] = request.build_absolute_uri(payload["video_url"])
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
            # include potential instructor id to support safe channel links later
            'instructor__id',
        )
    )

    return _json_success({'categories': categories, 'courses': courses})


@require_GET
def api_categories(request):
    """API: Return categories only (id, name) for dropdowns."""
    categories = list(Category.objects.values('id', 'name'))
    return _json_success({'categories': categories})
    
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
def api_purchase_course(request):
    """API: Purchase a course bundle using TC with strict balance check."""
    user, auth_error = _require_auth(request)
    if auth_error:
        return auth_error

    try:
        data = _parse_json_body(request)
    except ValueError as exc:
        return _json_error(str(exc), status=400)

    course_id = data.get('course_id')
    if not course_id:
        return _json_error('Thiếu course_id!', status=400)

    try:
        course = Course.objects.get(id=course_id, is_active=True, is_deleted=False)
    except Course.DoesNotExist:
        return _json_error('Khóa học không tồn tại!', status=404)

    # Normalize price to Decimal for safe arithmetic
    price = Decimal(course.bundle_price_tc)

    try:
        with transaction.atomic():
            buyer_wallet = _lock_wallet(user)
            buyer_balance = Decimal(buyer_wallet.balance)
            if buyer_balance < price:
                return _json_error('Insufficient funds', status=400)

            instructor_wallet = _lock_wallet(course.instructor)

            buyer_wallet.balance -= price
            instructor_wallet.balance += price

            buyer_wallet.save(update_fields=['balance'])
            instructor_wallet.save(update_fields=['balance'])

            # Keep profile wallet_balance in sync for UX that reads from profile
            UserProfile.objects.update_or_create(
                user=user,
                defaults={'wallet_balance': int(buyer_wallet.balance)},
            )
            UserProfile.objects.update_or_create(
                user=course.instructor,
                defaults={'wallet_balance': int(instructor_wallet.balance)},
            )

            Transaction.objects.create(
                sender=user,
                receiver=course.instructor,
                tx_type='SPEND_VIEW',
                amount_tc=price,
                reference_video=None,
            )
    except Wallet.DoesNotExist:
        return _json_error('Wallet not found.', status=404)
    except Exception as exc:
        return _json_error(str(exc), status=500)

    return _json_success({'message': 'Mua khóa học thành công!', 'remaining_tc': float(buyer_wallet.balance)})

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
            wallet.balance += reward_amount  # Credit TC for watching an ad
            wallet.save(update_fields=['balance', 'updated_at'])

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
            wallet.balance += Decimal('1.00')
            wallet.save(update_fields=['balance', 'updated_at'])

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
    - price_tc (alias bundle_price_tc)
    - category (id)
    - video (file) or video_url (Google Drive link / iframe)
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
    category_id = data.get('category')
    price_raw = data.get('bundle_price_tc') or data.get('price_tc')
    video_url_raw = (data.get('video_url') or '').strip()
    video_file = files.get('video') or files.get('video_file')
    thumbnail_file = files.get('thumbnail')

    video_url = _extract_drive_src(video_url_raw)

    if not title or not description or price_raw is None or (not video_file and not video_url):
        return _json_error('Thiếu dữ liệu cần thiết!', status=400)

    try:
        bundle_price_tc = Decimal(str(price_raw))
    except Exception:
        return _json_error('Giá TC không hợp lệ!', status=400)

    form = CourseForm({
        'title': title,
        'description': description,
        'category': category_id,
        'bundle_price_tc': bundle_price_tc,
    })

    if not form.is_valid():
        return _json_error(form.errors.as_json(), status=400)

    try:
        with transaction.atomic():
            course = form.save(commit=False)
            course.instructor = user
            course.save()

            video = Video(
                title=title,
                description=description,
                creator=user,
                course=course,
                category=course.category,
                price_tc=bundle_price_tc,
                duration_seconds=0,
            )

            if video_file:
                stored_name = default_storage.save(f"videos/{video_file.name}", video_file)
                video.file_url = stored_name
                video.video_file = stored_name
            else:
                video.file_url = video_url

            if thumbnail_file:
                thumb_name = default_storage.save(f"thumbnails/{thumbnail_file.name}", thumbnail_file)
                video.thumbnail = thumb_name

            video.save()
    except Exception as exc:
        return _json_error(str(exc), status=500)

    return _json_success({
        'course_id': course.id,
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

    # gather courses for owner
    courses = list(
        Course.objects.filter(instructor=owner, is_active=True).values(
            'id', 'title', 'bundle_price_tc'
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
            videos.append({
                'id': v.id,
                'title': v.title,
                'thumbnail': _safe_file_url(v.thumbnail) if v.thumbnail else '',
                'duration_seconds': v.duration_seconds,
                'video_url': _safe_file_url(v.file_url) if v.file_url else '',
            })
    except Exception:
        # on any error, fall back to empty list
        videos = []

    return _json_success({
        'owner': {'id': owner.id, 'username': owner.username},
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