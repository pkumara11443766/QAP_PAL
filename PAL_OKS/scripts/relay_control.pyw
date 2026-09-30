import tkinter as tk
from tkinter import messagebox, font
import sys
import time
import threading
from typing import Optional
import ctypes

try:
    import serial
except ImportError:
    root = tk.Tk()
    root.withdraw()
    messagebox.showerror("Error", "Required module 'pyserial' not found.\nPlease run setup.pyw to install dependencies.")
    root.destroy()
    sys.exit(1)

from ui_utilities import DockingManager, RECT, setup_custom_titlebar, minimize_window, apply_window_dwm, get_hwnd_by_title

RELAY_COMMANDS = {
    1: (0x65, 0x6F),
    2: (0x66, 0x70),
    3: (0x67, 0x71),
    4: (0x68, 0x72),
    5: (0x69, 0x73),
    6: (0x6A, 0x74),
    7: (0x6B, 0x75),
    8: (0x6C, 0x76)
}

RELAY_NAMES = [
    "Power Button",
    "Reset Button",
    "Kill Switch",
    "TPM",
    "Clear CMOS",
    "BMC Force Update",
    "NMI Button",
    "BMC Init"
]

class RelayController:
    def __init__(self, port: str):
        self.port = port
        self.states = {name: "0" for name in RELAY_NAMES}

    def read_relay_state(self) -> Optional[bytes]:
        try:
            with serial.Serial(self.port, 19200, timeout=2) as s:
                s.write(bytes([0x5B]))
                data = s.read(1)
            if not data:
                return None
            return data
        except serial.SerialException:
            return None

    def decode_relay_state(self) -> bool:
        data = self.read_relay_state()
        if data is None:
            return False
        binary_state = bin(int.from_bytes(data, "big"))[2:].zfill(8)
        for i, name in enumerate(reversed(RELAY_NAMES)):
            self.states[name] = binary_state[i]
        return True

    def change_relay_state(self, relay_num: int, action: int) -> bool:
        hw_relay = relay_num + 1
        if hw_relay not in RELAY_COMMANDS:
            return False

        cmd = RELAY_COMMANDS[hw_relay][0] if action == 1 else RELAY_COMMANDS[hw_relay][1]

        try:
            with serial.Serial(self.port, 19200, timeout=2) as s:
                s.write(bytes([cmd]))
            return True
        except serial.SerialException as e:
            return False

class RelayGUI(tk.Tk):
    def __init__(self, controller, parent_geom=None, parent_hwnd=None):
        super().__init__()
        self.withdraw()
        self.parent_geom = parent_geom
        self.parent_hwnd = parent_hwnd
        self.controller = controller
        self.title("8 Channel Relay Control")
        
        self.enabled_indices = []
        try:
            from config_manager import load_config
            cfg = load_config()
            enabled_str = cfg.get("ENABLED_RELAYS", "")
            if enabled_str:
                self.enabled_indices = sorted([int(x)-1 for x in enabled_str.split(",") if x.strip().isdigit()])
        except: pass
        
        self.configure(bg="#232323")
        self.overrideredirect(True)
        
        self.title_bar = setup_custom_titlebar(self, "8Ch Relay Control", on_close=self.quit, on_minimize=lambda: minimize_window(self))

        self.bold_font = font.Font(family="Consolas", size=9, weight="bold")
        self.processing = False
        self.relay_rows = []

        self.build_buttons()
        
        self.update_idletasks()
        self.geometry(f"{self.winfo_reqwidth()}x{self.winfo_reqheight()}")
        
        self.after(10, self.set_appwindow)

        self.refresh_states()
        self.docker = DockingManager(self, self.parent_hwnd)

    def get_pcm_rect(self):
        rect = RECT()
        
        if hasattr(self, 'pcm_hwnd') and self.pcm_hwnd:
            if ctypes.windll.user32.IsWindow(self.pcm_hwnd) and ctypes.windll.user32.IsWindowVisible(self.pcm_hwnd):
                ctypes.windll.user32.GetWindowRect(self.pcm_hwnd, ctypes.byref(rect))
                return (rect.left, rect.top, rect.right, rect.bottom)
            else:
                self.pcm_hwnd = None

        found_hwnd = get_hwnd_by_title("POST CODE MONITOR")

        if found_hwnd:
            self.pcm_hwnd = found_hwnd
            ctypes.windll.user32.GetWindowRect(found_hwnd, ctypes.byref(rect))
            return (rect.left, rect.top, rect.right, rect.bottom)
        return None

    def set_appwindow(self):
        self.update_idletasks()
        apply_window_dwm(self)
        
        w = self.winfo_width()
        h = self.winfo_height()
        rect = RECT()
        ctypes.windll.user32.SystemParametersInfoW(48, 0, ctypes.byref(rect), 0)
        
        main_rect = RECT()
        has_main = False
        if self.parent_hwnd:
            try:
                ctypes.windll.user32.GetWindowRect(self.parent_hwnd, ctypes.byref(main_rect))
                has_main = True
            except: pass

        if has_main:
            x = main_rect.right
            if self.parent_geom:
                _, py, _, _ = self.parent_geom
                y = py
            else:
                y = main_rect.bottom - h
        elif self.parent_geom:
            px, py, pw, ph = self.parent_geom
            x = px + pw
            y = py
        else:
            x = rect.left
            y = rect.bottom - h
            
        pcm_rect = self.get_pcm_rect()
        if pcm_rect:
            pcm_l, pcm_t, pcm_r, pcm_b = pcm_rect
            if (x < pcm_r) and (x + w > pcm_l) and (y < pcm_b) and (y + h > pcm_t):
                y = pcm_t - h
        
        if x + w > rect.right:
            if has_main:
                x = main_rect.left - w
            elif self.parent_geom:
                px, _, _, _ = self.parent_geom
                x = px - w
            else:
                x = rect.right - w
        
        if y < rect.top: y = rect.top
        if y + h > rect.bottom: y = rect.bottom - h
        
        self.geometry(f"{w}x{h}+{x}+{y}")
        
        self.wm_attributes("-topmost", 1)
        self.wm_attributes("-topmost", 0)
        self.deiconify()

    def build_buttons(self):
        frame = tk.Frame(self, bg="#232323")
        frame.pack(pady=3, padx=3, fill="both", expand=True)
        frame.grid_columnconfigure(1, weight=1)
        
        visible_count = 0
        
        for idx, name in enumerate(RELAY_NAMES):
            if idx not in self.enabled_indices:
                continue
            
            style = {
                "bg": "#990000", "fg": "white",
                "font": self.bold_font,
            }
            
            l_id = tk.Label(frame, text=f"{idx+1}.", width=3, **style)
            l_id.grid(row=visible_count, column=0, padx=(1,0), pady=2, sticky="ns", ipady=1)
            
            l_name = tk.Label(frame, text=name, **style)
            l_name.grid(row=visible_count, column=1, padx=0, pady=2, sticky="nsew", ipady=1)
            
            l_state = tk.Label(frame, text="OFF", width=5, **style)
            l_state.grid(row=visible_count, column=2, padx=(0,1), pady=2, sticky="ns", ipady=1)
            
            widgets = [l_id, l_name, l_state]
            row_data = {'widgets': widgets, 'relay_idx': idx}
            self.relay_rows.append(row_data)
            
            for w in widgets:
                w.bind("<Button-1>", lambda e, i=idx: self.toggle_relay(i))
                w.bind("<Enter>", lambda e, r=row_data: self.on_hover(r))
                w.bind("<Leave>", lambda e, r=row_data: self.on_leave(r))

            visible_count += 1

    def on_hover(self, row_data):
        for w in row_data['widgets']:
            w.config(bg="#6fcded", fg="black")

    def on_leave(self, row_data):
        relay_idx = row_data['relay_idx']
        name = RELAY_NAMES[relay_idx]
        state = self.controller.states[name]
        color = "#009900" if state == "1" else "#990000"
        for w in row_data['widgets']:
            w.config(bg=color, fg="white")

    def refresh_states(self):
        if self.processing: return
        self.processing = True
        threading.Thread(target=self._refresh_thread, daemon=True).start()

    def _refresh_thread(self):
        success = self.controller.decode_relay_state()
        self.after(0, lambda: self._update_ui_after_refresh(success))

    def _update_ui_after_refresh(self, success):
        for row_data in self.relay_rows:
            relay_idx = row_data['relay_idx']
            name = RELAY_NAMES[relay_idx]
            widgets = row_data['widgets']
            l_state = widgets[2]
            
            if not success:
                l_state.config(text="ERR")
                color = "#555555"
            else:
                state = self.controller.states[name]
                color = "#009900" if state == "1" else "#990000"
                l_state.config(text="ON" if state == "1" else "OFF")
            
            for w in widgets:
                w.config(bg=color, fg="white")
        
        self.processing = False

    def toggle_relay(self, relay_num):
        if self.processing: return
        self.processing = True
        threading.Thread(target=self._toggle_thread, args=(relay_num,), daemon=True).start()

    def _toggle_thread(self, relay_num):
        current_state = self.controller.states[RELAY_NAMES[relay_num]]
        new_state = 0 if current_state == "1" else 1
        self.controller.change_relay_state(relay_num, new_state)
        time.sleep(0.1)
        self._refresh_thread()

def main():
    import ctypes
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--parent_geom', nargs=4, type=int, help='Parent window geometry: x y w h')
    parser.add_argument('--parent_hwnd', type=int, help='Parent window HWND')
    args = parser.parse_args()

    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("RelayControlStandalone")
    except AttributeError:
        pass

    try:
        from config_manager import load_config
        config = load_config()
        relay_com = config.get("RELAYCOM")
        if not relay_com:
            raise ValueError("RELAYCOM not set in config.ini")
            
        custom_names = config.get("RELAY_NAMES", "")
        if custom_names:
            parts = custom_names.split(",")
            if len(parts) == 8:
                global RELAY_NAMES
                RELAY_NAMES = [p.strip() for p in parts]
    except Exception as e:
        root = tk.Tk()
        root.withdraw()
        messagebox.showerror("Configuration Error", f"Unable to load RELAYCOM from config.ini.\n\n{e}")
        root.destroy()
        sys.exit(1)

    controller = RelayController(relay_com)
    app = RelayGUI(controller, parent_geom=args.parent_geom, parent_hwnd=args.parent_hwnd)
    app.mainloop()

if __name__ == "__main__":
    main()
