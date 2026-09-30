import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import threading
import os
import subprocess
import time
import sys
import ctypes

class IConsoleImportTask:
    def __init__(self, app):
        self.app = app
        self.root = app.root
        self.python_path = self.app.entries["PYTHON_PATH"].get().strip().strip('"').strip("'")
        
        try:
            self.hwnd = ctypes.windll.user32.GetParent(self.root.winfo_id())
            if not self.hwnd: self.hwnd = self.root.winfo_id()
        except:
            self.hwnd = None

    def run(self):
        threading.Thread(target=self._execute, daemon=True).start()

    def _execute(self):
        hwnd = self.hwnd
        python_path = self.python_path
        python_exe = os.path.join(python_path, "python.exe")
        script_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "iconsole_import.py")

        if not os.path.exists(python_exe) or not os.path.exists(script_path):
            self.root.after(0, lambda: messagebox.showerror("Error", "Python executable or import script path is invalid.", parent=self.root))
            return

        try:
            cmd_str = f'"{python_exe}" "{script_path}" & echo. & echo Press Enter to close window... & pause > nul'
            proc = subprocess.Popen(f'cmd /c "{cmd_str}"', creationflags=subprocess.CREATE_NEW_CONSOLE)
            proc.wait()
            time.sleep(0.5)
        except Exception as e:
            self.root.after(0, lambda: messagebox.showerror("Error", f"Import failed: {e}", parent=self.root))
        finally:
            self.root.after(0, lambda: self.app.finalize_import_gui_update(hwnd))

class ConfigEditorApp:
    def __init__(self, root):
        self.root = root
        self.load_critical_modules()
        encryption_error = self.config_manager.check_encryption_health()
        if encryption_error:
            messagebox.showwarning("Encryption Warning", encryption_error, parent=self.root)
            
        self.root.title("PAL Setup for config.ini")
        self.root.configure(bg="#232323")
        self.FTDI_SCRIPT = os.path.join(self.config_manager.CI_GIT_BASE, "scripts", "windows", "ftdi-chip-flash.py")
        
        self.FT_PROG_EXE = r"C:\Program Files (x86)\FTDI\FT_Prog\FT_Prog.exe"
        if not os.path.exists(self.FT_PROG_EXE):
            alt_path = r"C:\Program Files\FTDI\FT_Prog\FT_Prog.exe"
            if os.path.exists(alt_path): self.FT_PROG_EXE = alt_path
            
        self.style_setup()
        self.values = self.config_manager.load_config() 
        self.entries = {}
        self.sut_entries = {}
        self.label_map = {}
        self.current_row = 0
        self.uniform_pady = 3
        self.sut_type_var = tk.StringVar(value=self.values.get("SUT_TYPE", ""))
        
        self.webcam_var = tk.StringVar(value=self.values.get("WEBCAM", "").lower())
        self.enabled_relays_var = tk.StringVar(value=self.values.get("ENABLED_RELAYS", ""))
        
        self.main_frame = ttk.Frame(root)
        self.main_frame.pack(fill="both", expand=True, padx=10, pady=(10, 0))
        self.field_frame = ttk.Frame(self.main_frame)
        self.field_frame.pack(fill="both", expand=True)
        self.field_frame.grid_columnconfigure(1, weight=1)
        self.add_sut_frame = ttk.Frame(self.field_frame)
        self.bottom_sep = ttk.Separator(self.field_frame, orient="horizontal")
        self.bottom_frame = ttk.Frame(self.main_frame)
        self.bottom_frame.pack(fill="x", pady=5)
        self.build_ui()

    def load_critical_modules(self):
        try:
            import scripts.config_manager as cm
            import scripts.ui_utilities as ui
        except ImportError:
            import config_manager as cm
            import ui_utilities as ui
        self.config_manager = cm
        self.ui_utilities = ui
        self.CONFIG_FILE = os.path.abspath(cm.CONFIG_FILE)
        try:
            import serial.tools.list_ports
            self.serial_tools = serial.tools.list_ports
        except ImportError:
            self.serial_tools = None
        try:
            try:
                from scripts.ssh_utils import SSHManager
            except ImportError:
                from ssh_utils import SSHManager
            self.SSHManager = SSHManager
        except ImportError:
            self.SSHManager = None

    def style_setup(self):
        style = ttk.Style()
        self.ui_utilities.apply_pal_style(style)
        style.configure("TEntry", insertcolor="white", fieldbackground="#333333", foreground="#ffffff", font=("Consolas", 9))
        style.configure("TSeparator", background="#444444")
        style.configure("TRadiobutton", background="#232323", foreground="#ffffff", font=("Consolas", 9, "bold"))
        style.map("TRadiobutton", background=[('active', '#232323')], indicatorcolor=[('selected', '#6fcded')])
        style.layout("TCheckbutton", style.layout("TRadiobutton"))
        style.configure("TCheckbutton", background="#232323", foreground="#ffffff", font=("Consolas", 9, "bold"))
        style.map("TCheckbutton", background=[('active', '#232323')], indicatorcolor=[('selected', '#6fcded'), ('!selected', '#555555')])
        style.configure("IconButton.TButton", font=("Segoe UI", 10))

    def _build_sut_type_section(self):
        ttk.Label(self.field_frame, text="Select SUT Type", anchor="e").grid(row=self.current_row, column=0, sticky="e", padx=5, pady=self.uniform_pady)
        radio_frame = ttk.Frame(self.field_frame)
        radio_frame.grid(row=self.current_row, column=1, sticky="w", padx=5, pady=self.uniform_pady)
        r1 = ttk.Radiobutton(radio_frame, text="Single Socket", variable=self.sut_type_var, value="1s")
        r2 = ttk.Radiobutton(radio_frame, text="Multisocket", variable=self.sut_type_var, value="ms")
        r1.pack(side="left", padx=(0, 15))
        r2.pack(side="left")
        self.current_row += 1

    def _build_webcam_section(self):
        self.add_separator()
        ttk.Label(self.field_frame, text="Include Webcam?", anchor="e").grid(row=self.current_row, column=0, sticky="e", padx=5, pady=self.uniform_pady)
        webcam_frame = ttk.Frame(self.field_frame)
        webcam_frame.grid(row=self.current_row, column=1, sticky="w", padx=5, pady=self.uniform_pady)
        r1 = ttk.Radiobutton(webcam_frame, text="Yes", variable=self.webcam_var, value="yes")
        r2 = ttk.Radiobutton(webcam_frame, text="No", variable=self.webcam_var, value="no")
        r1.pack(side="left", padx=(0, 15))
        r2.pack(side="left")
        self.current_row += 1

    def _build_com_ports_section(self):
        self.add_separator()
        ttk.Label(self.field_frame, text="In format COM#. e.g. COM123", foreground="#aaaaaa", font=("Consolas", 9)).grid(row=self.current_row, column=1, sticky="w", padx=5, pady=(2, 0))
        self.current_row += 1
        com_fields = [("8Ch Relay COM Port", "RELAYCOM"), ("BMC Serial COM Port", "BMCCOM"), ("BIOS Serial COM Port", "BIOSCOM")]
        for label, key in com_fields:
            self.add_field(label, key)
        ttk.Button(self.field_frame, text="Configure 8Ch Relay", command=self.configure_relay_channels).grid(row=self.current_row, column=1, sticky="w", padx=5, pady=self.uniform_pady)
        self.current_row += 1
        ttk.Button(self.field_frame, text="Program DC-SCM VID/PID", command=self.program_dc_scm).grid(row=self.current_row, column=1, sticky="w", padx=5, pady=self.uniform_pady)
        self.current_row += 1
        ttk.Button(self.field_frame, text="Auto-Detect BMC & BIOS Ports", command=self.run_auto_detect).grid(row=self.current_row, column=1, sticky="w", padx=5, pady=self.uniform_pady)
        self.current_row += 1

    def _build_paths_section(self):
        self.add_separator()
        path_fields = [("PuTTY.exe Path", "PUTTY_PATH", True, False),
                       ("PuTTY Logs Folder", "PUTTY_LOGS_PATH", True, True),
                       ("Python Folder", "PYTHON_PATH", True, True),
                       ("PythonSV Path", "PYTHONSV_PATH", True, False)]
        for label, key, is_path, is_folder in path_fields:
            self.add_field(label, key, is_path, is_folder)

    def configure_relay_channels(self):
        dialog = tk.Toplevel(self.root)
        dialog.title("Configure 8Ch Relay")
        dialog.configure(bg="#232323")
        dialog.transient(self.root)
        dialog.grab_set()
        
        dialog.update_idletasks()
        self.ui_utilities.apply_window_dwm(dialog, is_dialog=True)

        ttk.Label(dialog, text="Select Enabled RLY# Connections", font=("Consolas", 10, "bold"), foreground="#ffffff", background="#232323", justify="center").pack(pady=5)
        
        current_selection = self.enabled_relays_var.get().split(',') if self.enabled_relays_var.get() else []
        vars = []
        current_names = [
            "Power Button", "Reset Button", "Kill Switch", "TPM",
            "Clear CMOS", "BMC Force Update", "NMI Button", "BMC Init"
        ]
        
        saved_names_str = self.values.get("RELAY_NAMES", "")
        if saved_names_str:
            saved_names = saved_names_str.split(",")
            if len(saved_names) == 8:
                current_names = saved_names
        
        chk_frame = ttk.Frame(dialog)
        chk_frame.pack(padx=20, pady=5)
        
        for i in range(8):
            name = current_names[i]
            idx = str(i + 1)
            var = tk.BooleanVar(value=(idx in current_selection))
            
            cb = ttk.Checkbutton(chk_frame, variable=var)
            cb.grid(row=i, column=0, sticky="e", padx=(5, 2), pady=2)
            
            ttk.Label(chk_frame, text=f"{idx}.", width=3, anchor="e").grid(row=i, column=1, sticky="e", padx=(0, 5), pady=2)
            
            entry = ttk.Entry(chk_frame, width=25)
            entry.insert(0, name)
            entry.grid(row=i, column=2, sticky="w", padx=5, pady=2)
            
            vars.append((idx, var, entry))
            
        def on_save():
            selected = []
            names = []
            for idx, var, entry in vars:
                if var.get():
                    selected.append(idx)
                
                clean_name = entry.get().strip().replace(",", " ")
                if not clean_name: clean_name = f"Relay {idx}"
                names.append(clean_name)

            val_enabled = ",".join(selected)
            val_names = ",".join(names)
            
            self.enabled_relays_var.set(val_enabled)
            self.values["RELAY_NAMES"] = val_names
            
            try:
                cfg = self.config_manager.load_config()
                cfg["ENABLED_RELAYS"] = val_enabled
                cfg["RELAY_NAMES"] = val_names
                self.config_manager.save_config(cfg)
            except Exception as e:
                messagebox.showerror("Save Error", f"Failed to update config.ini:\n{e}", parent=dialog)
                return
            dialog.destroy()
            
        ttk.Button(dialog, text="Save", command=on_save).pack(pady=5)
        
        self.ui_utilities.center_toplevel(self.root, dialog)
        dialog.lift()
        dialog.focus_force()

    def _build_bmc_credentials_section(self):
        self.add_separator()
        bmc_fields = [("BMC Address", "BMC_IP", False), ("BMC root Pass", "BMC_ROOT_PASS", True), ("BMC debuguser Pass", "BMC_DEBUGUSER_PASS", True)]
        for label, key, mask in bmc_fields:
            self.add_field(label, key, is_password=mask)

    def _build_pdu_credentials_section(self):
        self.add_separator()
        raritan_fields = [("Raritan Username", "PDU_USER", False), ("Raritan Password", "PDU_PASS", True)]
        for label, key, mask in raritan_fields:
            self.add_field(label, key, is_password=mask)
        self.current_row += 1

    def _build_sut_outlets_section(self):
        ttk.Label(self.field_frame, text="In format HOST:OUTLET.\ne.g. jf12x1234ap1234.xyz.intel.com:99", foreground="#aaaaaa", font=("Consolas", 9)).grid(row=self.current_row, column=1, sticky="w", padx=5, pady=(2, 0))
        self.current_row += 1
        self.add_sut_frame.grid(row=self.current_row, column=0, columnspan=1, pady=5)
        ttk.Button(self.add_sut_frame, text="Add SUT_AC Outlet", command=lambda: self.add_sut_field(f"SUT_AC{len(self.sut_entries)+1}")).pack(anchor="center")
        self.current_row += 1
        self.bottom_sep.grid(row=self.current_row, column=0, columnspan=3, sticky="we", pady=5)
        self.current_row += 1
        self.add_sut_field("SUT_AC1", self.values.get("SUT_AC1", ""))
        
        for key in [k for k in self.config_manager.get_sorted_sut_keys(self.values, filter_empty=False) if k != "SUT_AC1"]:
            self.add_sut_field(key, self.values.get(key, ""))

    def _build_action_buttons_section(self):
        btn_container = ttk.Frame(self.bottom_frame)
        btn_container.pack(anchor="center")
        ttk.Button(btn_container, text="Import from iConsole", command=self.import_from_iconsole).pack(side="left", padx=10)
        ttk.Button(btn_container, text="Create & Pin Shortcut", command=lambda: self.config_manager.create_pal_shortcut(
                                os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "PAL_OKS.pyw"),
                                self.entries["PYTHON_PATH"].get().strip().strip('"').strip("'"),
                                parent=self.root)
                            ).pack(side="left", padx=10)
        self.save_btn = ttk.Button(btn_container, text="Save & Exit", command=self.save_and_exit)
        self.save_btn.pack(side="left", padx=10)

    def build_ui(self):
        self._build_sut_type_section()
        self._build_webcam_section()
        self._build_com_ports_section()
        self._build_paths_section()
        self._build_bmc_credentials_section()
        self._build_pdu_credentials_section()
        self._build_sut_outlets_section()
        self._build_action_buttons_section()

    def add_separator(self):
        ttk.Separator(self.field_frame, orient="horizontal").grid(row=self.current_row, column=0, columnspan=3, sticky="we", pady=5)
        self.current_row += 1

    def add_field(self, label, key, is_path=False, folder=False, is_password=False):
        ttk.Label(self.field_frame, text=label, anchor="e").grid(row=self.current_row, column=0, sticky="e", padx=5, pady=self.uniform_pady)
        if is_password:
            ent = ttk.Entry(self.field_frame, show='*')
        else:
            ent = ttk.Entry(self.field_frame)
        ent.grid(row=self.current_row, column=1, sticky="we", padx=5, pady=self.uniform_pady)
        ent.insert(0, self.values.get(key, ""))
        self.entries[key] = ent
        self.label_map[key] = label
        if is_path:
            btn = ttk.Button(self.field_frame, text="Browse", width=6)
            btn.grid(row=self.current_row, column=2, sticky="w", padx=5, pady=self.uniform_pady)
            btn.configure(command=(lambda e=ent: self.ui_utilities.pick_folder(e)) if folder else (lambda e=ent: self.ui_utilities.pick_file(e)))
        if is_password:
            btn = ttk.Button(self.field_frame, text="🔒", width=4, style="IconButton.TButton")
            btn.grid(row=self.current_row, column=2, sticky="w", padx=5, pady=self.uniform_pady)
            btn.bind('<ButtonPress-1>', lambda e: self._toggle_password_view(ent, btn, True))
            btn.bind('<ButtonRelease-1>', lambda e: self._toggle_password_view(ent, btn, False))
        self.current_row += 1
        
    def add_sut_field(self, key, value=""):
        row = self.current_row
        label_text = f"{key} Outlet"
        label = ttk.Label(self.field_frame, text=label_text, anchor="e")
        label.grid(row=row, column=0, sticky="e", padx=5, pady=self.uniform_pady)
        entry = ttk.Entry(self.field_frame)
        entry.grid(row=row, column=1, sticky="we", padx=5, pady=self.uniform_pady)
        entry.insert(0, value)
        delete_btn = None
        if key != "SUT_AC1": 
            delete_btn = ttk.Button(self.field_frame, text="X", width=3, command=lambda k=key: self.delete_sut_entry(k))
            delete_btn.grid(row=row, column=2, sticky="w", padx=5, pady=self.uniform_pady)
        self.sut_entries[key] = {'label': label, 'entry': entry, 'delete_btn': delete_btn, 'row': row}
        self.label_map[key] = label_text
        self.current_row += 1
        self.add_sut_frame.grid_forget()
        self.add_sut_frame.grid(row=self.current_row, column=0, columnspan=1, pady=5)
        self.bottom_sep.grid_forget()
        self.bottom_sep.grid(row=self.current_row+1, column=0, columnspan=3, sticky="we", pady=5)
        self.update_geometry()

    def delete_sut_entry(self, key_to_delete):
        sorted_keys = self.config_manager.get_sorted_sut_keys(self.sut_entries, filter_empty=False)
        
        remaining_values = [
            self.sut_entries[key]['entry'].get() 
            for key in sorted_keys 
            if key != key_to_delete
        ]
        
        self._rebuild_sut_fields(remaining_values)

    def update_geometry(self):
        self.root.update_idletasks()
        self.root.geometry("")

    def _toggle_password_view(self, entry, btn, show):
        if show:
            entry.config(show='')
            btn.config(text="👁")
        else:
            entry.config(show='*')
            btn.config(text="🔒")

    def run_auto_detect(self):
        bmc, bios, error_msg = self._detect_com_ports() 
        MAX_LABEL_WIDTH = 11 
        if error_msg:
            self.ui_utilities.show_fixed_info(self.root, "COM Detection Failed", error_msg, is_error=True) 
        else:
            ports_updated = []
            if bmc: 
                self.entries["BMCCOM"].delete(0, tk.END)
                self.entries["BMCCOM"].insert(0, bmc)
                ports_updated.append(f"{'BMC Serial':>{MAX_LABEL_WIDTH}} : {bmc}")
            if bios: 
                self.entries["BIOSCOM"].delete(0, tk.END)
                self.entries["BIOSCOM"].insert(0, bios)
                ports_updated.append(f"{'BIOS Serial':>{MAX_LABEL_WIDTH}} : {bios}")
            if ports_updated:
                message = "\n".join(ports_updated)
                self.ui_utilities.show_autoclose_message("COM Detection Success", message, timeout=1500, parent=self.root)
            else:
                self.ui_utilities.show_autoclose_message("COM Detection Success", "COM detection ran, but found no ports to update.", timeout=1500, parent=self.root)

    def program_dc_scm(self):
        python_folder = self.entries["PYTHON_PATH"].get().strip().strip('"').strip("'")
        if not python_folder:
            messagebox.showerror("Error", "Python Path is empty. Please configure it first.", parent=self.root)
            return
        python_exe = os.path.join(python_folder, "python.exe")
        if not os.path.exists(python_exe):
            messagebox.showerror("Error", f"python.exe not found in:\n{python_folder}", parent=self.root)
            return
        update_script = os.path.join(os.path.dirname(os.path.abspath(__file__)), "update_cigit.py")
        if not os.path.exists(update_script):
            messagebox.showerror("Error", f"Script not found:\n{update_script}", parent=self.root)
            return
        if not os.path.exists(self.FT_PROG_EXE):
            messagebox.showerror("Error", f"FT_Prog program not found:\n{self.FT_PROG_EXE}", parent=self.root)
            return

        def run_in_thread():
            try:
                update_cmd = f'"{python_exe}" "{update_script}" --programming'
                flash_cmd = f'"{python_exe}" "{self.FTDI_SCRIPT}"'
                
                cmd_str = (
                    f'{update_cmd} && '
                    f'({flash_cmd} & echo. & echo Process complete. Press Enter to close window... & pause > nul) || '
                    f'(echo. & echo ci.git update FAILED. Aborting. & pause)'
                )
                
                subprocess.run(f'cmd /c "{cmd_str}"', creationflags=subprocess.CREATE_NEW_CONSOLE)
            except Exception as e:
                self.root.after(0, lambda: messagebox.showerror("Error", f"Failed to launch programming task: {e}", parent=self.root))

        threading.Thread(target=run_in_thread, daemon=True).start()

    def finalize_import_gui_update(self, hwnd):
        self.refresh_after_iconsole_import()
        self.root.lift()
        self.root.attributes("-topmost", True)
        self.root.after(200, lambda: self.root.attributes("-topmost", False))
        self.root.focus_force()
        try:
            import win32gui
            import win32con
            if hwnd and win32gui.IsWindow(hwnd):
                win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
                win32gui.SetForegroundWindow(hwnd)
        except Exception:
            pass 

    def import_from_iconsole(self):
        task = IConsoleImportTask(self)
        task.run()

    def refresh_after_iconsole_import(self):
        new_values = self.config_manager.load_config() 
        current_gui_values = {k: w.get().strip() for k, w in self.entries.items()}
        current_gui_values.update({k: w['entry'].get().strip() for k, w in self.sut_entries.items()})
        
        current_webcam = self.webcam_var.get()
        current_enabled_relays = self.enabled_relays_var.get()
        
        PROTECTED_KEYS = [
            "PUTTY_PATH", "PUTTY_LOGS_PATH", "PYTHON_PATH", "PYTHONSV_PATH",
            "BMC_ROOT_PASS", "BMC_DEBUGUSER_PASS", "PDU_USER", "PDU_PASS"
        ]
        for key in PROTECTED_KEYS:
            if key in current_gui_values:
                new_values[key] = current_gui_values[key]

        for key, entry in self.entries.items():
            if key in new_values:
                entry.delete(0, tk.END)
                entry.insert(0, new_values[key])

        sut_values = [new_values.get(k, "") for k in self.config_manager.get_sorted_sut_keys(new_values, filter_empty=False)]
        
        if current_webcam:
            new_values["WEBCAM"] = current_webcam
        else:
            self.webcam_var.set(new_values.get("WEBCAM", "").lower())
        
        if current_enabled_relays:
            new_values["ENABLED_RELAYS"] = current_enabled_relays
        else:
            self.enabled_relays_var.set(new_values.get("ENABLED_RELAYS", ""))
        
        self._rebuild_sut_fields(sut_values)
        
        self.values = new_values 

    def _rebuild_sut_fields(self, sut_values):
        for w in self.sut_entries.values():
            w['label'].destroy()
            w['entry'].destroy()
            if w['delete_btn']: w['delete_btn'].destroy()
        self.sut_entries.clear()
        
        self.current_row = self.entries["PDU_PASS"].grid_info()['row'] + 3
        self.add_sut_frame.grid_forget()
        self.bottom_sep.grid_forget()
        self.add_sut_frame.grid(row=self.current_row, column=0, columnspan=1, pady=5)
        self.current_row += 1
        self.bottom_sep.grid(row=self.current_row, column=0, columnspan=3, sticky="we", pady=5)
        self.current_row += 1
        
        if sut_values:
            self.add_sut_field("SUT_AC1", sut_values[0])
            for i, val in enumerate(sut_values[1:]):
                self.add_sut_field(f"SUT_AC{i+2}", val)
        else:
            self.add_sut_field("SUT_AC1", "")
            
        self.update_geometry()

    def perform_final_save(self, all_data, sut_data):
        final_values = {"SUT_TYPE": self.sut_type_var.get()}
        final_values["WEBCAM"] = self.webcam_var.get()
        final_values["ENABLED_RELAYS"] = self.enabled_relays_var.get()
        
        # Load latest config from disk to preserve dynamic values that might have changed
        # (e.g. if user moved windows while setup was open)
        try:
            latest_disk_config = self.config_manager.load_config()
        except:
            latest_disk_config = self.values

        dynamic_keys = [
            "RELAY_NAMES", "CAMERA_ROTATION", "CAMERA_ZOOM", 
            "CAMERA_OFFSET_X", "CAMERA_OFFSET_Y", 
            "CAMERA_WIN_X", "CAMERA_WIN_Y", "CAMERA_WIN_W", "CAMERA_WIN_H",
            "PAL_WIN_X", "PAL_WIN_Y"
        ]

        for key in dynamic_keys:
            val = latest_disk_config.get(key) or self.values.get(key)
            if val: final_values[key] = val

        path_keys = ["PUTTY_PATH", "PUTTY_LOGS_PATH", "PYTHON_PATH", "PYTHONSV_PATH"]
        standard_keys = [k for k in self.entries.keys() if not k.startswith("SUT_AC")]
        for key in standard_keys:
            value = all_data.get(key, "").strip()
            if key in path_keys and value:
                value = value.replace("/", "\\")
            final_values[key] = value
            
        final_values.update(dict(sut_data))
        try:
            self.config_manager.save_config(final_values)
            self.ui_utilities.show_autoclose_message("Saved", f"Configuration saved to {self.CONFIG_FILE}", timeout=1500,
                                                     on_close=lambda: (self.config_manager.close_existing_pal_oks_deferred(), self.root.destroy()),
                                                     parent=self.root)
        except Exception as e:
            messagebox.showerror("Save Error", f"Failed to save configuration:\n{e}", parent=self.root)
            self.save_btn.config(state="normal")

    def show_com_warning_dialog(self, warnings_list, all_data, sut_data):
        dialog = tk.Toplevel(self.root)
        dialog.title("Critical Warning")
        dialog.withdraw() 
        dialog.configure(bg="#232323")
        dialog.grab_set() 
        dialog.transient(self.root)
        
        dialog.update_idletasks()
        self.ui_utilities.apply_window_dwm(dialog, is_dialog=True)

        dialog.result = False 
        warning_message = "The following issues were detected:\n\n" + "\n\n".join(warnings_list)
        ttk.Label(dialog, text="⚠️ WARNING ⚠️", font=("Consolas", 10, "bold"), foreground="#FFD700").pack(padx=15, pady=(15, 5))
        msg_frame = ttk.Frame(dialog)
        msg_frame.pack(padx=15, pady=(0, 15), fill="x")
        msg_label = ttk.Label(msg_frame, text=warning_message, justify=tk.LEFT, background="#232323", foreground="#ffffff", wraplength=400)
        msg_label.pack(fill="x", expand=True)
        ttk.Separator(msg_frame, orient="horizontal").pack(fill="x", pady=10)
        ttk.Label(msg_frame, text="Invalid entries may impact functionality.\n\nDo you want to save anyway?", justify=tk.LEFT, background="#232323", foreground="#ffffff", wraplength=400).pack(fill="x", expand=True)
        button_frame = ttk.Frame(dialog)
        button_frame.pack(pady=(0, 15), anchor="center")
        def confirm_save_and_destroy():
            dialog.result = True
            dialog.destroy()
        confirm_btn = ttk.Button(button_frame, text="✅ Confirm Save",
                                 command=confirm_save_and_destroy) 
        confirm_btn.pack(side="left", padx=10) 
        back_btn = ttk.Button(button_frame, text="⬅️ Go Back to Edit",
                              command=dialog.destroy)
        back_btn.pack(side="left", padx=10)
        dialog.update_idletasks()
        self.ui_utilities.center_toplevel(self.root, dialog) 
        dialog.deiconify()
        dialog.attributes("-topmost", True)
        dialog.lift()
        dialog.focus_force()
        dialog.after(50, dialog.focus_force)
        self.root.wait_window(dialog)
        if hasattr(dialog, 'result') and dialog.result:
            self.perform_final_save(all_data, sut_data)
        else:
            self.save_btn.config(state="normal")

    def _validate_sut_type(self, errors):
        if not self.sut_type_var.get():
            errors.append("Select SUT Type: Must choose either Single Socket or Multisocket.")
            
    def _validate_webcam(self, all_data, errors):
        if not all_data.get("WEBCAM"):
            errors.append("Select Webcam Option: Must choose either Yes or No.")
            
    def _validate_relay_config(self, all_data, errors):
        if all_data.get("RELAYCOM") and not self.enabled_relays_var.get():
            errors.append("Relay Configuration Required: 8Ch Relay COM is set but no relays are enabled.\nPlease click 'Configure 8Ch Relay'.")

    def _validate_com_ports(self, all_data, errors, section_warnings):
        if self.serial_tools is None:
            return
        available_ports = [port.device.upper() for port in self.serial_tools.comports()]
        com_fields = ["RELAYCOM", "BMCCOM", "BIOSCOM"]
        for key in com_fields:
            port = all_data.get(key)
            label = self.label_map.get(key, key)
            if not port:
                section_warnings.append(f"**{label}** is blank.")
            elif port.upper() not in available_ports:
                section_warnings.append(f"**{label}** ({port}) not found in Device Manager.")

    def _validate_paths(self, all_data, errors, section_warnings):
        path_checks = [
            ("PYTHON_PATH", True), ("PUTTY_PATH", False),
            ("PUTTY_LOGS_PATH", False), ("PYTHONSV_PATH", False)
        ]
        for key, required in path_checks:
            path = all_data.get(key)
            label = self.label_map.get(key, key)
            if not path:
                if required: errors.append(f"Path Error: **{label}** is required.")
                else: section_warnings.append(f"**{label}** is blank.")
            elif key == "PUTTY_LOGS_PATH":
                try: os.makedirs(path, exist_ok=True)
                except OSError: section_warnings.append(f"Could not create **{label}** at {path}")
            elif not os.path.exists(path):
                if key == "PYTHON_PATH":
                    errors.append(f"Path Error: **{label}** does not exist at {path}")
                else:
                    section_warnings.append(f"**{label}** does not exist at {path}")
            elif key == "PYTHON_PATH":
                if not os.path.exists(os.path.join(path, "python.exe")):
                    errors.append(f"Path Error: **{label}** must contain 'python.exe'.")
                elif not os.path.exists(os.path.join(path, "pythonw.exe")):
                    section_warnings.append(f"Path Warning: **{label}** is missing 'pythonw.exe'. Background tools may fail.")

    def _validate_sut_outlets(self, all_data, errors, section_warnings):
        sut_data = []
        pdu_usage = {}
        for i, key in enumerate(self.config_manager.get_sorted_sut_keys(all_data, filter_empty=False)):
            new_key = f"SUT_AC{i+1}"
            val = all_data[key]
            sut_data.append((new_key, val))
            if not val: 
                section_warnings.append(f"**{self.label_map.get(key, key)}** is blank.")
                continue
            
            parts = val.rsplit(':', 1)
            if len(parts) != 2 or not parts[0].strip() or not parts[1].strip():
                errors.append(f"Format Error: **{self.label_map.get(key, key)}** must be HOST:OUTLET (e.g. myhost:1).")
            else: pdu_usage.setdefault(val, []).append(self.label_map.get(key, key))
        for val, keys in pdu_usage.items():
            if len(keys) > 1: errors.append(f"Duplicate Error: **{val}** used by {', '.join(keys)}")
        return sut_data

    def _validate_bmc_credentials(self, all_data, section_warnings):
        for key in ["BMC_IP", "BMC_ROOT_PASS", "BMC_DEBUGUSER_PASS"]:
            if not all_data.get(key): 
                label = self.label_map.get(key, key)
                section_warnings.append(f"**{label}** is blank.")

    def _validate_pdu_credentials(self, all_data, sut_data, errors, section_warnings, ssh_warnings):
        pdu_u, pdu_p = all_data.get("PDU_USER"), all_data.get("PDU_PASS")
        if (pdu_u or pdu_p) and not (pdu_u and pdu_p):
            errors.append("Credential Error: PDU Username and Password must both be filled or both empty.")
        elif not pdu_u: 
            section_warnings.append(f"**{self.label_map.get('PDU_USER')}** is blank.")
            section_warnings.append(f"**{self.label_map.get('PDU_PASS')}** is blank.")

        if not errors and pdu_u and pdu_p:
            if not self.SSHManager:
                return
            checked_hosts = set()
            for _, val in sut_data:
                if not val or ':' not in val: continue
                host = val.rsplit(':', 1)[0].strip()
                if host in checked_hosts: continue
                checked_hosts.add(host)
                try:
                    with self.SSHManager(host, pdu_u, pdu_p, timeout=5): pass
                except Exception as e:
                    err_msg = str(e)
                    if "[Errno 11001]" in err_msg:
                        err_msg = "Address unreachable"
                    ssh_warnings.append(f"Could not connect to PDU {host}.\nError: {err_msg}")

    def validate_configuration(self, all_data):
        critical_errors = []
        
        com_warnings = []
        path_warnings = []
        bmc_warnings = []
        pdu_warnings = []
        sut_warnings = []
        ssh_warnings = []
        
        self._validate_sut_type(critical_errors)
        self._validate_webcam(all_data, critical_errors)
        self._validate_relay_config(all_data, critical_errors)
        self._validate_com_ports(all_data, critical_errors, com_warnings)
        self._validate_paths(all_data, critical_errors, path_warnings)
        sut_data = self._validate_sut_outlets(all_data, critical_errors, sut_warnings)
        self._validate_bmc_credentials(all_data, bmc_warnings)
        self._validate_pdu_credentials(all_data, sut_data, critical_errors, pdu_warnings, ssh_warnings)
        
        general_warnings = []
        if com_warnings:
            general_warnings.append("--- COM Port Warnings ---")
            general_warnings.extend(com_warnings)
        if path_warnings:
            general_warnings.append("--- Path Warnings ---")
            general_warnings.extend(path_warnings)
        if bmc_warnings:
            general_warnings.append("--- BMC Settings Warnings ---")
            general_warnings.extend(bmc_warnings)
        if pdu_warnings:
            general_warnings.append("--- PDU Credential Warnings ---")
            general_warnings.extend(pdu_warnings)
        if sut_warnings:
            general_warnings.append("--- SUT Outlet Warnings ---")
            general_warnings.extend(sut_warnings)
        if ssh_warnings:
            general_warnings.append("--- SSH Connection Failures ---")
            general_warnings.extend(ssh_warnings)
            
        return critical_errors, sut_data, general_warnings
        
    def save_and_exit(self):
        self.save_btn.config(state="disabled")
        self.root.config(cursor="watch")
        self.root.update_idletasks()
        all_data = {k: w.get().strip() for k, w in self.entries.items()}
        all_data.update({k: w['entry'].get().strip() for k, w in self.sut_entries.items()})
        
        all_data["WEBCAM"] = self.webcam_var.get()
        
        for key, value in all_data.items():
            if key not in self.config_manager.ENCRYPTED_KEYS and value:
                all_data[key] = value.strip('"').strip("'")

        path_keys = ["PUTTY_PATH", "PUTTY_LOGS_PATH", "PYTHON_PATH", "PYTHONSV_PATH"]
        for pk in path_keys:
            if all_data.get(pk):
                all_data[pk] = os.path.normpath(all_data[pk])
        
        critical_errors, sut_data, general_warnings = self.validate_configuration(all_data)

        self.root.config(cursor="") 
        if critical_errors:
            self.ui_utilities.show_modal_error(self.root, "Critical Errors", "\n\n".join(critical_errors))
            self.save_btn.config(state="normal")
            return

        if general_warnings:
            self.show_com_warning_dialog(general_warnings, all_data, sut_data)
        else:
            self.perform_final_save(all_data, sut_data)

    def _detect_com_ports(self):
        script_path = os.path.join(self.config_manager.CI_GIT_BASE, "scripts", "oks-ls-comports.py")
        if not os.path.exists(script_path):
            return None, None, f"COM detection script not found:\n{script_path}"
        try:
            python_folder = self.entries["PYTHON_PATH"].get().strip().strip('"').strip("'")
            python_exe = os.path.join(python_folder, "python.exe")
            if not os.path.exists(python_exe):
                python_exe = sys.executable
            result = subprocess.run([python_exe, script_path], capture_output=True, text=True, check=True, creationflags=0x08000000)
            output = result.stdout.strip().splitlines()
            
            def _parse_com_port_line(line, prefix):
                if prefix in line:
                    parts = line.split("uses port")
                    if len(parts) > 1: return parts[1].strip()
                return ""

            bmc_com = next((_parse_com_port_line(line, "BMC: uses port") for line in output if "BMC:" in line), "")
            bios_com = next((_parse_com_port_line(line, "BIOS: uses port") for line in output if "BIOS:" in line), "")
            
            if not bmc_com and not bios_com: return None, None, "COM port detection ran, but failed to find BMC or BIOS ports. Check hardware connection."
            return bmc_com, bios_com, None 
        except Exception as e:
            return None, None, f"Failed to detect COM ports due to system error:\n{e}"

    @staticmethod
    def ask_for_python_path(config_manager, parent=None):
        messagebox.showinfo(
            "Important Setup Step",
            "The next window will ask you to select your Python installation folder. (e.g., C:\\Python311)\n\n"
            "This folder MUST contain the 'python.exe' file, which is critical for certain setup functions.\n\nPlease click 'OK' to proceed to the folder selection.",
            parent=parent
        )
        python_path = filedialog.askdirectory(
            title="Select Your Python Installation Folder (Containing python.exe)",
            initialdir="C:\\",
            mustexist=True,
            parent=parent
        )
        if not python_path:
            return False 
        python_path = python_path.replace("/", "\\")
        python_exe = os.path.join(python_path, "python.exe")
        if not os.path.exists(python_exe):
            messagebox.showerror(
                "Path Error",
                f"The selected folder does not contain 'python.exe'.\nPlease select the correct Python installation folder (e.g., C:\\Python311).",
                parent=parent
            )
            return False 
        try:
            current_config = config_manager.load_config()
            current_config["PYTHON_PATH"] = python_path
            config_manager.save_config(current_config)
            return True
        except Exception as e:
            messagebox.showerror("Configuration Error", f"Failed to save PYTHON_PATH to config.ini:\n{e}", parent=parent)
            return False