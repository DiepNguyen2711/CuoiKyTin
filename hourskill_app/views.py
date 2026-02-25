import json
from django.http import JsonResponse # Dùng nếu muốn trả về API thay vì giao diện
from decimal import Decimal
from django.core.files.storage import FileSystemStorage
from django.views.decorators.csrf import csrf_exempt
from django.shortcuts import render, redirect
from django.contrib.auth import login, authenticate, logout
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from hourskill_app.models import User, Wallet
from django.db import transaction
from .models import WatchSession, User, Category, Course, Follow, Video, Transaction, CommentReview, Notification, UserBehavior
from datetime import timedelta
from django.utils import timezone

# 1. Hàm xử lý Đăng ký
def register_view(request):
    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            # Đăng nhập luôn sau khi đăng ký thành công
            login(request, user)
            return redirect('home') # Chuyển hướng về trang chủ
    else:
        form = UserCreationForm()
    return render(request, 'register.html', {'form': form})

# 2. Hàm xử lý Đăng nhập
def login_view(request):
    if request.method == 'POST':
        form = AuthenticationForm(data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            return redirect('home')
    else:
        form = AuthenticationForm()
    return render(request, 'login.html', {'form': form})

# 3. Xử lí JSON , bỏ qua CSRF cho API
@csrf_exempt
def api_register(request):
    if request.method == 'POST':
        try:
            # Đọc dữ liệu JSON từ Frontend gửi lên
            data = json.loads(request.body)
            
            # Gắn giá trị mặc định là '' và dùng .strip() để xóa khoảng trắng thừa
            username = data.get('username', '').strip()
            email = data.get('email', '').strip()
            password = data.get('password', '')

            # Chống Frontend gửi thiếu dữ liệu hoặc gửi chuỗi rỗng
            if not username or not email or not password:
                return JsonResponse({'status': 'error', 'message': 'Vui lòng điền đầy đủ tất cả các trường!'}, status=400)

            # Kiểm tra độ dài mật khẩu
            if len(password) < 8:
                return JsonResponse({'status': 'error', 'message': 'Mật khẩu phải có ít nhất 8 ký tự!'}, status=400)
            
            # Kiểm tra email trùng lặp
            if User.objects.filter(email=email).exists():
                return JsonResponse({'status': 'error', 'message': 'Email này đã được sử dụng! Vui lòng chọn email khác.'}, status=400)

            # Kiểm tra Username trùng lặp (Ngăn lỗi IntegrityError của Django)
            if User.objects.filter(username=username).exists():
                return JsonResponse({'status': 'error', 'message': 'Tên người dùng này đã tồn tại! Vui lòng chọn tên khác.'}, status=400)

            # Tạo User mới an toàn
            user = User.objects.create_user(username=username, email=email, password=password)
           
            return JsonResponse({
                'status': 'success', 
                'message': 'Đăng ký thành công! Bạn đã nhận được 5 TC vào ví.'
            }, status=201)

        except json.JSONDecodeError:
            return JsonResponse({'status': 'error', 'message': 'Dữ liệu không hợp lệ!'}, status=400)
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': 'Lỗi hệ thống: ' + str(e)}, status=500)

    return JsonResponse({'status': 'error', 'message': 'Chỉ chấp nhận POST!'}, status=405)

# 4. Đăng nhập hoạt động
@csrf_exempt
def api_login(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            # Dùng .strip() để tự động cắt bỏ các dấu cách thừa nếu người dùng lỡ tay gõ vào
            email = data.get('email', '').strip() 
            password = data.get('password', '')

            # Tìm User an toàn: Dùng filter().first() thay vì get() để tránh lỗi văng hệ thống
            user_obj = User.objects.filter(email=email).first()

            if not user_obj:
                # Nếu không tìm thấy ai có email này
                return JsonResponse({'status': 'error', 'message': 'Email chưa đăng ký!'}, status=400)

            # Xác thực mật khẩu
            user = authenticate(request, username=user_obj.username, password=password)

            if user is not None:
                login(request, user)
                return JsonResponse({'status': 'success'}, status=200)
            else:
                # Tìm thấy email nhưng sai mật khẩu
                return JsonResponse({'status': 'error', 'message': 'Sai mật khẩu! Vui lòng kiểm tra lại.'}, status=400)

        except Exception as e:
            # Chỉ báo lỗi 500 cho các lỗi hệ thống nghiêm trọng khác
            return JsonResponse({'status': 'error', 'message': 'Lỗi máy chủ: ' + str(e)}, status=500)
            
    return JsonResponse({'status': 'error', 'message': 'Chỉ dùng POST'}, status=405)

def main_view(request):
    # Chỉ cho phép người đã đăng nhập mới được vào xem ví
    if request.user.is_authenticated:
        return render(request, 'main.html')
    else:
        # Nếu chưa đăng nhập mà đòi vào main thì "đuổi" về trang login
        from django.shortcuts import redirect
        return redirect('login')

# Đăng xuất:
def user_logout(request):
    logout(request) # Lệnh này sẽ xóa phiên đăng nhập hiện tại
    return redirect('main_view') # Đăng xuất xong ở lại luôn trang chủ

# API nhận nhịp Ping
@csrf_exempt # Tạm thời tắt CSRF để test API dễ dàng
def ping_watch_session(request):
    if request.method == 'POST':
        data = json.loads(request.body)
        session_id = data.get('session_id')
        
        try:
            # Tìm phiên xem hiện tại
            session = WatchSession.objects.get(id=session_id)
            
            # Cập nhật số giây đã xem (Cộng thêm 10 giây mỗi lần ping)
            session.watched_seconds += 10 
            # (Thực tế bạn sẽ kết hợp lưu last_ping_time để chống hack)
            session.save()
            
            return JsonResponse({'status': 'success', 'watched_seconds': session.watched_seconds})
        except WatchSession.DoesNotExist:
            return JsonResponse({'status': 'error', 'message': 'Session not found'}, status=404)
        
# API Upload Video
@csrf_exempt
def api_upload_video(request):
    if request.method == 'POST':
        # 'video_file' là tên cái key mà Frontend sẽ gửi lên
        if request.FILES.get('video_file'):
            video = request.FILES['video_file']
            
            # Khởi tạo công cụ lưu file
            fs = FileSystemStorage()
            
            # Lưu file vào thư mục media/videos/
            filename = fs.save(f"videos/{video.name}", video)
            
            # Lấy đường dẫn URL của file vừa lưu để trả về cho Frontend
            video_url = fs.url(filename)
            
            return JsonResponse({
                'status': 'success', 
                'message': 'Upload video thành công!',
                'video_url': video_url
            }, status=201)
            
        return JsonResponse({'status': 'error', 'message': 'Không tìm thấy file video đính kèm!'}, status=400)
    
    return JsonResponse({'status': 'error', 'message': 'Chỉ chấp nhận phương thức POST'}, status=405)

# API lấy danh sách khóa học và danh mục
def api_get_courses(request):
    if request.method == 'GET':
        # Lấy danh sách category
        categories = list(Category.objects.values('id', 'name'))
        
        # Lấy danh sách course (chỉ lấy các course đang active, chống lỗi khi đã xóa mềm)
        courses = list(Course.objects.filter(is_active=True).values(
            'id', 
            'title', 
            'bundle_price_tc', # Lấy đúng tên biến giá TC của bạn
            'category__name', 
            'instructor__username' # Lấy tên của Creator tạo khóa học
        ))
        
        return JsonResponse({
            'status': 'success',
            'categories': categories,
            'courses': courses
        }, status=200)
    
# API Follow / Unfollow Creator:
@csrf_exempt
def api_toggle_follow(request):
    if request.method == 'POST':
        # Bắt buộc phải đăng nhập mới được follow
        if not request.user.is_authenticated:
            return JsonResponse({'status': 'error', 'message': 'Vui lòng đăng nhập!'}, status=401)
            
        try:
            data = json.loads(request.body)
            creator_id = data.get('creator_id')
            
            creator = User.objects.get(id=creator_id)
            
            # Chống trò gian lận: Tự follow chính mình
            if request.user == creator:
                return JsonResponse({'status': 'error', 'message': 'Bạn không thể tự follow chính mình!'}, status=400)
            
            # Tìm xem đã có bản ghi Follow nào giữa 2 người này chưa
            follow_record = Follow.objects.filter(follower=request.user, following=creator).first()
            
            if follow_record:
                # Nếu tìm thấy -> Đã follow rồi -> Xóa đi (Unfollow)
                follow_record.delete()
                action = 'unfollowed'
            else:
                # Nếu chưa có -> Tạo bản ghi mới (Follow)
                Follow.objects.create(follower=request.user, following=creator)
                action = 'followed'
                
            return JsonResponse({'status': 'success', 'action': action})
            
        except User.DoesNotExist:
            return JsonResponse({'status': 'error', 'message': 'Không tìm thấy Creator này!'}, status=404)
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=500)
            
    return JsonResponse({'status': 'error', 'message': 'Chỉ chấp nhận phương thức POST'}, status=405)

# API Mua Video (Trừ tiền, Cộng tiền, Ghi Sổ cái)
@csrf_exempt
def api_purchase_video(request):
    if request.method == 'POST':
        if not request.user.is_authenticated:
            return JsonResponse({'status': 'error', 'message': 'Vui lòng đăng nhập!'}, status=401)
            
        try:
            data = json.loads(request.body)
            video_id = data.get('video_id')
            video = Video.objects.get(id=video_id)
            
            # Kiểm tra xem User đã mở khóa video này chưa
            session, created = WatchSession.objects.get_or_create(user=request.user, video=video)
            if session.is_unlocked:
                return JsonResponse({'status': 'error', 'message': 'Bạn đã mua video này rồi!'}, status=400)

            # BẮT ĐẦU GIAO DỊCH TÀI CHÍNH (Đảm bảo ACID)
            with transaction.atomic():
                user_wallet = request.user.wallet
                creator_wallet = video.creator.wallet
                price = video.price_tc
                
                # 1. Kiểm tra số dư ví
                if user_wallet.balance_tc < price:
                    return JsonResponse({'status': 'error', 'message': 'Số dư TC không đủ. Vui lòng nạp thêm!'}, status=400)
                
                # 2. Trừ tiền User & Cộng tiền Creator
                user_wallet.balance_tc -= price
                creator_wallet.balance_tc += price
                
                user_wallet.save()
                creator_wallet.save()
                
                # 3. Ghi Sổ cái Transaction
                Transaction.objects.create(
                    sender=request.user,
                    receiver=video.creator,
                    tx_type='SPEND_VIEW',
                    amount_tc=price,
                    reference_video=video,
                    status='SUCCESS'
                )
                
                # 4. Đánh dấu đã mở khóa video
                session.is_unlocked = True
                session.save()
                
            return JsonResponse({'status': 'success', 'message': 'Mua video thành công!', 'remaining_tc': user_wallet.balance_tc})
            
        except Video.DoesNotExist:
            return JsonResponse({'status': 'error', 'message': 'Video không tồn tại!'}, status=404)
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=500)
            
    return JsonResponse({'status': 'error', 'message': 'Chỉ chấp nhận POST'}, status=405)

# API Đăng Bình luận & Đánh giá (Review)
@csrf_exempt
def api_post_comment(request):
    if request.method == 'POST':
        if not request.user.is_authenticated:
            return JsonResponse({'status': 'error', 'message': 'Vui lòng đăng nhập!'}, status=401)
            
        try:
            data = json.loads(request.body)
            video_id = data.get('video_id')
            content = data.get('content')
            rating = data.get('rating') # Có thể null
            
            video = Video.objects.get(id=video_id)
            
            # Tạo bình luận
            CommentReview.objects.create(
                user=request.user,
                video=video,
                content=content,
                rating=rating
            )
            
            # Gửi thông báo cho Creator
            if request.user != video.creator:
                Notification.objects.create(
                    user=video.creator,
                    content=f"🗣️ {request.user.username} đã bình luận về video '{video.title}' của bạn."
                )
                
            return JsonResponse({'status': 'success', 'message': 'Đã gửi bình luận!'})
            
        except Video.DoesNotExist:
            return JsonResponse({'status': 'error', 'message': 'Video không tồn tại!'}, status=404)
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=500)
            
    return JsonResponse({'status': 'error', 'message': 'Chỉ chấp nhận POST'}, status=405)

# API Lấy danh sách Thông báo (Notification)
def api_get_notifications(request):
    if request.method == 'GET':
        if not request.user.is_authenticated:
            return JsonResponse({'status': 'error', 'message': 'Vui lòng đăng nhập!'}, status=401)
            
        # Lấy 20 thông báo mới nhất của user đang đăng nhập
        notifs = Notification.objects.filter(user=request.user).order_by('-created_at')[:20]
        
        data = [{
            'id': n.id,
            'content': n.content,
            'is_read': n.is_read,
            'created_at': n.created_at.strftime("%H:%M %d/%m/%Y")
        } for n in notifs]
        
        # Đếm số thông báo chưa đọc để hiển thị số đỏ trên quả chuông
        unread_count = Notification.objects.filter(user=request.user, is_read=False).count()
        
        return JsonResponse({
            'status': 'success', 
            'notifications': data,
            'unread_count': unread_count
        }, status=200)
    
# API Cộng tiền xem Quảng cáo (Kèm chống Spam)
@csrf_exempt
def api_reward_ads(request):
    if request.method == 'POST':
        if not request.user.is_authenticated:
            return JsonResponse({'status': 'error', 'message': 'Vui lòng đăng nhập!'}, status=401)
            
        try:
            now = timezone.now()
            
            # --- LOGIC CHỐNG SPAM BẢO VỆ NỀN KINH TẾ ---
            # Tìm giao dịch nhận tiền quảng cáo gần nhất của User này
            last_ad_tx = Transaction.objects.filter(
                receiver=request.user, 
                tx_type='EARN_ADS'
            ).order_by('-timestamp').first()

            # Nếu khoảng cách giữa 2 lần nhận tiền < 30 giây -> Bắt quả tang gian lận!
            if last_ad_tx and (now - last_ad_tx.timestamp).total_seconds() < 30:
                request.user.trust_score -= 5 # Trừ 5 điểm uy tín
                request.user.save()
                return JsonResponse({
                    'status': 'error', 
                    'message': 'Phát hiện spam! Bạn xem quảng cáo quá nhanh. Bị trừ 5 điểm uy tín.'
                }, status=429) # 429: Too Many Requests

            # --- LOGIC CỘNG TIỀN (Giao dịch nguyên tử) ---
            reward_amount = Decimal('0.50') # Giả sử xem 1 quảng cáo được 0.5 TC
            
            with transaction.atomic():
                wallet = request.user.wallet
                wallet.balance_tc += reward_amount
                wallet.save()
                
                # Ghi vào sổ cái
                Transaction.objects.create(
                    receiver=request.user,
                    tx_type='EARN_ADS',
                    amount_tc=reward_amount,
                    status='SUCCESS'
                )
                
            return JsonResponse({
                'status': 'success', 
                'message': f'Đã cộng {reward_amount} TC vào ví!',
                'new_balance': wallet.balance_tc
            })
            
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=500)
            
    return JsonResponse({'status': 'error', 'message': 'Chỉ chấp nhận POST'}, status=405)

# API Âm thầm ghi nhận UserBehavior
@csrf_exempt
def api_log_behavior(request):
    if request.method == 'POST':
        # Dù đăng nhập hay chưa (khách vãng lai), ta vẫn có thể log hành vi (nếu gán user=None)
        user = request.user if request.user.is_authenticated else None
        
        try:
            data = json.loads(request.body)
            video_id = data.get('video_id')
            event_type = data.get('event_type') # PLAY, PAUSE, SEEK, COMPLETE, DROP_OFF
            timestamp_sec = data.get('video_timestamp_seconds', 0)
            
            video = Video.objects.get(id=video_id)
            
            # Lấy thông tin thiết bị/trình duyệt của người dùng (User-Agent)
            user_agent = request.META.get('HTTP_USER_AGENT', '')[:150]
            
            UserBehavior.objects.create(
                user=user,
                video=video,
                event_type=event_type,
                video_timestamp_seconds=timestamp_sec,
                device_info=user_agent
            )
            
            # API này chạy ngầm nên chỉ cần trả về status 200 rất gọn
            return JsonResponse({'status': 'success'}, status=200)
            
        except Video.DoesNotExist:
            return JsonResponse({'status': 'error'}, status=404)
        except Exception as e:
            return JsonResponse({'status': 'error'}, status=500)
            
    return JsonResponse({'status': 'error'}, status=405)

