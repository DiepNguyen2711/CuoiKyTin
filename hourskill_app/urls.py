"""URL routing for the HourSkill app covering pages and JSON APIs."""

from django.urls import path

from . import views


urlpatterns = [
    # Render the form-based registration page
    path('register/', views.register_view, name='register'),
    # Render the form-based login page
    path('login/', views.login_view, name='login'),
    # JSON: Create a new user account
    path('api/register/', views.api_register, name='api_register'),
    # JSON: Authenticate user via email/password
    path('api/login/', views.api_login, name='api_login'),
    # Auth-gated main page view
    path('main/', views.main_view, name='main_view'),
    # Terminate the current user session
    path('logout/', views.user_logout, name='logout'),
    # JSON: Heartbeat to track watch progress
    path('api/ping-watch/', views.ping_watch_session, name='ping_watch_session'),
    # JSON: Upload video assets to storage
    path('api/upload-video/', views.api_upload_video, name='api_upload_video'),
    # JSON: Video detail and unlock
    path('api/video/<int:video_id>/', views.api_get_video_detail, name='api_get_video_detail'),
    path('api/video/<int:video_id>', views.api_get_video_detail),
    path('api/video/<int:video_id>/unlock/', views.api_unlock_video, name='api_unlock_video'),
    path('api/video/<int:video_id>/unlock', views.api_unlock_video),
    # JSON: Fetch course and category catalog
    path('api/courses/', views.api_get_courses, name='api_get_courses'),
    # JSON: Follow or unfollow a creator
    path('api/follow/', views.api_toggle_follow, name='api_toggle_follow'),
    path('api/follow/<int:creator_id>/', views.api_toggle_follow, name='api_toggle_follow_path'),
    path('api/follow/<int:creator_id>', views.api_toggle_follow),
    # JSON: Creator notification toggle
    path('api/creator/notify-toggle', views.api_creator_notify_toggle, name='api_creator_notify_toggle'),
    # JSON: Purchase and unlock a video
    path('api/purchase-video/', views.api_purchase_video, name='api_purchase_video'),
    # JSON: Post a comment/review on a video
    path('api/post-comment/', views.api_post_comment, name='api_post_comment'),
    # JSON: Retrieve recent notifications and unread count
    path('api/notifications/', views.api_get_notifications, name='api_get_notifications'),
    # JSON: Reward TC for ad views with spam checks
    path('api/reward-ads/', views.api_reward_ads, name='api_reward_ads'),
    # JSON: Log playback events for analytics
    path('api/log-behavior/', views.api_log_behavior, name='api_log_behavior'),
]