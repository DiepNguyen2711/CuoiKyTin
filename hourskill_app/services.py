from decimal import Decimal
from math import ceil

from django.db import transaction

from .models import Transaction, Wallet


def transfer_tc(sender_user, receiver_user, amount_tc, tx_type):
    """Move TC from one user to another with audit logging and balance locks.

    Args:
        sender_user: User initiating the transfer (debited).
        receiver_user: User receiving the TC (credited).
        amount_tc: Decimal-compatible amount of TC to move.
        tx_type: Transaction code matching Transaction.TX_TYPES.
    """

    amount = Decimal(str(amount_tc))
    if amount <= 0:
        raise ValueError("Transfer amount must be positive.")

    # Wrap balance moves and ledger creation in a single atomic transaction
    with transaction.atomic():
        # Lock both wallets to prevent concurrent balance races
        sender_wallet = Wallet.objects.select_for_update().get(user=sender_user)
        receiver_wallet = Wallet.objects.select_for_update().get(user=receiver_user)

        if sender_wallet.balance < amount:
            raise ValueError("Số dư TC không đủ để thực hiện giao dịch.")

        # Record the ledger entry before mutating balances for traceability
        new_transaction = Transaction.objects.create(
            sender=sender_user,
            receiver=receiver_user,
            tx_type=tx_type,
            amount_tc=amount,
            status='SUCCESS',
        )

        # Apply debits/credits in-memory, then persist in a controlled order
        sender_wallet.balance -= amount
        receiver_wallet.balance += amount

        sender_wallet.save(update_fields=['balance', 'updated_at'])
        receiver_wallet.save(update_fields=['balance', 'updated_at'])

        return new_transaction
    
    
def process_view_payment(user, video):
    """Deduct viewer TC, credit creator, and log the ledger atomically.

    VIP users watch free (no wallet deduction) but still generate a VIEW_POINT
    transaction for creator revenue pooling. Non-VIP users are charged
    1 TC per minute (ceil on duration) with a wallet lock to prevent races.
    """
    # Bill by minutes watched (ceil) with a minimum of 1 minute
    duration_seconds = video.duration_seconds or 0
    billed_minutes = max(1, ceil(duration_seconds / 60))
    amount = Decimal(billed_minutes)

    # VIP users watch free but log view points
    if getattr(user, 'is_vip', False):
        Transaction.objects.create(
            sender=user,
            receiver=video.creator,
            tx_type='VIEW_POINT',
            amount_tc=Decimal('0.00'),
            reference_video=video,
            status='SUCCESS',
        )
        return Decimal('0.00')

    try:
        with transaction.atomic():
            viewer_wallet = Wallet.objects.select_for_update().get(user=user)

            if viewer_wallet.balance < amount:
                raise ValueError("Số dư TC không đủ để xem video này.")

            viewer_wallet.balance -= amount
            viewer_wallet.save(update_fields=['balance', 'updated_at'])

            # Record the view for creator revenue pooling (no immediate credit)
            Transaction.objects.create(
                sender=user,
                receiver=video.creator,
                tx_type='VIEW_POINT',
                amount_tc=amount,
                reference_video=video,
                status='SUCCESS',
            )
    except Exception:
        # Propagate for caller to handle and surface
        raise

    return amount
from .models import Video
from django.contrib.auth.models import User

def buy_video_service(user, video_id):

    try:
        video = Video.objects.get(id=video_id)

        # ví dụ trừ TC giả lập
        wallet = user.profile.time_credit

        if wallet < video.price_tc:
            return {
                "success": False,
                "message": "Không đủ Time Credit"
            }

        user.profile.time_credit -= video.price_tc
        user.profile.save()

        return {
            "success": True,
            "video_url": video.video_file.url
        }

    except Video.DoesNotExist:

        return {
            "success": False,
            "message": "Video không tồn tại"
        }