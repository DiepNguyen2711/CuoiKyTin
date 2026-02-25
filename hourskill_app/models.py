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
# ==========================================
# 3. HỆ THỐNG NỘI DUNG (VIDEO)
# ==========================================
class Video(models.Model):
    # Thêm Index cho trường title và category để tìm kiếm siêu tốc (milliseconds)
    title = models.CharField(max_length=255, db_index=True) 

    """Lưu trữ thông tin về các khóa học/video"""
    course = models.ForeignKey('Course', on_delete=models.CASCADE, related_name='videos', null=True, blank=True)
    category = models.ForeignKey('Category', on_delete=models.SET_NULL, null=True, related_name='videos')
    creator = models.ForeignKey(User, on_delete=models.CASCADE, related_name='uploaded_videos')
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
    # Thêm cờ Xóa mềm (Soft Delete)
    is_active = models.BooleanField(default=True)

    # (Tùy chọn) Ghi đè hàm delete mặc định để biến thành Xóa mềm
    def delete(self, *args, **kwargs):
        self.is_active = False
        self.save()

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
    
# ... (Phần code hiện tại của bạn từ HỆ THỐNG NGƯỜI DÙNG đến HỆ THỐNG THEO DÕI SỰ CHÚ Ý) ...

# ==========================================
# 6. HỆ THỐNG PHÂN LOẠI & TỔ CHỨC NỘI DUNG (CATEGORY & COURSE)
# ==========================================
class Category(models.Model):
    """Phân loại chủ đề cho Video/Khóa học"""
    name = models.CharField(max_length=100, unique=True, verbose_name="Tên danh mục")
    description = models.TextField(blank=True, null=True, verbose_name="Mô tả danh mục")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

class Course(models.Model):
    """
    Tập hợp nhiều Video thành một lộ trình có cấu trúc do Creator tự thiết kế.
    """
    title = models.CharField(max_length=255, verbose_name="Tên khóa học", db_index=True)
    description = models.TextField(verbose_name="Mô tả chi tiết")
    category = models.ForeignKey('Category', on_delete=models.SET_NULL, null=True, related_name='courses')
    # Instructor chính là Creator sở hữu khóa học này
    instructor = models.ForeignKey(User, on_delete=models.CASCADE, related_name='taught_courses')
    
    # ĐÃ XÓA dòng videos (ManyToManyField) ở đây để chuyển sang quan hệ 1-N
    
    bundle_price_tc = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, verbose_name="Giá trọn bộ (TC)")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title

    # Hàm Xóa mềm bảo vệ dữ liệu tài chính
    def delete(self, *args, **kwargs):
        self.is_active = False
        self.save()


# ==========================================
# 7. HỆ THỐNG TƯƠNG TÁC XÃ HỘI (SOCIAL FEATURES)
# ==========================================
class CommentReview(models.Model):
    """
    Kết hợp Bình luận và Đánh giá (Rating).
    """
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='comments')
    video = models.ForeignKey(Video, on_delete=models.CASCADE, related_name='comments')
    content = models.TextField(verbose_name="Nội dung bình luận")
    
    # Đánh giá sao (1-5). Để null=True vì người dùng có thể chỉ comment chứ không rate.
    RATING_CHOICES = [(i, str(i)) for i in range(1, 6)]
    rating = models.IntegerField(choices=RATING_CHOICES, null=True, blank=True, verbose_name="Đánh giá sao")
    
    # Có thể thêm self-referential để làm tính năng "Reply comment" nếu muốn:
    # parent = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True, related_name='replies')
    
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username} bình luận trên {self.video.title}"


class Follow(models.Model):
    """
    Lưu trữ quan hệ theo dõi giữa các User.
    """
    follower = models.ForeignKey(User, on_delete=models.CASCADE, related_name='following')
    following = models.ForeignKey(User, on_delete=models.CASCADE, related_name='followers')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        # Ràng buộc: Một người không thể follow người khác 2 lần
        unique_together = ('follower', 'following') 

    def __str__(self):
        return f"{self.follower.username} -> {self.following.username}"


class Notification(models.Model):
    """
    Thông báo hệ thống (có video mới, có người follow, v.v.)
    """
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
    content = models.CharField(max_length=255, verbose_name="Nội dung thông báo")
    link = models.CharField(max_length=255, blank=True, null=True, verbose_name="Đường dẫn chuyển hướng")
    is_read = models.BooleanField(default=False, verbose_name="Đã đọc?")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        status = "Đã đọc" if self.is_read else "Chưa đọc"
        return f"[{status}] Thông báo cho {self.user.username}"


# ==========================================
# 8. HỆ THỐNG PHÂN TÍCH DỮ LIỆU SÂU (ADVANCED ANALYTICS)
# ==========================================
class UserBehavior(models.Model):
    """
    Ghi nhận log hành vi chi tiết. Khác với WatchSession (dùng để ping time thật & mở khóa),
    bảng này lưu vết dạng event log để chạy các mô hình thống kê, kinh tế lượng sau này.
    Ví dụ: Phân tích các yếu tố ảnh hưởng đến tỷ lệ rời bỏ (drop-off rate).
    """
    EVENT_TYPES = (
        ('PLAY', 'Bắt đầu xem'),
        ('PAUSE', 'Tạm dừng'),
        ('SEEK', 'Tua video'),
        ('COMPLETE', 'Xem xong'),
        ('DROP_OFF', 'Thoát giữa chừng'),
    )

    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='behavior_logs')
    video = models.ForeignKey(Video, on_delete=models.CASCADE)
    
    event_type = models.CharField(max_length=20, choices=EVENT_TYPES)
    
    # Thời điểm trong video (tính bằng giây) mà event xảy ra.
    # Rất hữu ích để chạy mô hình hồi quy xem đoạn nào của video khiến người dùng thoát nhiều nhất.
    video_timestamp_seconds = models.IntegerField(default=0, help_text="Vị trí thời gian trong video lúc xảy ra event")
    
    device_info = models.CharField(max_length=150, blank=True, null=True, help_text="User Agent/Thiết bị")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Log: {self.user.username if self.user else 'Ẩn danh'} - {self.event_type} - {self.video.title}"

