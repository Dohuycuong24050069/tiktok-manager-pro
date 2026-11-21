import os
import sys
import time
import glob
import threading
import subprocess
import winsound
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import customtkinter as ctk

from config_manager import load_config, save_config, get_profile_path
from uploader import TikTokUploader, move_to_done_folder, check_proxy_alive
from history_manager import load_history, clear_all_history, export_history_to_csv, is_video_uploaded_to_account
from video_processor import parse_spintax
from tiktok_scraper import TikTokScraper
from device_manager import (
    get_or_create_device_profile,
    regenerate_device_profile,
    get_account_activities,
    clear_account_activities
)

ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

VIDEO_EXTENSIONS = ('.mp4', '.mov', '.avi', '.mkv', '.webm')

# ==========================================
# DIALOG: CÀI ĐẶT PROXY CHO NICK
# ==========================================
class ProxyDialog(ctk.CTkToplevel):
    def __init__(self, parent, account_name, current_proxy="", on_save_callback=None):
        super().__init__(parent)
        self.title(f"Cài Đặt Proxy - {account_name}")
        self.geometry("500x300")
        self.resizable(False, False)
        self.account_name = account_name
        self.on_save_callback = on_save_callback

        self.transient(parent)
        self.grab_set()

        lbl_title = ctk.CTkLabel(
            self, 
            text=f"🌐 Cấu Hình Proxy Cho Nick: {account_name}", 
            font=ctk.CTkFont(size=15, weight="bold")
        )
        lbl_title.pack(pady=(15, 5))

        lbl_desc = ctk.CTkLabel(
            self, 
            text="Định dạng hỗ trợ:\n• ip:port\n• ip:port:user:pass\n• http://user:pass@ip:port\n• socks5://user:pass@ip:port",
            font=ctk.CTkFont(size=11),
            text_color="gray",
            justify="left"
        )
        lbl_desc.pack(padx=20, pady=5)

        self.entry_proxy = ctk.CTkEntry(
            self, 
            placeholder_text="Ví dụ: 103.145.22.10:8080:username:password",
            width=440
        )
        if current_proxy:
            self.entry_proxy.insert(0, current_proxy)
        self.entry_proxy.pack(padx=20, pady=10)

        self.lbl_status = ctk.CTkLabel(self, text="Trạng thái: Chưa kiểm tra", font=ctk.CTkFont(size=11), text_color="gray")
        self.lbl_status.pack(pady=2)

        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(fill="x", padx=20, pady=15)

        self.btn_test = ctk.CTkButton(
            btn_frame, 
            text="⚡ Kiểm Tra Proxy", 
            width=130, 
            fg_color="#34495e",
            command=self.on_test_proxy
        )
        self.btn_test.pack(side="left", padx=5)

        self.btn_save = ctk.CTkButton(
            btn_frame, 
            text="💾 Lưu Proxy", 
            width=120, 
            fg_color="#27ae60",
            hover_color="#1e8449",
            command=self.on_save
        )
        self.btn_save.pack(side="right", padx=5)

        self.btn_remove = ctk.CTkButton(
            btn_frame, 
            text="Xoá Proxy (Dùng IP Thật)", 
            width=140, 
            fg_color="#7f8c8d",
            command=self.on_remove_proxy
        )
        self.btn_remove.pack(side="right", padx=5)

    def on_test_proxy(self):
        proxy_val = self.entry_proxy.get().strip()
        if not proxy_val:
            self.lbl_status.configure(text="Vui lòng nhập chuỗi proxy để kiểm tra!", text_color="#e74c3c")
            return

        self.lbl_status.configure(text="Đang kết nối kiểm tra proxy...", text_color="#f39c12")
        self.btn_test.configure(state="disabled")

        def test_worker():
            ok, msg = check_proxy_alive(proxy_val)
            color = "#2ecc71" if ok else "#e74c3c"
            self.after(0, lambda: self.lbl_status.configure(text=msg, text_color=color))
            self.after(0, lambda: self.btn_test.configure(state="normal"))

        threading.Thread(target=test_worker, daemon=True).start()

    def on_save(self):
        proxy_val = self.entry_proxy.get().strip()
        if self.on_save_callback:
            self.on_save_callback(self.account_name, proxy_val)
        self.destroy()

    def on_remove_proxy(self):
        if self.on_save_callback:
            self.on_save_callback(self.account_name, "")
        self.destroy()

# ==========================================
# DIALOG: NHẬP HÀNG LOẠT NICK & PROXY
# ==========================================
class BulkAccountDialog(ctk.CTkToplevel):
    def __init__(self, parent, on_import_callback=None):
        super().__init__(parent)
        self.title("📥 Nhập Hàng Loạt Nick & Proxy")
        self.geometry("540x400")
        self.resizable(False, False)
        self.on_import_callback = on_import_callback

        self.transient(parent)
        self.grab_set()

        lbl_title = ctk.CTkLabel(self, text="📥 Nhập Danh Sách Tài Khoản Hàng Loạt", font=ctk.CTkFont(size=15, weight="bold"))
        lbl_title.pack(pady=(15, 5))

        lbl_hint = ctk.CTkLabel(
            self,
            text="Định dạng mỗi dòng một tài khoản:\n• TenNick\n• TenNick|Proxy_IP:Port\n• TenNick|Proxy_IP:Port:User:Pass",
            font=ctk.CTkFont(size=11),
            text_color="gray",
            justify="left"
        )
        lbl_hint.pack(padx=20, pady=4)

        self.txt_bulk = ctk.CTkTextbox(self, font=ctk.CTkFont(family="Consolas", size=11))
        self.txt_bulk.pack(fill="both", expand=True, padx=20, pady=10)
        self.txt_bulk.insert("1.0", "# Ví dụ:\nNick_TikTok_01|103.145.22.10:8080:user:pass\nNick_TikTok_02\nNick_TikTok_03|socks5://user:pass@127.0.0.1:1080\n")

        btn_row = ctk.CTkFrame(self, fg_color="transparent")
        btn_row.pack(fill="x", padx=20, pady=(0, 15))

        btn_cancel = ctk.CTkButton(btn_row, text="Đóng", width=100, fg_color="#7f8c8d", command=self.destroy)
        btn_cancel.pack(side="left")

        btn_apply = ctk.CTkButton(btn_row, text="✅ Nhập Vào Hệ Thống", width=160, fg_color="#27ae60", command=self.on_apply)
        btn_apply.pack(side="right")

    def on_apply(self):
        raw_text = self.txt_bulk.get("1.0", "end").strip()
        lines = [l.strip() for l in raw_text.splitlines() if l.strip() and not l.strip().startswith("#")]
        if not lines:
            messagebox.showwarning("Cảnh báo", "Vui lòng nhập ít nhất 1 dòng tài khoản!")
            return

        imported_accs = {}
        for line in lines:
            parts = line.split("|", 1)
            acc_name = parts[0].strip()
            proxy = parts[1].strip() if len(parts) > 1 else ""
            if acc_name:
                imported_accs[acc_name] = proxy

        if self.on_import_callback:
            self.on_import_callback(imported_accs)
        self.destroy()

# ==========================================
# DIALOG: QUẢN LÝ THIẾT BỊ GIẢ LẬP & NHẬT KÝ NICK
# ==========================================
class AccountDeviceAndLogDialog(ctk.CTkToplevel):
    def __init__(self, parent, account_name, on_change_callback=None):
        super().__init__(parent)
        self.title(f"📱 Fake Device & Nhật Ký Hoạt Động - {account_name}")
        self.geometry("780x640")
        self.minsize(700, 520)
        self.account_name = account_name
        self.on_change_callback = on_change_callback

        self.transient(parent)
        self.grab_set()

        self.device_info = get_or_create_device_profile(account_name)

        # Header Title
        h_f = ctk.CTkFrame(self, fg_color="transparent")
        h_f.pack(fill="x", padx=20, pady=(15, 6))
        ctk.CTkLabel(
            h_f, 
            text=f"📱 THIẾT BỊ GIẢ LẬP & NHẬT KÝ HOẠT ĐỘNG: {account_name.upper()}", 
            font=ctk.CTkFont(size=15, weight="bold"),
            text_color="#1abc9c"
        ).pack(side="left")

        # Tabview
        self.tabview = ctk.CTkTabview(self)
        self.tabview.pack(fill="both", expand=True, padx=20, pady=(0, 15))

        self.tab_device = self.tabview.add("📱 Thiết Bị Giả Lập (Fingerprint)")
        self.tab_log = self.tabview.add("📜 Nhật Ký Hoạt Động (Account Log)")

        self.build_device_tab()
        self.build_log_tab()

    def build_device_tab(self):
        dev = self.device_info
        scroll_d = ctk.CTkScrollableFrame(self.tab_device)
        scroll_d.pack(fill="both", expand=True, padx=5, pady=5)

        # Info Box
        info_c = ctk.CTkFrame(scroll_d, fg_color="#1e272e")
        info_c.pack(fill="x", pady=6, padx=10)

        ctk.CTkLabel(
            info_c, 
            text="🛡️ CƠ CHẾ BẢO VỆ CHỐNG QUÉT MULTI-ACCOUNT TIKTOK", 
            font=ctk.CTkFont(size=13, weight="bold"), 
            text_color="#f1c40f"
        ).pack(anchor="w", padx=15, pady=(10, 4))

        ctk.CTkLabel(
            info_c,
            text="• Mỗi tài khoản được cấp một thông số phần cứng riêng biệt và CỐ ĐỊNH vĩnh viễn.\n• Fake toàn diện: GPU WebGL, CPU Cores, RAM, Màn hình, Canvas vi nhiễu, Audio vi nhiễu.\n• TikTok sẽ nhận diện đây là một máy tính độc lập duy nhất từ trước đến nay!",
            font=ctk.CTkFont(size=11),
            text_color="#c8d6e5",
            justify="left"
        ).pack(anchor="w", padx=15, pady=(0, 10))

        # Specs Card
        specs_card = ctk.CTkFrame(scroll_d)
        specs_card.pack(fill="x", pady=6, padx=10)

        self.lbl_dev_name = ctk.CTkLabel(specs_card, text=f"Thiết bị: {dev.get('name')}", font=ctk.CTkFont(size=13, weight="bold"), text_color="#3498db")
        self.lbl_dev_name.pack(anchor="w", padx=15, pady=(12, 6))

        self.lbl_dev_os = ctk.CTkLabel(specs_card, text=f"• Hệ điều hành: {dev.get('os')} ({dev.get('platform')})", font=ctk.CTkFont(size=11))
        self.lbl_dev_os.pack(anchor="w", padx=15, pady=2)

        self.lbl_dev_cpu = ctk.CTkLabel(specs_card, text=f"• CPU & RAM: {dev.get('cpu_cores')} Nhân Cores • {dev.get('device_memory_gb')} GB RAM", font=ctk.CTkFont(size=11))
        self.lbl_dev_cpu.pack(anchor="w", padx=15, pady=2)

        self.lbl_dev_gpu = ctk.CTkLabel(specs_card, text=f"• GPU WebGL: {dev.get('webgl_renderer')}", font=ctk.CTkFont(size=11), wraplength=640, justify="left")
        self.lbl_dev_gpu.pack(anchor="w", padx=15, pady=2)

        self.lbl_dev_screen = ctk.CTkLabel(specs_card, text=f"• Màn hình giả lập: {dev.get('screen_width')} x {dev.get('screen_height')} ({dev.get('color_depth')}-bit Color)", font=ctk.CTkFont(size=11))
        self.lbl_dev_screen.pack(anchor="w", padx=15, pady=2)

        self.lbl_dev_canvas = ctk.CTkLabel(specs_card, text=f"• Canvas & Audio Vi Nhiễu: Đang kích hoạt (Seed #{dev.get('canvas_noise_seed', 12345)})", font=ctk.CTkFont(size=11), text_color="#2ecc71")
        self.lbl_dev_canvas.pack(anchor="w", padx=15, pady=(2, 12))

        # Action Buttons
        btn_f = ctk.CTkFrame(scroll_d, fg_color="transparent")
        btn_f.pack(fill="x", pady=10, padx=10)

        ctk.CTkButton(
            btn_f,
            text="🎲 Đổi Sang Thiết Bị Khác Ngẫu Nhiên",
            fg_color="#e67e22",
            hover_color="#d35400",
            height=36,
            command=self.on_regenerate_device
        ).pack(side="left", padx=5)

    def on_regenerate_device(self):
        if messagebox.askyesno("Xác nhận", f"Bạn có chắc muốn cấp thiết bị giả lập MỚI cho nick '{self.account_name}'?\n(TikTok sẽ ghi nhận đây là bạn vừa đổi máy tính mới)"):
            self.device_info = regenerate_device_profile(self.account_name)
            dev = self.device_info
            self.lbl_dev_name.configure(text=f"Thiết bị: {dev.get('name')}")
            self.lbl_dev_os.configure(text=f"• Hệ điều hành: {dev.get('os')} ({dev.get('platform')})")
            self.lbl_dev_cpu.configure(text=f"• CPU & RAM: {dev.get('cpu_cores')} Nhân Cores • {dev.get('device_memory_gb')} GB RAM")
            self.lbl_dev_gpu.configure(text=f"• GPU WebGL: {dev.get('webgl_renderer')}")
            self.lbl_dev_screen.configure(text=f"• Màn hình giả lập: {dev.get('screen_width')} x {dev.get('screen_height')} ({dev.get('color_depth')}-bit Color)")
            self.lbl_dev_canvas.configure(text=f"• Canvas & Audio Vi Nhiễu: Đang kích hoạt (Seed #{dev.get('canvas_noise_seed', 12345)})")
            messagebox.showinfo("Thành Công", f"Đã gán thiết bị mới: {dev.get('name')}!")
            self.refresh_log_list()
            if self.on_change_callback:
                self.on_change_callback()

    def build_log_tab(self):
        # Action bar top of log
        log_act = ctk.CTkFrame(self.tab_log, fg_color="transparent")
        log_act.pack(fill="x", pady=(5, 8))

        ctk.CTkButton(log_act, text="🔄 Làm Mới Log", width=120, fg_color="#34495e", command=self.refresh_log_list).pack(side="left", padx=5)
        ctk.CTkButton(log_act, text="🗑 Xoá Nhật Ký Nick", width=140, fg_color="#c0392b", command=self.on_clear_logs).pack(side="right", padx=5)

        # Log Scroll Frame
        self.log_scroll = ctk.CTkScrollableFrame(self.tab_log)
        self.log_scroll.pack(fill="both", expand=True)

        self.refresh_log_list()

    def refresh_log_list(self):
        for w in self.log_scroll.winfo_children():
            w.destroy()

        activities = get_account_activities(self.account_name, limit=60)
        if not activities:
            ctk.CTkLabel(self.log_scroll, text="Chưa có nhật ký hoạt động nào cho nick này.", text_color="gray").pack(pady=30)
            return

        for act in activities:
            card = ctk.CTkFrame(self.log_scroll, fg_color="#2c3e50")
            card.pack(fill="x", pady=3, padx=5)

            top_r = ctk.CTkFrame(card, fg_color="transparent")
            top_r.pack(fill="x", padx=10, pady=(6, 2))

            ctk.CTkLabel(top_r, text=act.get("timestamp", ""), font=ctk.CTkFont(size=10), text_color="#bdc3c7").pack(side="left")
            
            st = act.get("status", "")
            st_color = "#2ecc71" if any(w in st.lower() for w in ["thành công", "sống", "đã gửi"]) else ("#e74c3c" if "lỗi" in st.lower() or "thất bại" in st.lower() or "hết phiên" in st.lower() else "#f39c12")
            ctk.CTkLabel(top_r, text=f"[{st}]", font=ctk.CTkFont(size=11, weight="bold"), text_color=st_color).pack(side="right")

            bot_r = ctk.CTkFrame(card, fg_color="transparent")
            bot_r.pack(fill="x", padx=10, pady=(0, 6))

            ctk.CTkLabel(bot_r, text=f"👉 {act.get('action')}:", font=ctk.CTkFont(size=11, weight="bold")).pack(side="left", padx=(0, 6))
            ctk.CTkLabel(bot_r, text=f"IP: {act.get('ip_proxy')} | {act.get('details')}", font=ctk.CTkFont(size=11), text_color="#ecf0f1").pack(side="left")

    def on_clear_logs(self):
        if messagebox.askyesno("Xác nhận", f"Bạn có chắc muốn xoá toàn bộ nhật ký của nick '{self.account_name}'?"):
            clear_account_activities(self.account_name)
            self.refresh_log_list()
            messagebox.showinfo("Thành Công", "Đã xoá sạch lịch sử log của nick!")

# ==========================================
# GIAO DIỆN CHÍNH: TIKTOK MANAGER PRO v4.5 ULTRA
# ==========================================
class TikTokManagerApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("TikTok Manager Pro v4.5 Ultra - Quản Lý Đa Kênh • Cào Video No Watermark")
        self.geometry("1280x880")
        self.minsize(1120, 760)

        self.config_data = load_config()
        self.uploader = TikTokUploader(log_callback=self.thread_safe_log)
        self.scraper = TikTokScraper(log_callback=self.thread_safe_log)

        self.is_running = False
        self.is_scraping = False
        self.stop_requested = False
        self.active_thread = None

        self.account_vars = {}        # {acc_name: BooleanVar}
        self.video_checkboxes = {}     # {video_path: BooleanVar}
        self.account_status_labels = {}# {acc_name: CTkLabel}

        self.build_ui()
        self.refresh_video_list()

    def build_ui(self):
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=1)

        # ==========================================
        # SIDEBAR (LEFT)
        # ==========================================
        self.sidebar_frame = ctk.CTkFrame(self, width=280, corner_radius=0)
        self.sidebar_frame.grid(row=0, column=0, sticky="nsew", padx=0, pady=0)
        self.sidebar_frame.grid_rowconfigure(5, weight=1)

        # Brand / Logo
        self.logo_label = ctk.CTkLabel(
            self.sidebar_frame, 
            text="TIKTOK MANAGER PRO", 
            font=ctk.CTkFont(size=18, weight="bold")
        )
        self.logo_label.grid(row=0, column=0, padx=15, pady=(15, 2))

        self.sub_label = ctk.CTkLabel(
            self.sidebar_frame, 
            text="⚡ v4.5 Ultra • Cào Kênh No Watermark", 
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color="#2ecc71"
        )
        self.sub_label.grid(row=1, column=0, padx=15, pady=(0, 10))

        # Stats Card Sidebar
        self.stats_card = ctk.CTkFrame(self.sidebar_frame, fg_color="#1e272e")
        self.stats_card.grid(row=2, column=0, padx=15, pady=(0, 10), sticky="ew")
        
        self.lbl_stat_accounts = ctk.CTkLabel(self.stats_card, text="Nick: 0 tài khoản", font=ctk.CTkFont(size=11))
        self.lbl_stat_accounts.pack(anchor="w", padx=10, pady=(6, 2))
        
        self.lbl_stat_videos = ctk.CTkLabel(self.stats_card, text="Video: 0 sẵn sàng", font=ctk.CTkFont(size=11))
        self.lbl_stat_videos.pack(anchor="w", padx=10, pady=(0, 6))

        # Quick Account Section Header
        acc_head_row = ctk.CTkFrame(self.sidebar_frame, fg_color="transparent")
        acc_head_row.grid(row=3, column=0, padx=15, pady=(0, 2), sticky="ew")

        ctk.CTkLabel(acc_head_row, text="Chọn nick đăng:", font=ctk.CTkFont(size=12, weight="bold")).pack(side="left")
        
        btn_sel_all = ctk.CTkButton(acc_head_row, text="Tất cả", width=45, height=22, font=ctk.CTkFont(size=10), fg_color="#34495e", command=self.select_all_accounts)
        btn_sel_all.pack(side="right", padx=(2, 0))

        btn_desel_all = ctk.CTkButton(acc_head_row, text="Bỏ chọn", width=45, height=22, font=ctk.CTkFont(size=10), fg_color="#2c3e50", command=self.deselect_all_accounts)
        btn_desel_all.pack(side="right")

        # Scrollable Account Selector
        self.acc_scroll = ctk.CTkScrollableFrame(self.sidebar_frame, label_text="Tài khoản đang chạy")
        self.acc_scroll.grid(row=5, column=0, padx=15, pady=2, sticky="nsew")
        self.render_account_list()

        # Sidebar Quick Actions
        sb_actions = ctk.CTkFrame(self.sidebar_frame, fg_color="transparent")
        sb_actions.grid(row=6, column=0, padx=15, pady=10, sticky="ew")

        btn_quick_chrome = ctk.CTkButton(
            sb_actions, 
            text="🔑 Đăng Nhập Chrome Nick Này", 
            fg_color="#1f538d",
            hover_color="#14375e",
            command=self.on_login_chrome
        )
        btn_quick_chrome.pack(fill="x", pady=2)

        # ==========================================
        # MAIN TABVIEW (RIGHT)
        # ==========================================
        self.tabview = ctk.CTkTabview(self, corner_radius=8)
        self.tabview.grid(row=0, column=1, sticky="nsew", padx=15, pady=12)

        self.tab_studio = self.tabview.add("🚀 Đăng Video")
        self.tab_scraper = self.tabview.add("📥 Cào Kênh & Tải Video (No Logo)")
        self.tab_videos = self.tabview.add("📁 Hàng Đợi & Spintax")
        self.tab_accounts = self.tabview.add("👥 Quản Lý Tài Khoản & Proxy")
        self.tab_settings = self.tabview.add("🛡️ Lách Bản Quyền & Cài Đặt 2026")
        self.tab_history = self.tabview.add("📊 Lịch Sử & Báo Cáo")

        self.build_tab_studio()
        self.build_tab_scraper()
        self.build_tab_videos()
        self.build_tab_accounts()
        self.build_tab_settings()
        self.build_tab_history()

    # ------------------------------------------
    # TAB 1: STUDIO UPLOAD & LIVE PROGRESS
    # ------------------------------------------
    def build_tab_studio(self):
        self.tab_studio.grid_rowconfigure(2, weight=1)
        self.tab_studio.grid_columnconfigure(0, weight=1)

        # Control Card
        ctrl_card = ctk.CTkFrame(self.tab_studio)
        ctrl_card.grid(row=0, column=0, sticky="ew", pady=(0, 8), padx=5)

        ctrl_row = ctk.CTkFrame(ctrl_card, fg_color="transparent")
        ctrl_row.pack(fill="x", padx=15, pady=10)

        self.btn_start = ctk.CTkButton(
            ctrl_row, 
            text="▶ BẮT ĐẦU ĐĂNG TỰ ĐỘNG", 
            font=ctk.CTkFont(size=14, weight="bold"),
            fg_color="#27ae60",
            hover_color="#1e8449",
            height=46,
            command=self.on_start_upload
        )
        self.btn_start.pack(side="left", fill="x", expand=True, padx=(0, 10))

        self.btn_stop = ctk.CTkButton(
            ctrl_row, 
            text="⏹ DỪNG", 
            font=ctk.CTkFont(size=14, weight="bold"),
            fg_color="#c0392b",
            hover_color="#922b21",
            height=46,
            width=130,
            command=self.on_stop_upload,
            state="disabled"
        )
        self.btn_stop.pack(side="right")

        # Distribution row
        dist_row = ctk.CTkFrame(ctrl_card, fg_color="transparent")
        dist_row.pack(fill="x", padx=15, pady=(0, 8))

        ctk.CTkLabel(dist_row, text="Chế độ phân phối:", font=ctk.CTkFont(size=12, weight="bold")).pack(side="left", padx=(0, 10))

        self.dist_mode_var = ctk.StringVar(value=self.config_data.get("dist_mode", "round_robin"))
        rb_rr = ctk.CTkRadioButton(dist_row, text="Chia đều video cho các nick", variable=self.dist_mode_var, value="round_robin")
        rb_rr.pack(side="left", padx=(0, 20))

        rb_sat = ctk.CTkRadioButton(dist_row, text="Đăng tất cả video lên mọi nick (Dàn vệ tinh)", variable=self.dist_mode_var, value="all_to_all")
        rb_sat.pack(side="left")

        # Progress bar
        self.progress_bar = ctk.CTkProgressBar(ctrl_card)
        self.progress_bar.pack(fill="x", padx=15, pady=(0, 4))
        self.progress_bar.set(0)

        self.lbl_progress_status = ctk.CTkLabel(
            ctrl_card, 
            text="Trạng thái: Sẵn sàng.", 
            font=ctk.CTkFont(size=12),
            text_color="gray"
        )
        self.lbl_progress_status.pack(anchor="w", padx=15, pady=(0, 8))

        # Live Logs Card
        log_card = ctk.CTkFrame(self.tab_studio)
        log_card.grid(row=2, column=0, sticky="nsew", padx=5)
        log_card.grid_rowconfigure(1, weight=1)
        log_card.grid_columnconfigure(0, weight=1)

        log_top = ctk.CTkFrame(log_card, fg_color="transparent")
        log_top.grid(row=0, column=0, sticky="ew", padx=15, pady=(8, 2))

        ctk.CTkLabel(log_top, text="📋 Nhật Ký Hoạt Động (Live Realtime Logs):", font=ctk.CTkFont(size=12, weight="bold")).pack(side="left")

        btn_clear = ctk.CTkButton(log_top, text="Xoá Log", width=70, height=24, fg_color="#4a4a4a", command=self.clear_logs)
        btn_clear.pack(side="right")

        self.txt_log = ctk.CTkTextbox(log_card, font=ctk.CTkFont(family="Consolas", size=11))
        self.txt_log.grid(row=1, column=0, sticky="nsew", padx=15, pady=(0, 10))

    # ------------------------------------------
    # TAB 2: CÀO KÊNH & TẢI VIDEO (NO LOGO)
    # ------------------------------------------
    def build_tab_scraper(self):
        scroll_sc = ctk.CTkScrollableFrame(self.tab_scraper)
        scroll_sc.pack(fill="both", expand=True, padx=5, pady=5)

        # Header Info Card
        info_card = ctk.CTkFrame(scroll_sc, fg_color="#1e272e")
        info_card.pack(fill="x", pady=6, padx=10)

        ctk.CTkLabel(
            info_card, 
            text="📥 CÀO VIDEO TIKTOK KHÔNG LOGO - CHẤT LƯỢNG GỐC 1080P FULL HD", 
            font=ctk.CTkFont(size=14, weight="bold"), 
            text_color="#00d2d3"
        ).pack(anchor="w", padx=15, pady=(10, 4))

        ctk.CTkLabel(
            info_card,
            text="• Tải video trực tiếp từ máy chủ CDN gốc của TikTok: Sạch 100% Logo Watermark.\n• Giữ nguyên độ phân giải cao nhất (1080p Full HD) và âm thanh gốc trong trẻo.\n• Hỗ trợ tải 1 video bất kỳ HOẶC cào toàn bộ danh sách video của một kênh bất kỳ.\n• Tự động trích xuất kèm Caption tiêu đề ra file .txt sẵn sàng đưa sang phân hệ Lách bản quyền & Đăng tự động!",
            font=ctk.CTkFont(size=11),
            text_color="#c8d6e5",
            justify="left"
        ).pack(anchor="w", padx=15, pady=(0, 10))

        # Main Input Card
        input_card = ctk.CTkFrame(scroll_sc)
        input_card.pack(fill="x", pady=6, padx=10)

        ctk.CTkLabel(input_card, text="🔗 Nhập Đường Dẫn (Link Video hoặc Link Kênh / @Username):", font=ctk.CTkFont(size=12, weight="bold")).pack(anchor="w", padx=15, pady=(10, 4))

        self.entry_scrape_url = ctk.CTkEntry(
            input_card, 
            placeholder_text="Ví dụ: @khaby.lame hoặc https://www.tiktok.com/@tiktok hoặc link 1 video cụ thể...",
            height=38,
            font=ctk.CTkFont(size=12)
        )
        self.entry_scrape_url.pack(fill="x", padx=15, pady=4)

        # Mode Options Row
        opt_row = ctk.CTkFrame(input_card, fg_color="transparent")
        opt_row.pack(fill="x", padx=15, pady=6)

        ctk.CTkLabel(opt_row, text="Chế độ:", font=ctk.CTkFont(size=11, weight="bold")).pack(side="left", padx=(0, 10))

        self.scrape_mode_var = ctk.StringVar(value="channel")
        ctk.CTkRadioButton(opt_row, text="Cào hàng loạt cả kênh", variable=self.scrape_mode_var, value="channel").pack(side="left", padx=(0, 20))
        ctk.CTkRadioButton(opt_row, text="Tải 1 video duy nhất", variable=self.scrape_mode_var, value="single").pack(side="left")

        # Limit & Destination Row
        limit_row = ctk.CTkFrame(input_card, fg_color="transparent")
        limit_row.pack(fill="x", padx=15, pady=6)

        ctk.CTkLabel(limit_row, text="Số lượng video tối đa:").pack(side="left", padx=(0, 5))
        self.entry_scrape_limit = ctk.CTkEntry(limit_row, width=70)
        self.entry_scrape_limit.insert(0, "20")
        self.entry_scrape_limit.pack(side="left", padx=(0, 20))

        self.cb_save_caption = ctk.CTkCheckBox(limit_row, text="Lưu kèm tiêu đề ra file .txt")
        self.cb_save_caption.pack(side="left", padx=(0, 15))
        self.cb_save_caption.select()

        self.cb_auto_refresh_queue = ctk.CTkCheckBox(limit_row, text="Tự động nạp vào Hàng đợi đăng video sau khi tải xong")
        self.cb_auto_refresh_queue.pack(side="left")
        self.cb_auto_refresh_queue.select()

        # Destination Folder Row
        dest_row = ctk.CTkFrame(input_card, fg_color="transparent")
        dest_row.pack(fill="x", padx=15, pady=6)

        ctk.CTkLabel(dest_row, text="Lưu video vào:", font=ctk.CTkFont(size=11, weight="bold")).pack(side="left", padx=(0, 10))
        self.lbl_scrape_dest = ctk.CTkLabel(
            dest_row, 
            text=self.config_data.get("video_folder") or "Chưa chọn thư mục (Bấm 'Đổi Thư Mục')", 
            text_color="#3498db"
        )
        self.lbl_scrape_dest.pack(side="left", fill="x", expand=True)

        ctk.CTkButton(dest_row, text="Đổi Thư Mục Lưu", width=130, fg_color="#34495e", command=self.on_change_scrape_folder).pack(side="right")

        # Action Button & Progress
        act_row = ctk.CTkFrame(input_card, fg_color="transparent")
        act_row.pack(fill="x", padx=15, pady=(10, 15))

        self.btn_start_scrape = ctk.CTkButton(
            act_row, 
            text="🚀 BẮT ĐẦU CÀO VIDEO (NO LOGO - FULL HD 1080P)", 
            font=ctk.CTkFont(size=13, weight="bold"),
            fg_color="#0984e3",
            hover_color="#076db5",
            height=44,
            command=self.on_start_scrape
        )
        self.btn_start_scrape.pack(fill="x", pady=(0, 8))

        self.scrape_progress = ctk.CTkProgressBar(act_row)
        self.scrape_progress.pack(fill="x", pady=2)
        self.scrape_progress.set(0)

        self.lbl_scrape_status = ctk.CTkLabel(act_row, text="Sẵn sàng cào dữ liệu.", font=ctk.CTkFont(size=11), text_color="gray")
        self.lbl_scrape_status.pack(anchor="w")

    def on_change_scrape_folder(self):
        f = filedialog.askdirectory(title="Chọn thư mục lưu video cào về")
        if f:
            self.config_data["video_folder"] = f
            save_config(self.config_data)
            self.lbl_scrape_dest.configure(text=f)
            self.lbl_folder_path.configure(text=f, text_color="#3498db")
            self.refresh_video_list()

    def on_start_scrape(self):
        if self.is_scraping:
            return

        target_input = self.entry_scrape_url.get().strip()
        if not target_input:
            messagebox.showwarning("Cảnh báo", "Vui lòng nhập Link video hoặc Link kênh / @Username TikTok!")
            return

        out_folder = self.config_data.get("video_folder")
        if not out_folder or not os.path.exists(out_folder):
            out_folder = filedialog.askdirectory(title="Chọn thư mục lưu video tải về")
            if not out_folder:
                return
            self.config_data["video_folder"] = out_folder
            save_config(self.config_data)
            self.lbl_scrape_dest.configure(text=out_folder)
            self.lbl_folder_path.configure(text=out_folder, text_color="#3498db")

        mode = self.scrape_mode_var.get()
        save_caption = self.cb_save_caption.get()
        auto_refresh = self.cb_auto_refresh_queue.get()

        try:
            limit = int(self.entry_scrape_limit.get())
        except Exception:
            limit = 20

        self.is_scraping = True
        self.btn_start_scrape.configure(state="disabled")
        self.scrape_progress.set(0)
        self.lbl_scrape_status.configure(text="Đang chuẩn bị bóc tách dữ liệu...", text_color="#f39c12")

        def worker():
            self.thread_safe_log(f"=== BẮT ĐẦU TIẾN TRÌNH CÀO VIDEO KHÔNG LOGO ===")
            is_single_video = (
                mode == "single" or 
                "/video/" in target_input or 
                "vt.tiktok.com" in target_input or 
                "vm.tiktok.com" in target_input or 
                "/t/" in target_input
            )
            if is_single_video:
                self.thread_safe_log(f"Đang tải video lẻ không logo: {target_input}")
                res = self.scraper.download_video_no_watermark(target_input, out_folder, save_caption_txt=save_caption)
                if res:
                    self.after(0, lambda: self.lbl_scrape_status.configure(text="Tải xong video thành công!", text_color="#2ecc71"))
                    self.after(0, lambda: self.scrape_progress.set(1.0))
                    self.thread_safe_log("Đã tải xong video chất lượng cao không logo.")
                else:
                    self.after(0, lambda: self.lbl_scrape_status.configure(text="Không thể tải video này!", text_color="#e74c3c"))
            else:
                self.thread_safe_log(f"Bắt đầu cào kênh TikTok '{target_input}' (Tối đa {limit} video)...")
                def progress_cb(cur, tot):
                    self.after(0, lambda c=cur, t=tot: self.scrape_progress.set(c / t if t > 0 else 0))
                    self.after(0, lambda c=cur, t=tot: self.lbl_scrape_status.configure(
                        text=f"Đang tải video [{c}/{t}]...", text_color="#3498db"
                    ))

                downloaded = self.scraper.scrape_and_download_channel(
                    channel_input=target_input,
                    output_dir=out_folder,
                    max_count=limit,
                    progress_callback=progress_cb
                )
                self.after(0, lambda d=downloaded: self.lbl_scrape_status.configure(
                    text=f"Hoàn tất! Đã tải về {d} video Full HD không logo.", text_color="#2ecc71"
                ))
                self.after(0, lambda: self.scrape_progress.set(1.0))

            self.is_scraping = False
            self.after(0, lambda: self.btn_start_scrape.configure(state="normal"))
            if auto_refresh:
                self.after(0, self.refresh_video_list)

            try:
                winsound.MessageBeep(winsound.MB_ICONASTERISK)
            except Exception:
                pass

        threading.Thread(target=worker, daemon=True).start()

    # ------------------------------------------
    # TAB 3: HÀNG ĐỢI VIDEO & SPINTAX
    # ------------------------------------------
    def build_tab_videos(self):
        self.tab_videos.grid_rowconfigure(1, weight=1)
        self.tab_videos.grid_columnconfigure(0, weight=1)

        # Folder select card
        f_card = ctk.CTkFrame(self.tab_videos)
        f_card.grid(row=0, column=0, sticky="ew", pady=(0, 8), padx=5)

        f_row = ctk.CTkFrame(f_card, fg_color="transparent")
        f_row.pack(fill="x", padx=15, pady=8)

        self.btn_select_folder = ctk.CTkButton(f_row, text="📁 Chọn Thư Mục Video", width=170, command=self.on_select_folder)
        self.btn_select_folder.pack(side="left", padx=(0, 10))

        self.lbl_folder_path = ctk.CTkLabel(
            f_row, 
            text=self.config_data.get("video_folder") or "Chưa chọn thư mục video nào!",
            anchor="w",
            text_color="#3498db" if self.config_data.get("video_folder") else "gray"
        )
        self.lbl_folder_path.pack(side="left", fill="x", expand=True)

        ctk.CTkButton(f_row, text="Mở Folder", width=80, fg_color="#34495e", command=self.on_open_current_folder).pack(side="right", padx=3)
        ctk.CTkButton(f_row, text="Mở _done", width=80, fg_color="#2c3e50", command=self.on_open_done_folder).pack(side="right", padx=3)
        ctk.CTkButton(f_row, text="🔄 Làm mới", width=80, fg_color="#34495e", command=self.refresh_video_list).pack(side="right")

        # Video List Frame (Checklist)
        v_list_card = ctk.CTkFrame(self.tab_videos)
        v_list_card.grid(row=1, column=0, sticky="nsew", pady=(0, 8), padx=5)
        v_list_card.grid_rowconfigure(1, weight=1)
        v_list_card.grid_columnconfigure(0, weight=1)

        v_top = ctk.CTkFrame(v_list_card, fg_color="transparent")
        v_top.grid(row=0, column=0, sticky="ew", padx=15, pady=(8, 4))

        self.lbl_video_count_detailed = ctk.CTkLabel(v_top, text="Danh sách file video trong thư mục:", font=ctk.CTkFont(size=12, weight="bold"))
        self.lbl_video_count_detailed.pack(side="left")

        ctk.CTkButton(v_top, text="Bỏ chọn hết", width=80, height=24, fg_color="#2c3e50", command=self.deselect_all_videos).pack(side="right", padx=3)
        ctk.CTkButton(v_top, text="Chọn tất cả", width=80, height=24, fg_color="#34495e", command=self.select_all_videos).pack(side="right")

        self.v_scroll = ctk.CTkScrollableFrame(v_list_card)
        self.v_scroll.grid(row=1, column=0, sticky="nsew", padx=15, pady=(0, 10))

        # Caption & Spintax Card
        cap_card = ctk.CTkFrame(self.tab_videos)
        cap_card.grid(row=2, column=0, sticky="ew", padx=5)

        cap_header = ctk.CTkFrame(cap_card, fg_color="transparent")
        cap_header.pack(fill="x", padx=15, pady=(8, 2))

        ctk.CTkLabel(cap_header, text="Mô hình tiêu đề (Caption):", font=ctk.CTkFont(size=12, weight="bold")).pack(side="left", padx=(0, 15))

        self.caption_mode_var = ctk.StringVar(value=self.config_data.get("caption_mode", "filename"))
        ctk.CTkRadioButton(cap_header, text="Theo tên file", variable=self.caption_mode_var, value="filename").pack(side="left", padx=(0, 15))
        ctk.CTkRadioButton(cap_header, text="Theo file .txt", variable=self.caption_mode_var, value="txt_file").pack(side="left", padx=(0, 15))
        ctk.CTkRadioButton(cap_header, text="Trống (chỉ hashtag)", variable=self.caption_mode_var, value="custom").pack(side="left", padx=(0, 15))
        ctk.CTkRadioButton(cap_header, text="🎲 Spintax Thông Minh", variable=self.caption_mode_var, value="spintax").pack(side="left")

        # Spintax Row
        spintax_row = ctk.CTkFrame(cap_card, fg_color="transparent")
        spintax_row.pack(fill="x", padx=15, pady=4)

        ctk.CTkLabel(spintax_row, text="Mẫu Spintax:", width=90, anchor="w", font=ctk.CTkFont(size=11, weight="bold")).pack(side="left")
        self.entry_spintax = ctk.CTkEntry(spintax_row, placeholder_text="{Review|Mở hộp|Đánh giá} {sản phẩm|món này} cực xịn {nhé mọi người|ạ}!")
        self.entry_spintax.insert(0, self.config_data.get("spintax_caption", "{Review|Trải nghiệm|Mở hộp} {sản phẩm|món đồ} cực đỉnh {này|nhé cả nhà}!"))
        self.entry_spintax.pack(side="left", fill="x", expand=True, padx=(0, 8))

        btn_test_spin = ctk.CTkButton(spintax_row, text="🎲 Xem Thử", width=90, fg_color="#8e44ad", command=self.on_test_spintax)
        btn_test_spin.pack(side="right")

        # Hashtags Row
        hash_row = ctk.CTkFrame(cap_card, fg_color="transparent")
        hash_row.pack(fill="x", padx=15, pady=(4, 10))

        ctk.CTkLabel(hash_row, text="Hashtags:", width=90, anchor="w", font=ctk.CTkFont(size=11, weight="bold")).pack(side="left")
        self.entry_hashtags = ctk.CTkEntry(hash_row, placeholder_text="#fyp #xuhuong #trending #viral...")
        self.entry_hashtags.insert(0, self.config_data.get("hashtags", "#fyp #xuhuong #trending"))
        self.entry_hashtags.pack(side="left", fill="x", expand=True)

    # ------------------------------------------
    # TAB 4: QUẢN LÝ TÀI KHOẢN & PROXY
    # ------------------------------------------
    def build_tab_accounts(self):
        self.tab_accounts.grid_rowconfigure(1, weight=1)
        self.tab_accounts.grid_columnconfigure(0, weight=1)

        # Top Add Account bar
        top_acc_bar = ctk.CTkFrame(self.tab_accounts)
        top_acc_bar.grid(row=0, column=0, sticky="ew", pady=(0, 8), padx=5)

        bar_inner = ctk.CTkFrame(top_acc_bar, fg_color="transparent")
        bar_inner.pack(fill="x", padx=15, pady=8)

        self.new_acc_entry = ctk.CTkEntry(bar_inner, placeholder_text="Nhập tên nick TikTok cần thêm...", width=260)
        self.new_acc_entry.pack(side="left", padx=(0, 8))

        ctk.CTkButton(bar_inner, text="+ Thêm Nick", width=90, fg_color="#27ae60", command=self.on_add_account).pack(side="left", padx=(0, 10))
        ctk.CTkButton(bar_inner, text="📥 Nhập Hàng Loạt", width=130, fg_color="#2980b9", command=self.on_open_bulk_dialog).pack(side="left", padx=(0, 10))

        self.btn_check_all_login = ctk.CTkButton(
            bar_inner, 
            text="⚡ Quét Trạng Thái Tất Cả Nick", 
            width=180, 
            fg_color="#8e44ad",
            command=self.on_check_all_accounts_login
        )
        self.btn_check_all_login.pack(side="right")

        # Accounts List Frame
        acc_manage_card = ctk.CTkFrame(self.tab_accounts)
        acc_manage_card.grid(row=1, column=0, sticky="nsew", padx=5)
        acc_manage_card.grid_rowconfigure(1, weight=1)
        acc_manage_card.grid_columnconfigure(0, weight=1)

        # Header
        h_frame = ctk.CTkFrame(acc_manage_card, fg_color="#2c3e50")
        h_frame.grid(row=0, column=0, sticky="ew", padx=15, pady=(10, 4))

        ctk.CTkLabel(h_frame, text="Tài Khoản TikTok", width=160, anchor="w", font=ctk.CTkFont(size=11, weight="bold")).pack(side="left", padx=6)
        ctk.CTkLabel(h_frame, text="Proxy Gán", width=150, anchor="w", font=ctk.CTkFont(size=11, weight="bold")).pack(side="left", padx=6)
        ctk.CTkLabel(h_frame, text="Trạng Thái Phiên", width=150, anchor="w", font=ctk.CTkFont(size=11, weight="bold")).pack(side="left", padx=6)
        ctk.CTkLabel(h_frame, text="Hành Động & Thiết Bị", width=320, anchor="w", font=ctk.CTkFont(size=11, weight="bold")).pack(side="left", padx=6)

        self.acc_manage_scroll = ctk.CTkScrollableFrame(acc_manage_card)
        self.acc_manage_scroll.grid(row=1, column=0, sticky="nsew", padx=15, pady=(0, 10))

        self.render_account_manager_table()

    # ------------------------------------------
    # TAB 5: LÁCH BẢN QUYỀN & CÀI ĐẶT 2026
    # ------------------------------------------
    def build_tab_settings(self):
        scroll_settings = ctk.CTkScrollableFrame(self.tab_settings)
        scroll_settings.pack(fill="both", expand=True, padx=5, pady=5)

        # CARD 1: LÁCH BẢN QUYỀN & CHỐNG QUÉT AI
        card_reup = ctk.CTkFrame(scroll_settings)
        card_reup.pack(fill="x", pady=6, padx=10)

        ctk.CTkLabel(card_reup, text="🛡️ CÔNG NGHỆ LÁCH BẢN QUYỀN (ANTI-REUP 2026)", font=ctk.CTkFont(size=13, weight="bold"), text_color="#2ecc71").pack(anchor="w", padx=15, pady=(10, 4))
        
        self.switch_anti_reup = ctk.CTkSwitch(card_reup, text="Bật đổi mã băm Hash MD5 & SHA-256 (Giữ nguyên 100% chất lượng video)", onvalue=True, offvalue=False)
        self.switch_anti_reup.pack(anchor="w", padx=15, pady=4)
        if self.config_data.get("anti_reup_enabled", True):
            self.switch_anti_reup.select()

        self.switch_deep_reup = ctk.CTkSwitch(card_reup, text="Deep Anti-Reup: Tiêm giả lập Metadata Camera (iPhone 16 Pro / S24 Ultra) & Timestamp ngẫu nhiên", onvalue=True, offvalue=False)
        self.switch_deep_reup.pack(anchor="w", padx=15, pady=4)
        if self.config_data.get("deep_anti_reup", True):
            self.switch_deep_reup.select()

        self.switch_prevent_dup = ctk.CTkSwitch(card_reup, text="Chống đăng lặp: Tự động đối chiếu database lịch sử từng nick, bỏ qua nếu đã từng đăng", onvalue=True, offvalue=False)
        self.switch_prevent_dup.pack(anchor="w", padx=15, pady=(4, 10))
        if self.config_data.get("prevent_duplicate", True):
            self.switch_prevent_dup.select()

        # CARD 2: QUYỀN RIÊNG TƯ & TƯƠNG TÁC TIKTOK STUDIO
        card_studio_opts = ctk.CTkFrame(scroll_settings)
        card_studio_opts.pack(fill="x", pady=6, padx=10)

        ctk.CTkLabel(card_studio_opts, text="⚙️ CẤU HÌNH TIKTOK STUDIO & QUYỀN RIÊNG TƯ", font=ctk.CTkFont(size=13, weight="bold"), text_color="#3498db").pack(anchor="w", padx=15, pady=(10, 4))

        priv_row = ctk.CTkFrame(card_studio_opts, fg_color="transparent")
        priv_row.pack(fill="x", padx=15, pady=4)
        ctk.CTkLabel(priv_row, text="Quyền riêng tư mặc định:", width=180, anchor="w").pack(side="left")
        self.priv_var = ctk.StringVar(value=self.config_data.get("privacy", "public"))
        ctk.CTkRadioButton(priv_row, text="Công khai (Public)", variable=self.priv_var, value="public").pack(side="left", padx=10)
        ctk.CTkRadioButton(priv_row, text="Bạn bè (Friends)", variable=self.priv_var, value="friends").pack(side="left", padx=10)
        ctk.CTkRadioButton(priv_row, text="Riêng tư (Private)", variable=self.priv_var, value="private").pack(side="left")

        interact_row = ctk.CTkFrame(card_studio_opts, fg_color="transparent")
        interact_row.pack(fill="x", padx=15, pady=4)
        ctk.CTkLabel(interact_row, text="Cho phép tương tác:", width=180, anchor="w").pack(side="left")
        
        self.cb_comment = ctk.CTkCheckBox(interact_row, text="Bình luận (Comments)")
        self.cb_comment.pack(side="left", padx=10)
        if self.config_data.get("allow_comment", True): self.cb_comment.select()

        self.cb_duet = ctk.CTkCheckBox(interact_row, text="Duet")
        self.cb_duet.pack(side="left", padx=10)
        if self.config_data.get("allow_duet", True): self.cb_duet.select()

        self.cb_stitch = ctk.CTkCheckBox(interact_row, text="Stitch")
        self.cb_stitch.pack(side="left")
        if self.config_data.get("allow_stitch", True): self.cb_stitch.select()

        self.switch_ai_label = ctk.CTkSwitch(card_studio_opts, text="Gán nhãn 'Nội dung do AI tạo' (Bắt buộc theo chuẩn kiểm duyệt TikTok 2026 nếu dùng video AI)", onvalue=True, offvalue=False)
        self.switch_ai_label.pack(anchor="w", padx=15, pady=(6, 10))
        if self.config_data.get("ai_content_label", False):
            self.switch_ai_label.select()

        # CARD 3: HẸN GIỜ ĐĂNG THÔNG MINH (SMART SCHEDULE)
        card_sched = ctk.CTkFrame(scroll_settings)
        card_sched.pack(fill="x", pady=6, padx=10)

        ctk.CTkLabel(card_sched, text="⏰ LÊN LỊCH ĐĂNG HẸN GIỜ (SMART SCHEDULE)", font=ctk.CTkFont(size=13, weight="bold"), text_color="#f39c12").pack(anchor="w", padx=15, pady=(10, 4))

        self.switch_schedule = ctk.CTkSwitch(card_sched, text="Bật chế độ hẹn giờ phát hành (Schedule Post trên TikTok Studio)", onvalue=True, offvalue=False)
        self.switch_schedule.pack(anchor="w", padx=15, pady=4)
        if self.config_data.get("schedule_mode", False):
            self.switch_schedule.select()

        sched_inputs = ctk.CTkFrame(card_sched, fg_color="transparent")
        sched_inputs.pack(fill="x", padx=15, pady=(4, 10))

        ctk.CTkLabel(sched_inputs, text="Bắt đầu sau:").pack(side="left", padx=(0, 5))
        self.entry_sched_start = ctk.CTkEntry(sched_inputs, width=60)
        self.entry_sched_start.insert(0, str(self.config_data.get("schedule_start_minutes", 30)))
        self.entry_sched_start.pack(side="left", padx=(0, 15))
        ctk.CTkLabel(sched_inputs, text="phút.").pack(side="left", padx=(0, 20))

        ctk.CTkLabel(sched_inputs, text="Mỗi video cách nhau:").pack(side="left", padx=(0, 5))
        self.entry_sched_interval = ctk.CTkEntry(sched_inputs, width=60)
        self.entry_sched_interval.insert(0, str(self.config_data.get("schedule_interval_minutes", 45)))
        self.entry_sched_interval.pack(side="left", padx=(0, 15))
        ctk.CTkLabel(sched_inputs, text="phút.").pack(side="left")

        # CARD 4: CÀI ĐẶT HỆ THỐNG
        card_sys = ctk.CTkFrame(scroll_settings)
        card_sys.pack(fill="x", pady=6, padx=10)

        ctk.CTkLabel(card_sys, text="🛠️ HỆ THỐNG & HIỂN THỊ", font=ctk.CTkFont(size=13, weight="bold"), text_color="#9b59b6").pack(anchor="w", padx=15, pady=(10, 4))

        self.switch_headless = ctk.CTkSwitch(card_sys, text="Hiện cửa sổ trình duyệt Chrome khi đang tự động đăng", onvalue=False, offvalue=True)
        self.switch_headless.pack(anchor="w", padx=15, pady=4)
        self.switch_headless.select() if not self.config_data.get("headless", False) else self.switch_headless.deselect()

        self.switch_move_done = ctk.CTkSwitch(card_sys, text="Tự động dọn video đã đăng xong vào thư mục '_done'", onvalue=True, offvalue=False)
        self.switch_move_done.pack(anchor="w", padx=15, pady=4)
        if self.config_data.get("auto_move_done", True):
            self.switch_move_done.select()

        self.switch_sound = ctk.CTkSwitch(card_sys, text="Phát âm thanh chuông báo khi hoàn thành toàn bộ hàng đợi", onvalue=True, offvalue=False)
        self.switch_sound.pack(anchor="w", padx=15, pady=4)
        if self.config_data.get("sound_alert", True):
            self.switch_sound.select()

        # Delay slider
        delay_f = ctk.CTkFrame(card_sys, fg_color="transparent")
        delay_f.pack(fill="x", padx=15, pady=(6, 15))
        
        self.lbl_delay = ctk.CTkLabel(delay_f, text=f"Giãn cách nghỉ giữa các lần đăng: {self.config_data.get('delay_seconds', 30)} giây")
        self.lbl_delay.pack(anchor="w")

        self.delay_slider = ctk.CTkSlider(delay_f, from_=10, to=180, number_of_steps=34, command=self.on_delay_change)
        self.delay_slider.set(self.config_data.get("delay_seconds", 30))
        self.delay_slider.pack(fill="x", pady=4)

    # ------------------------------------------
    # TAB 7: LỊCH SỬ & BÁO CÁO
    # ------------------------------------------
    def build_tab_history(self):
        self.tab_history.grid_rowconfigure(1, weight=1)
        self.tab_history.grid_columnconfigure(0, weight=1)

        top_h = ctk.CTkFrame(self.tab_history, fg_color="transparent")
        top_h.grid(row=0, column=0, sticky="ew", padx=10, pady=8)

        ctk.CTkLabel(top_h, text="📊 Lịch Sử Đăng Video & Xuất Báo Cáo", font=ctk.CTkFont(size=14, weight="bold")).pack(side="left")

        ctk.CTkButton(top_h, text="📥 Xuất Báo Cáo Excel / CSV", width=170, fg_color="#2980b9", command=self.on_export_csv).pack(side="right", padx=5)
        ctk.CTkButton(top_h, text="🗑 Xoá Lịch Sử", width=100, fg_color="#c0392b", command=self.on_clear_history).pack(side="right", padx=5)
        ctk.CTkButton(top_h, text="🔄 Tải Lại", width=80, fg_color="#34495e", command=self.render_history_table).pack(side="right", padx=5)

        h_card = ctk.CTkFrame(self.tab_history)
        h_card.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 10))
        h_card.grid_rowconfigure(1, weight=1)
        h_card.grid_columnconfigure(0, weight=1)

        # Header
        head = ctk.CTkFrame(h_card, fg_color="#2c3e50")
        head.grid(row=0, column=0, sticky="ew", padx=10, pady=(8, 2))

        ctk.CTkLabel(head, text="Thời Gian", width=140, anchor="w", font=ctk.CTkFont(size=11, weight="bold")).pack(side="left", padx=5)
        ctk.CTkLabel(head, text="Tài Khoản", width=120, anchor="w", font=ctk.CTkFont(size=11, weight="bold")).pack(side="left", padx=5)
        ctk.CTkLabel(head, text="Tên Video", width=220, anchor="w", font=ctk.CTkFont(size=11, weight="bold")).pack(side="left", padx=5)
        ctk.CTkLabel(head, text="Proxy", width=110, anchor="w", font=ctk.CTkFont(size=11, weight="bold")).pack(side="left", padx=5)
        ctk.CTkLabel(head, text="Trạng Thái", width=140, anchor="w", font=ctk.CTkFont(size=11, weight="bold")).pack(side="left", padx=5)

        self.hist_scroll = ctk.CTkScrollableFrame(h_card)
        self.hist_scroll.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 8))

        self.render_history_table()

    # ==========================================
    # LOGGING & HELPERS
    # ==========================================
    def thread_safe_log(self, message):
        self.after(0, self._append_log, message)

    def _append_log(self, message):
        self.txt_log.insert("end", message + "\n")
        self.txt_log.see("end")

    def clear_logs(self):
        self.txt_log.delete("1.0", "end")

    def on_delay_change(self, val):
        sec = int(val)
        self.lbl_delay.configure(text=f"Giãn cách nghỉ giữa các lần đăng: {sec} giây")
        self.config_data["delay_seconds"] = sec
        save_config(self.config_data)

    def on_test_spintax(self):
        spin_raw = self.entry_spintax.get().strip()
        if not spin_raw:
            messagebox.showinfo("Thông báo", "Vui lòng nhập mẫu Spintax trước!")
            return
        result = parse_spintax(spin_raw)
        messagebox.showinfo("🎲 Kết Quả Spintax Ngẫu Nhiên", f"Mẫu gốc:\n{spin_raw}\n\nBiến thể được sinh ngẫu nhiên:\n👉 \"{result}\"")

    # ==========================================
    # ACCOUNT MANAGEMENT LOGIC
    # ==========================================
    def render_account_list(self):
        """Render sidebar checklist."""
        for w in self.acc_scroll.winfo_children():
            w.destroy()

        accounts = self.config_data.get("accounts", [])
        proxies = self.config_data.get("account_proxies", {})
        self.account_vars.clear()

        if not accounts:
            lbl_empty = ctk.CTkLabel(self.acc_scroll, text="Chưa có nick nào.\nVào Tab 'Quản Lý Nick' để thêm!", text_color="gray", font=ctk.CTkFont(size=11))
            lbl_empty.pack(pady=10)
            self.lbl_stat_accounts.configure(text="Nick: 0 tài khoản")
            return

        for acc in accounts:
            var = ctk.BooleanVar(value=True)
            self.account_vars[acc] = var

            p_path = get_profile_path(acc)
            has_profile = os.path.exists(p_path)
            has_proxy = bool(proxies.get(acc))

            row = ctk.CTkFrame(self.acc_scroll, fg_color="transparent")
            row.pack(fill="x", pady=2)

            cb = ctk.CTkCheckBox(row, text=acc, variable=var, font=ctk.CTkFont(size=11))
            cb.pack(side="left")

            b_frame = ctk.CTkFrame(row, fg_color="transparent")
            b_frame.pack(side="right")

            if has_proxy:
                ctk.CTkLabel(b_frame, text="🌐", font=ctk.CTkFont(size=10)).pack(side="left", padx=1)

            ctk.CTkLabel(
                b_frame, 
                text="[OK]" if has_profile else "[Mới]", 
                font=ctk.CTkFont(size=10),
                text_color="#2ecc71" if has_profile else "#e67e22"
            ).pack(side="left")

        self.lbl_stat_accounts.configure(text=f"Nick: {len(accounts)} tài khoản ({len(proxies)} có Proxy)")

    def render_account_manager_table(self):
        """Render full table in Tab 4."""
        for w in self.acc_manage_scroll.winfo_children():
            w.destroy()

        accounts = self.config_data.get("accounts", [])
        proxies = self.config_data.get("account_proxies", {})
        self.account_status_labels.clear()

        if not accounts:
            ctk.CTkLabel(self.acc_manage_scroll, text="Chưa có tài khoản nào. Hãy nhập tên nick ở trên!", text_color="gray").pack(pady=20)
            return

        for acc in accounts:
            row = ctk.CTkFrame(self.acc_manage_scroll, fg_color="transparent")
            row.pack(fill="x", pady=4)

            # Col 1: Acc Name
            ctk.CTkLabel(row, text=acc, width=160, anchor="w", font=ctk.CTkFont(size=12, weight="bold")).pack(side="left", padx=6)

            # Col 2: Proxy
            prx = proxies.get(acc, "IP Mạng Thật")
            prx_display = prx[:18] + "..." if len(prx) > 18 else prx
            ctk.CTkLabel(row, text=prx_display, width=150, anchor="w", font=ctk.CTkFont(size=11), text_color="#9b59b6" if prx != "IP Mạng Thật" else "gray").pack(side="left", padx=6)

            # Col 3: Status
            p_path = get_profile_path(acc)
            has_profile = os.path.exists(p_path)
            status_txt = "Đã lưu Profile" if has_profile else "Chưa login"
            status_color = "#2ecc71" if has_profile else "#f39c12"

            lbl_st = ctk.CTkLabel(row, text=status_txt, width=150, anchor="w", font=ctk.CTkFont(size=11), text_color=status_color)
            lbl_st.pack(side="left", padx=6)
            self.account_status_labels[acc] = lbl_st

            # Col 4: Action Buttons
            act_f = ctk.CTkFrame(row, fg_color="transparent")
            act_f.pack(side="left", padx=6)

            ctk.CTkButton(act_f, text="🔑 Đăng nhập", width=80, height=24, fg_color="#1f538d", command=lambda a=acc: self.login_specific_account(a)).pack(side="left", padx=2)
            ctk.CTkButton(act_f, text="🌐 Proxy", width=58, height=24, fg_color="#8e44ad", command=lambda a=acc: self.open_proxy_for_account(a)).pack(side="left", padx=2)
            ctk.CTkButton(act_f, text="📱 Thiết Bị & Log", width=110, height=24, fg_color="#16a085", hover_color="#117a65", command=lambda a=acc: self.open_device_and_log_dialog(a)).pack(side="left", padx=2)
            ctk.CTkButton(act_f, text="🗑 Xoá", width=48, height=24, fg_color="#c0392b", command=lambda a=acc: self.delete_specific_account(a)).pack(side="left", padx=2)

    def open_device_and_log_dialog(self, account_name):
        AccountDeviceAndLogDialog(self, account_name, on_change_callback=self.render_account_manager_table)

    def select_all_accounts(self):
        for var in self.account_vars.values():
            var.set(True)

    def deselect_all_accounts(self):
        for var in self.account_vars.values():
            var.set(False)

    def on_add_account(self):
        name = self.new_acc_entry.get().strip()
        if not name:
            messagebox.showwarning("Cảnh báo", "Vui lòng nhập tên tài khoản TikTok!")
            return
        accounts = self.config_data.get("accounts", [])
        if name in accounts:
            messagebox.showinfo("Thông báo", "Tài khoản này đã tồn tại.")
            return

        accounts.append(name)
        self.config_data["accounts"] = accounts
        save_config(self.config_data)

        self.new_acc_entry.delete(0, "end")
        self.render_account_list()
        self.render_account_manager_table()
        self.thread_safe_log(f"Đã thêm tài khoản: '{name}'")

    def on_open_bulk_dialog(self):
        BulkAccountDialog(self, on_import_callback=self.on_bulk_imported)

    def on_bulk_imported(self, imported_dict):
        accounts = self.config_data.get("accounts", [])
        proxies = self.config_data.get("account_proxies", {})
        added_count = 0

        for acc, prx in imported_dict.items():
            if acc not in accounts:
                accounts.append(acc)
                added_count += 1
            if prx:
                proxies[acc] = prx

        self.config_data["accounts"] = accounts
        self.config_data["account_proxies"] = proxies
        save_config(self.config_data)

        self.render_account_list()
        self.render_account_manager_table()
        messagebox.showinfo("Thành Công", f"Đã nhập thành công {added_count} nick mới vào hệ thống!")

    def open_proxy_for_account(self, account_name):
        current_proxy = self.config_data.get("account_proxies", {}).get(account_name, "")
        ProxyDialog(self, account_name, current_proxy, on_save_callback=self.on_save_proxy_for_account)

    def on_save_proxy_for_account(self, account_name, proxy_str):
        if "account_proxies" not in self.config_data:
            self.config_data["account_proxies"] = {}
        if proxy_str:
            self.config_data["account_proxies"][account_name] = proxy_str
            self.thread_safe_log(f"Đã gán Proxy cho nick '{account_name}': {proxy_str}")
        else:
            if account_name in self.config_data["account_proxies"]:
                del self.config_data["account_proxies"][account_name]
            self.thread_safe_log(f"Đã gỡ Proxy của nick '{account_name}'.")

        save_config(self.config_data)
        self.render_account_list()
        self.render_account_manager_table()

    def delete_specific_account(self, account_name):
        if messagebox.askyesno("Xác nhận", f"Bạn có chắc muốn xoá tài khoản '{account_name}'?"):
            accounts = [a for a in self.config_data.get("accounts", []) if a != account_name]
            proxies = self.config_data.get("account_proxies", {})
            if account_name in proxies:
                del proxies[account_name]

            self.config_data["accounts"] = accounts
            self.config_data["account_proxies"] = proxies
            save_config(self.config_data)
            self.render_account_list()
            self.render_account_manager_table()
            self.thread_safe_log(f"Đã xoá tài khoản '{account_name}'.")

    def login_specific_account(self, account_name):
        proxy_str = self.config_data.get("account_proxies", {}).get(account_name, "")
        self.thread_safe_log(f"Mở Chrome đăng nhập cho nick: '{account_name}'...")
        def run_login():
            self.uploader.launch_login_browser(account_name, proxy_str=proxy_str)
            self.after(0, self.render_account_list)
            self.after(0, self.render_account_manager_table)
        threading.Thread(target=run_login, daemon=True).start()

    def on_login_chrome(self):
        selected = [acc for acc, var in self.account_vars.items() if var.get()]
        if not selected:
            messagebox.showinfo("Thông báo", "Vui lòng tick chọn ít nhất 1 tài khoản ở danh sách bên trái!")
            return
        self.login_specific_account(selected[0])

    def on_check_all_accounts_login(self):
        accounts = self.config_data.get("accounts", [])
        if not accounts:
            messagebox.showinfo("Thông báo", "Chưa có tài khoản nào để kiểm tra!")
            return

        self.btn_check_all_login.configure(state="disabled")
        self.thread_safe_log("=== BẮT ĐẦU KIỂM TRA PHIÊN ĐĂNG NHẬP TOÀN BỘ NICK ===")

        def worker():
            proxies = self.config_data.get("account_proxies", {})
            for acc in accounts:
                prx = proxies.get(acc, "")
                self.thread_safe_log(f"Đang kiểm tra nick '{acc}'...")
                alive, msg = self.uploader.check_login_status(acc, prx)
                color = "#2ecc71" if alive else "#e74c3c"
                if acc in self.account_status_labels:
                    lbl = self.account_status_labels[acc]
                    self.after(0, lambda l=lbl, m=msg, c=color: l.configure(text=m, text_color=c))
                self.thread_safe_log(f"[{acc}] Kết quả: {msg}")
                time.sleep(1)

            self.after(0, lambda: self.btn_check_all_login.configure(state="normal"))
            self.thread_safe_log("=== ĐÃ HOÀN TẤT KIỂM TRA PHIÊN TOÀN BỘ NICK ===")

        threading.Thread(target=worker, daemon=True).start()

    # ==========================================
    # VIDEO QUEUE LOGIC
    # ==========================================
    def on_select_folder(self):
        folder = filedialog.askdirectory(title="Chọn thư mục chứa video TikTok")
        if folder:
            self.config_data["video_folder"] = folder
            save_config(self.config_data)
            self.lbl_folder_path.configure(text=folder, text_color="#3498db")
            self.lbl_scrape_dest.configure(text=folder)
            self.refresh_video_list()

    def get_pending_videos(self):
        folder = self.config_data.get("video_folder")
        if not folder or not os.path.isdir(folder):
            return []
        all_files = os.listdir(folder)
        videos = [
            os.path.join(folder, f) for f in all_files 
            if f.lower().endswith(VIDEO_EXTENSIONS) and not f.startswith(".")
        ]
        return sorted(videos)

    def refresh_video_list(self):
        for w in self.v_scroll.winfo_children():
            w.destroy()

        videos = self.get_pending_videos()
        count = len(videos)
        total_size_mb = sum(os.path.getsize(v) for v in videos) / (1024 * 1024) if count > 0 else 0

        self.video_checkboxes.clear()
        self.lbl_stat_videos.configure(text=f"Video: {count} sẵn sàng ({total_size_mb:.1f} MB)")
        self.lbl_video_count_detailed.configure(text=f"Danh sách video ({count} file, {total_size_mb:.1f} MB):")

        if not videos:
            ctk.CTkLabel(self.v_scroll, text="Thư mục chưa có video nào hoặc chưa chọn thư mục!", text_color="gray").pack(pady=15)
            return

        for v_path in videos:
            fn = os.path.basename(v_path)
            f_mb = os.path.getsize(v_path) / (1024 * 1024)
            var = ctk.BooleanVar(value=True)
            self.video_checkboxes[v_path] = var

            row = ctk.CTkFrame(self.v_scroll, fg_color="transparent")
            row.pack(fill="x", pady=2)

            cb = ctk.CTkCheckBox(row, text=fn, variable=var, font=ctk.CTkFont(size=11))
            cb.pack(side="left")

            ctk.CTkLabel(row, text=f"{f_mb:.1f} MB", font=ctk.CTkFont(size=10), text_color="gray").pack(side="right", padx=10)

    def select_all_videos(self):
        for var in self.video_checkboxes.values():
            var.set(True)

    def deselect_all_videos(self):
        for var in self.video_checkboxes.values():
            var.set(False)

    def on_open_current_folder(self):
        folder = self.config_data.get("video_folder")
        if folder and os.path.exists(folder):
            os.startfile(folder)
        else:
            messagebox.showinfo("Thông báo", "Chưa chọn thư mục video nào!")

    def on_open_done_folder(self):
        folder = self.config_data.get("video_folder")
        if folder and os.path.exists(folder):
            done_dir = os.path.join(folder, "_done")
            os.makedirs(done_dir, exist_ok=True)
            os.startfile(done_dir)
        else:
            messagebox.showinfo("Thông báo", "Chưa chọn thư mục video nào!")

    # ==========================================
    # HISTORY & EXPORT
    # ==========================================
    def render_history_table(self):
        for w in self.hist_scroll.winfo_children():
            w.destroy()

        records = load_history()
        if not records:
            ctk.CTkLabel(self.hist_scroll, text="Chưa có lịch sử đăng nào.", text_color="gray").pack(pady=20)
            return

        for rec in records:
            row = ctk.CTkFrame(self.hist_scroll, fg_color="transparent")
            row.pack(fill="x", pady=2)

            time_str = rec.get("time", "")
            acc = rec.get("account", "")
            video = rec.get("video", "")
            proxy = rec.get("proxy", "IP Gốc")
            status = rec.get("status", "")

            color = "#2ecc71" if "Thành công" in status else ("#e74c3c" if "Thất bại" in status else "#f39c12")

            ctk.CTkLabel(row, text=time_str, width=140, anchor="w", font=ctk.CTkFont(size=11)).pack(side="left", padx=5)
            ctk.CTkLabel(row, text=acc, width=120, anchor="w", font=ctk.CTkFont(size=11, weight="bold")).pack(side="left", padx=5)
            ctk.CTkLabel(row, text=video[:28] + "..." if len(video) > 28 else video, width=220, anchor="w", font=ctk.CTkFont(size=11)).pack(side="left", padx=5)
            ctk.CTkLabel(row, text=proxy[:15], width=110, anchor="w", font=ctk.CTkFont(size=10), text_color="#9b59b6" if proxy != "IP Gốc" else "gray").pack(side="left", padx=5)
            ctk.CTkLabel(row, text=status, width=140, anchor="w", font=ctk.CTkFont(size=11), text_color=color).pack(side="left", padx=5)

    def on_export_csv(self):
        file_path = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
            title="Lưu file báo cáo lịch sử đăng"
        )
        if file_path:
            ok, msg = export_history_to_csv(file_path)
            if ok:
                messagebox.showinfo("Thành Công", msg)
            else:
                messagebox.showerror("Lỗi", f"Không thể xuất file: {msg}")

    def on_clear_history(self):
        if messagebox.askyesno("Xác nhận", "Bạn có chắc muốn xoá toàn bộ lịch sử đã ghi nhận?"):
            clear_all_history()
            self.render_history_table()

    # ==========================================
    # AUTO UPLOAD WORKFLOW
    # ==========================================
    def on_start_upload(self):
        if self.is_running:
            return

        # Lấy danh sách video được tick chọn
        selected_videos = [v for v, var in self.video_checkboxes.items() if var.get()]
        if not selected_videos:
            messagebox.showwarning("Cảnh báo", "Không có video nào được chọn để đăng!\nVui lòng vào Tab 'Hàng Đợi' và tick chọn các video cần đăng.")
            return

        selected_accounts = [acc for acc, var in self.account_vars.items() if var.get()]
        if not selected_accounts:
            messagebox.showwarning("Cảnh báo", "Vui lòng tick chọn ít nhất 1 tài khoản TikTok ở danh sách bên trái!")
            return

        # Lưu toàn bộ cấu hình mới
        self.config_data["caption_mode"] = self.caption_mode_var.get()
        self.config_data["dist_mode"] = self.dist_mode_var.get()
        self.config_data["hashtags"] = self.entry_hashtags.get().strip()
        self.config_data["spintax_caption"] = self.entry_spintax.get().strip()
        self.config_data["headless"] = not self.switch_headless.get()
        self.config_data["auto_move_done"] = self.switch_move_done.get()
        self.config_data["anti_reup_enabled"] = self.switch_anti_reup.get()
        self.config_data["deep_anti_reup"] = self.switch_deep_reup.get()
        self.config_data["schedule_mode"] = self.switch_schedule.get()
        self.config_data["prevent_duplicate"] = self.switch_prevent_dup.get()
        self.config_data["privacy"] = self.priv_var.get()
        self.config_data["allow_comment"] = self.cb_comment.get()
        self.config_data["allow_duet"] = self.cb_duet.get()
        self.config_data["allow_stitch"] = self.cb_stitch.get()
        self.config_data["ai_content_label"] = self.switch_ai_label.get()
        self.config_data["sound_alert"] = self.switch_sound.get()

        try:
            self.config_data["schedule_start_minutes"] = int(self.entry_sched_start.get())
            self.config_data["schedule_interval_minutes"] = int(self.entry_sched_interval.get())
        except Exception:
            pass

        save_config(self.config_data)

        # Chuyển ngay sang tab studio để quan sát
        self.tabview.set("🚀 Đăng Video")

        self.is_running = True
        self.stop_requested = False
        self.btn_start.configure(state="disabled")
        self.btn_stop.configure(state="normal")
        self.progress_bar.set(0)

        self.active_thread = threading.Thread(
            target=self.run_upload_process, 
            args=(selected_videos, selected_accounts),
            daemon=True
        )
        self.active_thread.start()

    def on_stop_upload(self):
        if self.is_running:
            self.stop_requested = True
            self.thread_safe_log("ĐÃ NHẬN LỆNH DỪNG! Đang hoàn tất video hiện tại...")
            self.lbl_progress_status.configure(text="Đang dừng...")

    def run_upload_process(self, videos, accounts):
        delay_sec = self.config_data.get("delay_seconds", 30)
        headless = self.config_data.get("headless", False)
        hashtags = self.config_data.get("hashtags", "")
        auto_move = self.config_data.get("auto_move_done", True)
        caption_mode = self.config_data.get("caption_mode", "filename")
        spintax_template = self.config_data.get("spintax_caption", "")
        dist_mode = self.config_data.get("dist_mode", "round_robin")
        anti_reup = self.config_data.get("anti_reup_enabled", True)
        deep_reup = self.config_data.get("deep_anti_reup", True)
        schedule_mode = self.config_data.get("schedule_mode", False)
        sched_start = self.config_data.get("schedule_start_minutes", 30)
        sched_interval = self.config_data.get("schedule_interval_minutes", 45)
        prevent_dup = self.config_data.get("prevent_duplicate", True)
        privacy = self.config_data.get("privacy", "public")
        allow_comment = self.config_data.get("allow_comment", True)
        allow_duet = self.config_data.get("allow_duet", True)
        allow_stitch = self.config_data.get("allow_stitch", True)
        ai_content = self.config_data.get("ai_content_label", False)
        sound_alert = self.config_data.get("sound_alert", True)
        proxies = self.config_data.get("account_proxies", {})

        jobs = []
        if dist_mode == "round_robin":
            for i, v in enumerate(videos):
                acc = accounts[i % len(accounts)]
                jobs.append((v, acc))
        else:
            for v in videos:
                for acc in accounts:
                    jobs.append((v, acc))

        total_jobs = len(jobs)
        uploaded_count = 0
        skipped_count = 0

        self.thread_safe_log(f"=== BẮT ĐẦU: {len(videos)} VIDEO | {len(accounts)} NICK | TỔNG CỘNG: {total_jobs} LƯỢT ĐĂNG ===")
        if anti_reup:
            self.thread_safe_log("🛡️ Chế độ Lách Bản Quyền: ĐÃ BẬT (Đổi mã Hash MD5, SHA256 & Metadata).")
        if deep_reup:
            self.thread_safe_log("📸 Deep Anti-Reup: Tiêm chữ ký Camera iPhone 16 Pro / S24 Ultra & Randomize Timestamp.")
        if prevent_dup:
            self.thread_safe_log("🔍 Chế độ Chống Trùng Lặp: ĐÃ BẬT (Đối chiếu DB lịch sử từng nick).")
        if schedule_mode:
            self.thread_safe_log(f"⏰ Hẹn Giờ Thông Minh: Bắt đầu +{sched_start}m, giãn cách +{sched_interval}m mỗi video.")

        for idx, (video_path, current_acc) in enumerate(jobs):
            if self.stop_requested:
                self.thread_safe_log("Tiến trình đã được dừng lại theo yêu cầu của bạn.")
                break

            file_name = os.path.basename(video_path)
            acc_proxy = proxies.get(current_acc, "")

            # 1. KIỂM TRA CHỐNG LẶP THEO LỊCH SỬ NICK
            if prevent_dup and is_video_uploaded_to_account(current_acc, file_name):
                self.thread_safe_log(f"⚠️ [BỎ QUA TRÙNG LẶP] Video '{file_name}' đã từng đăng thành công lên nick '{current_acc}'. Bỏ qua!")
                skipped_count += 1
                if auto_move and os.path.exists(video_path):
                    if all(is_video_uploaded_to_account(a, file_name) for a in accounts):
                        move_to_done_folder(video_path)
                        self.thread_safe_log(f"Video '{file_name}' đã hoàn tất mọi kênh, dọn sang '_done'.")
                continue

            self.after(0, lambda i=idx, fn=file_name, acc=current_acc: self.lbl_progress_status.configure(
                text=f"[{i+1}/{total_jobs}] Đang đăng '{fn}' lên nick '{acc}'..."
            ))
            self.after(0, lambda progress=(idx / total_jobs): self.progress_bar.set(progress))

            # Tính toán Caption
            caption = ""
            if caption_mode == "filename":
                base_name = os.path.splitext(file_name)[0]
                caption = base_name.replace("_", " ").replace("-", " ")
            elif caption_mode == "txt_file":
                txt_path = os.path.splitext(video_path)[0] + ".txt"
                if os.path.exists(txt_path):
                    try:
                        with open(txt_path, "r", encoding="utf-8") as f:
                            caption = f.read().strip()
                    except Exception:
                        caption = os.path.splitext(file_name)[0]
                else:
                    caption = os.path.splitext(file_name)[0]
            elif caption_mode == "spintax":
                caption = parse_spintax(spintax_template)
            else:
                caption = ""

            # Tính thời gian hẹn giờ (nếu bật Schedule Mode)
            sched_minutes = 0
            if schedule_mode:
                sched_minutes = sched_start + (uploaded_count * sched_interval)

            # Thực thi Upload
            success = self.uploader.upload_video(
                account_name=current_acc,
                video_path=video_path,
                caption=caption,
                hashtags=hashtags,
                headless=headless,
                proxy_str=acc_proxy,
                anti_reup=anti_reup,
                deep_anti_reup=deep_reup,
                schedule_minutes=sched_minutes,
                privacy=privacy,
                allow_comment=allow_comment,
                allow_duet=allow_duet,
                allow_stitch=allow_stitch,
                ai_content=ai_content
            )

            if success:
                uploaded_count += 1
                if auto_move and os.path.exists(video_path):
                    if dist_mode == "round_robin" or all(is_video_uploaded_to_account(a, file_name) for a in accounts):
                        move_to_done_folder(video_path)
                        self.thread_safe_log(f"Đã di chuyển '{file_name}' vào thư mục '_done'.")

            # Nghỉ giữa các video (Delay)
            if idx < total_jobs - 1 and not self.stop_requested:
                self.thread_safe_log(f"Đang nghỉ {delay_sec} giây trước khi chuyển video tiếp theo...")
                for s in range(delay_sec):
                    if self.stop_requested:
                        break
                    time.sleep(1)

        self.after(0, lambda: self.progress_bar.set(1.0))
        self.thread_safe_log(f"=== KẾT THÚC TIẾN TRÌNH: Thành công {uploaded_count} lượt, Bỏ qua trùng lặp {skipped_count} lượt! ===")
        
        if sound_alert:
            try:
                winsound.MessageBeep(winsound.MB_ICONASTERISK)
            except Exception:
                pass

        self.after(0, self.finish_upload_process, uploaded_count, total_jobs, skipped_count)

    def finish_upload_process(self, uploaded, total, skipped=0):
        self.is_running = False
        self.btn_start.configure(state="normal")
        self.btn_stop.configure(state="disabled")
        msg = f"Hoàn thành! Đã đăng thành công: {uploaded}/{total} lượt."
        if skipped > 0:
            msg += f" (Đã tự động bỏ qua {skipped} lượt trùng lặp)."
        self.lbl_progress_status.configure(text=msg)
        self.refresh_video_list()
        self.render_history_table()
        messagebox.showinfo("Thành Công", f"Đã hoàn tất tiến trình!\n- Đăng thành công: {uploaded} lượt\n- Bỏ qua trùng lặp: {skipped} lượt.")

if __name__ == "__main__":
    app = TikTokManagerApp()
    app.mainloop()
