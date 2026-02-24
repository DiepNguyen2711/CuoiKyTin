from django.contrib import admin
from django.urls import path, include 
from django.views.generic import RedirectView

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', RedirectView.as_view(pattern_name='login')),
    # Nối toàn bộ đường dẫn của hourskill_app vào hệ thống chính:
    path('', include('hourskill_app.urls')),     
]