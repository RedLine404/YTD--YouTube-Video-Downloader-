import customtkinter as ctk
import threading
import time
import requests
import os
import sys
import subprocess
import ctypes
from PIL import Image
from io import BytesIO
from backend import DownloaderBackend

def resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

if sys.platform == "win32":
    try:
        myappid = 'mycustom.youtubedownloader.app.1.0'
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
    except Exception:
        pass

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

class DownloaderApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        
        self.title("YouTube Downloader")
        
        # Center the app on the screen
        window_width = 600
        window_height = 850
        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()
        x_pos = int((screen_width / 2) - (window_width / 2))
        y_pos = int((screen_height / 2) - (window_height / 2))
        self.geometry(f"{window_width}x{window_height}+{x_pos}+{y_pos}")
        
        try:
            self.iconbitmap(resource_path("icon.ico")) # here
        except Exception:
            pass

        self.cancel_event = threading.Event()
        self.last_download_path = ""
        
        # --- Input Section ---
        self.input_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.input_frame.pack(pady=30, padx=20, fill="x")
        
        self.url_entry = ctk.CTkEntry(self.input_frame, placeholder_text="Paste YouTube URL here...", height=40)
        self.url_entry.pack(side="left", padx=(0, 10), expand=True, fill="x")
        self.url_entry.focus() # Auto-focus
        
        self.fetch_btn = ctk.CTkButton(self.input_frame, text="Fetch", width=100, height=40, command=self.start_fetch)
        self.fetch_btn.pack(side="right")
        
        self.status_label = ctk.CTkLabel(self, text="", text_color="gray")
        self.status_label.pack(pady=5)
        
        # --- Video Info Section ---
        self.info_frame = ctk.CTkFrame(self, fg_color="transparent")
        
        self.thumbnail_label = ctk.CTkLabel(self.info_frame, text="")
        self.thumbnail_label.pack(pady=10)
        
        self.title_label = ctk.CTkLabel(self.info_frame, text="", font=ctk.CTkFont(size=18, weight="bold"), wraplength=500)
        self.title_label.pack(pady=10)
        
        # --- Progress & Actions Section ---
        self.progress_frame = ctk.CTkFrame(self.info_frame, fg_color="transparent")
        
        self.stats_label = ctk.CTkLabel(self.progress_frame, text="Speed: -- MB/s | ETA: --:--")
        self.stats_label.pack(pady=(0, 5))
        
        self.progress_bar = ctk.CTkProgressBar(self.progress_frame, width=400)
        self.progress_bar.set(0)
        self.progress_bar.pack(pady=5)
        
        self.percentage_label = ctk.CTkLabel(self.progress_frame, text="0%")
        self.percentage_label.pack(pady=(0, 10))
        
        self.action_frame = ctk.CTkFrame(self.info_frame, fg_color="transparent")
        self.action_frame.pack(pady=10)
        
        self.download_btn = ctk.CTkButton(self.action_frame, text="Download", height=40, command=self.start_download)
        self.download_btn.pack(side="left", padx=10)
        
        self.cancel_btn = ctk.CTkButton(self.action_frame, text="Cancel", height=40, fg_color="#C62828", hover_color="#B71C1C", command=self.cancel_download, state="disabled")
        self.cancel_btn.pack(side="right", padx=10)

        # Dropdown placed UNDER the download and cancel buttons
        self.res_var = ctk.StringVar(value="Select Resolution")
        self.res_dropdown = ctk.CTkOptionMenu(self.info_frame, variable=self.res_var, values=[])
        self.res_dropdown.pack(pady=15)

        # --- Completion Section (Hidden initially) ---
        self.completion_frame = ctk.CTkFrame(self.info_frame, fg_color="transparent")
        
        self.success_label = ctk.CTkLabel(self.completion_frame, text="Download Completed!", font=ctk.CTkFont(size=22, weight="bold"), text_color="#4CAF50")
        self.success_label.pack(pady=(10, 5))
        
        self.path_label = ctk.CTkLabel(self.completion_frame, text="", text_color="gray", wraplength=500)
        self.path_label.pack(pady=5)
        
        self.qol_btn_frame = ctk.CTkFrame(self.completion_frame, fg_color="transparent")
        self.qol_btn_frame.pack(pady=10)
        
        self.open_folder_btn = ctk.CTkButton(self.qol_btn_frame, text="Open Folder", height=35, command=self.open_download_folder)
        self.open_folder_btn.pack(side="left", padx=10)
        
        self.reset_btn = ctk.CTkButton(self.qol_btn_frame, text="Download Another", height=35, fg_color="#555555", hover_color="#444444", command=self.reset_ui)
        self.reset_btn.pack(side="right", padx=10)

    def update_status(self, text, color="white"):
        self.status_label.configure(text=text, text_color=color)

    def start_fetch(self):
        url = self.url_entry.get()
        if not url:
            self.update_status("Please enter a valid URL.", "red")
            return
        
        self.update_status("Fetching video data...", "lightblue")
        self.info_frame.pack_forget()
        self.completion_frame.pack_forget()
        self.progress_frame.pack_forget()
        
        self.action_frame.pack(pady=10)
        self.res_dropdown.pack(pady=15)  # Make sure it repacks after buttons
        
        self.download_btn.configure(state="normal")
        self.res_dropdown.configure(state="normal")
        
        self.fetch_btn.configure(state="disabled")
        threading.Thread(target=self.fetch_video_data, args=(url,), daemon=True).start()

    def fetch_video_data(self, url):
        if not DownloaderBackend.is_valid_url(url):
            self.after(0, self.update_status, "Invalid URL or network error.", "red")
            self.after(0, lambda: self.fetch_btn.configure(state="normal"))
            return
            
        try:
            info = DownloaderBackend.get_video_info(url)
            response = requests.get(info["thumbnail"])
            img_data = Image.open(BytesIO(response.content))
            ctk_img = ctk.CTkImage(light_image=img_data, dark_image=img_data, size=(480, 270))
            
            self.after(0, self.show_video_info, info, ctk_img)
        except Exception as e:
            self.after(0, self.update_status, f"Error fetching video: {e}", "red")
            self.after(0, lambda: self.fetch_btn.configure(state="normal"))

    def show_video_info(self, info, ctk_img):
        self.thumbnail_label.configure(image=ctk_img)
        self.title_label.configure(text=info["title"])
        
        if info["resolutions"]:
            self.res_dropdown.configure(values=info["resolutions"])
            self.res_var.set(info["resolutions"][0])
        else:
            self.res_dropdown.configure(values=["No streams found"])
            
        self.update_status("", "white")
        self.fetch_btn.configure(state="normal")
        self.info_frame.pack(fill="both", expand=True, padx=20)

    def start_download(self):
        url = self.url_entry.get()
        res = self.res_var.get()
        
        self.cancel_event.clear()
        self.update_status(f"Downloading {res}...", "lightblue")
        
        self.download_btn.configure(state="disabled")
        self.cancel_btn.configure(state="normal")
        self.res_dropdown.configure(state="disabled")
        
        # Force UI to update states immediately so the Cancel button is fully ready
        self.update() 
        
        self.progress_bar.set(0)
        self.percentage_label.configure(text="0%")
        self.stats_label.configure(text="Speed: -- MB/s | ETA: --:--")
        
        # Pack progress bar above the action frame
        self.progress_frame.pack(pady=15, before=self.action_frame)
        
        threading.Thread(target=self.download_video, args=(url, res), daemon=True).start()

    def update_progress_ui(self, downloaded, total, speed_bps, eta_seconds):
        percentage = downloaded / total
        speed_mbs = speed_bps / (1024 * 1024)
        eta_str = time.strftime('%M:%S', time.gmtime(eta_seconds))
        
        self.after(0, self.progress_bar.set, percentage)
        self.after(0, self.percentage_label.configure, text=f"{int(percentage * 100)}%")
        self.after(0, self.stats_label.configure, text=f"Speed: {speed_mbs:.2f} MB/s | ETA: {eta_str}")

    def download_video(self, url, res):
        try:
            file_path = DownloaderBackend.download_video(
                url=url, 
                resolution=res, 
                progress_callback=self.update_progress_ui, 
                cancel_event=self.cancel_event
            )
            self.last_download_path = file_path
            self.after(0, self.show_completion_ui, file_path)
            self.after(0, self.update_status, "", "white")
        except Exception as e:
            if str(e) == "DOWNLOAD_CANCELLED":
                self.after(0, self.update_status, "Download cancelled and file deleted.", "orange")
            else:
                self.after(0, self.update_status, f"Download failed: {e}", "red")
            self.after(0, lambda: self.download_btn.configure(state="normal"))
        finally:
            self.after(0, lambda: self.cancel_btn.configure(state="disabled"))
            self.after(0, lambda: self.res_dropdown.configure(state="normal"))

    def cancel_download(self):
        self.cancel_event.set()
        self.update_status("Cancelling...", "orange")
        self.cancel_btn.configure(state="disabled")
        self.download_btn.configure(state="normal")
        self.res_dropdown.configure(state="normal")

    def show_completion_ui(self, file_path):
        self.action_frame.pack_forget()
        self.res_dropdown.pack_forget()
        self.path_label.configure(text=f"Saved to: {file_path}")
        self.completion_frame.pack(pady=10)

    def open_download_folder(self):
        if not self.last_download_path: return
        folder = os.path.dirname(self.last_download_path)
        
        if sys.platform == "win32":
            os.startfile(folder)
        elif sys.platform == "darwin":
            subprocess.Popen(["open", folder])
        else:
            subprocess.Popen(["xdg-open", folder])

    def reset_ui(self):
        self.url_entry.delete(0, "end")
        self.info_frame.pack_forget()
        self.update_status("Ready for the next video.", "white")
        self.url_entry.focus()

if __name__ == "__main__":
    app = DownloaderApp()
    app.mainloop()