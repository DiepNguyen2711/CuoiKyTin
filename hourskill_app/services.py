from decimal import Decimal

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

        if sender_wallet.balance_tc < amount:
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
        sender_wallet.balance_tc -= amount
        receiver_wallet.balance_tc += amount

        sender_wallet.save(update_fields=['balance_tc', 'updated_at'])
        receiver_wallet.save(update_fields=['balance_tc', 'updated_at'])

        return new_transaction