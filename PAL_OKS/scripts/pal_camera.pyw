import sys
import os
import ctypes
import traceback
import tkinter as tk
from tkinter import messagebox
import threading
import time

try:
    import cv2
    from PIL import Image, ImageTk
except ImportError:
    root = tk.Tk()
    root.withdraw()
    messagebox.showerror("Missing Dependencies", "Please install opencv-python and Pillow:\n\npython -m pip install opencv-python Pillow")
    sys.exit(1)

try:
    from ui_utilities import apply_window_dwm, minimize_window, RECT
except ImportError:
    try:
        from scripts.ui_utilities import apply_window_dwm, minimize_window, RECT
    except ImportError as e:
        ctypes.windll.user32.MessageBoxW(0, f"Critical Import Error: {e}\nEnsure ui_utilities.py is in the same folder or scripts folder.", "PAL Camera Error", 0x10)
        sys.exit(1)

try:
    import config_manager
except ImportError:
    config_manager = None

class WebcamApp:
    def __init__(self, root):
        self.root = root
        self.root.withdraw()
        self.root.title("PAL Camera")
        self.root.overrideredirect(True)

        self.root.configure(bg="#232323")
        
        self.setup_custom_titlebar()
        self.root.update_idletasks()
        self.min_width = self.dummy_lbl.winfo_reqwidth() + self.min_btn.winfo_reqwidth() + self.close_btn.winfo_reqwidth() + self.rot_btn.winfo_reqwidth()
        
        self.width = self.min_width
        self.height = 100
        self.root.geometry(f"{self.width}x{self.height}")
        self.root.resizable(True, True)
        
        self.cap = None
        self.running = False
        self.photo = None
        self.image_id = None
        self.rotation = 0
        self.zoom_level = 1.0
        self.offset_x = 0
        self.offset_y = 0
        self.frame_w = 640
        self.frame_h = 480
        self.saved_w = 0
        self.saved_h = 0
        self.saved_x = None
        self.saved_y = None
        
        if config_manager:
            try:
                config = config_manager.load_config()
                self.rotation = int(config.get("CAMERA_ROTATION", 0))
                self.zoom_level = float(config.get("CAMERA_ZOOM", 1.0))
                self.offset_x = float(config.get("CAMERA_OFFSET_X", 0))
                self.offset_y = float(config.get("CAMERA_OFFSET_Y", 0))
                w_val = config.get("CAMERA_WIN_W", 0)
                h_val = config.get("CAMERA_WIN_H", 0)
                self.saved_w = int(w_val) if w_val else 0
                self.saved_h = int(h_val) if h_val else 0
                x_val = config.get("CAMERA_WIN_X")
                y_val = config.get("CAMERA_WIN_Y")
                if x_val is not None and x_val != '': self.saved_x = int(x_val)
                if y_val is not None and y_val != '': self.saved_y = int(y_val)
            except (ValueError, TypeError):
                self.rotation = 0
                self.zoom_level = 1.0
                self.offset_x = 0
                self.offset_y = 0
                self.saved_x = None
                self.saved_y = None
        
        self._resize_mode = None
        self._moving = False
        self._cursor_mode = ""
        self.aspect_ratio = 0
        self._save_job = None
        
        self.main_frame = tk.Frame(self.root, bg="#232323")
        self.main_frame.pack(fill="both", expand=True, padx=1, pady=1)
        
        self.canvas = tk.Canvas(self.main_frame, bg="black", highlightthickness=0)
        self.canvas.pack(pady=5, padx=5, fill="both", expand=True)
        self.canvas.bind("<Configure>", self.on_resize)
        self.view_w = 1
        self.view_h = 1

        self._bind_window_events()

        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        threading.Thread(target=self.init_camera_thread, daemon=True).start()

    def on_resize(self, event):
        self.view_w = event.width
        self.view_h = event.height

    def setup_custom_titlebar(self):
        self.title_bar = tk.Frame(self.root, bg="#2d2d2d", relief="flat", bd=0)
        self.title_bar.pack(side="top", fill="x")

        self.title_lbl = tk.Label(self.title_bar, text="PAL Camera", bg="#2d2d2d", fg="#ffffff", font=("Segoe UI", 9, "bold"))
        self.title_lbl.place(x=2, rely=0.5, anchor="w")

        self.dummy_lbl = tk.Frame(self.title_bar, bg="#2d2d2d", width=10, height=30)
        self.dummy_lbl.pack(side="left")
        self.dummy_lbl.lower()

        self.close_btn = tk.Label(self.title_bar, text="✕", bg="#2d2d2d", fg="#ffffff", font=("Segoe UI", 9), width=4)
        self.close_btn.pack(side="right", fill="y")
        self.close_btn.bind("<Enter>", lambda e: self.close_btn.config(bg="#e81123"))
        self.close_btn.bind("<Leave>", lambda e: self.close_btn.config(bg="#2d2d2d"))
        self.close_btn.bind("<Button-1>", lambda e: self.on_close())

        self.min_btn = tk.Label(self.title_bar, text="—", bg="#2d2d2d", fg="#ffffff", font=("Segoe UI", 9, "bold"), width=4)
        self.min_btn.pack(side="right", fill="y")
        self.min_btn.bind("<Enter>", lambda e: self.min_btn.config(bg="#444444"))
        self.min_btn.bind("<Leave>", lambda e: self.min_btn.config(bg="#2d2d2d"))
        self.min_btn.bind("<Button-1>", lambda e: minimize_window(self.root))

        self.rot_btn = tk.Label(self.title_bar, text="↻", bg="#2d2d2d", fg="#ffffff", font=("Segoe UI", 11), width=4)
        self.rot_btn.pack(side="right", fill="y")
        self.rot_btn.bind("<Enter>", lambda e: self.rot_btn.config(bg="#444444"))
        self.rot_btn.bind("<Leave>", lambda e: self.rot_btn.config(bg="#2d2d2d"))
        self.rot_btn.bind("<Button-1>", lambda e: self.rotate_view())

    def rotate_view(self):
        self.rotation = (self.rotation + 90) % 360
        
        if self.aspect_ratio <= 0: return

        curr_w = self.root.winfo_width()
        curr_h = self.root.winfo_height()
        
        title_h = self.title_bar.winfo_height()
        if title_h < 1: title_h = 30
        pad_w = 12
        pad_h = title_h + 12
        
        vid_w = curr_w - pad_w
        vid_h = curr_h - pad_h
        
        new_vid_w = vid_h
        new_vid_h = vid_w
        
        new_w = int(new_vid_w + pad_w)
        new_h = int(new_vid_h + pad_h)

        min_vid_w = self.min_width - pad_w
        if new_w > self.min_width and abs(new_vid_h - min_vid_w) < 5:
            new_w = self.min_width
            effective_ar = self.aspect_ratio
            if self.rotation in [90, 270]:
                effective_ar = 1.0 / self.aspect_ratio
            new_vid_w = new_w - pad_w
            new_vid_h = new_vid_w / effective_ar
            new_h = int(new_vid_h + pad_h)

        wa_l, wa_t, wa_r, wa_b = self._get_work_area()
        max_w = wa_r - wa_l
        max_h = wa_b - wa_t

        if new_h > max_h:
            ratio = max_h / new_h
            new_h = max_h
            new_w = int(new_w * ratio)
        if new_w > max_w:
            ratio = max_w / new_w
            new_w = max_w
            new_h = int(new_h * ratio)
        
        if new_w < self.min_width:
            new_w = self.min_width
            effective_ar = self.aspect_ratio
            if self.rotation in [90, 270]:
                effective_ar = 1.0 / self.aspect_ratio
            new_vid_w = new_w - pad_w
            new_vid_h = new_vid_w / effective_ar
            new_h = int(new_vid_h + pad_h)
            
        center_x = self.root.winfo_x() + curr_w // 2
        center_y = self.root.winfo_y() + curr_h // 2
        new_x = int(center_x - new_w // 2)
        new_y = int(center_y - new_h // 2)
        
        self.root.geometry(f"{new_w}x{new_h}+{new_x}+{new_y}")
        
        self._schedule_save_settings()

    def _schedule_save_settings(self):
        if self._save_job:
            self.root.after_cancel(self._save_job)
        self._save_job = self.root.after(1000, self._save_camera_settings)

    def _save_camera_settings(self):
        self._save_job = None
        # Prevent saving if minimized or off-screen
        if self.root.state() == 'iconic' or self.root.winfo_x() < -30000: return
        if self.root.winfo_width() < 50 or self.root.winfo_height() < 50: return

        if config_manager:
            try:
                cfg = config_manager.load_config()
                cfg["CAMERA_ROTATION"] = str(self.rotation)
                cfg["CAMERA_ZOOM"] = str(self.zoom_level)
                cfg["CAMERA_OFFSET_X"] = str(self.offset_x)
                cfg["CAMERA_OFFSET_Y"] = str(self.offset_y)
                cfg["CAMERA_WIN_W"] = str(self.root.winfo_width())
                cfg["CAMERA_WIN_H"] = str(self.root.winfo_height())
                cfg["CAMERA_WIN_X"] = str(self.root.winfo_x())
                cfg["CAMERA_WIN_Y"] = str(self.root.winfo_y())
                config_manager.save_config(cfg)
            except Exception:
                pass # Fail silently

    def _get_work_area(self):
        try:
            import win32api, win32con
            monitor = win32api.MonitorFromWindow(self.root.winfo_id(), win32con.MONITOR_DEFAULTTONEAREST)
            work_area = win32api.GetMonitorInfo(monitor)['Work']
            return work_area
        except:
            try:
                rect = RECT()
                ctypes.windll.user32.SystemParametersInfoW(48, 0, ctypes.byref(rect), 0)
                return rect.left, rect.top, rect.right, rect.bottom
            except:
                return 0, 0, self.root.winfo_screenwidth(), self.root.winfo_screenheight()

    def _bind_window_events(self):
        widgets = [self.root, self.main_frame, self.title_bar, self.canvas, self.title_lbl, self.dummy_lbl]
        for w in widgets:
            w.bind("<Motion>", self._on_mouse_motion)
            w.bind("<ButtonPress-1>", self._on_mouse_press)
            w.bind("<B1-Motion>", self._on_mouse_drag)
            w.bind("<ButtonRelease-1>", self._on_mouse_release)
            w.bind("<MouseWheel>", self.on_mouse_wheel)

    def _get_resize_mode(self, x, y):
        w = self.root.winfo_width()
        h = self.root.winfo_height()
        m = 6
        mode = ""
        if y < m: mode += "n"
        elif y > h - m: mode += "s"
        if x < m: mode += "w"
        elif x > w - m: mode += "e"
        return mode if mode else None

    def _on_mouse_motion(self, event):
        x = event.x_root - self.root.winfo_rootx()
        y = event.y_root - self.root.winfo_rooty()
        mode = self._get_resize_mode(x, y)
        
        cursor = "arrow"
        if mode:
            if mode == "n" or mode == "s": cursor = "size_ns"
            elif mode == "e" or mode == "w": cursor = "size_we"
            elif mode == "nw" or mode == "se": cursor = "size_nw_se"
            elif mode == "ne" or mode == "sw": cursor = "size_ne_sw"
        
        if self._cursor_mode != cursor:
            self.root.config(cursor=cursor)
            self._cursor_mode = cursor

    def on_mouse_wheel(self, event):
        if event.delta > 0:
            self.zoom_level = min(self.zoom_level + 0.2, 5.0)
        else:
            self.zoom_level = max(self.zoom_level - 0.2, 1.0)
            if self.zoom_level == 1.0:
                self.offset_x = 0
                self.offset_y = 0
        self._schedule_save_settings()

    def _on_mouse_press(self, event):
        x = event.x_root - self.root.winfo_rootx()
        y = event.y_root - self.root.winfo_rooty()
        self._resize_mode = self._get_resize_mode(x, y)
        
        if self._resize_mode:
            self._start_x = event.x_root
            self._start_y = event.y_root
            self._start_geom = (self.root.winfo_x(), self.root.winfo_y(), self.root.winfo_width(), self.root.winfo_height())
            return "break"
        elif event.widget not in [self.close_btn, self.min_btn, self.rot_btn]:
            if y < 30 or event.widget in [self.title_bar, self.title_lbl, self.dummy_lbl]:
                self._move_start_x = event.x_root
                self._move_start_y = event.y_root
                self._win_start_x = self.root.winfo_x()
                self._win_start_y = self.root.winfo_y()
                self._moving = True
            elif self.zoom_level > 1.0:
                self._panning = True
                self._pan_start_x = event.x
                self._pan_start_y = event.y

    def _on_mouse_release(self, event):
        if self._resize_mode or self._moving or getattr(self, '_panning', False):
            self._schedule_save_settings()
        self._resize_mode = None
        self._moving = False
        self._panning = False

    def _on_mouse_drag(self, event):
        if self._resize_mode:
            dx = event.x_root - self._start_x
            dy = event.y_root - self._start_y
            x, y, w, h = self._start_geom
            
            if 'e' in self._resize_mode: w += dx
            elif 'w' in self._resize_mode: x += dx; w -= dx
            
            if 's' in self._resize_mode: h += dy
            elif 'n' in self._resize_mode: y += dy; h -= dy
            
            min_w = self.min_width

            if self.aspect_ratio > 0:
                title_h = self.title_bar.winfo_height()
                pad_w = 12
                pad_h = title_h + 12
                
                vid_w = w - pad_w
                vid_h = h - pad_h
                
                effective_ar = self.aspect_ratio
                if self.rotation in [90, 270]:
                    effective_ar = 1.0 / self.aspect_ratio
                
                if 'e' in self._resize_mode or 'w' in self._resize_mode:
                    vid_h = vid_w / effective_ar
                else:
                    vid_w = vid_h * effective_ar
                
                w = int(vid_w + pad_w)
                h = int(vid_h + pad_h)
                
                if w < min_w:
                    w = min_w
                    vid_w = w - pad_w
                    vid_h = vid_w / effective_ar
                    h = int(vid_h + pad_h)
                
                orig_x, orig_y, orig_w, orig_h = self._start_geom
                
                if 'w' in self._resize_mode:
                    x = (orig_x + orig_w) - w
                else:
                    x = orig_x
                if 'n' in self._resize_mode:
                    y = (orig_y + orig_h) - h
                else:
                    y = orig_y

            if w < min_w: w = min_w
            
            self.root.geometry(f"{w}x{h}+{x}+{y}")
            return "break"
            
        elif self._moving:
            dx = event.x_root - self._move_start_x
            dy = event.y_root - self._move_start_y
            self.root.geometry(f"+{self._win_start_x + dx}+{self._win_start_y + dy}")
            return "break"
        elif getattr(self, '_panning', False):
            dx = event.x - self._pan_start_x
            dy = event.y - self._pan_start_y
            
            if self.view_w > 0 and self.zoom_level > 0 and self.frame_w > 0:
                scale = (self.frame_w / self.zoom_level) / self.view_w
                self.offset_x -= dx * scale
                self.offset_y -= dy * scale
                self._pan_start_x = event.x
                self._pan_start_y = event.y
                self._schedule_save_settings()

    def set_appwindow(self):
        try:
            self.root.update_idletasks()
            apply_window_dwm(self.root)
            
            hwnd = ctypes.windll.user32.GetParent(self.root.winfo_id())
            if not hwnd: hwnd = self.root.winfo_id()
            
            script_dir = os.path.dirname(os.path.abspath(__file__))
            icon_path = os.path.join(script_dir, "PAL_Camera.ico")
            if os.path.exists(icon_path):
                hIcon = ctypes.windll.user32.LoadImageW(0, icon_path, 1, 0, 0, 0x00000010)
                if hIcon:
                    ctypes.windll.user32.SendMessageW(hwnd, 0x80, 1, hIcon)
                    ctypes.windll.user32.SendMessageW(hwnd, 0x80, 0, hIcon)
            
            self.root.wm_attributes("-topmost", 1)
            self.root.wm_attributes("-topmost", 0)
            self.root.deiconify()
            self.root.lift()
            self.root.focus_force()
        except Exception as e:
            print(f"Error setting app window: {e}")

    def init_camera_thread(self):
        try:
            idx = 0
            self.cap = cv2.VideoCapture(idx, cv2.CAP_DSHOW)
            if not self.cap.isOpened():
                self.root.after(0, lambda: [messagebox.showerror("Error", f"Could not open camera {idx}"), self.root.destroy()])
                return
            
            w = self.cap.get(cv2.CAP_PROP_FRAME_WIDTH)
            h = self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT)
            
            self.root.after(0, lambda: self.finalize_camera_start(w, h))
        except Exception as e:
            self.root.after(0, lambda: messagebox.showerror("Error", str(e)))

    def finalize_camera_start(self, w, h):
        if w > 0 and h > 0:
            self.aspect_ratio = w / h
            
            self.root.update_idletasks()
            title_h = self.title_bar.winfo_reqheight()
            if title_h < 20: title_h = 30
            
            pad_w = 12
            pad_h = title_h + 12
            
            if self.rotation in [90, 270]:
                target_vid_w = h * 0.20
            else:
                target_vid_w = w * 0.20
            
            target_win_w = int(target_vid_w + pad_w)
            
            buttons_w = self.min_btn.winfo_reqwidth() + self.close_btn.winfo_reqwidth() + self.rot_btn.winfo_reqwidth()
            full_title_w = 2 + self.title_lbl.winfo_reqwidth() + 5 + buttons_w
            
            if self.saved_w and self.saved_h:
                self.width = self.saved_w
                self.height = self.saved_h
                if self.width < self.min_width: self.width = self.min_width
                if self.height < 50: self.height = 50
            else:
                if target_win_w < full_title_w:
                    target_win_w = full_title_w

                if target_win_w < self.min_width:
                    target_win_w = self.min_width
                
                self.width = target_win_w
                
                final_vid_w = self.width - pad_w
                effective_ar = self.aspect_ratio
                if self.rotation in [90, 270]:
                    effective_ar = 1.0 / self.aspect_ratio
                final_vid_h = final_vid_w / effective_ar
                self.height = int(final_vid_h + pad_h)

            if self.saved_x is not None and self.saved_y is not None and self.saved_x > -30000 and self.saved_y > -30000:
                x = self.saved_x
                y = self.saved_y
            else:
                _, _, work_right, work_bottom = self._get_work_area()
                x = int(work_right - self.width)
                y = int(work_bottom - self.height)
            self.root.geometry(f"{self.width}x{self.height}+{x}+{y}")

        self.start_video_loop()
        self.root.after(10, self.set_appwindow)

    def start_video_loop(self):
        self.running = True
        threading.Thread(target=self.video_loop, daemon=True).start()

    def video_loop(self):
        while self.running:
            try:
                if not self.root.winfo_viewable():
                    time.sleep(0.5)
                    continue
            except:
                break
            
            if not self.cap or not self.cap.isOpened():
                time.sleep(0.1)
                continue

            ret, frame = self.cap.read()
            if ret:
                if self.rotation == 90:
                    frame = cv2.rotate(frame, cv2.ROTATE_90_CLOCKWISE)
                elif self.rotation == 180:
                    frame = cv2.rotate(frame, cv2.ROTATE_180)
                elif self.rotation == 270:
                    frame = cv2.rotate(frame, cv2.ROTATE_90_COUNTERCLOCKWISE)

                h, w = frame.shape[:2]
                self.frame_h = h
                self.frame_w = w

                if self.zoom_level > 1.0:
                    new_h, new_w = int(h / self.zoom_level), int(w / self.zoom_level)
                    
                    center_x = w / 2 + self.offset_x
                    center_y = h / 2 + self.offset_y
                    
                    x1 = int(center_x - new_w / 2)
                    y1 = int(center_y - new_h / 2)
                    
                    if x1 < 0: x1 = 0
                    if y1 < 0: y1 = 0
                    if x1 + new_w > w: x1 = w - new_w
                    if y1 + new_h > h: y1 = h - new_h
                    
                    self.offset_x = (x1 + new_w / 2) - w / 2
                    self.offset_y = (y1 + new_h / 2) - h / 2
                    
                    frame = frame[y1:y1+new_h, x1:x1+new_w]

                if self.view_w > 1 and self.view_h > 1:
                    frame = cv2.resize(frame, (self.view_w, self.view_h))
                cv2image = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                img = Image.fromarray(cv2image)
                try:
                    self.root.after(0, lambda i=img: self.update_image(i))
                except tk.TclError:
                    break
            else:
                time.sleep(0.1)

    def update_image(self, img):
        if not self.running: return
        try:
            photo = ImageTk.PhotoImage(image=img)
            self.photo = photo
            if self.image_id is None:
                x = (self.canvas.winfo_width() - photo.width()) // 2
                y = (self.canvas.winfo_height() - photo.height()) // 2
                self.image_id = self.canvas.create_image(x, y, image=photo, anchor=tk.NW)
            else:
                self.canvas.itemconfig(self.image_id, image=photo)
        except Exception as e:
            print(f"Error updating image: {e}", file=sys.stderr)

    def on_close(self):
        self.running = False
        if self._save_job:
            self.root.after_cancel(self._save_job)
            self._save_camera_settings()
            
        if self.cap: self.cap.release()
        self.root.destroy()

if __name__ == "__main__":
    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("PALCameraStandalone")
    except: 
        pass
    try:
        root = tk.Tk()
        app = WebcamApp(root)
        root.mainloop()
    except Exception as e:
        err_msg = f"Fatal Error: {e}\n\n{traceback.format_exc()}"
        print(err_msg, file=sys.stderr)
        ctypes.windll.user32.MessageBoxW(0, err_msg, "PAL Camera Error", 0x10)