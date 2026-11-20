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

ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

VIDEO_EXTENSIONS = ('.mp4', '.mov', '.avi', '.mkv', '.webm')

class ProxyDialog(ctk.CTkToplevel):
    def __init__(self, parent, account_name, current_proxy="", on_save_callback=None):
        super().__init__(parent)
        self.title(f"Cài Đặt Proxy - {account_name}")
        self.geometry("480x280")
        self.resizable(False, False)
        self.account_name = account_name
        self.on_save_callback = on_save_callback

        self.transient(parent)
        self.grab_set()

        lbl_title = ctk.CTkLabel(
            self, 
            text=f"🌐 Cấu Hình Proxy Cho: {account_name}", 
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
            width=420
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

class HistoryDialog(ctk.CTkToplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.title("📊 Lịch Sử Đăng Video - TikTok Manager Pro")
        self.geometry("880x520")
        self.minsize(750, 400)
        self.transient(parent)

        top_frame = ctk.CTkFrame(self, fg_color="transparent")
        top_frame.pack(fill="x", padx=15, pady=10)

        lbl_title = ctk.CTkLabel(top_frame, text="📋 Danh Sách Video Đã Xử Lý", font=ctk.CTkFont(size=16, weight="bold"))
        lbl_title.pack(side="left")

        btn_export = ctk.CTkButton(top_frame, text="📥 Xuất File Excel / CSV", width=140, fg_color="#2980b9", command=self.on_export_csv)
        btn_export.pack(side="right", padx=5)

        btn_clear = ctk.CTkButton(top_frame, text="🗑 Xoá Lịch Sử", width=100, fg_color="#c0392b", command=self.on_clear_history)
        btn_clear.pack(side="right", padx=5)

        self.scroll_frame = ctk.CTkScrollableFrame(self)
        self.scroll_frame.pack(fill="both", expand=True, padx=15, pady=(0, 15))

        self.render_history()

    def render_history(self):
        for w in self.scroll_frame.winfo_children():
            w.destroy()

        records = load_history()
        if not records:
            lbl_empty = ctk.CTkLabel(self.scroll_frame, text="Chưa có lịch sử đăng nào.", text_color="gray")
            lbl_empty.pack(pady=20)
            return

        h_frame = ctk.CTkFrame(self.scroll_frame, fg_color="#2c3e50")
        h_frame.pack(fill="x", pady=(0, 4), padx=2)

        ctk.CTkLabel(h_frame, text="Thời Gian", width=140, anchor="w", font=ctk.CTkFont(size=11, weight="bold")).pack(side="left", padx=5)
        ctk.CTkLabel(h_frame, text="Tài Khoản", width=120, anchor="w", font=ctk.CTkFont(size=11, weight="bold")).pack(side="left", padx=5)
        ctk.CTkLabel(h_frame, text="Tên Video", width=200, anchor="w", font=ctk.CTkFont(size=11, weight="bold")).pack(side="left", padx=5)
        ctk.CTkLabel(h_frame, text="Proxy", width=110, anchor="w", font=ctk.CTkFont(size=11, weight="bold")).pack(side="left", padx=5)
        ctk.CTkLabel(h_frame, text="Trạng Thái", width=150, anchor="w", font=ctk.CTkFont(size=11, weight="bold")).pack(side="left", padx=5)

        for rec in records:
            row = ctk.CTkFrame(self.scroll_frame, fg_color="transparent")
            row.pack(fill="x", pady=2, padx=2)

            time_str = rec.get("time", "")
            acc = rec.get("account", "")
            video = rec.get("video", "")
            proxy = rec.get("proxy", "IP Gốc")
            status = rec.get("status", "")

            color = "#2ecc71" if "Thành công" in status else ("#e74c3c" if "Thất bại" in status else "#f39c12")

            ctk.CTkLabel(row, text=time_str, width=140, anchor="w", font=ctk.CTkFont(size=11)).pack(side="left", padx=5)
            ctk.CTkLabel(row, text=acc, width=120, anchor="w", font=ctk.CTkFont(size=11, weight="bold")).pack(side="left", padx=5)
            ctk.CTkLabel(row, text=video[:25] + "..." if len(video) > 25 else video, width=200, anchor="w", font=ctk.CTkFont(size=11)).pack(side="left", padx=5)
            ctk.CTkLabel(row, text=proxy[:15], width=110, anchor="w", font=ctk.CTkFont(size=10), text_color="#9b59b6" if proxy != "IP Gốc" else "gray").pack(side="left", padx=5)
            ctk.CTkLabel(row, text=status, width=150, anchor="w", font=ctk.CTkFont(size=11), text_color=color).pack(side="left", padx=5)

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
            self.render_history()

class TikTokManagerApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("TikTok Manager Pro v3.1 - Quản Lý Đa Kênh • Chống Trùng Lặp 100%")
        self.geometry("1160x810")
        self.minsize(1050, 720)

        self.config_data = load_config()
        self.uploader = TikTokUploader(log_callback=self.thread_safe_log)
        self.is_running = False
        self.stop_requested = False
        self.active_thread = None

        self.account_vars = {}  # {acc_name: BooleanVar}

        self.build_ui()
        self.refresh_video_list()

    def build_ui(self):
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=1)

        # ==========================================
        # SIDEBAR (LEFT)
        # ==========================================
        self.sidebar_frame = ctk.CTkFrame(self, width=320, corner_radius=0)
        self.sidebar_frame.grid(row=0, column=0, sticky="nsew", padx=0, pady=0)
        self.sidebar_frame.grid_rowconfigure(4, weight=1)

        # App Title
        self.logo_label = ctk.CTkLabel(
            self.sidebar_frame, 
            text="TIKTOK MANAGER PRO", 
            font=ctk.CTkFont(size=20, weight="bold")
        )
        self.logo_label.grid(row=0, column=0, padx=20, pady=(15, 2))

        self.sub_label = ctk.CTkLabel(
            self.sidebar_frame, 
            text="Chống Trùng Lặp 3 Lớp • Đa Kênh • Proxy", 
            font=ctk.CTkFont(size=11),
            text_color="#2ecc71"
        )
        self.sub_label.grid(row=1, column=0, padx=20, pady=(0, 8))

        # Add account input
        self.add_acc_frame = ctk.CTkFrame(self.sidebar_frame, fg_color="transparent")
        self.add_acc_frame.grid(row=2, column=0, padx=15, pady=3, sticky="ew")
        
        self.new_acc_entry = ctk.CTkEntry(self.add_acc_frame, placeholder_text="Tên nick TikTok...")
        self.new_acc_entry.pack(side="left", fill="x", expand=True, padx=(0, 5))
        
        self.btn_add_acc = ctk.CTkButton(self.add_acc_frame, text="+ Thêm", width=65, command=self.on_add_account)
        self.btn_add_acc.pack(side="right")

        # Account List Header
        self.acc_header_label = ctk.CTkLabel(
            self.sidebar_frame, 
            text="Danh sách nick TikTok:", 
            font=ctk.CTkFont(size=13, weight="bold"),
            anchor="w"
        )
        self.acc_header_label.grid(row=3, column=0, padx=20, pady=(5, 2), sticky="w")

        # Scrollable Frame for Accounts
        self.acc_scroll = ctk.CTkScrollableFrame(self.sidebar_frame, label_text="Tài khoản & Proxy")
        self.acc_scroll.grid(row=4, column=0, padx=15, pady=2, sticky="nsew")

        self.render_account_list()

        # Account Action Buttons
        self.acc_actions_frame = ctk.CTkFrame(self.sidebar_frame, fg_color="transparent")
        self.acc_actions_frame.grid(row=5, column=0, padx=15, pady=3, sticky="ew")

        self.btn_config_proxy = ctk.CTkButton(
            self.acc_actions_frame, 
            text="🌐 Gán Proxy Cho Nick", 
            fg_color="#8e44ad",
            hover_color="#6c3483",
            command=self.on_open_proxy_dialog
        )
        self.btn_config_proxy.pack(fill="x", pady=2)

        self.btn_login_chrome = ctk.CTkButton(
            self.acc_actions_frame, 
            text="🔑 Đăng nhập Chrome", 
            fg_color="#1f538d",
            hover_color="#14375e",
            command=self.on_login_chrome
        )
        self.btn_login_chrome.pack(fill="x", pady=2)

        self.btn_delete_acc = ctk.CTkButton(
            self.acc_actions_frame, 
            text="🗑 Xoá nick đã chọn", 
            fg_color="#5c1d1d",
            hover_color="#3d1313",
            command=self.on_delete_account
        )
        self.btn_delete_acc.pack(fill="x", pady=2)

        # Settings Section
        self.settings_label = ctk.CTkLabel(
            self.sidebar_frame, 
            text="Cấu hình hệ thống:", 
            font=ctk.CTkFont(size=13, weight="bold"),
            anchor="w"
        )
        self.settings_label.grid(row=6, column=0, padx=20, pady=(4, 2), sticky="w")

        # Anti-Duplicate toggle (NEW)
        self.switch_prevent_dup = ctk.CTkSwitch(
            self.sidebar_frame, 
            text="Chống đăng lặp (Theo lịch sử)",
            onvalue=True, offvalue=False
        )
        self.switch_prevent_dup.grid(row=7, column=0, padx=20, pady=2, sticky="w")
        if self.config_data.get("prevent_duplicate", True):
            self.switch_prevent_dup.select()

        # Anti-Reup toggle
        self.switch_anti_reup = ctk.CTkSwitch(
            self.sidebar_frame, 
            text="🛡️ Lách bản quyền (Đổi MD5)",
            onvalue=True, offvalue=False
        )
        self.switch_anti_reup.grid(row=8, column=0, padx=20, pady=2, sticky="w")
        if self.config_data.get("anti_reup_enabled", True):
            self.switch_anti_reup.select()

        # Headless toggle
        self.switch_headless = ctk.CTkSwitch(
            self.sidebar_frame, 
            text="Hiện cửa sổ Chrome khi đăng",
            onvalue=False, offvalue=True
        )
        self.switch_headless.grid(row=9, column=0, padx=20, pady=2, sticky="w")
        self.switch_headless.select() if not self.config_data.get("headless", False) else self.switch_headless.deselect()

        # Auto move done toggle
        self.switch_move_done = ctk.CTkSwitch(
            self.sidebar_frame, 
            text="Chuyển video xong vào '_done'",
            onvalue=True, offvalue=False
        )
        self.switch_move_done.grid(row=10, column=0, padx=20, pady=2, sticky="w")
        if self.config_data.get("auto_move_done", True):
            self.switch_move_done.select()

        # Delay slider
        self.delay_frame = ctk.CTkFrame(self.sidebar_frame, fg_color="transparent")
        self.delay_frame.grid(row=11, column=0, padx=20, pady=(2, 6), sticky="ew")
        
        self.delay_val_label = ctk.CTkLabel(
            self.delay_frame, 
            text=f"Giãn cách: {self.config_data.get('delay_seconds', 30)} giây",
            font=ctk.CTkFont(size=12)
        )
        self.delay_val_label.pack(anchor="w")

        self.delay_slider = ctk.CTkSlider(
            self.delay_frame, 
            from_=10, to=180, 
            number_of_steps=34,
            command=self.on_delay_slider_change
        )
        self.delay_slider.set(self.config_data.get("delay_seconds", 30))
        self.delay_slider.pack(fill="x", pady=2)

        # History button
        self.btn_history = ctk.CTkButton(
            self.sidebar_frame, 
            text="📊 Xem Lịch Sử Đăng", 
            fg_color="#2c3e50",
            hover_color="#1a252f",
            command=self.on_open_history
        )
        self.btn_history.grid(row=12, column=0, padx=20, pady=(2, 10), sticky="ew")


        # ==========================================
        # MAIN CONTENT (RIGHT)
        # ==========================================
        self.main_frame = ctk.CTkFrame(self, corner_radius=0, fg_color="transparent")
        self.main_frame.grid(row=0, column=1, sticky="nsew", padx=15, pady=12)
        self.main_frame.grid_rowconfigure(3, weight=1)
        self.main_frame.grid_columnconfigure(0, weight=1)

        # ------------------------------------------
        # CARD 1: FOLDER VIDEO & QUEUE
        # ------------------------------------------
        self.folder_card = ctk.CTkFrame(self.main_frame)
        self.folder_card.grid(row=0, column=0, sticky="ew", pady=(0, 8))

        folder_header_frame = ctk.CTkFrame(self.folder_card, fg_color="transparent")
        folder_header_frame.pack(fill="x", padx=15, pady=8)

        self.btn_select_folder = ctk.CTkButton(
            folder_header_frame, 
            text="📁 Chọn Thư Mục Video", 
            width=170,
            command=self.on_select_folder
        )
        self.btn_select_folder.pack(side="left", padx=(0, 10))

        self.lbl_folder_path = ctk.CTkLabel(
            folder_header_frame, 
            text=self.config_data.get("video_folder") or "Chưa chọn thư mục video nào!",
            anchor="w",
            text_color="#3498db" if self.config_data.get("video_folder") else "gray"
        )
        self.lbl_folder_path.pack(side="left", fill="x", expand=True)

        self.btn_open_folder = ctk.CTkButton(
            folder_header_frame, 
            text="Mở Folder", 
            width=80, 
            fg_color="#34495e",
            command=self.on_open_current_folder
        )
        self.btn_open_folder.pack(side="right", padx=4)

        self.btn_open_done = ctk.CTkButton(
            folder_header_frame, 
            text="Mở _done", 
            width=80, 
            fg_color="#2c3e50",
            command=self.on_open_done_folder
        )
        self.btn_open_done.pack(side="right", padx=4)

        self.btn_refresh_videos = ctk.CTkButton(
            folder_header_frame, 
            text="🔄 Làm mới", 
            width=80, 
            fg_color="#34495e",
            command=self.refresh_video_list
        )
        self.btn_refresh_videos.pack(side="right")

        self.lbl_queue_stat = ctk.CTkLabel(
            self.folder_card, 
            text="Sẵn sàng: 0 video đang chờ đăng.",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color="#2ecc71"
        )
        self.lbl_queue_stat.pack(anchor="w", padx=15, pady=(0, 6))

        # ------------------------------------------
        # CARD 2: PHÂN PHỐI, HẸN GIỜ & CAPTION
        # ------------------------------------------
        self.caption_card = ctk.CTkFrame(self.main_frame)
        self.caption_card.grid(row=1, column=0, sticky="ew", pady=(0, 8))

        top_row = ctk.CTkFrame(self.caption_card, fg_color="transparent")
        top_row.pack(fill="x", padx=15, pady=(6, 2))

        lbl_dist = ctk.CTkLabel(top_row, text="Chế độ:", font=ctk.CTkFont(size=12, weight="bold"), width=70, anchor="w")
        lbl_dist.pack(side="left")

        self.dist_mode_var = ctk.StringVar(value=self.config_data.get("dist_mode", "round_robin"))
        rb_dist1 = ctk.CTkRadioButton(
            top_row, 
            text="Chia đều video cho các nick", 
            variable=self.dist_mode_var, 
            value="round_robin"
        )
        rb_dist1.pack(side="left", padx=(0, 15))

        rb_dist2 = ctk.CTkRadioButton(
            top_row, 
            text="Đăng tất cả lên mọi nick (Dàn vệ tinh)", 
            variable=self.dist_mode_var, 
            value="all_to_all"
        )
        rb_dist2.pack(side="left", padx=(0, 20))

        self.switch_schedule = ctk.CTkSwitch(
            top_row, 
            text="⏰ Hẹn giờ đăng (TikTok Studio)",
            onvalue=True, offvalue=False
        )
        self.switch_schedule.pack(side="right")

        cap_radio_frame = ctk.CTkFrame(self.caption_card, fg_color="transparent")
        cap_radio_frame.pack(fill="x", padx=15, pady=2)

        lbl_cap = ctk.CTkLabel(cap_radio_frame, text="Tiêu đề:", font=ctk.CTkFont(size=12, weight="bold"), width=70, anchor="w")
        lbl_cap.pack(side="left")

        self.caption_mode_var = ctk.StringVar(value=self.config_data.get("caption_mode", "filename"))
        r1 = ctk.CTkRadioButton(cap_radio_frame, text="Lấy theo tên file video", variable=self.caption_mode_var, value="filename")
        r1.pack(side="left", padx=(0, 15))

        r2 = ctk.CTkRadioButton(cap_radio_frame, text="Đọc từ file .txt tương ứng", variable=self.caption_mode_var, value="txt_file")
        r2.pack(side="left", padx=(0, 15))

        r3 = ctk.CTkRadioButton(cap_radio_frame, text="Caption trống (chỉ hashtag)", variable=self.caption_mode_var, value="custom")
        r3.pack(side="left")

        hash_frame = ctk.CTkFrame(self.caption_card, fg_color="transparent")
        hash_frame.pack(fill="x", padx=15, pady=(2, 8))

        lbl_hash = ctk.CTkLabel(hash_frame, text="Hashtags:", font=ctk.CTkFont(size=12, weight="bold"), width=70, anchor="w")
        lbl_hash.pack(side="left")

        self.entry_hashtags = ctk.CTkEntry(hash_frame, placeholder_text="#fyp #xuhuong #trending #viral...")
        self.entry_hashtags.insert(0, self.config_data.get("hashtags", "#fyp #xuhuong #trending"))
        self.entry_hashtags.pack(side="left", fill="x", expand=True)

        # ------------------------------------------
        # CARD 3: CONTROL & PROGRESS
        # ------------------------------------------
        self.control_card = ctk.CTkFrame(self.main_frame)
        self.control_card.grid(row=2, column=0, sticky="ew", pady=(0, 8))

        ctrl_inner = ctk.CTkFrame(self.control_card, fg_color="transparent")
        ctrl_inner.pack(fill="x", padx=15, pady=8)

        self.btn_start = ctk.CTkButton(
            ctrl_inner, 
            text="▶ BẮT ĐẦU ĐĂNG TỰ ĐỘNG", 
            font=ctk.CTkFont(size=14, weight="bold"),
            fg_color="#27ae60",
            hover_color="#1e8449",
            height=44,
            command=self.on_start_upload
        )
        self.btn_start.pack(side="left", fill="x", expand=True, padx=(0, 10))

        self.btn_stop = ctk.CTkButton(
            ctrl_inner, 
            text="⏹ DỪNG", 
            font=ctk.CTkFont(size=14, weight="bold"),
            fg_color="#c0392b",
            hover_color="#922b21",
            height=44,
            width=120,
            command=self.on_stop_upload,
            state="disabled"
        )
        self.btn_stop.pack(side="right")

        self.progress_bar = ctk.CTkProgressBar(self.control_card)
        self.progress_bar.pack(fill="x", padx=15, pady=(0, 4))
        self.progress_bar.set(0)

        self.lbl_progress_status = ctk.CTkLabel(
            self.control_card, 
            text="Trạng thái: Sẵn sàng.", 
            font=ctk.CTkFont(size=12),
            text_color="gray"
        )
        self.lbl_progress_status.pack(anchor="w", padx=15, pady=(0, 6))

        # ------------------------------------------
        # CARD 4: LOGS
        # ------------------------------------------
        self.log_card = ctk.CTkFrame(self.main_frame)
        self.log_card.grid(row=3, column=0, sticky="nsew")
        self.log_card.grid_rowconfigure(1, weight=1)
        self.log_card.grid_columnconfigure(0, weight=1)

        log_top = ctk.CTkFrame(self.log_card, fg_color="transparent")
        log_top.grid(row=0, column=0, sticky="ew", padx=15, pady=(6, 2))

        log_title = ctk.CTkLabel(log_top, text="📋 Nhật Ký Hoạt Động (Live Logs):", font=ctk.CTkFont(size=12, weight="bold"))
        log_title.pack(side="left")

        btn_clear_log = ctk.CTkButton(log_top, text="Xoá Log", width=70, height=24, fg_color="#4a4a4a", command=self.clear_logs)
        btn_clear_log.pack(side="right")

        self.txt_log = ctk.CTkTextbox(self.log_card, font=ctk.CTkFont(family="Consolas", size=11))
        self.txt_log.grid(row=1, column=0, sticky="nsew", padx=15, pady=(0, 10))

    # ==========================================
    # LOGGING HELPER
    # ==========================================
    def thread_safe_log(self, message):
        self.after(0, self._append_log, message)

    def _append_log(self, message):
        self.txt_log.insert("end", message + "\n")
        self.txt_log.see("end")

    def clear_logs(self):
        self.txt_log.delete("1.0", "end")

    # ==========================================
    # ACCOUNT & PROXY MANAGEMENT
    # ==========================================
    def render_account_list(self):
        for widget in self.acc_scroll.winfo_children():
            widget.destroy()

        accounts = self.config_data.get("accounts", [])
        proxies = self.config_data.get("account_proxies", {})
        self.account_vars.clear()

        if not accounts:
            lbl_empty = ctk.CTkLabel(self.acc_scroll, text="Chưa có nick nào.\nHãy nhập tên nick ở trên!", text_color="gray")
            lbl_empty.pack(pady=10)
            return

        for acc in accounts:
            var = ctk.BooleanVar(value=True)
            self.account_vars[acc] = var
            
            p_path = get_profile_path(acc)
            has_profile = os.path.exists(p_path)
            has_proxy = bool(proxies.get(acc))

            acc_frame = ctk.CTkFrame(self.acc_scroll, fg_color="transparent")
            acc_frame.pack(fill="x", pady=2)

            cb = ctk.CTkCheckBox(acc_frame, text=acc, variable=var, font=ctk.CTkFont(size=12))
            cb.pack(side="left", padx=(0, 5))

            badge_frame = ctk.CTkFrame(acc_frame, fg_color="transparent")
            badge_frame.pack(side="right")

            if has_proxy:
                badge_p = ctk.CTkLabel(
                    badge_frame, 
                    text="🌐Proxy",
                    font=ctk.CTkFont(size=10, weight="bold"),
                    text_color="#9b59b6"
                )
                badge_p.pack(side="left", padx=2)

            badge = ctk.CTkLabel(
                badge_frame, 
                text="[Profile OK]" if has_profile else "[Mới]",
                font=ctk.CTkFont(size=10),
                text_color="#2ecc71" if has_profile else "#e67e22"
            )
            badge.pack(side="left", padx=2)

    def on_add_account(self):
        name = self.new_acc_entry.get().strip()
        if not name:
            messagebox.showwarning("Cảnh báo", "Vui lòng nhập tên tài khoản/nick TikTok!")
            return
        
        accounts = self.config_data.get("accounts", [])
        if name in accounts:
            messagebox.showinfo("Thông báo", "Tài khoản này đã tồn tại trong danh sách.")
            return

        accounts.append(name)
        self.config_data["accounts"] = accounts
        save_config(self.config_data)

        self.new_acc_entry.delete(0, "end")
        self.render_account_list()
        self.thread_safe_log(f"Đã thêm tài khoản: '{name}'")

    def on_open_proxy_dialog(self):
        selected = [acc for acc, var in self.account_vars.items() if var.get()]
        if not selected:
            messagebox.showinfo("Thông báo", "Vui lòng tick chọn 1 tài khoản để gán Proxy!")
            return

        target_acc = selected[0]
        current_proxy = self.config_data.get("account_proxies", {}).get(target_acc, "")
        ProxyDialog(self, target_acc, current_proxy, on_save_callback=self.on_save_proxy_for_account)

    def on_save_proxy_for_account(self, account_name, proxy_str):
        if "account_proxies" not in self.config_data:
            self.config_data["account_proxies"] = {}
        
        if proxy_str:
            self.config_data["account_proxies"][account_name] = proxy_str
            self.thread_safe_log(f"Đã gán Proxy cho nick '{account_name}': {proxy_str}")
        else:
            if account_name in self.config_data["account_proxies"]:
                del self.config_data["account_proxies"][account_name]
            self.thread_safe_log(f"Đã xoá Proxy của nick '{account_name}' (Sẽ dùng IP mạng thật).")

        save_config(self.config_data)
        self.render_account_list()

    def on_delete_account(self):
        selected = [acc for acc, var in self.account_vars.items() if var.get()]
        if not selected:
            messagebox.showinfo("Thông báo", "Vui lòng tick chọn tài khoản muốn xoá.")
            return

        confirm = messagebox.askyesno("Xác nhận", f"Bạn có chắc muốn xoá {len(selected)} tài khoản đã chọn?")
        if confirm:
            accounts = [a for a in self.config_data.get("accounts", []) if a not in selected]
            proxies = self.config_data.get("account_proxies", {})
            for a in selected:
                if a in proxies:
                    del proxies[a]

            self.config_data["accounts"] = accounts
            self.config_data["account_proxies"] = proxies
            save_config(self.config_data)
            self.render_account_list()
            self.thread_safe_log(f"Đã xoá các tài khoản: {', '.join(selected)}")

    def on_login_chrome(self):
        selected = [acc for acc, var in self.account_vars.items() if var.get()]
        if not selected:
            messagebox.showinfo("Thông báo", "Vui lòng tick chọn 1 tài khoản để mở Chrome đăng nhập!")
            return

        target_acc = selected[0]
        proxy_str = self.config_data.get("account_proxies", {}).get(target_acc, "")
        self.thread_safe_log(f"Mở Chrome đăng nhập cho nick: '{target_acc}'...")
        
        def run_login():
            self.btn_login_chrome.configure(state="disabled")
            self.uploader.launch_login_browser(target_acc, proxy_str=proxy_str)
            self.after(0, lambda: self.btn_login_chrome.configure(state="normal"))
            self.after(0, self.render_account_list)

        threading.Thread(target=run_login, daemon=True).start()

    def on_open_history(self):
        HistoryDialog(self)

    # ==========================================
    # FOLDER & VIDEO QUEUE
    # ==========================================
    def on_select_folder(self):
        folder = filedialog.askdirectory(title="Chọn thư mục chứa video TikTok")
        if folder:
            self.config_data["video_folder"] = folder
            save_config(self.config_data)
            self.lbl_folder_path.configure(text=folder, text_color="#3498db")
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
        videos = self.get_pending_videos()
        count = len(videos)
        total_size_mb = sum(os.path.getsize(v) for v in videos) / (1024 * 1024) if count > 0 else 0
        
        self.lbl_queue_stat.configure(
            text=f"Sẵn sàng: {count} video đang chờ đăng. (Tổng dung lượng: {total_size_mb:.1f} MB)",
            text_color="#2ecc71" if count > 0 else "gray"
        )
        if count > 0:
            self.thread_safe_log(f"Thư mục hiện có {count} video ({total_size_mb:.1f} MB) sẵn sàng đăng.")

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

    def on_delay_slider_change(self, val):
        seconds = int(val)
        self.delay_val_label.configure(text=f"Giãn cách: {seconds} giây")
        self.config_data["delay_seconds"] = seconds
        save_config(self.config_data)

    # ==========================================
    # AUTO UPLOAD WORKFLOW
    # ==========================================
    def on_start_upload(self):
        if self.is_running:
            return

        videos = self.get_pending_videos()
        if not videos:
            messagebox.showwarning("Cảnh báo", "Không tìm thấy video nào trong thư mục đã chọn!\nVui lòng copy video vào folder hoặc chọn lại folder.")
            return

        selected_accounts = [acc for acc, var in self.account_vars.items() if var.get()]
        if not selected_accounts:
            messagebox.showwarning("Cảnh báo", "Vui lòng tick chọn ít nhất 1 tài khoản TikTok ở danh sách bên trái!")
            return

        # Save settings
        self.config_data["caption_mode"] = self.caption_mode_var.get()
        self.config_data["dist_mode"] = self.dist_mode_var.get()
        self.config_data["hashtags"] = self.entry_hashtags.get().strip()
        self.config_data["headless"] = not self.switch_headless.get()
        self.config_data["auto_move_done"] = self.switch_move_done.get()
        self.config_data["anti_reup_enabled"] = self.switch_anti_reup.get()
        self.config_data["schedule_mode"] = self.switch_schedule.get()
        self.config_data["prevent_duplicate"] = self.switch_prevent_dup.get()
        save_config(self.config_data)

        self.is_running = True
        self.stop_requested = False
        self.btn_start.configure(state="disabled")
        self.btn_stop.configure(state="normal")
        self.progress_bar.set(0)

        self.active_thread = threading.Thread(
            target=self.run_upload_process, 
            args=(videos, selected_accounts),
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
        dist_mode = self.config_data.get("dist_mode", "round_robin")
        anti_reup = self.config_data.get("anti_reup_enabled", True)
        schedule_mode = self.config_data.get("schedule_mode", False)
        prevent_dup = self.config_data.get("prevent_duplicate", True)
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
            self.thread_safe_log("🛡️ Chế độ Lách Bản Quyền: ĐÃ BẬT (Tự động đổi mã Hash MD5 & Metadata).")
        if prevent_dup:
            self.thread_safe_log("🔍 Chế độ Chống Trùng Lặp: ĐÃ BẬT (Kiểm tra đối chiếu lịch sử từng nick).")

        for idx, (video_path, current_acc) in enumerate(jobs):
            if self.stop_requested:
                self.thread_safe_log("Tiến trình đã được dừng lại theo yêu cầu của bạn.")
                break

            file_name = os.path.basename(video_path)
            acc_proxy = proxies.get(current_acc, "")

            # 1. KIỂM TRA CHỐNG LẶP VIDEO THEO LỊCH SỬ NICK
            if prevent_dup and is_video_uploaded_to_account(current_acc, file_name):
                self.thread_safe_log(f"⚠️ [BỎ QUA TRÙNG LẶP] Video '{file_name}' đã từng đăng thành công lên nick '{current_acc}'. Tự động bỏ qua!")
                skipped_count += 1
                if auto_move and os.path.exists(video_path):
                    # Nếu video này đã đăng trên tất cả nick được chọn thì dọn vào _done
                    if all(is_video_uploaded_to_account(a, file_name) for a in accounts):
                        move_to_done_folder(video_path)
                        self.thread_safe_log(f"Video '{file_name}' đã đăng đủ mọi nick, dọn sang '_done'.")
                continue

            self.after(0, lambda i=idx, fn=file_name, acc=current_acc: self.lbl_progress_status.configure(
                text=f"[{i+1}/{total_jobs}] Đang đăng '{fn}' lên nick '{acc}'..."
            ))
            self.after(0, lambda progress=(idx / total_jobs): self.progress_bar.set(progress))

            # Caption
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
            else:
                caption = ""

            schedule_mins = (idx + 1) * 60 if schedule_mode else 0

            success = self.uploader.upload_video(
                account_name=current_acc,
                video_path=video_path,
                caption=caption,
                hashtags=hashtags,
                headless=headless,
                proxy_str=acc_proxy,
                anti_reup=anti_reup,
                schedule_minutes=schedule_mins
            )

            if success:
                uploaded_count += 1
                is_last_for_video = (dist_mode == "round_robin") or (current_acc == accounts[-1])
                if auto_move and is_last_for_video and os.path.exists(video_path):
                    done_path = move_to_done_folder(video_path)
                    if done_path:
                        self.thread_safe_log(f"Đã chuyển '{file_name}' vào thư mục '_done'.")
            else:
                self.thread_safe_log(f"Đăng video '{file_name}' thất bại trên nick '{current_acc}'.")

            # Giãn cách
            if idx < total_jobs - 1 and not self.stop_requested:
                self.thread_safe_log(f"Chờ giãn cách {delay_sec} giây trước lượt tiếp theo...")
                for d in range(delay_sec):
                    if self.stop_requested:
                        break
                    time.sleep(1)

        self.after(0, lambda: self.progress_bar.set(1.0))
        self.thread_safe_log(f"=== KẾT THÚC: Thành công {uploaded_count} lượt, Bỏ qua trùng lặp {skipped_count} lượt! ===")
        
        try:
            winsound.MessageBeep(winsound.MB_ICONASTERISK)
        except Exception:
            pass

        self.after(0, self.finish_upload_process, uploaded_count, total_jobs, skipped_count)

    def finish_upload_process(self, uploaded, total, skipped=0):
        self.is_running = False
        self.btn_start.configure(state="normal")
        self.btn_stop.configure(state="disabled")
        msg = f"Hoàn thành! Đã đăng: {uploaded} lượt."
        if skipped > 0:
            msg += f" (Đã tự động bỏ qua {skipped} lượt trùng lặp)."
        self.lbl_progress_status.configure(text=msg)
        self.refresh_video_list()
        messagebox.showinfo("Thành Công", f"Đã hoàn tất tiến trình!\n- Đăng thành công: {uploaded} lượt\n- Tự động bỏ qua trùng lặp: {skipped} lượt.")

if __name__ == "__main__":
    app = TikTokManagerApp()
    app.mainloop()
