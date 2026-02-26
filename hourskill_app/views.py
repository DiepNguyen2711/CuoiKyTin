import json
from decimal import Decimal
from datetime import timedelta
from django.utils import timezone
from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth import login, logout, authenticate, get_user_model
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.core.files.storage import FileSystemStorage
from django.db import transaction
from .models import (
    Wallet, Video, Follow, UploadFile, Category, Course, 
    Transaction, WatchSession, CommentReview, Notification, UserBehavior
)

User = get_user_model()

# ==========================================
# PHẦN 1: GIAO DIỆN HTML (Frontend)
# ==========================================

def main_view(request):
    """Trang chủ: Hiển thị Video Feed và Ví"""
    # Nếu chưa đăng nhập thì bắt đăng nhập
    if not request.user.is_authenticated:
        return redirect('login')
        
    # Lấy hoặc tạo ví tiền
    wallet, _ = Wallet.objects.get_or_create(user=request.user)
    
    # Lấy danh sách video (Mới nhất lên đầu)
    videos = Video.objects.all().order_by('-created_at')
    
    return render(request, 'main.html', {
        'wallet': wallet, 
        'videos': videos
    })

def profile_view(request, username):
    """Trang cá nhân: Hiển thị thông tin và video của 1 người"""
    if not request.user.is_authenticated:
        return redirect('login')

    # Tìm người dùng theo username (Nếu không thấy báo lỗi 404)
    profile_user = get_object_or_404(User, username=username)
    
    # Lấy video của người đó
    user_videos = Video.objects.filter(creator=profile_user).order_by('-created_at')
    
    # Kiểm tra xem mình đã follow họ chưa
    is_following = False
    if request.user != profile_user:
        is_following = Follow.objects.filter(follower=request.user, following=profile_user).exists()
        
    return render(request, 'profile.html', {
        'profile_user': profile_user,
        'videos': user_videos,
        'is_following': is_following,
        'follower_count': profile_user.followers.count()
    })

def register_view(request):
    """Giao diện Đăng ký"""
    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            Wallet.objects.create(user=user, balance_tc=5.0) # Tặng 5 TC
            login(request, user)
            return redirect('home')
    else:
        form = UserCreationForm()
    return render(request, 'register.html', {'form': form})

def login_view(request):
    """Giao diện Đăng nhập"""
    if request.method == 'POST':
        form = AuthenticationForm(data=request.POST)
        if form.is_valid():
            login(request, form.get_user())
            return redirect('home')
    else:
        form = AuthenticationForm()
    return render(request, 'login.html', {'form': form})

def user_logout(request):
    """Đăng xuất"""
    logout(request)
    return redirect('login')


# ==========================================
# PHẦN 2: API TÍNH NĂNG MỚI (Upload & Follow)
# ==========================================

@csrf_exempt
def api_upload_video(request):
    """Xử lý Form Upload Video (Có lưu file thật)"""
    if request.method == 'POST':
        # Nhận file và tiêu đề từ Form
        video_file = request.FILES.get('video_file') or request.FILES.get('video')
        title = request.POST.get('title', 'Video Mới')
        
        if video_file:
            try:
                # 1. Lưu file vào thư mục media/videos/
                fs = FileSystemStorage(location='media/videos')
                filename = fs.save(video_file.name, video_file)
                
                # 2. Tạo bản ghi trong Database
                Video.objects.create(
                    creator=request.user,
                    title=title,
                    file=f"videos/{filename}", 
                    price_tc=2.0 # Giá mặc định
                )
                return JsonResponse({'status': 'success', 'message': 'Upload thành công!'})
            except Exception as e:
                return JsonResponse({'status': 'error', 'message': str(e)}, status=500)
            
        return JsonResponse({'status': 'error', 'message': 'Chưa chọn file!'}, status=400)
    return JsonResponse({'status': 'error'}, status=405)

@csrf_exempt
def api_toggle_follow(request):
    """Xử lý nút Follow (AJAX - Không reload trang)"""
    if request.method == 'POST' and request.user.is_authenticated:
        try:
            data = json.loads(request.body)
            creator_id = data.get('creator_id')
            creator = User.objects.get(id=creator_id)
            
            if request.user == creator: 
                return JsonResponse({'status': 'error', 'message': 'Không thể tự follow'}, status=400)
            
            # Kiểm tra xem đã follow chưa
            follow, created = Follow.objects.get_or_create(follower=request.user, following=creator)
            
            if not created:
                follow.delete() # Đã có -> Xóa (Unfollow)
                action = 'unfollowed'
                text = '+ Follow'
                is_active = False
            else:
                action = 'followed' # Chưa có -> Tạo mới (Follow)
                text = 'Đang theo dõi'
                is_active = True
                
            return JsonResponse({
                'status': 'success', 
                'action': action, 
                'text': text,
                'is_active': is_active,
                'new_count': creator.followers.count()
            })
        except Exception as e: 
            return JsonResponse({'status': 'error', 'message': str(e)}, status=500)
    return JsonResponse({'status': 'error'}, status=401)


# ==========================================
# PHẦN 3: API CŨ CỦA NHÓM BẠN (Đã phục hồi đầy đủ)
# ==========================================

@csrf_exempt
def api_register(request):
    """API Đăng ký bằng JSON"""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            username = data.get('username', '').strip()
            email = data.get('email', '').strip()
            password = data.get('password', '')

            if not username or not email or not password:
                return JsonResponse({'status': 'error', 'message': 'Thiếu thông tin'}, status=400)
            
            if User.objects.filter(email=email).exists():
                return JsonResponse({'status': 'error', 'message': 'Email đã tồn tại'}, status=400)

            user = User.objects.create_user(username=username, email=email, password=password)
            Wallet.objects.create(user=user, balance_tc=5.0)
            login(request, user)
            return JsonResponse({'status': 'success', 'message': 'Đăng ký thành công'}, status=201)
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=500)
    return JsonResponse({'status': 'error'}, status=405)

@csrf_exempt
def api_login(request):
    """API Đăng nhập bằng JSON"""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            email = data.get('email', '').strip()
            password = data.get('password', '')
            
            user_obj = User.objects.filter(email=email).first()
            if not user_obj:
                return JsonResponse({'status': 'error', 'message': 'Email không đúng'}, status=400)
            
            user = authenticate(request, username=user_obj.username, password=password)
            if user:
                login(request, user)
                return JsonResponse({'status': 'success'})
            else:
                return JsonResponse({'status': 'error', 'message': 'Sai mật khẩu'}, status=400)
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=500)
    return JsonResponse({'status': 'error'}, status=405)

@csrf_exempt
def ping_watch_session(request):
    """API Ping thời gian xem video"""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            session = WatchSession.objects.get(id=data.get('session_id'))
            session.watched_seconds += 10
            session.save()
            return JsonResponse({'status': 'success', 'watched_seconds': session.watched_seconds})
        except:
            return JsonResponse({'status': 'error'}, status=400)

def api_get_courses(request):
    """API lấy danh sách khóa học"""
    if request.method == 'GET':
        categories = list(Category.objects.values('id', 'name'))
        courses = list(Course.objects.filter(is_active=True).values('id', 'title', 'bundle_price_tc'))
        return JsonResponse({'status': 'success', 'categories': categories, 'courses': courses})

@csrf_exempt
def api_purchase_video(request):
    """API Mua video bằng tiền ảo TC"""
    if request.method == 'POST' and request.user.is_authenticated:
        try:
            data = json.loads(request.body)
            video = Video.objects.get(id=data.get('video_id'))
            session, _ = WatchSession.objects.get_or_create(user=request.user, video=video)
            
            if session.is_unlocked:
                return JsonResponse({'status': 'error', 'message': 'Đã mua rồi'}, status=400)
            
            with transaction.atomic():
                user_wallet = request.user.wallet
                if user_wallet.balance_tc < video.price_tc:
                    return JsonResponse({'status': 'error', 'message': 'Không đủ tiền'}, status=400)
                
                user_wallet.balance_tc -= video.price_tc
                user_wallet.save()
                
                # Cộng tiền cho creator
                if hasattr(video.creator, 'wallet'):
                    video.creator.wallet.balance_tc += video.price_tc
                    video.creator.wallet.save()

                # Ghi log giao dịch
                Transaction.objects.create(
                    sender=request.user, receiver=video.creator,
                    tx_type='SPEND_VIEW', amount_tc=video.price_tc,
                    reference_video=video
                )

                session.is_unlocked = True
                session.save()
            return JsonResponse({'status': 'success'})
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=500)
    return JsonResponse({'status': 'error'}, status=405)

@csrf_exempt
def api_post_comment(request):
    """API Bình luận video"""
    if request.method == 'POST' and request.user.is_authenticated:
        try:
            data = json.loads(request.body)
            video = Video.objects.get(id=data.get('video_id'))
            CommentReview.objects.create(
                user=request.user, video=video, 
                content=data.get('content'), rating=data.get('rating')
            )
            return JsonResponse({'status': 'success'})
        except:
            return JsonResponse({'status': 'error'}, status=500)
    return JsonResponse({'status': 'error'}, status=405)

def api_get_notifications(request):
    """API Lấy thông báo"""
    if request.user.is_authenticated:
        notifs = Notification.objects.filter(user=request.user).order_by('-created_at')[:20]
        data = [{'content': n.content, 'created_at': n.created_at} for n in notifs]
        return JsonResponse({'status': 'success', 'notifications': data})
    return JsonResponse({'status': 'error'}, status=401)

@csrf_exempt
def api_reward_ads(request):
    """API Xem quảng cáo nhận tiền (Có chống spam)"""
    if request.method == 'POST' and request.user.is_authenticated:
        try:
            # Chống spam
            last_tx = Transaction.objects.filter(receiver=request.user, tx_type='EARN_ADS').order_by('-timestamp').first()
            if last_tx and (timezone.now() - last_tx.timestamp).total_seconds() < 30:
                return JsonResponse({'status': 'error', 'message': 'Xem quá nhanh!'}, status=429)

            with transaction.atomic():
                wallet = request.user.wallet
                wallet.balance_tc += Decimal('0.5')
                wallet.save()
                
                Transaction.objects.create(
                    receiver=request.user, tx_type='EARN_ADS', amount_tc=0.5
                )
            return JsonResponse({'status': 'success', 'message': '+0.5 TC'})
        except:
            return JsonResponse({'status': 'error'}, status=500)
    return JsonResponse({'status': 'error'}, status=405)

@csrf_exempt
def api_log_behavior(request):
    """API Log hành vi người dùng"""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            video = Video.objects.get(id=data.get('video_id'))
            UserBehavior.objects.create(
                user=request.user if request.user.is_authenticated else None,
                video=video,
                event_type=data.get('event_type'),
                video_timestamp_seconds=data.get('timestamp', 0)
            )
            return JsonResponse({'status': 'success'})
        except: return JsonResponse({'status': 'error'})
    return JsonResponse({'status': 'error'}, status=405)

@csrf_exempt
def upload_file(request):
    """API Upload file phụ (ảnh, tài liệu...)"""
    if request.method == 'POST' and request.FILES.get('file'):
        UploadFile.objects.create(
            file=request.FILES['file'], 
            user=request.user if request.user.is_authenticated else None
        )
        return JsonResponse({'message': 'Success'})
    return JsonResponse({'error': 'Fail'})