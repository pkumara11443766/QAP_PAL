import tkinter as tk
from tkinter import ttk, messagebox
import ctypes
import subprocess
import threading
from scripts.ui_utilities import apply_window_dwm, position_window_side
from scripts.console_utils import strip_ansi_codes

class MultiFlashDialog(tk.Toplevel):
    def __init__(self, parent, flash_options, callback=None, on_close=None):
        super().__init__(parent)
        self.callback = callback
        self.on_close_callback = on_close
        self.withdraw()
        self.title("Device Flash Selection")
        self.result = None
        
        self.configure(bg="#232323")
        self.resizable(False, False)
        self.transient(parent)
        
        self.main_frame = tk.Frame(self, bg="#232323", padx=16, pady=5)
        self.main_frame.pack(fill="both", expand=True)

        self.vars = {}
        
        select_all_frame = ttk.Frame(self.main_frame)
        select_all_frame.pack(pady=(0, 2))
        ttk.Button(select_all_frame, text="Select All", command=self.toggle_select_all).pack()

        check_frame = ttk.Frame(self.main_frame)
        check_frame.pack(pady=2)

        current_row = 0
        grid_options = [opt for opt in flash_options if opt != "AGG"]

        if "AGG" in flash_options:
            var = tk.IntVar()
            chk = ttk.Checkbutton(check_frame, text="AGG CPLD", variable=var)
            chk.grid(row=current_row, column=0, columnspan=2, padx=5, pady=2)
            self.vars["AGG"] = var
            current_row += 1

        for i, option in enumerate(grid_options):
            display_text = option
            if option == "SCM": display_text = "SCM CPLD"
            elif option == "HPM": display_text = "HPM CPLD"
            elif option == "BMC": display_text = "BMC SPI"
            elif option == "BIOS": display_text = "BIOS SPI"
            
            var = tk.IntVar()
            chk = ttk.Checkbutton(check_frame, text=display_text, variable=var)
            chk.grid(row=current_row + (i // 2), column=i % 2, sticky="w", padx=5, pady=2)
            self.vars[option] = var

        gfs_node_frame = ttk.Frame(self.main_frame)
        gfs_node_frame.pack(pady=(5, 5), fill="x")
        ttk.Label(gfs_node_frame, text="GFS Node:").pack(side="left", padx=(0, 5))
        self.gfs_node_var = tk.StringVar(value="Auto-Discover")
        self.gfs_node_entry = ttk.Entry(gfs_node_frame, textvariable=self.gfs_node_var)
        self.gfs_node_entry.pack(side="left", fill="x", expand=True)

        ttk.Label(self.main_frame, text="Choose Source Location", font=("Consolas", 10, "bold")).pack(pady=(5, 2))

        selection_btn_frame = ttk.Frame(self.main_frame)
        selection_btn_frame.pack(pady=2)
        ttk.Button(selection_btn_frame, text="Local / NFS", width=12, command=self.on_ok).pack(side="left", padx=2)
        ttk.Button(selection_btn_frame, text="GFS Node", width=12, command=self.on_gfs).pack(side="left", padx=2)

        apply_window_dwm(self, is_dialog=True)
        position_window_side(self, parent)
        self.deiconify()

        self.attributes("-topmost", True)
        self.after(10, lambda: self.focus_force())

        self.protocol("WM_DELETE_WINDOW", self.on_cancel)

    def on_ok(self):
        selected = [key for key, var in self.vars.items() if var.get() == 1]
        if not selected:
            messagebox.showwarning("No Selection", "Please select at least one device to flash.", parent=self)
            return
        gfs_node = self.gfs_node_var.get().strip()
        self.result = (",".join(selected), gfs_node)
        if self.callback: self.callback(self.result)
        if self.on_close_callback: self.on_close_callback()
        self.destroy()

    def on_gfs(self):
        selected = [key for key, var in self.vars.items() if var.get() == 1]
        if not selected:
            messagebox.showwarning("No Selection", "Please select at least one device to flash.", parent=self)
            return
        gfs_node = self.gfs_node_var.get().strip()
        self.result = ("GFS", selected, gfs_node)
        if self.callback: self.callback(self.result)
        self.destroy()

    def toggle_select_all(self):
        are_all_selected = all(var.get() == 1 for var in self.vars.values())
        new_state = 0 if are_all_selected else 1
        for var in self.vars.values():
            var.set(new_state)
            
    def on_cancel(self):
        if self.on_close_callback: self.on_close_callback()
        self.destroy()

class GFSFlashDialog(tk.Toplevel):
    def __init__(self, parent, selected_devices, callback=None, on_close=None):
        super().__init__(parent)
        self.callback = callback
        self.on_close_callback = on_close
        self.withdraw()
        self.title("GFS File Entry")
        self.result = None
        self.configure(bg="#232323")
        self.resizable(True, False)
        self.transient(parent)
        
        self.main_frame = tk.Frame(self, bg="#232323", padx=16, pady=5)
        self.main_frame.pack(fill="both", expand=True)

        self.entries = {}
        
        content_frame = ttk.Frame(self.main_frame)
        content_frame.pack(fill="both", expand=True, pady=(2, 5))
        
        ttk.Label(content_frame, text="Enter GFS Paths:\ne.g. /gfs/BKC/OKS-JC-DMR/25.52.2.162/cpld_scm.jic", 
                  font=("Consolas", 10, "bold"), justify="left").grid(row=0, column=1, sticky="w", pady=(0, 10))

        for i, dev in enumerate(selected_devices):
            lbl_text = dev
            if dev == "SCM": lbl_text = "SCM CPLD"
            elif dev == "HPM": lbl_text = "HPM CPLD"
            elif dev == "BMC": lbl_text = "BMC SPI"
            elif dev == "BIOS": lbl_text = "BIOS SPI"
            elif dev == "AGG": lbl_text = "AGG CPLD"

            ttk.Label(content_frame, text=lbl_text, anchor="e").grid(row=i+1, column=0, sticky="e", padx=(0, 5), pady=2)
            ent = ttk.Entry(content_frame, width=60)
            ent.grid(row=i+1, column=1, sticky="ew", pady=2)
            self.entries[dev] = ent
            
        content_frame.columnconfigure(1, weight=1)

        btn_frame = ttk.Frame(self.main_frame)
        btn_frame.pack(pady=(5, 2))

        ttk.Button(btn_frame, text="Begin Flash Process", width=22, command=self.on_flash).pack(side="left", padx=2)

        apply_window_dwm(self, is_dialog=True)
        position_window_side(self, parent)
        self.deiconify()

        self.attributes("-topmost", True)
        self.after(10, lambda: self.focus_force())

        self.protocol("WM_DELETE_WINDOW", self.on_cancel)

    def on_flash(self):
        file_map = {}
        for dev, ent in self.entries.items():
            val = ent.get().strip()
            if not val:
                messagebox.showwarning("Missing Path", f"Please enter a path for {dev}.", parent=self)
                return
            file_map[dev] = val
        
        flash_type_str = ",".join(self.entries.keys())
        self.result = (flash_type_str, file_map)
        if self.callback: self.callback(self.result)
        if self.on_close_callback: self.on_close_callback()
        self.destroy()

    def on_cancel(self):
        if self.on_close_callback: self.on_close_callback()
        self.destroy()

class PowerControlDialog(tk.Toplevel):
    def __init__(self, parent, title, command, on_close_callback=None):
        super().__init__(parent)
        self.on_close_callback = on_close_callback
        self.withdraw()
        self.title(title)
        
        self.configure(bg="#232323")
        self.resizable(True, True)
        self.minsize(280, 90)
        
        self.main_frame = tk.Frame(self, bg="#232323", padx=12, pady=5)
        self.main_frame.pack(fill="both", expand=True)
        
        self.text_area = tk.Text(self.main_frame, bg="#333333", fg="#ffffff", font=("Consolas", 10), height=5, width=42, state="disabled", relief="flat", wrap="word")
        self.text_area.pack(pady=(8, 5), fill="both", expand=True)
        
        self.command = command
        try:
            self.action = command[2].capitalize()
            self.outlets_str = command[7]
        except IndexError:
            self.action = "Unknown"
            self.outlets_str = ""
            
        self.process = None
        self.last_line_was_waiting = False
        
        apply_window_dwm(self, is_dialog=True)
        
        try:
            hwnd = ctypes.windll.user32.GetParent(self.winfo_id())
            if not hwnd: hwnd = self.winfo_id()
            style = ctypes.windll.user32.GetWindowLongW(hwnd, -16)
            style = (style & ~0x00010000) | 0x00020000
            ctypes.windll.user32.SetWindowLongW(hwnd, -16, style)
            ctypes.windll.user32.SetWindowPos(hwnd, 0, 0, 0, 0, 0, 0x0002 | 0x0001 | 0x0004 | 0x0020)
        except: pass
        
        position_window_side(self, parent)
        self.deiconify()

        self.attributes("-topmost", True)
        self.attributes("-topmost", False)
        self.after(10, lambda: self.focus_force())
        
        self.after(100, self.run_command)
        
        self.bind("<Destroy>", self._on_destroy)

    def run_command(self):
        threading.Thread(target=self._execute, daemon=True).start()

    def _on_destroy(self, event):
        if event.widget == self and self.on_close_callback:
            self.on_close_callback()
            self.on_close_callback = None

    def _execute(self):
        def _init_ui():
            if not self.winfo_exists(): return
            self.text_area.config(state="normal")
            pass
            self.text_area.config(state="disabled")
            
            self.text_area.tag_config("header", foreground="#6fcded", font=("Consolas", 10, "bold"))
            self.text_area.tag_config("info", foreground="#aaaaaa")
            self.text_area.tag_config("success", foreground="#98FB98", font=("Consolas", 10, "bold"))
            self.text_area.tag_config("error", foreground="#FF6347")
        
        try:
            self.after(0, _init_ui)
        except:
            return

        try:
            self.process = subprocess.Popen(self.command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1, encoding='utf-8', errors='replace', creationflags=0x08000000)
            
            output_buffer = []
            while True:
                line = self.process.stdout.readline()
                if not line and self.process.poll() is not None: break
                if line: 
                    output_buffer.append(line)
                    clean_line = strip_ansi_codes(line).strip()
                    if clean_line:
                        try:
                            self.text_area.after(0, lambda m=clean_line: self._append_status(m))
                        except: pass
            
            self.process.wait()
            
            def _finalize_ui():
                if not self.winfo_exists(): return
                self.text_area.config(state="normal")
                if self.process.returncode == 0:
                    self.after(3000, self.destroy)
                else:
                    self.text_area.insert(tk.END, f"\nError occurred:\n", "error")
                    raw_output = "".join(output_buffer)
                    clean_output = strip_ansi_codes(raw_output)
                    self.text_area.insert(tk.END, clean_output)
                    self.text_area.insert(tk.END, "\n\n" + "-"*65 + "\nPress Enter to close...")
                    self.bind("<Return>", lambda e: self.destroy())
                    self.focus_force()
                
                self.text_area.see(tk.END)
                self.text_area.config(state="disabled")
            
            try:
                self.after(0, _finalize_ui)
            except: pass
            
        except Exception as e:
            def _error_ui(err_msg):
                if not self.winfo_exists(): return
                self.text_area.config(state="normal")
                self.text_area.insert(tk.END, f"\nError: {err_msg}\n", "error")
                self.text_area.insert(tk.END, "\n\n" + "-"*65 + "\nPress Enter to close...")
                self.text_area.config(state="disabled")
                self.bind("<Return>", lambda e: self.destroy())
                self.focus_force()
            
            try:
                self.after(0, lambda: _error_ui(str(e)))
            except: pass

    def _append_status(self, msg):
        if not self.winfo_exists(): return
        self.text_area.config(state="normal")
        is_waiting = msg.strip().startswith("Waiting")
        tag = "success" if (msg.strip().startswith("Successfully") or msg.strip().startswith("Powered ") or msg.strip().startswith("Outlet(s)")) else "header"
        
        if self.last_line_was_waiting:
            self.text_area.delete("end-2c linestart", "end-1c")
            
        self.text_area.insert(tk.END, f"{msg}\n", tag)
        self.text_area.see(tk.END)
        self.text_area.config(state="disabled")
        self.last_line_was_waiting = is_waiting