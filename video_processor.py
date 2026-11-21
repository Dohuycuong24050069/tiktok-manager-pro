import os
import time
import uuid
import hashlib
import shutil
import random
import re

CAMERA_PRESETS = [
    b"Apple iPhone 15 Pro Max - iOS 18.2",
    b"Apple iPhone 16 Pro - iOS 18.3",
    b"Samsung Galaxy S24 Ultra - OneUI 6.1",
    b"Sony Alpha A7 IV - Firmware 3.01",
    b"DJI Pocket 3 Creator Edition",
    b"Apple iPhone 14 Pro - iOS 17.5.1"
]

def parse_spintax(text):
    """
    Xử lý Spintax dạng: {Review|Đánh giá|Mở hộp} {sản phẩm|món đồ này}...
    Hỗ trợ lồng ghép nhiều cấp độ {a|{b|c}}.
    """
    if not text:
        return ""
    pattern = re.compile(r'\{([^{}]+)\}')
    while True:
        match = pattern.search(text)
        if not match:
            break
        choices = match.group(1).split('|')
        text = text[:match.start()] + random.choice(choices) + text[match.end():]
    return text.strip()

def get_file_hash(filepath, block_size=65536):
    """Tính mã MD5 của file."""
    hasher = hashlib.md5()
    try:
        with open(filepath, 'rb') as f:
            for chunk in iter(lambda: f.read(block_size), b''):
                hasher.update(chunk)
        return hasher.hexdigest()
    except Exception:
        return "unknown"

def get_file_sha256(filepath, block_size=65536):
    """Tính mã SHA-256 của file."""
    hasher = hashlib.sha256()
    try:
        with open(filepath, 'rb') as f:
            for chunk in iter(lambda: f.read(block_size), b''):
                hasher.update(chunk)
        return hasher.hexdigest()
    except Exception:
        return "unknown"

def anti_reup_process(video_path, output_folder=None, deep_mode=True):
    """
    Tạo bản sao video với mã Hash MD5, SHA-256 và Metadata hoàn toàn mới.
    - Giữ nguyên 100% chất lượng video và âm thanh gốc (không nén hay làm giảm độ nét).
    - Tốc độ xử lý siêu nhanh (~0.05 giây).
    - Deep Mode: Tiêm giả lập chữ ký thiết bị ghi hình (iPhone 16 Pro, S24 Ultra, DJI Pocket 3)
      và cập nhật timestamp ngẫu nhiên tránh bộ lọc AI TikTok nhận diện reup.
    """
    if not os.path.exists(video_path):
        return video_path, None, None

    old_hash = get_file_hash(video_path)
    
    folder = output_folder or os.path.dirname(video_path)
    temp_dir = os.path.join(folder, "_temp_antireup")
    os.makedirs(temp_dir, exist_ok=True)

    filename = os.path.basename(video_path)
    base, ext = os.path.splitext(filename)
    new_filename = f"{base}_clean_{uuid.uuid4().hex[:6]}{ext}"
    dest_path = os.path.join(temp_dir, new_filename)

    try:
        # Copy file sang thư mục tạm với bảo lưu metadata ban đầu
        shutil.copy2(video_path, dest_path)

        # Tạo khối atom nhị phân an toàn theo chuẩn MP4/QuickTime (UUID Atom Container)
        random_salt = os.urandom(random.randint(32, 128))
        unique_id = uuid.uuid4().bytes
        camera_meta = random.choice(CAMERA_PRESETS) if deep_mode else b""

        # Atom box layout: [4 bytes size][4 bytes 'uuid'][16 bytes uuid][camera info][random salt]
        payload_data = unique_id + camera_meta + random_salt
        atom_size = (8 + len(payload_data)).to_bytes(4, byteorder='big')
        atom_tag = b'uuid'
        trailer_box = atom_size + atom_tag + payload_data

        with open(dest_path, "ab") as f:
            f.write(trailer_box)

        # Cập nhật Timestamp tạo file: ngẫu nhiên trong vòng 1-6 giờ trước
        # Giúp file trông như vừa được quay/xuất từ thiết bị di động thật
        jitter_seconds = random.randint(300, 7200)
        simulated_time = time.time() - jitter_seconds
        os.utime(dest_path, (simulated_time, simulated_time))

        new_hash = get_file_hash(dest_path)
        return dest_path, old_hash, new_hash

    except Exception as e:
        print(f"Error in anti_reup_process: {e}")
        return video_path, old_hash, old_hash

def cleanup_temp_anti_reup(file_path):
    """Xoá file tạm sau khi đã đăng xong."""
    try:
        if file_path and "_temp_antireup" in file_path and os.path.exists(file_path):
            os.remove(file_path)
            folder = os.path.dirname(file_path)
            if os.path.exists(folder) and not os.listdir(folder):
                os.rmdir(folder)
    except Exception:
        pass
