import tkinter as tk
from tkinter import ttk, filedialog, scrolledtext
import ctypes
from ctypes import wintypes
import time
import webbrowser
import os

class RECT(ctypes.Structure):
    _fields_ = [("left", ctypes.c_long), ("top", ctypes.c_long),
                ("right", ctypes.c_long), ("bottom", ctypes.c_long)]

def center_toplevel(parent, dialog, width=None, height=None):
    parent.update_idletasks()
    parent_width = parent.winfo_width()
    parent_height = parent.winfo_height()
    parent_x = parent.winfo_rootx()
    parent_y = parent.winfo_rooty()
    
    dialog.update_idletasks()
    dialog_width = width if width else dialog.winfo_reqwidth()
    dialog_height = height if height else dialog.winfo_reqheight()
    
    center_x = parent_x + (parent_width // 2) - (dialog_width // 2)
    center_y = parent_y + (parent_height // 2) - (dialog_height // 2)

    screen_width = dialog.winfo_screenwidth()
    screen_height = dialog.winfo_screenheight()

    if center_x < 0: center_x = 0
    if center_y < 0: center_y = 0
    if center_x + dialog_width > screen_width: center_x = screen_width - dialog_width
    if center_y + dialog_height > screen_height: center_y = screen_height - dialog_height

    dialog.geometry(f"+{center_x}+{center_y}")

def apply_window_dwm(window, is_dialog=False, enable_maximize=False):
    window.update_idletasks()
    try:
        hwnd = ctypes.windll.user32.GetParent(window.winfo_id())
        if not hwnd: hwnd = window.winfo_id()
        
        value = ctypes.c_int(1)
        if ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, 20, ctypes.byref(value), ctypes.sizeof(value)) != 0:
            ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, 19, ctypes.byref(value), ctypes.sizeof(value))
        
        ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, 33, ctypes.byref(value), ctypes.sizeof(value))

        if not is_dialog:
            ex_style = ctypes.windll.user32.GetWindowLongW(hwnd, -20)
            ex_style |= 0x00040000
            ctypes.windll.user32.SetWindowLongW(hwnd, -20, ex_style)
            
            style = ctypes.windll.user32.GetWindowLongW(hwnd, -16)
            style |= 0x00080000 | 0x00020000
            if enable_maximize:
                style |= 0x00010000
            ctypes.windll.user32.SetWindowLongW(hwnd, -16, style)
            
        ctypes.windll.user32.SetWindowPos(hwnd, 0, 0, 0, 0, 0, 0x0002 | 0x0001 | 0x0004 | 0x0020)
    except Exception:
        pass

def minimize_window(window):
    try:
        hwnd = ctypes.windll.user32.GetParent(window.winfo_id())
        if not hwnd: hwnd = window.winfo_id()
        ctypes.windll.user32.ShowWindow(hwnd, 6)
    except: pass

class WindowDragger:
    def __init__(self, window, *widgets):
        self.window = window
        for w in widgets:
            w.bind("<Button-1>", self.start_move)
            w.bind("<B1-Motion>", self.do_move)
        self._drag_start_x = 0
        self._drag_start_y = 0

    def start_move(self, event):
        self._drag_start_x = event.x_root
        self._drag_start_y = event.y_root
        self._win_start_x = self.window.winfo_x()
        self._win_start_y = self.window.winfo_y()

    def do_move(self, event):
        delta_x = event.x_root - self._drag_start_x
        delta_y = event.y_root - self._drag_start_y
        x = self._win_start_x + delta_x
        y = self._win_start_y + delta_y
        self.window.geometry(f"+{x}+{y}")

def setup_custom_titlebar(window, title_text, on_close=None, on_minimize=None):
    title_bar = tk.Frame(window, bg="#2d2d2d", relief="flat", bd=0)
    title_bar.pack(side="top", fill="x")

    title_lbl = tk.Label(title_bar, text=title_text, bg="#2d2d2d", fg="#ffffff", font=("Segoe UI", 9, "bold"))
    
    if "Camera" in title_text:
        title_lbl.place(x=2, rely=0.5, anchor="w")
        # Spacer ensures at least "P" is visible and provides a drag handle
        dummy_lbl = tk.Frame(title_bar, bg="#2d2d2d", width=10, height=30)
        dummy_lbl.pack(side="left")
        dummy_lbl.lower()
    else:
        title_lbl.pack(side="left", padx=5, pady=5)
        dummy_lbl = None

    if on_close:
        close_btn = tk.Label(title_bar, text="✕", bg="#2d2d2d", fg="#ffffff", font=("Segoe UI", 9), width=5)
        close_btn.pack(side="right", fill="y")
        close_btn.bind("<Enter>", lambda e: close_btn.config(bg="#e81123"))
        close_btn.bind("<Leave>", lambda e: close_btn.config(bg="#2d2d2d"))
        close_btn.bind("<Button-1>", lambda e: on_close())

    if on_minimize:
        min_btn = tk.Label(title_bar, text="—", bg="#2d2d2d", fg="#ffffff", font=("Segoe UI", 9, "bold"), width=5)
        min_btn.pack(side="right", fill="y")
        min_btn.bind("<Enter>", lambda e: min_btn.config(bg="#444444"))
        min_btn.bind("<Leave>", lambda e: min_btn.config(bg="#2d2d2d"))
        min_btn.bind("<Button-1>", lambda e: on_minimize())

    if dummy_lbl:
        WindowDragger(window, title_bar, title_lbl, dummy_lbl)
    else:
        WindowDragger(window, title_bar, title_lbl)
    return title_bar

def position_window_bottom_left(window):
    window.update_idletasks()
    w = window.winfo_reqwidth()
    h = window.winfo_reqheight()
    
    try:
        rect = RECT()
        ctypes.windll.user32.SystemParametersInfoW(48, 0, ctypes.byref(rect), 0)
        x = rect.left
        y = rect.bottom - h
    except:
        x = 0
        y = window.winfo_screenheight() - h
        
    window.geometry(f"{w}x{h}+{x}+{y}")

class DockingManager:
    def __init__(self, root, parent_hwnd, threshold=20):
        self.root = root
        self.parent_hwnd = parent_hwnd
        self.threshold = threshold
        self.is_docked = False
        self.last_parent_rect = None
        self.user32 = ctypes.windll.user32
        self.check_interval = 20
        if self.parent_hwnd:
            self.root.after(100, self.update_loop)

    def get_rect(self, hwnd):
        rect = RECT()
        self.user32.GetWindowRect(hwnd, ctypes.byref(rect))
        return rect

    def update_loop(self):
        try:
            if self.user32.IsIconic(self.parent_hwnd):
                self.root.after(self.check_interval, self.update_loop)
                return

            parent_rect = self.get_rect(self.parent_hwnd)
            if parent_rect.right == 0 and parent_rect.bottom == 0:
                self.root.after(self.check_interval, self.update_loop)
                return

            hwnd = self.user32.GetParent(self.root.winfo_id())
            if not hwnd: hwnd = self.root.winfo_id()
            my_rect = self.get_rect(hwnd)
            
            p_dx = 0
            p_dy = 0
            if self.last_parent_rect:
                p_dx = parent_rect.left - self.last_parent_rect.left
                p_dy = parent_rect.top - self.last_parent_rect.top

            moving_docked = (p_dx != 0 or p_dy != 0) and self.is_docked

            if moving_docked:
                proj_x = my_rect.left + p_dx
                proj_y = my_rect.top + p_dy
                
                new_x = proj_x
                new_y = proj_y
                
                screen_width = self.root.winfo_screenwidth()
                my_width = my_rect.right - my_rect.left
                
                vert_overlap = (my_rect.top < self.last_parent_rect.bottom) and (my_rect.bottom > self.last_parent_rect.top)
                
                if vert_overlap:
                    parent_cx = (self.last_parent_rect.left + self.last_parent_rect.right) // 2
                    my_cx = (my_rect.left + my_rect.right) // 2
                    
                    if my_cx > parent_cx: 
                        if new_x + my_width > screen_width and parent_rect.left - my_width >= 0:
                            new_x = parent_rect.left - my_width
                    else: 
                        if new_x < 0 and parent_rect.right + my_width <= screen_width:
                            new_x = parent_rect.right
                
                self.root.geometry(f"+{new_x}+{new_y}")
                my_width = my_rect.right - my_rect.left
                my_height = my_rect.bottom - my_rect.top
                my_rect.left = new_x; my_rect.right = new_x + my_width; my_rect.top = new_y; my_rect.bottom = new_y + my_height

            else:
                my_width = my_rect.right - my_rect.left
                my_height = my_rect.bottom - my_rect.top
                
                vert_overlap = (my_rect.top < parent_rect.bottom) and (my_rect.bottom > parent_rect.top)
                horiz_overlap = (my_rect.left < parent_rect.right) and (my_rect.right > parent_rect.left)
                
                dist_right = abs(my_rect.left - parent_rect.right)
                dist_left = abs(my_rect.right - parent_rect.left)
                dist_bottom = abs(my_rect.top - parent_rect.bottom)
                dist_top = abs(my_rect.bottom - parent_rect.top)
                
                snap_x = None
                snap_y = None
                
                if vert_overlap:
                    if dist_right < self.threshold: snap_x = parent_rect.right
                    elif dist_left < self.threshold: snap_x = parent_rect.left - my_width
                
                if horiz_overlap:
                    if dist_bottom < self.threshold: snap_y = parent_rect.bottom
                    elif dist_top < self.threshold: snap_y = parent_rect.top - my_height
                
                if snap_x is not None or snap_y is not None:
                    new_x = snap_x if snap_x is not None else my_rect.left
                    new_y = snap_y if snap_y is not None else my_rect.top
                    
                    if new_x != my_rect.left or new_y != my_rect.top:
                        self.root.geometry(f"+{new_x}+{new_y}")
                        my_rect.left = new_x; my_rect.right = new_x + my_width; my_rect.top = new_y; my_rect.bottom = new_y + my_height

            if not moving_docked and hasattr(self.root, 'get_pcm_rect'):
                pcm_rect = self.root.get_pcm_rect()
                if pcm_rect:
                    pcm_l, pcm_t, pcm_r, pcm_b = pcm_rect
                    if (my_rect.left < pcm_r) and (my_rect.right > pcm_l) and \
                       (my_rect.top < pcm_b) and (my_rect.bottom > pcm_t):
                        my_h = my_rect.bottom - my_rect.top
                        new_y = pcm_t - my_h
                        new_x = my_rect.left
                        self.root.geometry(f"+{new_x}+{new_y}")
                        my_w = my_rect.right - my_rect.left
                        my_rect.left = new_x; my_rect.right = new_x + my_w
                        my_rect.top = new_y; my_rect.bottom = new_y + my_h

            dist_right = abs(my_rect.left - parent_rect.right)
            dist_left = abs(my_rect.right - parent_rect.left)
            vert_overlap = (my_rect.top < parent_rect.bottom) and (my_rect.bottom > parent_rect.top)
            
            dist_bottom = abs(my_rect.top - parent_rect.bottom)
            dist_top = abs(my_rect.bottom - parent_rect.top)
            horiz_overlap = (my_rect.left < parent_rect.right) and (my_rect.right > parent_rect.left)
            
            self.is_docked = (vert_overlap and (dist_right < self.threshold or dist_left < self.threshold)) or \
                             (horiz_overlap and (dist_bottom < self.threshold or dist_top < self.threshold))
            self.last_parent_rect = parent_rect
        except Exception: pass
        self.root.after(self.check_interval, self.update_loop)

def get_hwnd_by_title(title_substring):
    try:
        import win32gui
    except ImportError:
        return None

    found_hwnd = None
    def enum_handler(hwnd, _):
        nonlocal found_hwnd
        if win32gui.IsWindowVisible(hwnd) and title_substring in win32gui.GetWindowText(hwnd).upper():
            found_hwnd = hwnd
            raise StopIteration
    try:
        win32gui.EnumWindows(enum_handler, None)
    except StopIteration:
        pass
    return found_hwnd

def find_and_focus_window_by_title(title_substring):
    try:
        import win32gui
        import win32con
    except ImportError:
        return False

    hwnd = get_hwnd_by_title(title_substring)
    if hwnd:
        try:
            win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
            win32gui.SetForegroundWindow(hwnd)
            return True
        except Exception:
            pass
    return False

def position_external_window(pid, position_mode):
    try:
        import win32gui
        import win32con
        import win32api
        import win32process
    except ImportError:
        return

    hwnd = None
    for _ in range(40):
        time.sleep(0.25)
        def enum_handler(h, list_ref):
            try:
                _, current_pid = win32process.GetWindowThreadProcessId(h)
                if current_pid == pid:
                    style = win32gui.GetWindowLong(h, win32con.GWL_STYLE)
                    if (style & win32con.WS_CAPTION) and (style & win32con.WS_SYSMENU):
                        list_ref.append(h)
            except: pass
        found = []
        win32gui.EnumWindows(enum_handler, found)
        if found:
            hwnd = found[0]
            break
    
    if hwnd:
        time.sleep(0.1)
        try:
            rect = wintypes.RECT()
            DWMWA_EXTENDED_FRAME_BOUNDS = 9
            try:
                ctypes.windll.dwmapi.DwmGetWindowAttribute(
                    wintypes.HWND(hwnd),
                    ctypes.c_int(DWMWA_EXTENDED_FRAME_BOUNDS),
                    ctypes.byref(rect),
                    ctypes.sizeof(rect)
                )
                frame_left, frame_top, frame_right, frame_bottom = rect.left, rect.top, rect.right, rect.bottom
            except:
                r = win32gui.GetWindowRect(hwnd)
                frame_left, frame_top, frame_right, frame_bottom = r[0], r[1], r[2], r[3]

            wr = win32gui.GetWindowRect(hwnd)
            w_full = wr[2] - wr[0]
            
            offset_right = wr[2] - frame_right
            offset_top = frame_top - wr[1]
            visual_h = frame_bottom - frame_top

            monitor_info = win32api.GetMonitorInfo(win32api.MonitorFromWindow(hwnd, win32con.MONITOR_DEFAULTTOPRIMARY))
            work_area = monitor_info['Work']
            
            x = work_area[2] - w_full + offset_right
            y = work_area[1] - offset_top
            
            if position_mode == "below_top_right":
                y += visual_h
            
            win32gui.SetWindowPos(hwnd, 0, x, y, 0, 0, win32con.SWP_NOSIZE | win32con.SWP_NOZORDER)
            win32gui.ShowWindow(hwnd, win32con.SW_SHOW)
            win32gui.SetForegroundWindow(hwnd)
        except Exception: pass

def show_fixed_info(parent, title, message, is_error=False, text_justify=tk.CENTER):
    dialog = tk.Toplevel(parent)
    dialog.title(title)
    dialog.attributes("-topmost", True)
    dialog.transient(parent)
    dialog.grab_set()
    dialog.resizable(False, False)
    
    dialog.update_idletasks()
    apply_window_dwm(dialog, is_dialog=True)

    if is_error:
        header_text = "FAILURE"
        header_color = "#FF6347"
    else:
        header_text = "SUCCESS"
        header_color = "#98FB98"
    
    width, height = 240, 90
    dialog.geometry(f"{width}x{height}")

    frame = tk.Frame(dialog, bg="#232323", padx=5, pady=5) 
    frame.pack(expand=True, fill="both")
    
    tk.Label(frame, text=header_text, bg="#232323", fg=header_color, font=("Consolas", 12, "bold")).pack(pady=(0, 2))
    
    tk.Label(frame, 
             text=message, 
             bg="#232323", 
             fg="white", 
             font=("Consolas", 10), 
             wraplength=230, 
             justify=text_justify
             ).pack(padx=2, fill="both", expand=True)

    center_toplevel(parent, dialog, width, height)
    dialog.lift()
    dialog.focus_force()
    dialog.after(50, dialog.focus_force)
    dialog.wait_window(dialog)
    
    
def show_autoclose_message(title, message, timeout=3000, on_close=None, parent=None):
    if parent:
        win = tk.Toplevel(parent)
    else:
        win = tk.Toplevel()
    win.title(title)
    win.resizable(False, False)
    win.attributes("-topmost", True)
    
    win.update_idletasks()
    apply_window_dwm(win, is_dialog=True)

    width, height = 300, 100
    if parent:
        parent.update_idletasks()
        x = parent.winfo_rootx() + (parent.winfo_width() // 2) - (width // 2)
        y = parent.winfo_rooty() + (parent.winfo_height() // 2) - (height // 2)
        win.geometry(f"{width}x{height}+{x}+{y}")
    else:
        x = (win.winfo_screenwidth() // 2) - (width // 2)
        y = (win.winfo_screenheight() // 2) - (height // 2)
        win.geometry(f"{width}x{height}+{x}+{y}")

    win.lift()
    win.focus_force()
    win.after(50, win.focus_force)

    frame = tk.Frame(win, bg="#232323")
    frame.pack(expand=True, fill="both")
    tk.Label(frame, text=message, bg="#232323", fg="white", font=("Consolas", 11), wraplength=280).pack(expand=True)
    
    win.protocol("WM_DELETE_WINDOW", lambda: None)

    def close_win():
        try:
            win.destroy()
            if on_close: on_close()
        except tk.TclError: pass

    win.after(timeout, close_win)


def show_modal_dialog(parent, title, message, is_error=False):
    dialog = tk.Toplevel(parent)
    dialog.title(title)
    dialog.attributes("-topmost", True)
    dialog.transient(parent) 
    dialog.grab_set()        
    dialog.resizable(True, True) 
    
    dialog.update_idletasks()
    apply_window_dwm(dialog, is_dialog=True)

    max_line_length = max([len(line.strip()) for line in message.split('\n')] + [25]) 
    required_width = (max_line_length * 8) + 60
    MIN_DIALOG_WIDTH = 350
    MAX_DIALOG_WIDTH = 900 
    MIN_DIALOG_HEIGHT = 220
    final_width = min(max(required_width, MIN_DIALOG_WIDTH), MAX_DIALOG_WIDTH)

    screen_height = dialog.winfo_screenheight()
    MAX_DIALOG_HEIGHT = min(max(int(screen_height * 0.80), 480), 800)
    lines = message.count('\n') + 1
    MAX_TEXT_LINES = int((MAX_DIALOG_HEIGHT - 120) / 18)
    buffer_lines = 1 if lines <= 5 else 0
    text_height_lines = max(4, min(lines + buffer_lines, MAX_TEXT_LINES))
    required_content_height = 120 + (text_height_lines * 18)
    final_height = max(MIN_DIALOG_HEIGHT, required_content_height) 

    dialog.geometry(f"{final_width}x{final_height}")
    dialog.maxsize(width=MAX_DIALOG_WIDTH, height=MAX_DIALOG_HEIGHT)

    dialog_style = ttk.Style()
    icon_text = "ERROR" if is_error else "SUCCESS"
    icon_color = "#FF6347" if is_error else "#98FB98"
    
    dialog_style.configure("Dialog.TFrame", background="#232323")
    dialog_style.configure("Dialog.TLabel", foreground="white", background="#232323", font=("Consolas", 10))
    dialog_style.configure("Dialog.TButton", font=("Consolas", 9, "bold"), relief='flat', background="#a9a9a9", foreground="#000000", padding=(2,2))
    
    if is_error:
        dialog_style.configure("Dialog.TButton", background="#FF6347")
    else:
        dialog_style.configure("Dialog.TButton", background="#6fcded")
    
    frame = ttk.Frame(dialog, style="Dialog.TFrame", padding=15)
    frame.pack(expand=True, fill="both")

    tk.Label(frame, text=icon_text, background="#232323", font=("Consolas", 12, "bold"), foreground=icon_color).pack(pady=(0, 5))
    
    text_area = scrolledtext.ScrolledText(
        frame, 
        height=text_height_lines, 
        background="#333333", 
        foreground="#ffffff", 
        font=("Consolas", 10), 
        relief=tk.FLAT,
        wrap=tk.WORD
    )
    
    if lines <= text_height_lines:
        text_area.vbar.pack_forget()

    text_area.insert(tk.END, message)
    text_area.config(state=tk.DISABLED) 
    text_area.pack(pady=(5, 10), fill="both", expand=True) 
    
    button_frame = ttk.Frame(frame, style="Dialog.TFrame")
    button_frame.pack(fill="x") 
    
    ttk.Button(button_frame, text="OK", style="Dialog.TButton", command=dialog.destroy).pack(pady=(5, 0), anchor="center")

    center_toplevel(parent, dialog, final_width, final_height)
    dialog.lift()
    dialog.focus_force()
    dialog.after(50, dialog.focus_force)
    dialog.wait_window(dialog)

def show_modal_error(parent, title, message):
    show_modal_dialog(parent, title, message, is_error=True)
    
def show_modal_info(parent, title, message):
    show_modal_dialog(parent, title, message, is_error=False)

def pick_file(entry_widget):
    path = filedialog.askopenfilename()
    if path:
        entry_widget.delete(0, tk.END)
        entry_widget.insert(0, path.replace("/", "\\"))

def pick_folder(entry_widget):
    path = filedialog.askdirectory()
    if path:
        entry_widget.delete(0, tk.END)
        entry_widget.insert(0, path.replace("/", "\\"))

def apply_pal_style(style):
    style.theme_use("default")
    
    style.layout("TButton", [
        ('Button.border', {'sticky': 'nswe', 'border': '1', 'children': [
            ('Button.padding', {'sticky': 'nswe', 'children': [
                ('Button.label', {'sticky': 'nswe'})
            ]})
        ]})
    ])
    
    style.configure("TFrame", background="#232323")
    style.configure("TLabel", background="#232323", foreground="#ffffff", font=("Consolas", 9, "bold"))
    style.configure("TButton", font=("Consolas", 9, "bold"), relief='flat', background="#a9a9a9", foreground="#000000", padding=(2,1))
    style.map("TButton", 
              background=[('active', '#6fcded'), ('disabled', '#555555')], 
              foreground=[('active', '#000000'), ('disabled', '#a6a6a6')])

def position_window_side(window, parent):
    window.update_idletasks()
    parent.update_idletasks()
    
    width = window.winfo_reqwidth()
    height = window.winfo_reqheight()
    screen_width = window.winfo_screenwidth()
    screen_height = window.winfo_screenheight()
    
    parent_x = parent.winfo_rootx()
    parent_y = parent.winfo_rooty()
    parent_w = parent.winfo_width()
    
    try:
        is_decorated = not window.overrideredirect()
    except AttributeError:
        is_decorated = True
    border_offset = 16 if is_decorated else 0

    space_right = screen_width - (parent_x + parent_w)
    x = (parent_x + parent_w + 2) if space_right >= parent_x else (parent_x - width - 2 - border_offset)
    
    x = max(0, min(x, screen_width - width))
    y = max(0, min(parent_y, screen_height - height))
    
    window.geometry(f"{width}x{height}+{x}+{y}")

def terminate_process_by_window_title(title_substring, safe_process_names=None):
    try:
        import psutil
    except ImportError:
        return
        
    if safe_process_names is None:
        safe_process_names = ['putty.exe', 'kitty.exe', 'ttermpro.exe', 'python.exe', 'pythonw.exe']
        
    def enum_windows_callback(hwnd, lParam):
        length = ctypes.windll.user32.GetWindowTextLengthW(hwnd)
        if length > 0:
            buff = ctypes.create_unicode_buffer(length + 1)
            ctypes.windll.user32.GetWindowTextW(hwnd, buff, length + 1)
            title = buff.value
            if title_substring.lower() in title.lower():
                lpdw_pid = ctypes.c_ulong()
                ctypes.windll.user32.GetWindowThreadProcessId(hwnd, ctypes.byref(lpdw_pid))
                if lpdw_pid.value != 0:
                    try:
                        proc = psutil.Process(lpdw_pid.value)
                        if proc.name().lower() in [n.lower() for n in safe_process_names]:
                            proc.terminate()
                    except: pass
        return True
    WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_int, ctypes.c_int)
    ctypes.windll.user32.EnumWindows(WNDENUMPROC(enum_windows_callback), 0)

def open_url_in_browser(url):
    chrome_paths = [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"
    ]
    for path in chrome_paths:
        if os.path.exists(path):
            try:
                webbrowser.register('chrome', None, webbrowser.BackgroundBrowser(path))
                webbrowser.get('chrome').open(url)
                return
            except: pass
    webbrowser.open(url)

def ask_open_filename_console(prompt, file_filter, initial_dir="C:\\"):
    root = tk.Tk()
    root.withdraw()
    
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except: pass

    screen_width = root.winfo_screenwidth()
    screen_height = root.winfo_screenheight()
    root.geometry(f"1x1+{int(screen_width/2)}+{int(screen_height/2)}")
    root.attributes("-alpha", 0.0)
    root.deiconify()
    root.attributes("-topmost", True)
    
    filename = filedialog.askopenfilename(parent=root, title=prompt, initialdir=initial_dir, filetypes=[tuple(file_filter.split('|'))])
    
    root.destroy()
    return filename

def read_windows_credential(target):
    try:
        
        CRED_TYPE_GENERIC = 1
        
        class CREDENTIAL(ctypes.Structure):
            _fields_ = [
                ("Flags", wintypes.DWORD),
                ("Type", wintypes.DWORD),
                ("TargetName", wintypes.LPWSTR),
                ("Comment", wintypes.LPWSTR),
                ("LastWritten", wintypes.FILETIME),
                ("CredentialBlobSize", wintypes.DWORD),
                ("CredentialBlob", ctypes.POINTER(ctypes.c_ubyte)),
                ("Persist", wintypes.DWORD),
                ("AttributeCount", wintypes.DWORD),
                ("Attributes", ctypes.c_void_p),
                ("TargetAlias", wintypes.LPWSTR),
                ("UserName", wintypes.LPWSTR),
            ]

        Advapi32 = ctypes.windll.Advapi32
        CredReadW = Advapi32.CredReadW
        CredReadW.argtypes = [wintypes.LPWSTR, wintypes.DWORD, wintypes.DWORD, ctypes.POINTER(ctypes.POINTER(CREDENTIAL))]
        CredReadW.restype = wintypes.BOOL
        
        pCred = ctypes.POINTER(CREDENTIAL)()
        
        if CredReadW(target, CRED_TYPE_GENERIC, 0, ctypes.byref(pCred)):
            cred = pCred.contents
            c_user = cred.UserName
            c_pass_bytes = ctypes.string_at(cred.CredentialBlob, cred.CredentialBlobSize)
            try: c_pass = c_pass_bytes.decode('utf-16')
            except: c_pass = c_pass_bytes.decode('utf-8', errors='ignore')
            
            Advapi32.CredFree(pCred)
            return c_user, c_pass
    except Exception:
        pass
    return None, None