# 🚀 TikTok Manager Pro

> Ứng dụng Desktop quản lý đa tài khoản TikTok, tự động đăng video hàng loạt từ thư mục, hỗ trợ Proxy riêng cho từng tài khoản, lách bản quyền Anti-Reup (đổi mã Hash MD5), lên lịch đăng khung giờ vàng và chống trùng lặp video tuyệt đối.

---

## 🌟 Tính Năng Nổi Bật

- **Quản lý đa tài khoản độc lập:** Mỗi nick chạy trên 1 Persistent Chrome Profile riêng biệt, lưu phiên đăng nhập vĩnh viễn, tránh checkpoint/quét bot.
- **Hỗ trợ Proxy riêng từng nick:** Gán Proxy IP riêng (HTTP/SOCKS5 có User/Pass) cho từng nick kèm công cụ kiểm tra trạng thái IP trực tiếp trong app.
- **Lách bản quyền siêu tốc (Anti-Reup MD5):** Tự động đổi mã băm MD5 và metadata nhị phân mà không làm giảm 1% chất lượng video hay âm thanh.
- **Chống trùng lặp 3 lớp:**
  1. Tự động chuyển video đã đăng xong vào thư mục `_done/`.
  2. Đối chiếu cơ sở dữ liệu lịch sử (`history.json`) của từng nick để bỏ qua nếu đã từng đăng.
  3. Đổi hash độc lập khi đăng đa kênh vệ tinh.
- **2 Chế độ phân phối video:** Chia đều video cho các kênh hoặc đăng đồng loạt mọi kênh.
- **Lên lịch đăng (Schedule Post):** Hẹn giờ đăng theo khung giờ vàng nhiều view trên TikTok Studio.
- **Báo cáo lịch sử & Xuất CSV:** Xem toàn bộ lịch sử đăng và xuất file Excel/CSV theo dõi doanh thu.
- **Giao diện hiện đại (CustomTkinter Dark Mode):** Có nhật ký trực tiếp (Live Logs), phím Dừng khẩn cấp và chuông báo khi hoàn thành.

---

## 🛠️ Cài Đặt & Sử Dụng

### 1. Yêu cầu hệ thống
- Windows 10/11
- Python 3.10+
- Google Chrome

### 2. Cài đặt thư viện
```bash
pip install -r requirements.txt
playwright install chromium
```

### 3. Khởi động ứng dụng
Chạy trực tiếp file `run_app.bat` hoặc lệnh:
```bash
python app_gui.py
```
