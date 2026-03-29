from decimal import Decimal

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

    wallet, created_wallet = Wallet.objects.get_or_create(user=instance)
    if created_wallet:
        wallet.balance = Decimal('30.00')
        wallet.save(update_fields=['balance'])

    # Profile keeps lightweight wallet_balance for quick reads
    UserProfile.objects.get_or_create(
        user=instance,
        defaults={
            'wallet_balance': 30,
            'balance_tc': Decimal('30.00'),
        },
    )
        