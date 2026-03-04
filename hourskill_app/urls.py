"""URL routing for the HourSkill app covering pages and JSON APIs."""

from django.urls import path

from . import views


urlpatterns = [
    path('api/register/', views.api_register, name='api_register'),
    path('api/login/', views.api_login, name='api_login'),
    path('api/survey/', views.api_survey, name='survey'),
    path('api/select-role/', views.api_select_role, name='select-role'),
    path('api/ping-watch/', views.ping_watch_session, name='ping_watch_session'),
    path('api/upload-video/', views.api_upload_video, name='api_upload_video'),
    path('api/video/<int:video_id>/', views.api_get_video_detail, name='api_get_video_detail'),
    path('api/video/<int:video_id>', views.api_get_video_detail),
    path('api/video/<int:video_id>/unlock/', views.api_unlock_video, name='api_unlock_video'),
    path('api/video/<int:video_id>/unlock', views.api_unlock_video),
    path('api/courses/', views.api_get_courses, name='api_get_courses'),
    path('api/follow/', views.api_toggle_follow, name='api_toggle_follow'),
    path('api/follow/<int:creator_id>/', views.api_toggle_follow, name='api_toggle_follow_path'),
    path('api/follow/<int:creator_id>', views.api_toggle_follow),
    path('api/creator/notify-toggle', views.api_creator_notify_toggle, name='api_creator_notify_toggle'),
    path('api/purchase-video/', views.api_purchase_video, name='api_purchase_video'),
    path('api/post-comment/', views.api_post_comment, name='api_post_comment'),
    path('api/notifications/', views.api_get_notifications, name='api_get_notifications'),
    path('api/reward-ads/', views.api_reward_ads, name='api_reward_ads'),
    path('api/log-behavior/', views.api_log_behavior, name='api_log_behavior'),
    path('api/channel/', views.api_channel_detail, name='api_channel_detail'),
    path('api/create-course/', views.api_create_course_with_video, name='api_create_course_with_video'),
    path('create-course/', views.create_course, name='create_course'),
    path('api/follow-toggle/', views.api_toggle_follow, name='api_toggle_follow'),
]