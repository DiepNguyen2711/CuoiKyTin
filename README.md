# CuoiKyTin
# HourSkill Project 🚀

Chào mừng đến với kho lưu trữ mã nguồn của dự án **HourSkill** - Nền tảng kết nối người dạy và người học.

Tài liệu này hướng dẫn chi tiết cách thiết lập môi trường và quy trình làm việc chuẩn dành cho tất cả thành viên trong nhóm. **Vui lòng đọc kỹ trước khi bắt đầu code!**

---

## 🛠 1. Yêu cầu phần mềm (Prerequisites)
Trước khi bắt đầu, đảm bảo máy tính của bạn đã cài đặt:
* **Python** (phiên bản 3.x trở lên).
* **Git** và **GitHub Desktop** (tùy chọn nhưng khuyên dùng).
* **VS Code** (hoặc trình soạn thảo code tương đương).

---

## ⚙️ 2. Hướng dẫn cài đặt lần đầu (Setup)
*Lưu ý: Bạn chỉ cần thực hiện quy trình này MỘT LẦN DUY NHẤT khi mới tham gia dự án hoặc đổi máy tính.*

**Bước 1: Tải code về máy (Clone)**
Mở Terminal trong thư mục bạn muốn lưu dự án và chạy:
`git clone <đường-link-github-của-repo>`
`cd CuoiKyTin`

**Bước 2: Tạo và kích hoạt Môi trường ảo (Virtual Environment)**
Đây là bước bắt buộc để không làm rác máy tính.
* Tạo môi trường: 
  `python -m venv venv`
* Kích hoạt môi trường:
  * Trên Windows: `venv\Scripts\activate`
  * Trên Mac/Linux: `source venv/bin/activate`
*(Lưu ý: Nếu thấy chữ `(venv)` xuất hiện ở đầu dòng Terminal là thành công).*

**Bước 3: Cài đặt thư viện**
Cài đặt chính xác các phiên bản thư viện mà dự án đang dùng:
`pip install -r requirements.txt`

**Bước 4: Thiết lập Cơ sở dữ liệu (Database)**
Tạo các bảng dữ liệu mặc định của Django:
`python manage.py migrate`

*(Tùy chọn) Chạy file dữ liệu mẫu để có sẵn tài khoản test:*
`python seed.py`

**Bước 5: Chạy thử Server**
Khởi động website ở môi trường local:
`python manage.py runserver`
Mở trình duyệt và truy cập: `http://127.0.0.1:8000/`. Nếu không hiện lỗi đỏ là bạn đã setup thành công!

---

## 🔄 3. Quy trình làm việc hàng ngày (Daily Workflow)
Để tránh giẫm chân lên code của nhau, mọi người TUYỆT ĐỐI tuân thủ 5 bước sau mỗi khi làm một chức năng mới:

* **Bước 1 - Cập nhật code mới nhất:** Mở Terminal, đảm bảo bạn đang ở nhánh `main`, chạy lệnh `git pull origin main` để lấy code mới nhất từ Leader về.
* **Bước 2 - Tạo nhánh mới:** KHÔNG code trên nhánh `main`. Hãy tạo nhánh theo cú pháp: `feature/<tên-chức-năng>`. Ví dụ: `git checkout -b feature/giao-dien-dang-nhap`.
* **Bước 3 - Viết code:** Thoải mái sáng tạo phần việc của bạn trên nhánh này.
* **Bước 4 - Lưu và Đẩy code:** Khi xong việc, commit code và đẩy nhánh này lên GitHub (`git push origin feature/giao-dien-dang-nhap`).
* **Bước 5 - Tạo Pull Request (PR):** Lên trang GitHub, tạo một Pull Request để yêu cầu gộp nhánh của bạn vào `main`. Nhắn tin cho Leader (Diệp) vào kiểm tra và duyệt code.

---

## ⚠️ 4. Quy tắc Bắt Buộc (Strict Rules)
1. **Cấm Push thẳng lên Main:** Nhánh `main` đã được khóa bảo vệ. Mọi thay đổi phải thông qua Pull Request.
2. **Luôn bật venv:** Đảm bảo Terminal luôn có chữ `(venv)` trước khi chạy lệnh `pip install` hoặc `python manage.py`.
3. **Lỗi lạ? Xóa DB làm lại:** Nếu database bị lỗi không cứu được, hãy xóa file `db.sqlite3` đi và chạy lại lệnh `migrate` + `seed.py`.
