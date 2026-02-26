from django.contrib import admin
from django.apps import apps
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User
from django.contrib.admin.sites import NotRegistered
from .models import UserProfile

# ==========================================
# 1. TÙY CHỈNH CHUNG CỦA TRANG ADMIN
# ==========================================
# Tùy chỉnh tiêu đề trang quản trị cho xịn sò
admin.site.site_header = "Hệ thống Quản trị HourSkill"
admin.site.site_title = "Admin HourSkill"


# ==========================================
# 2. ĐĂNG KÝ THỦ CÔNG CÁC BẢNG QUAN TRỌNG (Giao diện Custom)
# ==========================================

# --- A. Check khảo sát của các user (Gắn vào bảng User) ---
# Tạo một block hiển thị cho UserProfile
class UserProfileInline(admin.StackedInline):
    model = UserProfile
    can_delete = False
    verbose_name_plural = 'Thông tin Onboarding (Vai trò & Khảo sát)'

# Tạo một UserAdmin mới, kế thừa cái cũ và nhét block UserProfile vào
class UserAdmin(BaseUserAdmin):
    inlines = (UserProfileInline,)

# Bắt lỗi an toàn khi gỡ đăng ký bảng User cũ của Django 
try:
    admin.site.unregister(User)
except NotRegistered:
    pass # Nếu User chưa được đăng ký thì lẳng lặng bỏ qua, không báo lỗi

# Đăng ký lại bằng bảng User mới đã được nâng cấp
admin.site.register(User, UserAdmin)


# --- B. MỤC USER PROFILE ĐỨNG RIÊNG ---
@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    # Hiển thị 2 cột này ở ngoài danh sách
    list_display = ('user', 'role') 
    
    # Thêm thanh tìm kiếm theo tên, email và vai trò (rất tiện để lọc)
    search_fields = ('user__username', 'user__email', 'role') 
    
    # Thêm bộ lọc bên tay phải
    list_filter = ('role',)


# ==========================================
# 3. TỰ ĐỘNG ĐĂNG KÝ CÁC BẢNG CÒN LẠI (Quét tự động)
# ==========================================
# Đặt vòng lặp ở cuối cùng để không "giành giật" với các model đã custom ở trên
app_models = apps.get_app_config('hourskill_app').get_models()

for model in app_models:
    try:
        admin.site.register(model)
    except admin.sites.AlreadyRegistered:
        pass # Bảng nào đăng ký ở trên rồi thì nó sẽ lướt qua êm ái