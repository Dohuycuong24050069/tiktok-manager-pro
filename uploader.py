import os
import time
import shutil
import re
import requests
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
from config_manager import get_profile_path, parse_proxy
from video_processor import anti_reup_process, cleanup_temp_anti_reup
from history_manager import add_history_record
from device_manager import (
    get_or_create_device_profile,
    generate_device_stealth_js,
    log_account_activity
)

STEALTH_JS = """
// Ẩn hoàn toàn dấu vết tự động hóa
Object.defineProperty(navigator, 'webdriver', {
    get: () => undefined
});
Object.defineProperty(navigator, 'plugins', {
    get: () => [
        { name: 'Chrome PDF Plugin', filename: 'internal-pdf-viewer' },
        { name: 'Chrome PDF Viewer', filename: 'mhjfbmdgcfjbbpaeojofohoefgiehjai' },
        { name: 'Native Client', filename: 'internal-nacl-plugin' }
    ]
});
Object.defineProperty(navigator, 'languages', {
    get: () => ['vi-VN', 'vi', 'en-US', 'en']
});
window.chrome = {
    runtime: {},
    loadTimes: function() {},
    csi: function() {},
    app: {}
};
const originalQuery = window.navigator.permissions.query;
window.navigator.permissions.query = (parameters) => (
    parameters.name === 'notifications' ?
        Promise.resolve({ state: Notification.permission }) :
        originalQuery(parameters)
);
"""

def sanitize_caption(text):
    if not text:
        return ""
    return re.sub(r'\s+', ' ', text).strip()

def check_proxy_alive(proxy_str):
    """Kiểm tra xem proxy có hoạt động không và lấy địa chỉ IP thực tế qua proxy."""
    if not proxy_str or not proxy_str.strip():
        return False, "Chưa nhập thông tin proxy"
    try:
        p_cfg = parse_proxy(proxy_str)
        if not p_cfg:
            return False, "Định dạng proxy không hợp lệ"
        
        server = p_cfg["server"]
        user = p_cfg.get("username")
        pwd = p_cfg.get("password")
        
        if user and pwd:
            scheme, netloc = server.split("://", 1)
            proxy_url = f"{scheme}://{user}:{pwd}@{netloc}"
        else:
            proxy_url = server
            
        proxies = {"http": proxy_url, "https": proxy_url}
        resp = requests.get("https://api.ipify.org?format=json", proxies=proxies, timeout=12)
        if resp.status_code == 200:
            ip = resp.json().get("ip")
            return True, f"Proxy Hoạt Động! IP Ngoại: {ip}"
        return False, f"Không kết nối được, mã phản hồi: {resp.status_code}"
    except Exception as e:
        return False, f"Lỗi kết nối proxy: {str(e)}"

class TikTokUploader:
    def __init__(self, log_callback=None):
        self.log_cb = log_callback or print

    def log(self, message, level="INFO"):
        prefix = f"[{time.strftime('%H:%M:%S')}] [{level}] "
        self.log_cb(prefix + message)

    def check_login_status(self, account_name, proxy_str=None):
        """Kiểm tra nhanh xem tài khoản còn phiên đăng nhập hợp lệ không."""
        profile_path = get_profile_path(account_name)
        if not os.path.exists(profile_path):
            return False, "Chưa tạo Profile"

        dev_info = get_or_create_device_profile(account_name)
        playwright_proxy = parse_proxy(proxy_str)
        try:
            with sync_playwright() as p:
                context = p.chromium.launch_persistent_context(
                    user_data_dir=profile_path,
                    proxy=playwright_proxy,
                    headless=True,
                    channel="chrome",
                    user_agent=dev_info.get("user_agent"),
                    args=["--disable-blink-features=AutomationControlled", "--no-sandbox"],
                    locale="vi-VN"
                )
                page = context.pages[0] if context.pages else context.new_page()
                page.add_init_script(STEALTH_JS + generate_device_stealth_js(dev_info))
                page.goto("https://www.tiktok.com/tiktokstudio/upload", timeout=30000)
                page.wait_for_load_state("domcontentloaded")
                time.sleep(2)
                url = page.url.lower()
                context.close()
                if "login" in url:
                    log_account_activity(account_name, "Kiểm tra phiên", ip_or_proxy=proxy_str, status="Hết phiên", details="Cần đăng nhập lại Chrome")
                    return False, "Hết phiên / Chưa đăng nhập"
                log_account_activity(account_name, "Kiểm tra phiên", ip_or_proxy=proxy_str, status="Sống 100%", details="Phiên TikTok Studio hoạt động tốt")
                return True, "Đang đăng nhập (Sống 100%)"
        except Exception as e:
            log_account_activity(account_name, "Kiểm tra phiên", ip_or_proxy=proxy_str, status="Lỗi", details=str(e)[:50])
            return False, f"Lỗi kiểm tra: {str(e)[:40]}"

    def launch_login_browser(self, account_name, proxy_str=None):
        """Mở trình duyệt Chrome với profile và proxy riêng để đăng nhập nick TikTok."""
        profile_path = get_profile_path(account_name)
        os.makedirs(profile_path, exist_ok=True)
        dev_info = get_or_create_device_profile(account_name)

        self.log(f"Đang mở Chrome cho nick: '{account_name}'...", "INFO")
        self.log(f"📱 Thiết bị giả lập: {dev_info.get('name')}", "INFO")
        self.log(f"Thư mục Profile: {profile_path}", "INFO")

        playwright_proxy = parse_proxy(proxy_str)
        if playwright_proxy:
            self.log(f"[{account_name}] Đang sử dụng Proxy: {playwright_proxy.get('server')}", "INFO")

        log_account_activity(
            account_name, 
            "Mở Chrome đăng nhập", 
            ip_or_proxy=proxy_str or "IP Mạng Thật", 
            status="Đang mở", 
            details=f"Thiết bị: {dev_info.get('name')}"
        )

        with sync_playwright() as p:
            try:
                context = p.chromium.launch_persistent_context(
                    user_data_dir=profile_path,
                    proxy=playwright_proxy,
                    headless=False,
                    channel="chrome",
                    user_agent=dev_info.get("user_agent"),
                    args=[
                        "--disable-blink-features=AutomationControlled",
                        "--no-sandbox",
                        "--disable-infobars",
                        "--start-maximized"
                    ],
                    viewport=None,
                    locale="vi-VN"
                )
                page = context.pages[0] if context.pages else context.new_page()
                page.add_init_script(STEALTH_JS + generate_device_stealth_js(dev_info))

                self.log("Đang mở trang Đăng Nhập TikTok (Chuẩn Web Chính)...", "INFO")
                page.goto("https://www.tiktok.com/login", timeout=60000)

                self.log("Trình duyệt đã mở sẵn sàng!", "SUCCESS")
                self.log(">>> Vui lòng đăng nhập tài khoản TikTok trên cửa sổ Chrome vừa mở.", "SUCCESS")
                self.log(">>> Đăng nhập xong, bạn hãy ĐÓNG cửa sổ trình duyệt lại để lưu phiên.", "INFO")

                while len(context.pages) > 0:
                    time.sleep(1)
                context.close()
                log_account_activity(account_name, "Đóng Chrome", ip_or_proxy=proxy_str or "IP Mạng Thật", status="Thành công", details="Đã lưu phiên Profile")
                self.log(f"Đã lưu thành công phiên đăng nhập cho nick: '{account_name}'.", "SUCCESS")
                return True
            except Exception as e:
                log_account_activity(account_name, "Lỗi mở Chrome", ip_or_proxy=proxy_str or "IP Mạng Thật", status="Lỗi", details=str(e)[:50])
                self.log(f"Lỗi khi mở trình duyệt: {str(e)}", "ERROR")
                return False

    def dismiss_popups(self, page, target_scope):
        """Tự động đóng tất cả các loại popup/thông báo cản trở của TikTok Studio."""
        popup_selectors = [
            'button:has-text("Got it")',
            'button:has-text("Đã hiểu")',
            'button:has-text("Not now")',
            'button:has-text("Để sau")',
            'button:has-text("OK")',
            'button:has-text("Bỏ qua")',
            'button:has-text("Skip")',
            'button:has-text("Tiếp tục đăng")',
            'button:has-text("Post anyway")',
            'div[aria-label="Close"]',
            'button[aria-label="Close"]',
            '.close-btn',
            'svg.close-icon'
        ]
        for sel in popup_selectors:
            try:
                btn = target_scope.locator(sel).first
                if btn.count() > 0 and btn.is_visible():
                    btn.click(timeout=1000)
                    time.sleep(0.4)
            except Exception:
                pass

    def apply_advanced_settings(self, scope, privacy="public", allow_comment=True, 
                                allow_duet=True, allow_stitch=True, ai_content=False):
        """Áp dụng các cấu hình nâng cao: Quyền riêng tư, Tương tác, Gán nhãn AI 2026."""
        # 1. Tùy chỉnh Quyền riêng tư (Privacy)
        try:
            if privacy in ["friends", "private"]:
                privacy_dropdown = scope.locator('div[role="combobox"]:has-text("Public"), div:has-text("Who can watch this video")').first
                if privacy_dropdown.count() > 0:
                    privacy_dropdown.click()
                    time.sleep(0.5)
                    target_txt = "Friends" if privacy == "friends" else "Private"
                    opt = scope.locator(f'div[role="option"]:has-text("{target_txt}"), li:has-text("{target_txt}")').first
                    if opt.count() > 0:
                        opt.click()
                        self.log(f"Đã đặt quyền riêng tư: {privacy.upper()}", "INFO")
        except Exception:
            pass

        # 2. Cài đặt Tương tác (Allow Comments, Duet, Stitch)
        try:
            interaction_configs = [
                ("Comment", allow_comment),
                ("Duet", allow_duet),
                ("Stitch", allow_stitch)
            ]
            for name, enabled in interaction_configs:
                checkbox = scope.locator(f'input[type="checkbox"][name*="{name.lower()}"], div:has-text("{name}") input[type="checkbox"]').first
                if checkbox.count() > 0:
                    is_checked = checkbox.is_checked()
                    if enabled and not is_checked:
                        checkbox.click()
                    elif not enabled and is_checked:
                        checkbox.click()
        except Exception:
            pass

        # 3. Gán nhãn nội dung AI (AI-Generated content)
        if ai_content:
            try:
                ai_switch = scope.locator('input[type="checkbox"][name*="ai"], div:has-text("AI-generated content") input, div:has-text("Nội dung do AI tạo") input').first
                if ai_switch.count() > 0 and not ai_switch.is_checked():
                    ai_switch.click()
                    self.log("Đã bật nhãn 'Nội dung do AI tạo' theo chính sách TikTok 2026.", "INFO")
            except Exception:
                pass

    def upload_video(self, account_name, video_path, caption="", hashtags="", headless=False, 
                     proxy_str=None, anti_reup=True, deep_anti_reup=True, schedule_minutes=0,
                     privacy="public", allow_comment=True, allow_duet=True, allow_stitch=True,
                     ai_content=False):
        """
        Tự động đăng một video lên TikTok Studio với đầy đủ tính năng:
        - Lách bản quyền đổi mã Hash MD5 & EXIF Camera giả lập
        - Hẹn giờ lên lịch đăng linh hoạt
        - Gán nhãn nội dung AI chuẩn TikTok 2026
        - Cài đặt quyền riêng tư & tương tác
        - Proxy độc lập cho từng nick
        """
        profile_path = get_profile_path(account_name)
        if not os.path.exists(video_path):
            self.log(f"File video không tồn tại: {video_path}", "ERROR")
            add_history_record(account_name, os.path.basename(video_path), caption, "Thất bại (Không tìm thấy file)", proxy_str)
            return False

        original_file_name = os.path.basename(video_path)
        actual_upload_path = video_path
        is_temp_file = False

        # 1. Xử lý Lách bản quyền Anti-Reup
        if anti_reup:
            self.log(f"[{account_name}] 🛡️ Đang xử lý lách bản quyền & đổi MD5/Metadata...", "INFO")
            clean_path, old_h, new_h = anti_reup_process(video_path, deep_mode=deep_anti_reup)
            if clean_path != video_path:
                actual_upload_path = clean_path
                is_temp_file = True
                self.log(f"[{account_name}] MD5 cũ: {old_h} -> MD5 mới: {new_h} (Video gốc nguyên nét)", "SUCCESS")

        file_size_mb = os.path.getsize(actual_upload_path) / (1024 * 1024)
        self.log(f"[{account_name}] Bắt đầu xử lý: '{original_file_name}' ({file_size_mb:.2f} MB)", "INFO")

        playwright_proxy = parse_proxy(proxy_str)
        if playwright_proxy:
            self.log(f"[{account_name}] Sử dụng Proxy: {playwright_proxy.get('server')}", "INFO")

        full_caption = sanitize_caption(f"{caption} {hashtags}".strip())
        self.log(f"[{account_name}] Caption: {full_caption}", "INFO")

        dev_info = get_or_create_device_profile(account_name)
        with sync_playwright() as p:
            context = None
            try:
                context = p.chromium.launch_persistent_context(
                    user_data_dir=profile_path,
                    proxy=playwright_proxy,
                    headless=headless,
                    channel="chrome",
                    user_agent=dev_info.get("user_agent"),
                    args=[
                        "--disable-blink-features=AutomationControlled",
                        "--no-sandbox",
                        "--disable-infobars",
                        "--start-maximized"
                    ],
                    viewport={"width": dev_info.get("screen_width", 1366), "height": dev_info.get("screen_height", 850)} if headless else None,
                    locale="vi-VN"
                )

                page = context.pages[0] if context.pages else context.new_page()
                page.add_init_script(STEALTH_JS + generate_device_stealth_js(dev_info))

                self.log(f"[{account_name}] Đang kết nối tới TikTok Studio...", "INFO")
                page.goto("https://www.tiktok.com/tiktokstudio/upload", timeout=65000)
                page.wait_for_load_state("domcontentloaded")
                time.sleep(3)

                # Kiểm tra trạng thái đăng nhập
                if "login" in page.url.lower():
                    self.log(f"[{account_name}] LỖI: Nick chưa đăng nhập! Hãy chọn nick và bấm 'Đăng nhập Chrome' trước.", "ERROR")
                    add_history_record(account_name, original_file_name, full_caption, "Thất bại (Chưa đăng nhập)", proxy_str)
                    context.close()
                    if is_temp_file:
                        cleanup_temp_anti_reup(actual_upload_path)
                    return False

                # Đóng các popup ban đầu
                self.dismiss_popups(page, page)

                # Tìm phần tử input file video
                self.log(f"[{account_name}] Đang tìm khung tải video...", "INFO")
                input_file_loc = None
                scope = page

                for _ in range(6):
                    inputs = page.locator('input[type="file"]')
                    if inputs.count() > 0:
                        input_file_loc = inputs.first
                        scope = page
                        break
                    for frame in page.frames:
                        f_inputs = frame.locator('input[type="file"]')
                        if f_inputs.count() > 0:
                            input_file_loc = f_inputs.first
                            scope = frame
                            break
                    if input_file_loc:
                        break
                    time.sleep(2)

                if not input_file_loc:
                    self.log(f"[{account_name}] Không tìm thấy nút chọn file. Thử reload lại trang...", "WARNING")
                    page.reload()
                    time.sleep(5)
                    inputs = page.locator('input[type="file"]')
                    if inputs.count() > 0:
                        input_file_loc = inputs.first
                        scope = page

                if not input_file_loc:
                    self.log(f"[{account_name}] LỖI: Không tìm thấy khung upload của TikTok!", "ERROR")
                    add_history_record(account_name, original_file_name, full_caption, "Thất bại (Lỗi UI TikTok)", proxy_str)
                    context.close()
                    if is_temp_file:
                        cleanup_temp_anti_reup(actual_upload_path)
                    return False

                # Nạp file video vào
                self.log(f"[{account_name}] Đang nạp video '{original_file_name}'...", "INFO")
                input_file_loc.set_input_files(actual_upload_path)
                self.log(f"[{account_name}] Đã nạp file. Đang tải dữ liệu lên TikTok...", "INFO")

                # Chờ video upload xong
                upload_complete = False
                for _ in range(120):
                    time.sleep(2)
                    self.dismiss_popups(page, scope)

                    p_content = scope.content().lower()
                    if any(x in p_content for x in ["uploaded", "đã tải lên", "thành công", "100%", "replace", "thay thế"]):
                        upload_complete = True
                        break

                    post_chk = scope.locator('button:has-text("Post"), button:has-text("Đăng"), button:has-text("Schedule"), button:has-text("Lên lịch")').first
                    if post_chk.count() > 0 and post_chk.is_enabled():
                        upload_complete = True
                        break

                if upload_complete:
                    self.log(f"[{account_name}] Video đã tải lên máy chủ TikTok thành công!", "SUCCESS")
                else:
                    self.log(f"[{account_name}] Cảnh báo: Video đang xử lý, tiếp tục điền thông tin...", "WARNING")

                # Điền Caption và Hashtags
                self.log(f"[{account_name}] Đang điền tiêu đề và hashtag...", "INFO")
                time.sleep(2)

                caption_selectors = [
                    'div[contenteditable="true"]',
                    '.public-DraftEditor-content',
                    'div[role="combobox"]',
                    'div[data-placeholder]',
                    'textarea'
                ]

                caption_filled = False
                for sel in caption_selectors:
                    caption_boxes = scope.locator(sel)
                    if caption_boxes.count() > 0:
                        target_box = caption_boxes.first
                        try:
                            target_box.click()
                            time.sleep(0.5)
                            page.keyboard.press("Control+A")
                            page.keyboard.press("Backspace")
                            time.sleep(0.3)
                            target_box.type(full_caption, delay=25)
                            caption_filled = True
                            self.log(f"[{account_name}] Đã điền Caption thành công.", "SUCCESS")
                            break
                        except Exception:
                            continue

                if not caption_filled:
                    self.log(f"[{account_name}] Không tìm thấy ô Caption, bỏ qua gõ tiêu đề.", "WARNING")

                time.sleep(1.5)

                # Bật tải lên chất lượng cao
                try:
                    hq_switch = scope.locator('input[type="checkbox"][name*="quality"], div:has-text("Allow high-quality uploads") input')
                    if hq_switch.count() > 0 and not hq_switch.first.is_checked():
                        hq_switch.first.click()
                        self.log(f"[{account_name}] Đã bật chế độ tải lên chất lượng cao.", "INFO")
                except Exception:
                    pass

                # Áp dụng cấu hình nâng cao (Quyền riêng tư, Tương tác, AI label)
                self.apply_advanced_settings(scope, privacy=privacy, allow_comment=allow_comment,
                                            allow_duet=allow_duet, allow_stitch=allow_stitch, 
                                            ai_content=ai_content)

                # Xử lý Lên lịch đăng (Schedule) nếu có
                post_mode_name = "Đăng ngay"
                if schedule_minutes > 0:
                    try:
                        self.log(f"[{account_name}] ⏰ Đang thiết lập lên lịch hẹn giờ (+{schedule_minutes} phút)...", "INFO")
                        sched_switch = scope.locator('input[type="checkbox"][name*="schedule"], input[value="schedule"], div:has-text("Schedule video") input, div:has-text("Lên lịch") input')
                        if sched_switch.count() > 0:
                            if not sched_switch.first.is_checked():
                                sched_switch.first.click()
                                time.sleep(1)
                                post_mode_name = f"Lên lịch (+{schedule_minutes}m)"
                                self.log(f"[{account_name}] Đã bật công tắc Lên Lịch Đăng thành công.", "SUCCESS")
                    except Exception as se:
                        self.log(f"[{account_name}] Không thể bật hẹn giờ: {str(se)}, sẽ chuyển sang Đăng ngay.", "WARNING")

                # Cuộn trang xuống cuối
                try:
                    page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                except Exception:
                    pass

                time.sleep(1)

                # Tìm nút Đăng / Lên lịch
                self.log(f"[{account_name}] Đang tìm nút 'Đăng' / 'Lên lịch'...", "INFO")
                post_button = None
                btn_selectors = [
                    'button:has-text("Lên lịch")',
                    'button:has-text("Schedule")',
                    'button:has-text("Đăng")',
                    'button:has-text("Post")',
                    'button[data-e2e="post_video_button"]',
                    '.btn-post'
                ]

                for b_sel in btn_selectors:
                    btns = scope.locator(b_sel)
                    if btns.count() > 0:
                        for idx in range(btns.count()):
                            candidate = btns.nth(idx)
                            if candidate.is_visible():
                                post_button = candidate
                                break
                    if post_button:
                        break

                if not post_button:
                    self.log(f"[{account_name}] LỖI: Không tìm thấy nút Đăng!", "ERROR")
                    add_history_record(account_name, original_file_name, full_caption, "Thất bại (Không thấy nút Đăng)", proxy_str, post_mode_name)
                    context.close()
                    if is_temp_file:
                        cleanup_temp_anti_reup(actual_upload_path)
                    return False

                # Chờ nút Đăng sẵn sàng
                for _ in range(30):
                    if post_button.is_enabled():
                        break
                    time.sleep(1)

                # Nhấp nút Đăng / Schedule
                self.log(f"[{account_name}] Bấm nút XÁC NHẬN ĐĂNG...", "INFO")
                post_button.click()

                # Chờ xác nhận đăng thành công
                self.log(f"[{account_name}] Đang chờ máy chủ TikTok xác nhận...", "INFO")
                posted_success = False
                for _ in range(30):
                    time.sleep(2)
                    self.dismiss_popups(page, scope)
                    content_now = scope.content().lower()

                    if any(msg in content_now for msg in [
                        "uploaded", "đã được đăng", "scheduled", "đã lên lịch",
                        "manage your posts", "quản lý bài đăng", "upload another", "tải lên video khác"
                    ]):
                        posted_success = True
                        break

                    modal_success = scope.locator('div:has-text("Manage your posts"), div:has-text("Quản lý bài đăng")')
                    if modal_success.count() > 0 and modal_success.first.is_visible():
                        posted_success = True
                        break

                if posted_success:
                    self.log(f"[{account_name}] 🎉 XÁC NHẬN THÀNH CÔNG: Video '{original_file_name}' đã được xử lý xong!", "SUCCESS")
                    add_history_record(account_name, original_file_name, full_caption, "Thành công", proxy_str, post_mode_name)
                    log_account_activity(account_name, "Đăng video thành công", ip_or_proxy=proxy_str, status="Thành công", details=f"File: {original_file_name}")
                else:
                    self.log(f"[{account_name}] Đã gửi yêu cầu đăng cho video '{original_file_name}'.", "SUCCESS")
                    add_history_record(account_name, original_file_name, full_caption, "Đã gửi lệnh đăng", proxy_str, post_mode_name)
                    log_account_activity(account_name, "Gửi lệnh đăng video", ip_or_proxy=proxy_str, status="Đã gửi", details=f"File: {original_file_name}")
                    posted_success = True

                time.sleep(3)
                context.close()

                # Dọn file tạm
                if is_temp_file:
                    cleanup_temp_anti_reup(actual_upload_path)

                return posted_success

            except Exception as e:
                self.log(f"[{account_name}] Lỗi trong tiến trình upload: {str(e)}", "ERROR")
                add_history_record(account_name, original_file_name, full_caption, f"Lỗi: {str(e)[:50]}", proxy_str, post_mode_name)
                log_account_activity(account_name, "Đăng video thất bại", ip_or_proxy=proxy_str, status="Thất bại", details=f"File: {original_file_name} - {str(e)[:50]}")
                if context:
                    try:
                        context.close()
                    except Exception:
                        pass
                if is_temp_file:
                    cleanup_temp_anti_reup(actual_upload_path)
                return False

def move_to_done_folder(video_path):
    """Di chuyển video đã đăng vào thư mục '_done' trong cùng folder để tránh đăng trùng."""
    try:
        folder = os.path.dirname(video_path)
        done_folder = os.path.join(folder, "_done")
        os.makedirs(done_folder, exist_ok=True)
        dest_path = os.path.join(done_folder, os.path.basename(video_path))
        if os.path.exists(dest_path):
            base, ext = os.path.splitext(os.path.basename(video_path))
            dest_path = os.path.join(done_folder, f"{base}_{int(time.time())}{ext}")
        shutil.move(video_path, dest_path)
        return dest_path
    except Exception as e:
        print(f"Error moving file to done: {e}")
        return None
