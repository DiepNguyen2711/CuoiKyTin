from django.shortcuts import render, redirect
from django.contrib.auth import login, authenticate
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.http import JsonResponse # Dùng nếu muốn trả về API thay vì giao diện

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