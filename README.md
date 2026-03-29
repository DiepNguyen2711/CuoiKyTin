# HourSkills - Huong Dan Su Dung Nhanh

Tai lieu nay danh cho nguoi dung muon tai source ve va chay thu nen tang HourSkills tren may ca nhan.

## 1. HourSkills La Gi?
HourSkills la nen tang hoc online co:
- Khoa hoc va video.
- Mo khoa video theo TC.
- Kenh giao vien cong khai.
- Trang ca nhan rieng tu.
- Goi VIP (xem theo chinh sach VIP hien tai).

## 2. Yeu Cau He Thong
Can cai san:
- Python 3.x
- pip
- Node.js (de chay static frontend server)
- Git

Khuyen nghi: dung virtual environment (venv) cho Python.

## 3. Tai Va Chay Du An (Local)

### Buoc 1: Clone
```bash
git clone <link-github-cua-repo>
cd CuoiKyTin
```

### Buoc 2: Tao va kich hoat venv
```bash
python -m venv venv
```

Windows:
```bash
venv\Scripts\activate
```

Mac/Linux:
```bash
source venv/bin/activate
```

### Buoc 3: Cai thu vien backend
```bash
pip install -r requirements.txt
```

### Buoc 4: Tao file .env
Tao file `.env` trong thu muc goc voi toi thieu:
```env
SECRET_KEY=your_secret_key_here
DEBUG=true
ALLOWED_HOSTS=127.0.0.1,localhost
CSRF_TRUSTED_ORIGINS=http://localhost:3000,http://127.0.0.1:3000
STORAGE_BACKEND=local
```

### Buoc 5: Khoi tao database
```bash
python manage.py migrate
```

### Buoc 6: Nap du lieu mau (khuyen nghi)
```bash
python seed.py
```

### Buoc 7: Chay backend
```bash
python manage.py runserver
```

Backend mac dinh: http://127.0.0.1:8000

### Buoc 8: Chay frontend
```bash
cd frontend
npm install
node server.js
```

Frontend mac dinh: http://localhost:3000

Luu y: frontend goi API ve backend 127.0.0.1:8000, vi vay can chay ca 2 phia.

## 4. Cach Truy Cap Nhanh Sau Khi Chay
- Trang chu: http://localhost:3000/main.html
- Khoa hoc: http://localhost:3000/courses.html
- Giao vien: http://localhost:3000/teachers.html
- Trang ca nhan: http://localhost:3000/profile.html

## 5. Tai Khoan Test
Neu ban da chay `python seed.py`, he thong tao creator mau mac dinh:
- username: `Diep`
- password: `123`

Co the doi bang bien moi truong truoc khi seed:
- `SEED_OWNER_USERNAME`
- `SEED_OWNER_EMAIL`
- `SEED_OWNER_PASSWORD`

## 6. Cac Luu Y Quan Trong Khi Su Dung
- `profile.html` la trang ca nhan rieng tu.
- `channel.html?id=<user_id>` la kenh cong khai.
- Video bi khoa thi can mo khoa bang TC (tru owner/VIP/video free).
- Neu sua code ma giao dien khong doi: hard reload (Ctrl+F5).

## 7. Su Co Thuong Gap

### Loi SECRET_KEY
Kiem tra lai file `.env` co dong `SECRET_KEY=...` va khong rong.

### Khong tai duoc API tu frontend
Dam bao backend dang chay o `127.0.0.1:8000`.

### DB loi sau khi cap nhat code
Chay lai migrate:
```bash
python manage.py migrate
```

### Anh/video khong hien thi
Neu chay local, dam bao `STORAGE_BACKEND=local` trong `.env`.

## 8. Tuy Chon Chay Bang Docker (Nang Cao)
Du an co `docker-compose.yml` cho mo hinh web + postgres.
Neu ban muon chay bang Docker, can cau hinh `.env` phu hop truoc khi up.

---

Neu ban chi can trai nghiem nen tang nhanh, chi can lam dung Muc 3 va Muc 4 la du.
