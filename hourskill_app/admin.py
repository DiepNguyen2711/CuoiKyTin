from django.apps import apps
from django.contrib import admin
from django.contrib.admin.sites import AlreadyRegistered, NotRegistered
from django.contrib.auth import get_user_model
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import UserProfile


User = get_user_model()


admin.site.site_header = "Hệ thống Quản trị HourSkill"
admin.site.site_title = "Admin HourSkill"


class UserProfileInline(admin.StackedInline):
    """Embed onboarding details (role, survey) inside the user edit page."""

    model = UserProfile
    can_delete = False
    verbose_name_plural = 'Thông tin Onboarding (Vai trò & Khảo sát)'


class UserAdmin(BaseUserAdmin):
    """Extend the default user admin to surface profile data inline."""

    inlines = (UserProfileInline,)


try:
    admin.site.unregister(User)
except NotRegistered:
    # If the user model was not registered yet, continue without error
    pass

admin.site.register(User, UserAdmin)


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    """Admin view for standalone profile records with helpful filters."""

    list_display = ('user', 'role')
    search_fields = ('user__username', 'user__email', 'role')
    list_filter = ('role',)


app_models = apps.get_app_config('hourskill_app').get_models()

for model in app_models:
    # Skip models that are explicitly registered above to avoid duplicates
    if model in {User, UserProfile}:
        continue
    try:
        admin.site.register(model)
    except AlreadyRegistered:
        # If a model is already registered elsewhere, leave it untouched
        continue