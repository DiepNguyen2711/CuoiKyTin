import json
from django.views.decorators.csrf import csrf_exempt
from django.shortcuts import render, redirect
from django.contrib.auth import login, authenticate, logout
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from hourskill_app.models import User, Wallet
from django.http import JsonResponse # Dùng nếu muốn trả về API thay vì giao diện
from .models import WatchSession

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
            # 1. Đọc dữ liệu JSON từ Frontend gửi lên
            data = json.loads(request.body)
            username = data.get('username')
            email = data.get('email')
            password = data.get('password')

            # 2. Kiểm tra xem username đã tồn tại chưa
            if User.objects.filter(username=username).exists():
                return JsonResponse({'status': 'error', 'message': 'Tên đăng nhập đã tồn tại!'}, status=400)

            # 3. Tạo User mới (dùng create_user để mật khẩu được mã hóa)
            user = User.objects.create_user(username=username, email=email, password=password)
           
            return JsonResponse({
                'status': 'success', 
                'message': 'Đăng ký thành công! Bạn đã nhận được 5 TC vào ví.'
            }, status=201)

        except json.JSONDecodeError:
            return JsonResponse({'status': 'error', 'message': 'Dữ liệu không hợp lệ!'}, status=400)
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=500)

    return JsonResponse({'status': 'error', 'message': 'Chỉ chấp nhận POST!'}, status=405)

# 4. Đăng nhập hoạt động
@csrf_exempt
def api_login(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            email = data.get('email')
            password = data.get('password')

            from django.contrib.auth import authenticate, login as auth_login
            from hourskill_app.models import User
            
            # Tìm User theo email và xác thực
            user_obj = User.objects.get(email=email)
            user = authenticate(request, username=user_obj.username, password=password)
            
            if user is not None:
                auth_login(request, user)
                return JsonResponse({'status': 'success'}, status=200)
            else:
                return JsonResponse({'status': 'error', 'message': 'Sai mật khẩu!'}, status=400)
        except User.DoesNotExist:
            return JsonResponse({'status': 'error', 'message': 'Email chưa đăng ký!'}, status=400)
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=500)
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