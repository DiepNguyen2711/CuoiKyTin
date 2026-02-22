from django.db import models

# Create your models here.
from django.contrib.auth.models import AbstractUser
from django.utils import timezone

# ==========================================
# 1. HỆ THỐNG NGƯỜI DÙNG & PHÂN QUYỀN
# ==========================================
class User(AbstractUser):
    """
    Mở rộng bảng User mặc định của Django.
    Phân biệt rõ người dùng thường (Học viên) và Creator.
    """
    is_creator = models.BooleanField(default=False, help_text="Đánh dấu nếu là người sáng tạo nội dung")
    is_vip = models.BooleanField(default=False, help_text="Đánh dấu nếu là người dùng trả phí VND")
    vip_expiry = models.DateTimeField(null=True, blank=True)
    
    # Điểm uy tín để chống spam (Innovation Feature)
    trust_score = models.IntegerField(default=100, help_text="Điểm uy tín, trừ điểm nếu phát hiện treo máy xem video")

    def __str__(self):
        return f"{self.username} (VIP)" if self.is_vip else self.username

# ==========================================
# 2. HỆ THỐNG VÍ & TIỀN TỆ (CORE ECONOMY)
# ==========================================
class Wallet(models.Model):
    """
    Ví tiền của người dùng. 
    LƯU Ý KỸ THUẬT QUAN TRỌNG: LUÔN DÙNG DecimalField cho tiền tệ, KHÔNG DÙNG FloatField để tránh sai số.
    """
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='wallet')
    
    # TC (Time-Credit) - Tiền ảo nội bộ
    balance_tc = models.DecimalField(max_digits=12, decimal_places=2, default=5.00) # Tặng 5 TC khi tạo tài khoản
    
    # Tiền thật (VNĐ) - Dành cho Creator rút hoặc User nạp VIP
    balance_vnd = models.DecimalField(max_digits=15, decimal_places=0, default=0)
    
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Ví của {self.user.username} | {self.balance_tc} TC"

# ==========================================
# 3. HỆ THỐNG NỘI DUNG (VIDEO)
# ==========================================
class Video(models.Model):
    """Lưu trữ thông tin về các khóa học/video"""
    creator = models.ForeignKey(User, on_delete=models.CASCADE, related_name='videos')
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    
    # Đường dẫn file (nên thiết lập Upload vào folder 'videos/')
    file_url = models.FileField(upload_to='videos/') 
    thumbnail = models.ImageField(upload_to='thumbnails/', null=True, blank=True)
    
    duration_seconds = models.IntegerField(help_text="Thời lượng video (giây)")
    
    # Giá để mở khóa video này (ví dụ: 0.5 TC)
    price_tc = models.DecimalField(max_digits=8, decimal_places=2, default=0.00)
    
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title

# ==========================================
# 4. NHẬT KÝ GIAO DỊCH (LEDGER/TRANSACTIONS) - GHI ĐIỂM "SYSTEM THINKING"
# ==========================================
class Transaction(models.Model):
    """
    Sổ cái ghi chép mọi biến động số dư. Bắt buộc phải có để truy vết dòng tiền.
    """
    TX_TYPES = (
        ('EARN_ADS', 'Nhận TC từ xem quảng cáo'),
        ('SPEND_VIEW', 'Trả TC để xem video'),
        ('EARN_CREATOR', 'Creator nhận TC từ người xem'),
        ('DEPOSIT_VND', 'Nạp VND'),
        ('WITHDRAW_VND', 'Rút VND'),
    )
    
    STATUS_CHOICES = (
        ('PENDING', 'Đang chờ xử lý'),
        ('SUCCESS', 'Thành công'),
        ('FAILED', 'Thất bại'),
    )

    # Nếu hệ thống tặng tiền (ví dụ xem Ads), sender sẽ là NULL
    sender = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='sent_tx')
    receiver = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='received_tx')
    
    tx_type = models.CharField(max_length=20, choices=TX_TYPES)
    amount_tc = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    amount_vnd = models.DecimalField(max_digits=15, decimal_places=0, default=0)
    
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='SUCCESS')
    timestamp = models.DateTimeField(auto_now_add=True)
    
    # Gắn với video nào (nếu có)
    reference_video = models.ForeignKey(Video, on_delete=models.SET_NULL, null=True, blank=True)

    def __str__(self):
        return f"{self.tx_type} | {self.amount_tc} TC | {self.status}"

# ==========================================
# 5. HỆ THỐNG THEO DÕI SỰ CHÚ Ý (PROOF OF ATTENTION)
# ==========================================
class WatchSession(models.Model):
    """
    Bảng này giải quyết bài toán cốt lõi: Làm sao biết User thực sự xem video?
    Client (JS) sẽ gọi API ping server mỗi 10 giây để update 'watched_seconds'.
    """
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    video = models.ForeignKey(Video, on_delete=models.CASCADE)
    
    start_time = models.DateTimeField(auto_now_add=True)
    last_ping_time = models.DateTimeField(auto_now=True)
    
    watched_seconds = models.IntegerField(default=0)
    is_unlocked = models.BooleanField(default=False, help_text="Đã trả TC để mở khóa chưa?")
    
    class Meta:
        # Một user chỉ có 1 session duy nhất cho 1 video
        unique_together = ('user', 'video')

    def __str__(self):
        return f"{self.user.username} xem {self.video.title} ({self.watched_seconds}s)"