from decimal import Decimal

from django.contrib.auth.models import AbstractUser
from django.db import models


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
    # Single Time-Credit balance (1 TC = 1 minute)
    balance = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('30.00'))
    # Auto-updated on every save to trace wallet mutations
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Wallet of {self.user.username} | {self.balance} TC"


class Video(models.Model):
    """Represents a single video asset with pricing, ownership, and metadata."""

    # Indexed for faster title search
    title = models.CharField(max_length=255, db_index=True)
    # Optional course grouping for structured learning paths
    course = models.ForeignKey('Course', on_delete=models.CASCADE, related_name='videos', null=True, blank=True)
    # Optional prerequisite video that must be completed before unlocking this video
    prerequisite_video = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='dependent_videos'
    )
    # Top-level thematic category
    category = models.ForeignKey('Category', on_delete=models.SET_NULL, null=True, related_name='videos')
    # Owner/creator of the video
    creator = models.ForeignKey(User, on_delete=models.CASCADE, related_name='uploaded_videos')
    # Freeform description for SEO/context
    description = models.TextField(blank=True)
    # Stored media path for the video file
    file_url = models.FileField(upload_to='videos/')
    # New field to keep the uploaded video file itself (future proofing + FormData API)
    video_file = models.FileField(upload_to='videos/', null=True, blank=True)
    # Optional thumbnail image
    thumbnail = models.ImageField(upload_to='thumbnails/', null=True, blank=True)
    # Duration in seconds, used for analytics and UX cues
    duration_seconds = models.IntegerField(default=0)
    # Free content bypasses payment checks for all users
    is_free = models.BooleanField(default=False)
    # Manual base price in TC; when zero, pricing falls back to duration-based pricing
    base_price = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    # Marks short independent clips for home feed (not tied to a full course flow)
    is_standalone = models.BooleanField(default=False)
    # Soft-delete flag to hide content without losing ledger history
    is_active = models.BooleanField(default=True)
    # Soft-delete flag for retaining history while removing from listings
    is_deleted = models.BooleanField(default=False)
    # Creation timestamp for ordering
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title

    @property
    def price_tc(self):
        """Dynamic TC price from duration with round-half-up-to-minute rule."""
        if self.is_free:
            return 0
        if self.base_price and self.base_price > 0:
            return int(self.base_price)
        duration = max(0, self.duration_seconds or 0)
        return (duration + 30) // 60

    def delete(self, *args, **kwargs):
        """Soft-delete by toggling is_active instead of removing rows."""
        self.is_active = False
        self.is_deleted = True
        self.save(update_fields=['is_active', 'is_deleted'])


class Transaction(models.Model):
    """Ledger entry capturing every balance mutation for auditing and rollback."""

    TX_TYPES = (
        ('RECHARGE', 'Recharge TC via VND'),
        ('VIP_PURCHASE', 'VIP package purchase'),
        ('CONTENT_SALE', 'Paid content sale'),
        ('EARN_ADS', 'Earn TC from ads'),
        ('SPEND_VIEW', 'Spend TC to view'),
        ('EARN_CREATOR', 'Creator earns TC from viewers'),
        ('DEPOSIT_VND', 'Deposit VND'),
        ('BUY_VIP', 'Buy VIP package'),
        ('WITHDRAW_VND', 'Withdraw VND'),
        ('VIEW_POINT', 'View point accrual for creator'),
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
    amount_vnd = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    # For recharge logs: TC credited from VND top-up
    tc_added = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    # Processing status for async flows
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='SUCCESS')
    # Timestamp when the transaction was recorded
    timestamp = models.DateTimeField(auto_now_add=True)
    # Optional linkage to a video (e.g., purchases)
    reference_video = models.ForeignKey(Video, on_delete=models.SET_NULL, null=True, blank=True)

    def __str__(self):
        return f"{self.tx_type} | {self.amount_tc} TC | {self.status}"


class WatchSession(models.Model):
    """Per-user, per-video watch session tracking unlock state and progress."""

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
        return f"{self.user.username} watching {self.video.title} ({self.watched_seconds}s)"


class VideoAccess(models.Model):
    """Tracks whether a user has unlocked a specific video."""

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='video_accesses')
    video = models.ForeignKey(Video, on_delete=models.CASCADE, related_name='access_records')
    unlocked_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'video')

    def __str__(self):
        return f"{self.user.username} unlocked {self.video.title}"


class Category(models.Model):
    """Topic grouping used to organize videos and courses."""

    name = models.CharField(max_length=100, unique=True, verbose_name="Tên danh mục")
    description = models.TextField(blank=True, null=True, verbose_name="Mô tả danh mục")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name_plural = "Categories"

    def __str__(self):
        return self.name


class Course(models.Model):
    """Structured collection of videos curated by a creator."""

    title = models.CharField(max_length=255, verbose_name="Tên khóa học", db_index=True)
    description = models.TextField(verbose_name="Mô tả chi tiết")
    # Optional legacy category relation kept for backward compatibility
    category = models.ForeignKey('Category', on_delete=models.SET_NULL, null=True, blank=True, related_name='courses')
    # Free-text category used by course creation UI
    category_text = models.CharField(max_length=120, blank=True, default='')
    # Course owner/teacher (creator)
    instructor = models.ForeignKey(User, on_delete=models.CASCADE, related_name='taught_courses')
    # Soft-delete flag to keep history while hiding from listings
    is_active = models.BooleanField(default=True)
    # Soft-delete flag to prevent hard deletes that break ledger history
    is_deleted = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title

    def delete(self, *args, **kwargs):
        """Soft-delete courses to preserve financial and content history."""
        self.is_active = False
        self.is_deleted = True
        self.save(update_fields=['is_active', 'is_deleted'])


class CommentReview(models.Model):
    """Combined comment and optional rating for a video."""

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='comments')
    video = models.ForeignKey(Video, on_delete=models.CASCADE, related_name='comments')
    # Freeform feedback text
    content = models.TextField(verbose_name="Nội dung bình luận")
    # Discrete 1-5 star rating; nullable to allow comment-only feedback
    RATING_CHOICES = [(i, str(i)) for i in range(1, 6)]
    rating = models.IntegerField(choices=RATING_CHOICES, null=True, blank=True, verbose_name="Đánh giá sao")
    # When the comment was created
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username} commented on {self.video.title}"


class Follow(models.Model):
    """Directed relationship showing one user following another."""

    follower = models.ForeignKey(User, on_delete=models.CASCADE, related_name='following')
    following = models.ForeignKey(User, on_delete=models.CASCADE, related_name='followers')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('follower', 'following')

    def __str__(self):
        return f"{self.follower.username} -> {self.following.username}"


class Notification(models.Model):
    """Stores user-facing alerts like follows and ratings."""

    TYPE_COMMENT = 'comment'
    TYPE_FOLLOW = 'follow'
    TYPE_RATING = 'rating'
    TYPE_PURCHASE = 'purchase'
    TYPE_CHOICES = (
        (TYPE_COMMENT, 'Comment'),
        (TYPE_FOLLOW, 'Follow'),
        (TYPE_RATING, 'Rating'),
        (TYPE_PURCHASE, 'Purchase'),
    )

    recipient = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications_received')
    sender = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='notifications_sent')
    video = models.ForeignKey(Video, on_delete=models.CASCADE, null=True, blank=True, related_name='notifications')
    notification_type = models.CharField(max_length=20, choices=TYPE_CHOICES)
    text = models.CharField(max_length=255, verbose_name="Nội dung thông báo")
    link = models.CharField(max_length=255, blank=True, null=True, verbose_name="Đường dẫn chuyển hướng")
    is_read = models.BooleanField(default=False, verbose_name="Đã đọc?")
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    def __str__(self):
        status = "Đã đọc" if self.is_read else "Chưa đọc"
        return f"[{status}] {self.recipient.username} | {self.notification_type}"


class UserBehavior(models.Model):
    """Event-level telemetry for playback interactions, separate from watch sessions."""

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
    # Position in the video when the event occurred (seconds)
    video_timestamp_seconds = models.IntegerField(default=0, help_text="Timestamp within the video when the event happened")
    # Lightweight device fingerprint (user-agent or platform hint)
    device_info = models.CharField(max_length=150, blank=True, null=True, help_text="User Agent/Thiết bị")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        user_label = self.user.username if self.user else 'Ẩn danh'
        return f"Log: {user_label} - {self.event_type} - {self.video.title}"


class UserProfile(models.Model):
    """Per-user profile storing role selection and survey answers for recommendations."""

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    # Chosen persona (e.g., student/lecturer/researcher)
    role = models.CharField(max_length=50, blank=True, null=True)
    specialization = models.CharField(max_length=120, blank=True, default='')
    bio = models.TextField(blank=True, default='')
    # Flexible survey response storage for personalization
    survey_answers = models.JSONField(default=list, blank=True, null=True)
    avatar = models.ImageField(upload_to='avatars/', default='default.png')
    balance_tc = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('5.00'))
    wallet_balance = models.IntegerField(default=5)
    is_vip = models.BooleanField(default=False)
    vip_expiry = models.DateTimeField(null=True, blank=True)
    notify_comments = models.BooleanField(default=True)
    notify_follows = models.BooleanField(default=True)
    dark_mode = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.user.email} - Vai trò: {self.role}"


class CreatorAccount(models.Model):
    """Revenue pool for creator earnings split from purchases."""

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='creator_account')
    pending_vnd = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    available_vnd = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    total_earned_vnd = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"CreatorAccount<{self.user.username}> A:{self.available_vnd} P:{self.pending_vnd}"


class WithdrawalRequest(models.Model):
    """Tracks creator withdrawal requests before payout completion."""

    STATUS_CHOICES = (
        ('PENDING', 'Pending'),
        ('APPROVED', 'Approved'),
        ('REJECTED', 'Rejected'),
        ('PAID', 'Paid'),
    )

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='withdrawal_requests')
    amount_tc = models.DecimalField(max_digits=12, decimal_places=2)
    amount_vnd = models.DecimalField(max_digits=12, decimal_places=2)
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default='PENDING')
    note = models.CharField(max_length=255, blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Withdraw<{self.user.username}> {self.amount_tc} TC ({self.status})"