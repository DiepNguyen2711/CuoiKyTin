import os
import django
from django.utils import timezone

# Khởi tạo môi trường Django để chạy script độc lập
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from hourskill_app.models import User, Wallet, Video, Transaction, WatchSession

def run_seed():
    print("Đang dọn dẹp dữ liệu cũ (nếu có)...")
    # Xóa user cũ (ngoại trừ tài khoản admin của bạn)
    User.objects.filter(is_superuser=False).delete()

    print("Đang tạo người dùng mẫu...")
    # 1. Tạo Creator (Người sáng tạo nội dung)
    creator_nhan = User.objects.create_user(username='creator_nhan', password='123', is_creator=True)
    Wallet.objects.create(user=creator_nhan, balance_tc=500.0, balance_vnd=150000)

    # 2. Tạo User VIP
    vip_trong = User.objects.create_user(username='vip_trong', password='123', is_vip=True, vip_expiry=timezone.now())
    Wallet.objects.create(user=vip_trong, balance_tc=50.0)

    # 3. Tạo User thường
    user_quynhanh = User.objects.create_user(username='user_quynhanh', password='123')
    Wallet.objects.create(user=user_quynhanh, balance_tc=5.0) # Tặng 5 TC mặc định

    print("Đang tạo Video mẫu...")
    vid1 = Video.objects.create(
        creator=creator_nhan, 
        title='Khóa học Python cơ bản cho người mới', 
        duration_seconds=3600, 
        price_tc=10.0, 
        file_url='videos/python_co_ban.mp4'
    )
    vid2 = Video.objects.create(
        creator=creator_nhan, 
        title='Phân tích dữ liệu với Pandas', 
        duration_seconds=4500, 
        price_tc=15.0, 
        file_url='videos/pandas_data.mp4'
    )

    print("Đang tạo Giao dịch (Transaction) mẫu...")
    # Trọng mua video của Nhân
    Transaction.objects.create(
        sender=vip_trong, receiver=creator_nhan, tx_type='SPEND_VIEW', 
        amount_tc=10.0, status='SUCCESS', reference_video=vid1
    )
    # Quỳnh Anh được hệ thống tặng tiền xem quảng cáo
    Transaction.objects.create(
        sender=None, receiver=user_quynhanh, tx_type='EARN_ADS', 
        amount_tc=2.0, status='SUCCESS'
    )

    print("Đang tạo Lịch sử xem (Watch Session)...")
    WatchSession.objects.create(user=vip_trong, video=vid1, watched_seconds=1200, is_unlocked=True)
    WatchSession.objects.create(user=user_quynhanh, video=vid2, watched_seconds=45, is_unlocked=False)

    print("Thành công! Đã bơm toàn bộ dữ liệu mẫu vào Database.")

if __name__ == '__main__':
    run_seed()