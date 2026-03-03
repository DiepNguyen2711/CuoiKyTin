import os
import django
import pandas as pd

# 1. Setup môi trường Django để script có thể gọi Models
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings') # Thay 'core' bằng tên folder chứa settings.py của bạn
django.setup()

from hourskill_app.models import Category, Video, Course, User

def run_seed():
    # Thay 'data.xlsx' bằng tên file Excel của nhóm
    file_path = 'data.xlsx' 
    
    print("🚀 Bắt đầu đọc dữ liệu từ Excel...")

    # --- NHẬP CATEGORY ---
    df_category = pd.read_excel(file_path, sheet_name='CATEGORY')
    for index, row in df_category.iterrows():
        cat, created = Category.objects.get_or_create(
            name=row['name'],
            defaults={'description': str(row['description'])}
        )
        if created:
            print(f"✅ Đã tạo danh mục: {cat.name}")

    # --- NHẬP VIDEO ---
    df_video = pd.read_excel(file_path, sheet_name='VIDEO')
    for index, row in df_video.iterrows():
        try:
            category = Category.objects.get(name=row['category'])
            creator = User.objects.get(username=row['creator'])
            
            video, created = Video.objects.get_or_create(
                title=row['title'],
                defaults={
                    'description': str(row['description']),
                    'category': category,
                    'creator': creator,
                    'duration_seconds': int(row['duration_seconds']),
                    'price_tc': float(row['price_tc']),
                    'file_url': f"videos/{row['file_url']}", 
                    'thumbnail': f"thumbnails/{row['thumbnail']}" if pd.notna(row['thumbnail']) else None,
                }
            )
            if created:
                print(f"✅ Đã thêm video: {video.title}")
        except Exception as e:
            print(f"❌ Lỗi ở video '{row['title']}': {e}")

    print("🎉 Hoàn tất nạp dữ liệu!")

if __name__ == '__main__':
    run_seed()