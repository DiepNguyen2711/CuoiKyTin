from django.contrib.auth import get_user_model
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import UserProfile, Wallet


User = get_user_model()


@receiver(post_save, sender=User)
def create_user_relations(sender, instance, created, **kwargs):
    """Auto-provision wallet and profile with signup bonus TC."""

    if not created:
        return

    # Wallet default already seeds 5 TC via model default
    Wallet.objects.get_or_create(user=instance)
    # Profile keeps lightweight wallet_balance for quick reads
    UserProfile.objects.get_or_create(user=instance, defaults={'wallet_balance': 5})
        