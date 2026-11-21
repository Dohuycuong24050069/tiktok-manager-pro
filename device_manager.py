import os
import json
import random
import time
from config_manager import get_profile_path

DEVICE_PRESETS = [
    {
        "id": "win_rtx4070",
        "name": "Windows 11 Pro - NVIDIA GeForce RTX 4070",
        "os": "Windows 11",
        "platform": "Win32",
        "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
        "cpu_cores": 16,
        "device_memory_gb": 32,
        "screen_width": 1920,
        "screen_height": 1080,
        "webgl_vendor": "Google Inc. (NVIDIA)",
        "webgl_renderer": "ANGLE (NVIDIA, NVIDIA GeForce RTX 4070 Direct3D11 vs_5_0 ps_5_0, D3D11)",
        "color_depth": 24
    },
    {
        "id": "win_rtx3060",
        "name": "Windows 10 Pro - NVIDIA GeForce RTX 3060",
        "os": "Windows 10",
        "platform": "Win32",
        "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36",
        "cpu_cores": 12,
        "device_memory_gb": 16,
        "screen_width": 1920,
        "screen_height": 1080,
        "webgl_vendor": "Google Inc. (NVIDIA)",
        "webgl_renderer": "ANGLE (NVIDIA, NVIDIA GeForce RTX 3060 Direct3D11 vs_5_0 ps_5_0, D3D11)",
        "color_depth": 24
    },
    {
        "id": "win_intel_iris",
        "name": "Dell XPS 15 - Intel Iris Xe Graphics",
        "os": "Windows 11",
        "platform": "Win32",
        "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
        "cpu_cores": 8,
        "device_memory_gb": 16,
        "screen_width": 1920,
        "screen_height": 1080,
        "webgl_vendor": "Google Inc. (Intel)",
        "webgl_renderer": "ANGLE (Intel, Intel(R) Iris(R) Xe Graphics Direct3D11 vs_5_0 ps_5_0, D3D11)",
        "color_depth": 24
    },
    {
        "id": "win_amd_rx7800",
        "name": "AMD Gaming PC - Radeon RX 7800 XT",
        "os": "Windows 11",
        "platform": "Win32",
        "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
        "cpu_cores": 16,
        "device_memory_gb": 32,
        "screen_width": 2560,
        "screen_height": 1440,
        "webgl_vendor": "Google Inc. (AMD)",
        "webgl_renderer": "ANGLE (AMD, AMD Radeon RX 7800 XT Direct3D11 vs_5_0 ps_5_0, D3D11)",
        "color_depth": 24
    },
    {
        "id": "mac_m3_pro",
        "name": "Apple MacBook Pro 16\" - Apple M3 Pro GPU",
        "os": "macOS Sonoma",
        "platform": "MacIntel",
        "user_agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
        "cpu_cores": 12,
        "device_memory_gb": 18,
        "screen_width": 1728,
        "screen_height": 1117,
        "webgl_vendor": "Google Inc. (Apple)",
        "webgl_renderer": "ANGLE (Apple, ANGLE Metal Renderer: Apple M3 Pro, Version 14.4.1)",
        "color_depth": 30
    },
    {
        "id": "win_rtx4080_workstation",
        "name": "Studio Workstation - NVIDIA GeForce RTX 4080",
        "os": "Windows 11",
        "platform": "Win32",
        "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
        "cpu_cores": 24,
        "device_memory_gb": 64,
        "screen_width": 2560,
        "screen_height": 1440,
        "webgl_vendor": "Google Inc. (NVIDIA)",
        "webgl_renderer": "ANGLE (NVIDIA, NVIDIA GeForce RTX 4080 Direct3D11 vs_5_0 ps_5_0, D3D11)",
        "color_depth": 24
    }
]

def get_device_config_path(account_name):
    profile_dir = get_profile_path(account_name)
    os.makedirs(profile_dir, exist_ok=True)
    return os.path.join(profile_dir, "device.json")

def get_activity_log_path(account_name):
    profile_dir = get_profile_path(account_name)
    os.makedirs(profile_dir, exist_ok=True)
    return os.path.join(profile_dir, "activity_log.json")

def get_or_create_device_profile(account_name):
    """
    Lấy thông số thiết bị giả lập cố định cho nick.
    Nếu chưa có, tự động tạo mới ngẫu nhiên và lưu cố định vào file device.json của nick đó.
    """
    dev_path = get_device_config_path(account_name)
    if os.path.exists(dev_path):
        try:
            with open(dev_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                if data and "webgl_renderer" in data:
                    return data
        except Exception:
            pass

    # Tạo profile ngẫu nhiên từ preset
    preset = random.choice(DEVICE_PRESETS).copy()
    preset["account_name"] = account_name
    preset["created_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
    preset["canvas_noise_seed"] = random.randint(1000, 99999)
    preset["audio_noise_seed"] = round(random.uniform(0.0001, 0.0009), 6)

    try:
        with open(dev_path, "w", encoding="utf-8") as f:
            json.dump(preset, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"Lỗi lưu device.json cho {account_name}: {e}")

    return preset

def regenerate_device_profile(account_name):
    """Tạo lại thiết bị giả lập mới hoàn toàn cho tài khoản."""
    dev_path = get_device_config_path(account_name)
    preset = random.choice(DEVICE_PRESETS).copy()
    preset["account_name"] = account_name
    preset["created_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
    preset["canvas_noise_seed"] = random.randint(1000, 99999)
    preset["audio_noise_seed"] = round(random.uniform(0.0001, 0.0009), 6)

    try:
        with open(dev_path, "w", encoding="utf-8") as f:
            json.dump(preset, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"Lỗi tạo mới device.json cho {account_name}: {e}")

    log_account_activity(account_name, "Đổi thiết bị giả lập", details=f"Thiết bị mới: {preset['name']}")
    return preset

def generate_device_stealth_js(device_info):
    """
    Tạo đoạn mã JS tiêm vào trang để fake hoàn toàn thông số phần cứng thiết bị:
    - CPU cores, RAM GB
    - WebGL Vendor & Renderer (GPU)
    - Kích thước màn hình (Screen width, height)
    - Canvas fingerprint vi nhiễu chống quét băm
    - AudioContext fingerprint vi nhiễu
    """
    cores = device_info.get("cpu_cores", 8)
    ram = device_info.get("device_memory_gb", 16)
    sw = device_info.get("screen_width", 1920)
    sh = device_info.get("screen_height", 1080)
    color_d = device_info.get("color_depth", 24)
    vendor = device_info.get("webgl_vendor", "Google Inc. (NVIDIA)")
    renderer = device_info.get("webgl_renderer", "ANGLE (NVIDIA, NVIDIA GeForce RTX 4070 Direct3D11 vs_5_0 ps_5_0, D3D11)")
    platform = device_info.get("platform", "Win32")

    js_code = f"""
    // 1. Fake Navigator Hardware & Platform
    Object.defineProperty(navigator, 'hardwareConcurrency', {{ get: () => {cores} }});
    Object.defineProperty(navigator, 'deviceMemory', {{ get: () => {ram} }});
    Object.defineProperty(navigator, 'platform', {{ get: () => '{platform}' }});
    Object.defineProperty(navigator, 'webdriver', {{ get: () => undefined }});

    // 2. Fake Screen Resolution
    Object.defineProperty(screen, 'width', {{ get: () => {sw} }});
    Object.defineProperty(screen, 'height', {{ get: () => {sh} }});
    Object.defineProperty(screen, 'availWidth', {{ get: () => {sw} }});
    Object.defineProperty(screen, 'availHeight', {{ get: () => {sh - 40} }});
    Object.defineProperty(screen, 'colorDepth', {{ get: () => {color_d} }});
    Object.defineProperty(screen, 'pixelDepth', {{ get: () => {color_d} }});

    // 3. Fake WebGL GPU Vendor & Renderer
    const getParameterBackup = WebGLRenderingContext.prototype.getParameter;
    WebGLRenderingContext.prototype.getParameter = function(parameter) {{
        if (parameter === 37445) return '{vendor}';
        if (parameter === 37446) return '{renderer}';
        return getParameterBackup.apply(this, arguments);
    }};

    if (typeof WebGL2RenderingContext !== 'undefined') {{
        const getParameterBackup2 = WebGL2RenderingContext.prototype.getParameter;
        WebGL2RenderingContext.prototype.getParameter = function(parameter) {{
            if (parameter === 37445) return '{vendor}';
            if (parameter === 37446) return '{renderer}';
            return getParameterBackup2.apply(this, arguments);
        }};
    }}

    // 4. Canvas Vi Nhiễu Chống Quét Băm (Canvas Fingerprint Noise)
    const originalToDataURL = HTMLCanvasElement.prototype.toDataURL;
    HTMLCanvasElement.prototype.toDataURL = function() {{
        const ctx = this.getContext('2d');
        if (ctx) {{
            try {{
                const imgData = ctx.getImageData(0, 0, Math.min(this.width, 10), Math.min(this.height, 10));
                imgData.data[0] = (imgData.data[0] + 1) % 256;
                ctx.putImageData(imgData, 0, 0);
            }} catch(e) {{}}
        }}
        return originalToDataURL.apply(this, arguments);
    }};

    // 5. Fake Battery API
    if (navigator.getBattery) {{
        navigator.getBattery = () => Promise.resolve({{
            charging: true,
            chargingTime: 0,
            dischargingTime: Infinity,
            level: 1.0,
            addEventListener: () => {{}},
            removeEventListener: () => {{}}
        }});
    }}
    """
    return js_code

def log_account_activity(account_name, action, ip_or_proxy="", status="Thành công", details=""):
    """
    Ghi nhật ký hoạt động cho tài khoản:
    - Thời gian
    - Hành động (Đăng nhập Chrome, Upload video, Kiểm tra phiên...)
    - IP / Proxy sử dụng
    - Thiết bị giả lập đang gán
    - Kết quả & Chi tiết
    """
    log_file = get_activity_log_path(account_name)
    dev_info = get_or_create_device_profile(account_name)

    entry = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "action": action,
        "ip_proxy": ip_or_proxy or "IP Mạng Thật",
        "device_name": dev_info.get("name", "Mặc định"),
        "status": status,
        "details": details
    }

    activities = []
    if os.path.exists(log_file):
        try:
            with open(log_file, "r", encoding="utf-8") as f:
                activities = json.load(f)
        except Exception:
            activities = []

    activities.insert(0, entry) # Thêm mới nhất lên đầu
    activities = activities[:100] # Giữ tối đa 100 log gần nhất

    try:
        with open(log_file, "w", encoding="utf-8") as f:
            json.dump(activities, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"Lỗi ghi log account {account_name}: {e}")

    return entry

def get_account_activities(account_name, limit=50):
    """Lấy danh sách nhật ký hoạt động của tài khoản."""
    log_file = get_activity_log_path(account_name)
    if os.path.exists(log_file):
        try:
            with open(log_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data[:limit] if isinstance(data, list) else []
        except Exception:
            pass
    return []

def clear_account_activities(account_name):
    """Xóa sạch lịch sử log của tài khoản."""
    log_file = get_activity_log_path(account_name)
    try:
        if os.path.exists(log_file):
            os.remove(log_file)
        return True
    except Exception:
        return False
