from django.contrib import admin
from django.apps import apps
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User
from .models import UserProfile

# Tùy chỉnh tiêu đề trang quản trị cho xịn sò
admin.site.site_header = "Hệ thống Quản trị HourSkill"
admin.site.site_title = "Admin HourSkill"

# Tự động quét và lấy tất cả các bảng trong database của app
app_models = apps.get_app_config('hourskill_app').get_models()

for model in app_models:
    try:
        admin.site.register(model)
    except admin.sites.AlreadyRegistered:
        pass


# Check khảo sát của các user
# Tạo một block hiển thị cho UserProfile
class UserProfileInline(admin.StackedInline):
    model = UserProfile
    can_delete = False
    verbose_name_plural = 'Thông tin Onboarding (Vai trò & Khảo sát)'

# Tạo một UserAdmin mới, kế thừa cái cũ và nhét block UserProfile vào
class UserAdmin(BaseUserAdmin):
    inlines = (UserProfileInline,)

# Hủy đăng ký bảng User cũ của Django và đăng ký lại bằng bảng User mới đã được nâng cấp
admin.site.unregister(User)
admin.site.register(User, UserAdmin)

#  Mục UserProfile đứng riêng lẻ bên ngoài menu chính
@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'role') # Hiển thị 2 cột này ở ngoài danh sách
    search_fields = ('user__username', 'user__email', 'role') # Thêm thanh tìm kiếm