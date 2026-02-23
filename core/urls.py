from django.contrib import admin
from django.urls import path, include 

urlpatterns = [
    path('admin/', admin.site.urls),
    # Nối toàn bộ đường dẫn của hourskill_app vào hệ thống chính:
    path('', include('hourskill_app.urls')), 
]