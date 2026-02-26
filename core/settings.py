"""
Django settings for core project.
"""

import os
from pathlib import Path

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = "django-insecure-8e828-(y-#ze)j$wt6$$*m)vo^c=8uzs(g^kyrw069lw)7eymq"

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True

ALLOWED_HOSTS = []

# Application definition
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    
    # App của dự án
    'hourskill_app',
    'corsheaders',
]

MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware', # Middleware của nhóm bạn
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "core.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        # QUAN TRỌNG: Thêm 'templates' vào để Django tìm thấy file HTML mới của bạn
        # Đồng thời giữ 'frontend' để code nhóm bạn vẫn chạy bình thường.
        "DIRS": [
            BASE_DIR / 'frontend', 
            BASE_DIR / 'templates'
        ],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "core.wsgi.application"

# Database
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# Internationalization
LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

# Static files (CSS, JavaScript, Images)
STATIC_URL = '/static/'
STATICFILES_DIRS = [
    BASE_DIR / 'frontend', # Giữ nguyên theo code nhóm
]

# --- CẤU HÌNH QUAN TRỌNG CHO TÍNH NĂNG MỚI ---

# 1. User Model tùy chỉnh (Để dùng được Follow, Ví tiền, Profile)
AUTH_USER_MODEL = 'hourskill_app.User'

# 2. Cấu hình Upload Video/Ảnh (Bắt buộc để tính năng Upload chạy)
MEDIA_URL = '/media/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')

# 3. CORS (Của nhóm bạn)
CORS_ALLOW_ALL_ORIGINS = True
# --- CẤU HÌNH BỔ SUNG (CHO ĐỠ LỖI VẶT) ---

# 1. Khi đăng nhập xong -> Chuyển ngay về trang chủ ('home' là name trong urls.py)
LOGIN_REDIRECT_URL = 'home'

# 2. Khi đăng xuất xong -> Chuyển về trang login
LOGOUT_REDIRECT_URL = 'login'

# 3. Nếu chưa đăng nhập mà cố vào trang kín -> Đá về trang login
LOGIN_URL = 'login'

# 4. Loại khóa chính mặc định cho các Model (Tránh cảnh báo vàng)
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'