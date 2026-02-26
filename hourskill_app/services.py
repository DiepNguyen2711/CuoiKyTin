from django.db import transaction
from .models import Wallet, Transaction

def transfer_tc(sender_user, receiver_user, amount, transaction_type):
    # Bước 1: Mở phiên giao dịch nguyên tử (Atomic)
    with transaction.atomic():
        # Khóa Bi quan (Pessimistic Locking) - select_for_update()
        # Khóa ví của người gửi và người nhận lại cho đến khi giao dịch xong
        sender_wallet = Wallet.objects.select_for_update().get(user=sender_user)
        receiver_wallet = Wallet.objects.select_for_update().get(user=receiver_user)

        # Kiểm tra số dư
        if sender_wallet.balance < amount:
            raise ValueError("Số dư không đủ để thực hiện giao dịch.")

        # Bước 2: Ghi nhận 1 dòng Transaction mới (Bằng chứng kiểm toán)
        new_transaction = Transaction.objects.create(
            sender=sender_user,
            receiver=receiver_user,
            amount=amount,
            transaction_type=transaction_type,
            status='SUCCESS' # Hoặc PENDING tùy luồng của bạn
        )

        # Bước 3 & 4: Trừ tiền người gửi, Cộng tiền người nhận
        sender_wallet.balance -= amount
        sender_wallet.save()

        receiver_wallet.balance += amount
        receiver_wallet.save()

        return new_transaction