from django.contrib.auth import get_user_model
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import Wallet


User = get_user_model()


@receiver(post_save, sender=User)
def create_user_wallet(sender, instance, created, **kwargs):
    """Auto-provision a wallet for every newly created user."""

    if created:
        # Wallet default adds signup bonus via model default values
        Wallet.objects.create(user=instance)
        