import os
import json

CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")
PROFILES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "profiles")

DEFAULT_CONFIG = {
    "accounts": [],
    "account_proxies": {},  # {acc_name: "ip:port:user:pass"}
    "video_folder": "",
    "caption_mode": "filename",  # "filename", "txt_file", "custom"
    "dist_mode": "round_robin",  # "round_robin", "all_to_all"
    "custom_caption": "",
    "hashtags": "#fyp #xuhuong #trending",
    "delay_seconds": 30,
    "headless": False,
    "auto_move_done": True,
    "anti_reup_enabled": True,  # Lách bản quyền đổi mã Hash MD5
    "schedule_mode": False,     # Lên lịch hẹn giờ đăng
    "privacy": "public"         # "public", "friends", "private"
}

def load_config():
    if not os.path.exists(PROFILES_DIR):
        os.makedirs(PROFILES_DIR, exist_ok=True)
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                config = DEFAULT_CONFIG.copy()
                config.update(data)
                return config
        except Exception:
            return DEFAULT_CONFIG.copy()
    return DEFAULT_CONFIG.copy()

def save_config(config):
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"Error saving config: {e}")

def get_profile_path(account_name):
    clean_name = "".join([c for c in account_name if c.isalnum() or c in ('_', '-')]).strip()
    return os.path.join(PROFILES_DIR, clean_name)

def parse_proxy(proxy_str):
    if not proxy_str or not proxy_str.strip():
        return None
    
    proxy_str = proxy_str.strip()
    scheme = "http"
    if "://" in proxy_str:
        scheme, rest = proxy_str.split("://", 1)
    else:
        rest = proxy_str

    if "@" in rest:
        auth, host = rest.split("@", 1)
        user, pwd = auth.split(":", 1) if ":" in auth else (auth, "")
        return {
            "server": f"{scheme}://{host}",
            "username": user,
            "password": pwd
        }

    parts = rest.split(":")
    if len(parts) == 2:
        ip, port = parts
        return {"server": f"{scheme}://{ip}:{port}"}
    elif len(parts) == 4:
        ip, port, user, pwd = parts
        return {
            "server": f"{scheme}://{ip}:{port}",
            "username": user,
            "password": pwd
        }
    
    return {"server": proxy_str}
