"""URL routing for the HourSkill app covering pages and JSON APIs."""

from django.urls import path

from . import views


urlpatterns = [
    # JSON: Create a new user account
    path('api/register/', views.api_register, name='api_register'),
    # JSON: Authenticate user via email/password
    path('api/login/', views.api_login, name='api_login'),
    path('api/wallet/', views.api_get_wallet, name='api_get_wallet'),
    path('api/survey/', views.api_survey, name='survey'),
    path('api/select-role/', views.api_select_role, name='select-role'),
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
    # Instructor channel detail showing their courses and follower count
    path('api/channel/', views.api_channel_detail, name='api_channel_detail'),
    # Create a course together with a video file upload
    path('api/create-course/', views.api_create_course_with_video, name='api_create_course_with_video'),
    # front-end page for uploading courses (non-API)
    path('create-course/', views.create_course, name='create_course'),
    # alias for follow toggle, kept for clarity
    path('api/follow-toggle/', views.api_toggle_follow, name='api_toggle_follow'),
]