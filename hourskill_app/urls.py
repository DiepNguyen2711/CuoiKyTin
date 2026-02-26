from django.urls import path
from . import views

urlpatterns = [
    # --- GIAO DIỆN CHÍNH ---
    path('', views.main_view, name='home'),
    path('profile/<str:username>/', views.profile_view, name='profile_view'), # Trang cá nhân
    path('register/', views.register_view, name='register'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.user_logout, name='logout'),

    # --- API TÍNH NĂNG MỚI ---
    path('api/upload-video/', views.api_upload_video, name='api_upload_video'),
    path('api/follow/', views.api_toggle_follow, name='api_toggle_follow'),
    path('api/upload-file/', views.upload_file, name='upload_file'),

    # --- API TÍNH NĂNG CŨ (Của nhóm) ---
    path('api/register/', views.api_register, name='api_register'),
    path('api/login/', views.api_login, name='api_login'),
    path('api/courses/', views.api_get_courses, name='api_get_courses'),
    path('api/purchase-video/', views.api_purchase_video, name='api_purchase_video'),
    path('api/ping-watch/', views.ping_watch_session, name='ping_watch_session'),
    path('api/reward-ads/', views.api_reward_ads, name='api_reward_ads'),
    path('api/post-comment/', views.api_post_comment, name='api_post_comment'),
    path('api/notifications/', views.api_get_notifications, name='api_get_notifications'),
    path('api/log-behavior/', views.api_log_behavior, name='api_log_behavior'),
]