from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import User, Wallet 

@receiver(post_save, sender=User)
def create_user_wallet(sender, instance, created, **kwargs):
    # Biến 'created' sẽ mang giá trị True nếu đây là User mới được đăng ký
    if created:
        # Tự động tạo Ví nối với User này và nạp sẵn 5 TC
        Wallet.objects.create(user=instance)
        