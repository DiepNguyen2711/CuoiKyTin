from django.contrib import admin
from django.apps import apps

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