import os
import subprocess
import sys
import ctypes
import tkinter as tk
import traceback
import threading
from tkinter import ttk, messagebox

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.join(SCRIPT_DIR, "scripts"))

try:
    from scripts import config_manager
    from scripts.ui_utilities import apply_pal_style, open_url_in_browser, apply_window_dwm, setup_custom_titlebar, position_window_bottom_left, minimize_window, find_and_focus_window_by_title, position_external_window
    from scripts.pal_dialogs import MultiFlashDialog, GFSFlashDialog, PowerControlDialog
    from scripts.ssh_utils import create_debug_user
except ImportError as e:
    root = tk.Tk()
    root.withdraw()
    messagebox.showerror("Startup Error", f"Failed to import required modules.\n\nError: {e}\n\nPlease run setup.pyw to install dependencies.")
    sys.exit(1)

class PALApp:
    def __init__(self, root):
        self.root = root
        self.root.withdraw()
        self.root.title("PAL")
        self.root.configure(bg="#232323")
        self.root.resizable(False, False)
        self.root.overrideredirect(True)

        self.active_processes = {}
        self.button_locks = {}
        self.buttons_to_disable = [] 
        self.power_buttons = []
        self.ftdi_buttons = []
        self.misc_widgets = []
        
        self._save_job = None
        
        self.load_configuration()
        
        self.title_bar = setup_custom_titlebar(self.root, "PAL - MS" if getattr(self, 'sut_type', '') == 'ms' else "PAL - 1S", on_close=self.on_closing, on_minimize=lambda: minimize_window(self.root))
        self.root.after(10, self.set_appwindow)

        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.root.bind("<Configure>", self.on_window_configure)
        
        self.setup_styles()
        
        self.main_frame = tk.Frame(self.root, bg="#232323", padx=6, pady=5)
        self.main_frame.pack(fill="both", expand=True)
        
        self.build_ui()
        
        self.auto_refresh_ui()

    def set_appwindow(self):
        self.root.update_idletasks()
        apply_window_dwm(self.root)
        hwnd = ctypes.windll.user32.GetParent(self.root.winfo_id())
        if not hwnd: hwnd = self.root.winfo_id()
        
        try:
            icon_path = os.path.join(SCRIPT_DIR, "PAL.ico")
            if os.path.exists(icon_path):
                hIcon = ctypes.windll.user32.LoadImageW(0, icon_path, 1, 0, 0, 0x00000010)
                if hIcon:
                    ctypes.windll.user32.SendMessageW(hwnd, 0x80, 1, hIcon)
                    ctypes.windll.user32.SendMessageW(hwnd, 0x80, 0, hIcon)
        except: pass
        
        saved_x = self.config.get("PAL_WIN_X")
        saved_y = self.config.get("PAL_WIN_Y")
        
        if saved_x and saved_y:
            try:
                sx = int(saved_x)
                sy = int(saved_y)
                # Sanity check: if coords look like minimized/off-screen values, reset
                if sx < -30000 or sy < -30000: position_window_bottom_left(self.root)
                
                # Robust Sanity check: verify coordinates are within the current primary monitor bounds
                # Windows uses ~-32000 for minimized windows. We also check if the window is beyond current resolution.
                screen_w = self.root.winfo_screenwidth()
                screen_h = self.root.winfo_screenheight()

                if sx < -30000 or sy < -30000 or sx > screen_w or sy > screen_h:
                    position_window_bottom_left(self.root)
                else: self.root.geometry(f"+{sx}+{sy}")
            except:
                position_window_bottom_left(self.root)
        else:
            position_window_bottom_left(self.root)
        
        self.root.update()
        self.root.deiconify()
        self.root.lift()
        self.root.wm_attributes("-topmost", 1)
        self.root.wm_attributes("-topmost", 0)
        self.root.focus_force()

    def load_configuration(self):
        if not os.path.exists(config_manager.CONFIG_FILE):
            messagebox.showerror("Configuration Not Found", "config.ini not found.\nPlease run setup.pyw to create it.")
            sys.exit(1)

        health_warning = config_manager.check_encryption_health()
        if health_warning:
            messagebox.showwarning("Encryption Key Warning", health_warning)

        try:
            self.config = config_manager.load_config()
        except Exception as e:
            messagebox.showerror("Config Error", f"Failed to load config: {e}")
            sys.exit(1)

        self.sut_type = self.config.get("SUT_TYPE", "").strip('"').strip("'").lower()
        if self.sut_type not in ('1s', 'ms'):
            messagebox.showerror("Invalid Configuration", "Invalid or incomplete configuration found.\nPlease run setup.pyw to configure the application.")
            sys.exit(1)

        self.python_path = self.config.get("PYTHON_PATH", "").strip('"').strip("'")
        self.python_exe = os.path.join(self.python_path, "python.exe")
        self.pythonw_exe = os.path.join(self.python_path, "pythonw.exe")
        self.putty_path = self.config.get("PUTTY_PATH", "").strip('"').strip("'")
        self.putty_logs_path = self.config.get("PUTTY_LOGS_PATH", "").strip('"').strip("'")
        self.log_dir = config_manager.get_log_dir()
        
        self.raritan_script = "SSH"

    def setup_styles(self):
        style = ttk.Style()
        apply_pal_style(style)
        style.configure("ModeSeparator.TSeparator", background="#555555")
        style.configure("Running.TButton", background="#00cd24", font="consolas 9 bold")
        style.map("Running.TButton",
                  background=[("disabled", "#00cd24")],
                  foreground=[("disabled", "#000000"), ("!disabled", "#000000")])
        style.configure("TCheckbutton", background="#232323", foreground="#ffffff", font="consolas 9 bold")
        style.map("TCheckbutton",
                  background=[('active', '#232323')],
                  indicatorcolor=[('selected', '#6fcded'), ('!selected', '#555555')])

    def _build_power_control_section(self, row):
        ttk.Label(self.main_frame, text="SUT Power Control", style="TLabel", anchor="center").grid(row=row, column=0, columnspan=2, pady=2, sticky="ew")
        row += 1
        power_frame = ttk.Frame(self.main_frame, style="TFrame")
        power_frame.grid(row=row, column=0, columnspan=2, sticky="ew")
        for i in range(3): power_frame.grid_columnconfigure(i, weight=1)
        
        self.btn_on = ttk.Button(power_frame, text="On", width=4, command=lambda: self.launch_power("on"))
        self.btn_on.grid(row=0, column=0, padx=2, pady=2, sticky="ew")
        self.btn_cycle = ttk.Button(power_frame, text="Cycle", width=4, command=lambda: self.launch_power("cycle"))
        self.btn_cycle.grid(row=0, column=1, padx=2, pady=2, sticky="ew")
        self.btn_off = ttk.Button(power_frame, text="Off", width=4, command=lambda: self.launch_power("off"))
        self.btn_off.grid(row=0, column=2, padx=2, pady=2, sticky="ew")
        
        self.power_buttons.extend([self.btn_on, self.btn_cycle, self.btn_off])
        self.buttons_to_disable.extend(self.power_buttons)
        row += 1
        return row

    def _build_putty_section(self, row):
        ttk.Label(self.main_frame, text="PuTTY Serial COMs", style="TLabel", anchor="center").grid(row=row, column=0, columnspan=2, pady=2, sticky="ew")
        row += 1
        putty_frame = ttk.Frame(self.main_frame, style="TFrame")
        putty_frame.grid(row=row, column=0, columnspan=2, sticky="ew")
        for i in range(3): putty_frame.grid_columnconfigure(i, weight=1)
        
        ttk.Button(putty_frame, text="BIOS", width=4, command=lambda: self.open_putty(self.config.get("BIOSCOM"), "BIOS_&M-&D-&Y_&T.log", "top_right")).grid(row=0, column=0, padx=2, pady=2, sticky="ew")
        self.btn_bmc_com = ttk.Button(putty_frame, text="BMC", width=4, command=lambda: self.open_putty(self.config.get("BMCCOM"), "BMC_&M-&D-&Y_&T.log", "below_top_right"))
        self.btn_bmc_com.grid(row=0, column=1, padx=2, pady=2, sticky="ew")
        ttk.Button(putty_frame, text="Logs", width=4, command=lambda: self.open_folder(self.putty_logs_path)).grid(row=0, column=2, padx=2, pady=2, sticky="ew")
        
        self.buttons_to_disable.append(self.btn_bmc_com)
        row += 1
        return row

    def _build_ftdi_section(self, row):
        ttk.Label(self.main_frame, text="Firmware Flashing", style="TLabel", anchor="center").grid(row=row, column=0, columnspan=2, pady=2, sticky="ew")
        row += 1
        
        ftdi_frame = ttk.Frame(self.main_frame, style="TFrame")
        ftdi_frame.grid(row=row, column=0, columnspan=2, sticky="ew")
        ftdi_frame.grid_columnconfigure(0, weight=1, uniform="ftdi")
        ftdi_frame.grid_columnconfigure(1, weight=1, uniform="ftdi")
        
        btn_multi = ttk.Button(ftdi_frame, text="Start", command=self.open_multi_flash_dialog)
        btn_multi.grid(row=0, column=0, padx=2, pady=2, sticky="ew")
        self.ftdi_buttons.append(btn_multi)
        self.buttons_to_disable.append(btn_multi)
        
        self.btn_flash_log = ttk.Button(ftdi_frame, text="Logs", command=self.open_logs)
        self.btn_flash_log.grid(row=0, column=1, padx=2, pady=2, sticky="ew")
        
        row += 1
        self.btn_update = ttk.Button(self.main_frame, text="Update ci.git", command=self.update_cigit)
        self.btn_update.grid(row=row, column=0, columnspan=2, padx=2, pady=2, sticky="ew")
        self.buttons_to_disable.append(self.btn_update)
        row += 1
        return row

    def build_ui(self):
        self.main_frame.grid_columnconfigure(0, weight=1)
        self.main_frame.grid_columnconfigure(1, weight=1)
        row = 0

        row = self._build_power_control_section(row)
        row = self._build_putty_section(row)
        row = self._build_ftdi_section(row)

        self.btn_full_row = row - 1
        
        self.lbl_misc = ttk.Label(self.main_frame, text="Miscellaneous", style="TLabel", anchor="center")
        
        self.misc_frame = ttk.Frame(self.main_frame, style="TFrame")
        self.misc_frame.grid_columnconfigure(0, weight=1)
        
        self.btn_pythonsv = ttk.Button(self.misc_frame, text="Launch PythonSV", command=lambda: self.launch_python(self.config.get("PYTHONSV_PATH")))
        self.btn_bmc_web = ttk.Button(self.misc_frame, text="OpenBMC Web UI", command=lambda: open_url_in_browser(f"https://{self.config.get('BMC_IP')}"))
        self.btn_bmc_debug = ttk.Button(self.misc_frame, text="Create debuguser", command=self.create_bmc_debuguser)
        self.btn_clear_cmos_bmc = ttk.Button(self.misc_frame, text="Clear CMOS (BMC)", command=self.clear_cmos_bmc)
        self.btn_relay = ttk.Button(self.misc_frame, text="8Ch Relay Control", command=lambda: self.focus_window("8 Channel Relay Control", "relay_control.pyw", self.btn_relay))
        self.btn_post_code = ttk.Button(self.misc_frame, text="POST Code Monitor", command=lambda: self.focus_window("POST Code Monitor", "bmc_pc_monitor.pyw"))
        
        self.btn_webcam = ttk.Button(self.misc_frame, text="Camera", command=self.launch_webcam)
        
        self.buttons_to_disable.append(self.btn_relay)

    def refresh_dynamic_ui(self):
        current_row = self.btn_full_row + 1
        
        self.lbl_misc.grid(row=current_row, column=0, columnspan=2, padx=2, pady=2, sticky="ew")
        current_row += 1
        
        self.misc_frame.grid(row=current_row, column=0, columnspan=2, sticky="ew")
        
        r = 0
        self.btn_pythonsv.grid(row=r, column=0, padx=2, pady=2, sticky="ew"); r+=1
        self.btn_bmc_web.grid(row=r, column=0, padx=2, pady=2, sticky="ew"); r+=1
        self.btn_bmc_debug.grid(row=r, column=0, padx=2, pady=2, sticky="ew"); r+=1
        self.btn_clear_cmos_bmc.grid(row=r, column=0, padx=2, pady=2, sticky="ew"); r+=1

        if self.config.get("RELAYCOM"):
            self.btn_relay.grid(row=r, column=0, padx=2, pady=2, sticky="ew"); r+=1
        else:
            self.btn_relay.grid_forget()
        
        self.btn_post_code.grid(row=r, column=0, padx=2, pady=2, sticky="ew"); r+=1

        if self.config.get("WEBCAM", "").lower() == "yes":
            self.btn_webcam.grid(row=r, column=0, padx=2, pady=2, sticky="ew"); r+=1
        else:
            self.btn_webcam.grid_forget()

    def auto_refresh_ui(self):
        try:
            self.config = config_manager.load_config()
        except: pass
        self.refresh_dynamic_ui()
        self.root.after(3000, self.auto_refresh_ui)

    def set_ui_state(self, buttons, lock_key, state):
        for btn in buttons:
            locks = self.button_locks.setdefault(btn, set())
            if state == 'disabled':
                locks.add(lock_key)
                btn.config(state='disabled')
            else:
                locks.discard(lock_key)
                if not locks:
                    btn.config(state='normal')

    def run_subprocess(self, cmd, source_button=None, original_text=None, lock_key="main", buttons_to_lock=None):
        if self.active_processes.get(lock_key):
            messagebox.showwarning("In Progress", "A task is already running.")
            return

        if buttons_to_lock is None:
            buttons_to_lock = self.buttons_to_disable

        self.set_ui_state(buttons_to_lock, lock_key, 'disabled')
        
        if source_button:
            source_button.config(style="Running.TButton")

        try:
            proc = subprocess.Popen(cmd, creationflags=subprocess.CREATE_NEW_CONSOLE)
            self.active_processes[lock_key] = proc
            self.monitor_process(lock_key, source_button, original_text, buttons_to_lock)
        except Exception as e:
            messagebox.showerror("Launch Error", str(e))
            self.reset_ui(lock_key, source_button, original_text, buttons_to_lock)

    def monitor_process(self, lock_key, source_button, original_text, buttons_to_lock):
        proc = self.active_processes.get(lock_key)
        if proc and proc.poll() is None:
            self.root.after(250, lambda: self.monitor_process(lock_key, source_button, original_text, buttons_to_lock))
        else:
            self.active_processes.pop(lock_key, None)
            self.reset_ui(lock_key, source_button, original_text, buttons_to_lock)

    def reset_ui(self, lock_key, source_button, original_text, buttons_to_lock):
        self.set_ui_state(buttons_to_lock, lock_key, 'normal')
        if source_button:
            source_button.config(style="TButton")
            if original_text: source_button.config(text=original_text)
        self.refresh_dynamic_ui()

    def launch_power(self, action):
        try:
                import paramiko
        except ImportError:
            messagebox.showerror("Dependency Error", "The required 'paramiko' package is not installed.\n\nPlease run 'setup.pyw' to install required dependencies.")
            return

        sut_acs = [self.config[k].strip('"').strip("'") for k in config_manager.get_sorted_sut_keys(self.config)]
        pdu_pass = self.config.get("PDU_PASS", "")
        enc_pass = config_manager.encrypt_value(pdu_pass) if pdu_pass else ""
        cmd = [
            self.python_exe, os.path.join(SCRIPT_DIR, "scripts", "raritan_power_control.py"),
            action, self.python_exe, self.raritan_script,
            self.config.get("PDU_USER"), enc_pass, ",".join(sut_acs),
            "--no-wait"
        ]
        title_map = {"on": "Power On", "off": "Power Off", "cycle": "Power Cycle"}
        
        buttons_to_lock = self.power_buttons + self.ftdi_buttons + [self.btn_relay]
        self.set_ui_state(buttons_to_lock, "power_dialog", 'disabled')
        
        def on_close():
            try: self.set_ui_state(buttons_to_lock, "power_dialog", 'normal')
            except: pass
            
        PowerControlDialog(self.root, title_map.get(action, "Power Control"), cmd, on_close_callback=on_close)

    def run_ftdi(self, flash_type, file_map=None, gfs_node=None):
        cmd = [
            self.python_exe, os.path.join(SCRIPT_DIR, "scripts", "ftdi_flash.py"),
            flash_type, self.sut_type
        ]
        if file_map:
            map_str = ";".join([f"{k}={v}" for k, v in file_map.items()])
            cmd.extend(["--file-map", map_str])
        if gfs_node and gfs_node.lower() != "auto-discover":
            cmd.extend(["--gfs-node", gfs_node])
            
        disable_list = self.power_buttons + self.ftdi_buttons + [self.btn_bmc_com, self.btn_update, self.btn_relay]
        self.run_subprocess(cmd, lock_key="ftdi", buttons_to_lock=disable_list)

    def update_cigit(self):
        cmd = [self.python_exe, os.path.join(SCRIPT_DIR, "scripts", "update_cigit.py")]
        disable_list = self.ftdi_buttons + [self.btn_update]
        self.run_subprocess(cmd, self.btn_update, lock_key="update", buttons_to_lock=disable_list)

    def open_multi_flash_dialog(self):
        self.set_ui_state([self.ftdi_buttons[0]], "flash_dialog", "disabled")
        
        flash_options = ["SCM", "HPM", "BMC", "BIOS"]
        if self.sut_type == 'ms':
            flash_options.insert(0, "AGG")
            
        MultiFlashDialog(self.root, flash_options, callback=self._handle_flash_selection, on_close=self.unlock_flash_ui)

    def unlock_flash_ui(self):
        self.set_ui_state([self.ftdi_buttons[0]], "flash_dialog", "normal")

    def _handle_flash_selection(self, result):
        if not isinstance(result, tuple):
            self.run_ftdi(result)
            return

        # Handle result from MultiFlashDialog
        if result[0] == "GFS":
            # result is ("GFS", selected_list, gfs_node)
            selected_devices = result[1]
            gfs_node = result[2]
            GFSFlashDialog(self.root, selected_devices, 
                           callback=lambda res: self.run_ftdi(res[0], res[1], gfs_node=gfs_node), 
                           on_close=self.unlock_flash_ui)
        else:
            # result is (flash_type_str, gfs_node)
            self.run_ftdi(result[0], gfs_node=result[1])

    def open_putty(self, com, log_name, position_mode=None):
        if not com: return
        if find_and_focus_window_by_title(f"{com.upper()} - PUTTY"):
            return
        
        os.makedirs(self.putty_logs_path, exist_ok=True)
        
        if not self.putty_path or not os.path.exists(self.putty_path):
            messagebox.showerror("Configuration Error", f"PuTTY executable not found at:\n{self.putty_path}\n\nPlease check your configuration.")
            return

        log_file = os.path.join(self.putty_logs_path, log_name)
        try:
            startupinfo = None
            if position_mode:
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                startupinfo.wShowWindow = 0

            proc = subprocess.Popen(
                [self.putty_path, "-serial", com, "-sercfg", "115200,8,n,1,X", "-sessionlog", log_file],
                creationflags=subprocess.CREATE_NEW_CONSOLE,
                startupinfo=startupinfo,
                cwd=os.environ.get("TEMP", "C:\\")
            )
            if position_mode:
                threading.Thread(target=position_external_window, args=(proc.pid, position_mode), daemon=True).start()
        except Exception as e:
            messagebox.showerror("Launch Error", f"Failed to launch PuTTY:\n{e}")

    def open_folder(self, path):
        if os.path.exists(path): os.startfile(path)
        else: messagebox.showerror("Error", f"Folder not found:\n{path}")

    def open_logs(self):
        target_dir = os.path.join(self.log_dir, "FTDI_Flash")
        if os.path.exists(target_dir):
            self.open_folder(target_dir)
        else:
            messagebox.showinfo("Logs", "No logs exist yet.\nPlease run a flash operation to generate logs.")

    def launch_python(self, script_path):
        if not script_path:
            messagebox.showerror("Error", "Script/Folder path is empty.")
            return
        
        if not os.path.exists(script_path):
            messagebox.showerror("Error", f"Script not found:\n{script_path}")
            return

        if not os.path.exists(self.python_exe):
            messagebox.showerror("Configuration Error", f"Python executable not found at:\n{self.python_exe}")
            return

        if os.path.isdir(script_path):
            try:
                subprocess.run(f'start "Python Shell" cmd /k "{self.python_exe}"', cwd=script_path, shell=True)
            except Exception as e:
                messagebox.showerror("Launch Error", f"Failed to launch Python shell:\n{e}")
            return

        try:
            abs_script_path = os.path.abspath(script_path)
            subprocess.Popen(["cmd.exe", "/k", self.python_exe, "-i", abs_script_path], cwd=os.path.dirname(abs_script_path), creationflags=subprocess.CREATE_NEW_CONSOLE)
        except Exception as e:
            messagebox.showerror("Launch Error", f"Failed to launch script:\n{e}")

    def create_bmc_debuguser(self):
        ip = self.config.get("BMC_IP")
        user = "root"
        password = self.config.get("BMC_ROOT_PASS")
        debug_pass = self.config.get("BMC_DEBUGUSER_PASS")
        
        def _run_ssh_task():
            try:
                create_debug_user(ip, password, debug_pass)
                self.root.after(0, lambda: messagebox.showinfo("Success", "BMC debuguser created successfully."))
            except Exception as e:
                self.root.after(0, lambda err=e: messagebox.showerror("Error", f"Failed to create debug user:\n{err}"))

        import threading
        threading.Thread(target=_run_ssh_task, daemon=True).start()

    def clear_cmos_bmc(self):
        cmd = [self.python_exe, os.path.join(SCRIPT_DIR, "scripts", "clear_cmos_bmc.py")]
        disable_list = self.power_buttons + self.ftdi_buttons + [self.btn_relay, self.btn_clear_cmos_bmc]
        self.run_subprocess(cmd, self.btn_clear_cmos_bmc, lock_key="cmos_bmc", buttons_to_lock=disable_list)

    def focus_window(self, title, script_name, relative_widget=None):
        if find_and_focus_window_by_title(title.upper()):
            return
        script_path = os.path.join(SCRIPT_DIR, "scripts", script_name)
        if os.path.exists(script_path):
            cmd = [self.pythonw_exe, script_path]
            
            if script_name in ["bmc_pc_monitor.pyw", "relay_control.pyw"]:
                if relative_widget:
                    x = relative_widget.winfo_rootx()
                    y = relative_widget.winfo_rooty()
                    w = relative_widget.winfo_width()
                    h = relative_widget.winfo_height()
                else:
                    x = self.root.winfo_x()
                    y = self.root.winfo_y()
                    w = self.root.winfo_width()
                    h = self.root.winfo_height()
                
                hwnd = ctypes.windll.user32.GetParent(self.root.winfo_id())
                if not hwnd: hwnd = self.root.winfo_id()
                
                cmd.extend(["--parent_geom", str(x), str(y), str(w), str(h)])
                cmd.extend(["--parent_hwnd", str(hwnd)])
            
            try:
                subprocess.Popen(cmd, creationflags=0x01000208, close_fds=True)
                try: ctypes.windll.user32.AllowSetForegroundWindow(-1)
                except: pass
            except Exception as e:
                messagebox.showerror("Launch Error", f"Failed to launch {script_name}:\n{e}")

    def launch_webcam(self):
        title = "PAL Camera"
        script_name = "pal_camera.pyw"
        
        if find_and_focus_window_by_title(title.upper()):
            return

        script_path = os.path.join(SCRIPT_DIR, "scripts", script_name)
        if os.path.exists(script_path):
            cmd = [self.pythonw_exe, script_path]
            try:
                subprocess.Popen(cmd, creationflags=0x01000208, close_fds=True)
            except Exception as e:
                messagebox.showerror("Launch Error", f"Failed to launch {script_name}:\n{e}")
        else:
            messagebox.showerror("Error", f"Script not found: {script_name}")

    def on_window_configure(self, event):
        if event.widget == self.root:
            self._schedule_save_settings()

    def _schedule_save_settings(self):
        if self._save_job:
            self.root.after_cancel(self._save_job)
        self._save_job = self.root.after(2000, self._save_window_position)

    def _save_window_position(self):
        self._save_job = None
        try:
            if not self.root.winfo_exists(): return
            # Prevent saving if minimized or off-screen
            if self.root.state() == 'iconic' or self.root.winfo_x() < -30000: return

            cfg = config_manager.load_config()
            cfg["PAL_WIN_X"] = str(self.root.winfo_x())
            cfg["PAL_WIN_Y"] = str(self.root.winfo_y())
            config_manager.save_config(cfg)
        except: pass

    def on_closing(self):
        if self.active_processes:
            messagebox.showwarning("Task in Progress", "Cannot close while a task is active.")
            return
        
        if self._save_job:
            self.root.after_cancel(self._save_job)

        self._save_window_position()
        self.root.destroy()

if __name__ == "__main__":
    try:
        root = tk.Tk()
        app = PALApp(root)
        root.mainloop()
    except Exception as e:
        err_msg = f"Fatal Error: {e}\n\n{traceback.format_exc()}"
        ctypes.windll.user32.MessageBoxW(0, err_msg, "PAL Error", 0x10)