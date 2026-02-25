from django.urls import path
from . import views

urlpatterns = [
    path('register/', views.register_view, name='register'),
    path('login/', views.login_view, name='login'),
    path('api/register/', views.api_register, name='api_register'),
    path('api/login/', views.api_login, name='api_login'),
    path('main/', views.main_view, name='main_view'),
    path('logout/', views.user_logout, name='logout'),
    path('api/ping-watch/', views.ping_watch_session, name='ping_watch_session'),
    path('api/upload-video/', views.api_upload_video, name='api_upload_video'),
    path('api/courses/', views.api_get_courses, name='api_get_courses'),
    path('api/follow/', views.api_toggle_follow, name='api_toggle_follow'),
    path('api/purchase-video/', views.api_purchase_video, name='api_purchase_video'),
    path('api/post-comment/', views.api_post_comment, name='api_post_comment'),
    path('api/notifications/', views.api_get_notifications, name='api_get_notifications'),
]