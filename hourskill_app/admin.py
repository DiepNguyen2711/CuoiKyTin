from django.contrib import admin
from .models import User, Wallet, Video, Transaction, WatchSession

# Đăng ký các bảng để hiển thị lên trang Quản trị
admin.site.register(User)
admin.site.register(Wallet)
admin.site.register(Video)
admin.site.register(Transaction)
admin.site.register(WatchSession)