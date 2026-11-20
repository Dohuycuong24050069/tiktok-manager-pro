import os
import time
import uuid
import hashlib
import shutil

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

def anti_reup_process(video_path, output_folder=None):
    """
    Tạo một bản sao video với mã Hash MD5 và Metadata hoàn toàn mới.
    - Giữ nguyên 100% chất lượng video và âm thanh gốc (không nén hay làm giảm độ nét).
    - Tốc độ xử lý siêu nhanh (chỉ mất ~0.1 giây).
    - Tránh bị bộ lọc TikTok quét trùng mã file với các video đã có trên mạng.
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
        # Copy file sang thư mục tạm
        shutil.copy2(video_path, dest_path)

        # Chèn thêm một khối metadata nhị phân ngẫu nhiên (safe trailer box)
        # Giúp thay đổi mã băm SHA256/MD5 100% mà không ảnh hưởng tới khả năng phát video
        random_salt = os.urandom(32)
        unique_id = uuid.uuid4().bytes
        # MP4 custom atom container header (tag: 'uuid')
        atom_size = (16 + len(random_salt) + len(unique_id)).to_bytes(4, byteorder='big')
        atom_tag = b'uuid'
        trailer_payload = atom_size + atom_tag + unique_id + random_salt

        with open(dest_path, "ab") as f:
            f.write(trailer_payload)

        # Thay đổi timestamp tạo file thành thời điểm hiện tại
        now = time.time()
        os.utime(dest_path, (now, now))

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
            # Thử xoá folder nếu rỗng
            folder = os.path.dirname(file_path)
            if os.path.exists(folder) and not os.listdir(folder):
                os.rmdir(folder)
    except Exception:
        pass
