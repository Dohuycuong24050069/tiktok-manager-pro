import os
import re
import time
import requests
from playwright.sync_api import sync_playwright
import yt_dlp
from uploader import STEALTH_JS

def sanitize_filename(name):
    """Làm sạch tên file để không chứa ký tự đặc biệt của Windows."""
    clean = re.sub(r'[\\/*?:"<>|]', "", name)
    clean = re.sub(r'\s+', " ", clean).strip()
    return clean[:80] if clean else "tiktok_video"

def resolve_tiktok_url(url):
    """Mở rộng link rút gọn vt.tiktok.com, vm.tiktok.com, tiktok.com/t/ thành link gốc."""
    url = url.strip()
    if any(short in url for short in ["vt.tiktok.com", "vm.tiktok.com", "/t/"]):
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36'
            }
            resp = requests.head(url, headers=headers, allow_redirects=True, timeout=10)
            if resp.url and resp.url != url:
                return resp.url
        except Exception:
            try:
                resp = requests.get(url, headers=headers, allow_redirects=True, timeout=10)
                if resp.url and resp.url != url:
                    return resp.url
            except Exception:
                pass
    return url

class TikTokScraper:
    def __init__(self, log_callback=None):
        self.log_cb = log_callback or print

    def log(self, message, level="INFO"):
        prefix = f"[{time.strftime('%H:%M:%S')}] [{level}] "
        self.log_cb(prefix + message)

    def download_video_no_watermark(self, video_url, output_dir, save_caption_txt=True):
        """
        Tải 1 video TikTok chất lượng cao nhất (Full HD 1080p),
        KHÔNG LOGO WATERMARK, CÓ ĐẦY ĐỦ ÂM THANH.
        Tự động lưu kèm file .txt chứa tiêu đề/caption gốc.
        """
        os.makedirs(output_dir, exist_ok=True)
        resolved_url = resolve_tiktok_url(video_url)
        self.log(f"Đang bóc tách video không logo: {resolved_url}", "INFO")

        # 1. Phương pháp 1 (Nhanh và tối ưu nhất): TikWM API lấy luồng Full HD 1080p
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
                'Referer': 'https://www.tikwm.com/'
            }
            resp = requests.post("https://www.tikwm.com/api/", data={"url": resolved_url, "hd": 1}, headers=headers, timeout=15)
            if resp.status_code == 200:
                res_data = resp.json().get('data', {})
                video_download_url = res_data.get('hdplay') or res_data.get('play')
                caption = res_data.get('title', '')
                video_id = res_data.get('id', str(int(time.time())))

                if video_download_url:
                    filename = f"{sanitize_filename(caption)}_{video_id}.mp4"
                    dest_file = os.path.join(output_dir, filename)

                    dl_headers = {
                        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36'
                    }
                    v_resp = requests.get(video_download_url, headers=dl_headers, stream=True, timeout=40)
                    if v_resp.status_code == 200:
                        with open(dest_file, "wb") as f:
                            for chunk in v_resp.iter_content(chunk_size=131072):
                                if chunk:
                                    f.write(chunk)

                        if save_caption_txt and caption:
                            txt_path = os.path.splitext(dest_file)[0] + ".txt"
                            with open(txt_path, "w", encoding="utf-8") as f:
                                f.write(caption)

                        file_mb = os.path.getsize(dest_file) / (1024 * 1024)
                        self.log(f"✅ Tải thành công (No Logo, Full HD {file_mb:.1f} MB): {filename}", "SUCCESS")
                        return dest_file
        except Exception as ex:
            self.log(f"TikWM API gặp sự cố ({str(ex)[:60]}), chuyển sang phương thức dự phòng yt-dlp...", "WARNING")

        # 2. Phương pháp dự phòng 2: Sử dụng yt-dlp
        ydl_opts = {
            'outtmpl': os.path.join(output_dir, '%(title).70s_%(id)s.%(ext)s'),
            'format': 'bestvideo+bestaudio/best',
            'quiet': True,
            'no_warnings': True,
            'ignoreerrors': True
        }

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(resolved_url, download=True)
                if info:
                    title = info.get('title', 'tiktok_video')
                    video_id = info.get('id', str(int(time.time())))
                    ext = info.get('ext', 'mp4')
                    downloaded_file = os.path.join(output_dir, f"{sanitize_filename(title)}_{video_id}.{ext}")

                    if not os.path.exists(downloaded_file):
                        files = [os.path.join(output_dir, f) for f in os.listdir(output_dir) if video_id in f and f.endswith(('.mp4', '.mkv', '.webm'))]
                        if files:
                            downloaded_file = files[0]

                    if os.path.exists(downloaded_file):
                        if save_caption_txt and title:
                            txt_path = os.path.splitext(downloaded_file)[0] + ".txt"
                            with open(txt_path, "w", encoding="utf-8") as f:
                                f.write(title)

                        file_mb = os.path.getsize(downloaded_file) / (1024 * 1024)
                        self.log(f"✅ Tải thành công qua yt-dlp ({file_mb:.1f} MB, No Logo): {os.path.basename(downloaded_file)}", "SUCCESS")
                        return downloaded_file

        except Exception as e:
            self.log(f"yt-dlp lỗi: {str(e)[:60]}", "ERROR")

        return None

    def extract_channel_video_urls(self, channel_input, max_count=20):
        """
        Sử dụng Playwright tự động duyệt trang cá nhân kênh TikTok,
        cuộn trang để lấy toàn bộ danh sách liên kết video mới nhất.
        Hỗ trợ: '@username', 'username', hoặc 'https://www.tiktok.com/@username'
        """
        raw_input = channel_input.strip()
        resolved_input = resolve_tiktok_url(raw_input)

        # Nếu là link video đơn lẻ
        if "/video/" in resolved_input:
            self.log("Phát hiện link video đơn lẻ, đưa vào danh sách tải...", "INFO")
            return [resolved_input]

        clean_user = resolved_input
        if "tiktok.com" in clean_user:
            match = re.search(r'@([^/?]+)', clean_user)
            if match:
                clean_user = match.group(1)
            else:
                parts = [p for p in clean_user.split("/") if p and not p.startswith("http")]
                if parts:
                    clean_user = parts[-1].lstrip("@")
        elif clean_user.startswith("@"):
            clean_user = clean_user[1:]

        profile_url = f"https://www.tiktok.com/@{clean_user}"
        self.log(f"Đang phân tích kênh TikTok: @{clean_user} ({profile_url})...", "INFO")

        video_urls = []
        with sync_playwright() as p:
            try:
                browser = p.chromium.launch(
                    headless=True,
                    args=["--disable-blink-features=AutomationControlled", "--no-sandbox"]
                )
                context = browser.new_context(
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
                    viewport={"width": 1280, "height": 800},
                    locale="vi-VN"
                )
                page = context.new_page()
                page.add_init_script(STEALTH_JS)
                page.goto(profile_url, timeout=40000)
                time.sleep(3)

                last_height = 0
                for scroll_round in range(20):
                    # Tìm tất cả link video
                    links = page.locator('a[href*="/video/"]').all()
                    for l in links:
                        try:
                            href = l.get_attribute("href")
                            if href and "/video/" in href and href not in video_urls:
                                if not href.startswith("http"):
                                    href = "https://www.tiktok.com" + href
                                video_urls.append(href)
                                if len(video_urls) >= max_count:
                                    break
                        except Exception:
                            pass

                    if len(video_urls) >= max_count:
                        break

                    # Cuộn trang xuống
                    page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                    time.sleep(1.5)

                    new_height = page.evaluate("document.body.scrollHeight")
                    if new_height == last_height and scroll_round > 2:
                        break
                    last_height = new_height

                browser.close()
            except Exception as e:
                self.log(f"Lỗi khi quét kênh: {str(e)}", "ERROR")

        self.log(f"Tìm thấy tổng cộng {len(video_urls)} video từ kênh @{clean_user}.", "SUCCESS")
        return video_urls[:max_count]

    def scrape_and_download_channel(self, channel_input, output_dir, max_count=20, progress_callback=None):
        """
        Cào hàng loạt video của một kênh TikTok người khác về thư mục:
        - Không logo TikTok (No Watermark)
        - Độ phân giải cao nhất (Full HD 1080p/720p)
        - Đầy đủ âm thanh gốc
        - Kèm file .txt chứa tiêu đề/caption sẵn sàng cho auto upload!
        """
        urls = self.extract_channel_video_urls(channel_input, max_count=max_count)
        if not urls:
            self.log("Không tìm thấy video nào từ kênh này hoặc kênh để chế độ riêng tư!", "WARNING")
            return 0

        self.log(f"=== BẮT ĐẦU TẢI {len(urls)} VIDEO KHÔNG LOGO TỪ KÊNH VỀ MÁY ===", "INFO")
        downloaded = 0
        total = len(urls)

        for idx, url in enumerate(urls):
            self.log(f"[{idx+1}/{total}] Đang xử lý video...", "INFO")
            res = self.download_video_no_watermark(url, output_dir)
            if res:
                downloaded += 1

            if progress_callback:
                progress_callback(idx + 1, total)

            time.sleep(1)

        self.log(f"=== HOÀN TẤT CÀO KÊNH: Đã tải thành công {downloaded}/{total} video Full HD không logo! ===", "SUCCESS")
        return downloaded
