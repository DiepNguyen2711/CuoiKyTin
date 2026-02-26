from django.contrib import admin
from django.urls import path, include
from django.views.generic import RedirectView
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),

    # --- LOGIC CŨ CỦA NHÓM ---
    # (Tạm ẩn dòng này để Trang Chủ hoạt động)
    # Lý do: Trong hourskill_app/views.py đã có logic "Chưa đăng nhập -> Chuyển về Login" rồi.
    # Nếu bật dòng dưới đây, đăng nhập xong cũng sẽ không vào được trang xem video.
    # path('', RedirectView.as_view(pattern_name='login')),

    # --- KẾT NỐI VỚI APP (Logic mới + cũ) ---
    path('', include('hourskill_app.urls')),     
]

# --- CẤU HÌNH HIỂN THỊ FILE MEDIA (BẮT BUỘC ĐỂ XEM VIDEO/ẢNH) ---
# Đoạn này giúp trình duyệt truy cập được vào thư mục /media/ trên máy bạn
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)