from decimal import Decimal

from django.contrib.auth.models import AbstractUser
from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils import timezone

class User(AbstractUser):
    """Custom user carrying role flags and trust scoring for anti-abuse controls."""

    # Marks whether the account can publish content
    is_creator = models.BooleanField(default=False, help_text="Creator accounts can upload content")
    # Marks whether the account has VIP privileges (paid VND)
    is_vip = models.BooleanField(default=False, help_text="VIP users have paid VND benefits")
    # Expiry timestamp for VIP status
    vip_expiry = models.DateTimeField(null=True, blank=True)
    # Reputation signal to throttle spammy behavior
    trust_score = models.IntegerField(default=100, help_text="Lower scores indicate suspicious activity")

    def __str__(self):
        return f"{self.username} (VIP)" if self.is_vip else self.username


class Wallet(models.Model):
    """Holds both in-app credits (TC) and real-currency VND for a single user."""

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='wallet')
    # Time-Credit balance (defaults to signup bonus)
    balance_tc = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('5.00'))
    # Fiat balance tracked for deposits/withdrawals
    balance_vnd = models.DecimalField(max_digits=15, decimal_places=0, default=0)
    # Auto-updated on every save to trace wallet mutations
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Wallet of {self.user.username} | {self.balance_tc} TC"


# ==========================================
# 3. HỆ THỐNG NỘI DUNG (VIDEO)
# ==========================================
class Video(models.Model):
    """Represents a single video asset with pricing, ownership, and metadata."""

    # Indexed for faster title search
    title = models.CharField(max_length=255, db_index=True)
    # Optional course grouping for structured learning paths
    course = models.ForeignKey('Course', on_delete=models.CASCADE, related_name='videos', null=True, blank=True)
    # Top-level thematic category
    category = models.ForeignKey('Category', on_delete=models.SET_NULL, null=True, related_name='videos')
    # Owner/creator of the video
    creator = models.ForeignKey(User, on_delete=models.CASCADE, related_name='uploaded_videos')
    # Freeform description for SEO/context
    description = models.TextField(blank=True)
    
    # --- [SỬA]: Đổi file_url -> file để khớp logic Upload mới ---
    file = models.FileField(upload_to='videos/') 
    thumbnail = models.ImageField(upload_to='thumbnails/', null=True, blank=True)
    
    duration_seconds = models.IntegerField(default=0, help_text="Thời lượng video (giây)")
    
    # Giá để mở khóa video này (ví dụ: 0.5 TC)
    price_tc = models.DecimalField(max_digits=8, decimal_places=2, default=0.00)
    
    is_active = models.BooleanField(default=True)
    # Creation timestamp for ordering
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title  
    
    # Ghi đè hàm delete mặc định để biến thành Xóa mềm
    def delete(self, *args, **kwargs):
        """Soft-delete by toggling is_active instead of removing rows."""
        self.is_active = False
        self.save(update_fields=['is_active'])


# ==========================================
# 4. NHẬT KÝ GIAO DỊCH (LEDGER/TRANSACTIONS)
# ==========================================
class Transaction(models.Model):
    """Ledger entry capturing every balance mutation for auditing and rollback."""

    TX_TYPES = (
        ('EARN_ADS', 'Earn TC from ads'),
        ('SPEND_VIEW', 'Spend TC to view'),
        ('EARN_CREATOR', 'Creator earns TC from viewers'),
        ('DEPOSIT_VND', 'Deposit VND'),
        ('WITHDRAW_VND', 'Withdraw VND'),
    )

    STATUS_CHOICES = (
        ('PENDING', 'Pending'),
        ('SUCCESS', 'Success'),
        ('FAILED', 'Failed'),
    )

    # Sender may be null for system-generated credits
    sender = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='sent_transactions')
    # Receiver captures the beneficiary of the transaction
    receiver = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='received_transactions')
    # Business reason for the transaction
    tx_type = models.CharField(max_length=20, choices=TX_TYPES)
    # Token amount involved (TC)
    amount_tc = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    # Fiat amount involved (VND)
    amount_vnd = models.DecimalField(max_digits=15, decimal_places=0, default=0)
    # Processing status for async flows
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='SUCCESS')
    # Timestamp when the transaction was recorded
    timestamp = models.DateTimeField(auto_now_add=True)
    # Optional linkage to a video (e.g., purchases)
    reference_video = models.ForeignKey(Video, on_delete=models.SET_NULL, null=True, blank=True)

    def __str__(self):
        return f"{self.tx_type} | {self.amount_tc} TC | {self.status}"


class WatchSession(models.Model):
    """
    Bảng này giải quyết bài toán cốt lõi: Làm sao biết User thực sự xem video?
    """
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    video = models.ForeignKey(Video, on_delete=models.CASCADE)
    # Start of the session used for analytics
    start_time = models.DateTimeField(auto_now_add=True)
    # Updated on every ping to detect drop-offs
    last_ping_time = models.DateTimeField(auto_now=True)
    # Total watched seconds accumulated via heartbeats
    watched_seconds = models.IntegerField(default=0)
    # Marks whether the viewer paid/unlocked the video
    is_unlocked = models.BooleanField(default=False, help_text="True once TC payment is completed")

    class Meta:
        # Prevent duplicate sessions for the same user/video pair
        unique_together = ('user', 'video')

    def __str__(self):
        return f"{self.user.username} xem {self.video.title} ({self.watched_seconds}s)"

class Category(models.Model):
    """Topic grouping used to organize videos and courses."""

    name = models.CharField(max_length=100, unique=True, verbose_name="Tên danh mục")
    description = models.TextField(blank=True, null=True, verbose_name="Mô tả danh mục")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class Course(models.Model):
    """Structured collection of videos curated by a creator."""

    title = models.CharField(max_length=255, verbose_name="Tên khóa học", db_index=True)
    description = models.TextField(verbose_name="Mô tả chi tiết")
    # Optional category to group courses by topic
    category = models.ForeignKey('Category', on_delete=models.SET_NULL, null=True, related_name='courses')
    # Course owner/teacher (creator)
    instructor = models.ForeignKey(User, on_delete=models.CASCADE, related_name='taught_courses')
    
    bundle_price_tc = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, verbose_name="Giá trọn bộ (TC)")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title

    def delete(self, *args, **kwargs):
        """Soft-delete courses to preserve financial and content history."""
        self.is_active = False
        self.save(update_fields=['is_active'])

# ==========================================
# 7. HỆ THỐNG TƯƠNG TÁC XÃ HỘI (SOCIAL FEATURES)
# ==========================================
class CommentReview(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='comments')
    video = models.ForeignKey(Video, on_delete=models.CASCADE, related_name='comments')
    # Freeform feedback text
    content = models.TextField(verbose_name="Nội dung bình luận")
    
    RATING_CHOICES = [(i, str(i)) for i in range(1, 6)]
    rating = models.IntegerField(choices=RATING_CHOICES, null=True, blank=True, verbose_name="Đánh giá sao")
    
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username} commented on {self.video.title}"

class Follow(models.Model):
    follower = models.ForeignKey(User, on_delete=models.CASCADE, related_name='following')
    following = models.ForeignKey(User, on_delete=models.CASCADE, related_name='followers')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('follower', 'following') 

    def __str__(self):
        return f"{self.follower.username} -> {self.following.username}"

class Notification(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
    content = models.CharField(max_length=255, verbose_name="Nội dung thông báo")
    link = models.CharField(max_length=255, blank=True, null=True, verbose_name="Đường dẫn chuyển hướng")
    is_read = models.BooleanField(default=False, verbose_name="Đã đọc?")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"[{'Đã đọc' if self.is_read else 'Chưa đọc'}] Thông báo cho {self.user.username}"

# ==========================================
# 8. HỆ THỐNG PHÂN TÍCH DỮ LIỆU SÂU
# ==========================================
class UserBehavior(models.Model):
    EVENT_TYPES = (
        ('PLAY', 'Bắt đầu xem'),
        ('PAUSE', 'Tạm dừng'),
        ('SEEK', 'Tua video'),
        ('COMPLETE', 'Xem xong'),
        ('DROP_OFF', 'Thoát giữa chừng'),
    )

    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='behavior_logs')
    video = models.ForeignKey(Video, on_delete=models.CASCADE)
    # Type of interaction captured for analytics
    event_type = models.CharField(max_length=20, choices=EVENT_TYPES)
    video_timestamp_seconds = models.IntegerField(default=0, help_text="Vị trí thời gian trong video lúc xảy ra event")
    device_info = models.CharField(max_length=150, blank=True, null=True, help_text="User Agent/Thiết bị")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        user_label = self.user.username if self.user else 'Ẩn danh'
        return f"Log: {user_label} - {self.event_type} - {self.video.title}"

# ==========================================
# [MỚI] 9. MODEL HỖ TRỢ UPLOAD FILE
# (Cần thêm cái này để sửa lỗi ImportError)
# ==========================================
class UploadFile(models.Model):
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    file = models.FileField(upload_to='uploads/')
    uploaded_at = models.DateTimeField(auto_now_add=True)
    def __str__(self): return self.file.name
