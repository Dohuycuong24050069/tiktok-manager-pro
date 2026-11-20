import os
import json
import csv
import time

HISTORY_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "history.json")

def load_history():
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []
    return []

def add_history_record(account, video_name, caption, status, proxy="", mode="Đăng ngay"):
    history = load_history()
    record = {
        "id": int(time.time() * 1000),
        "time": time.strftime("%Y-%m-%d %H:%M:%S"),
        "account": account,
        "video": video_name,
        "caption": caption[:100] + "..." if len(caption) > 100 else caption,
        "status": status,
        "proxy": proxy if proxy else "IP Gốc",
        "mode": mode
    }
    history.insert(0, record)
    if len(history) > 1000:
        history = history[:1000]

    try:
        with open(HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(history, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"Error saving history: {e}")

def is_video_uploaded_to_account(account_name, video_filename):
    """Kiểm tra xem video này đã từng đăng thành công lên tài khoản này hay chưa."""
    history = load_history()
    for rec in history:
        if (rec.get("account") == account_name and 
            rec.get("video") == video_filename and 
            ("Thành công" in rec.get("status", "") or "Đã gửi lệnh" in rec.get("status", ""))):
            return True
    return False

def clear_all_history():
    try:
        with open(HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump([], f, ensure_ascii=False, indent=2)
        return True
    except Exception:
        return False

def export_history_to_csv(export_path):
    history = load_history()
    try:
        with open(export_path, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.writer(f)
            writer.writerow(["Thời gian", "Tài khoản TikTok", "Tên Video", "Trạng thái", "Proxy", "Chế độ", "Tiêu đề (Caption)"])
            for h in history:
                writer.writerow([
                    h.get("time", ""),
                    h.get("account", ""),
                    h.get("video", ""),
                    h.get("status", ""),
                    h.get("proxy", ""),
                    h.get("mode", ""),
                    h.get("caption", "")
                ])
        return True, f"Đã xuất {len(history)} dòng ra file CSV!"
    except Exception as e:
        return False, str(e)
