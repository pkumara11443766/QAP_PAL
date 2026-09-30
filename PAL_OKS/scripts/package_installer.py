import sys
import subprocess
import tkinter as tk
from tkinter import ttk, messagebox
import threading
import urllib.parse

required_packages = [
    "colorama", "compo", "cryptography", "ftd2xx", "opencv-python", "paramiko", "pexpect", "Pillow",
    "psutil", "pyserial", "pywin32", "requests", "urllib3", "ymodem"
]
base_index_url = "https://intelpypi.intel.com/pythonsv/production"

IMPORT_MAP = {
    'pywin32': 'win32com',
    'pyserial': 'serial',
    'opencv-python': 'cv2',
    'Pillow': 'PIL'
}

class PackageInstaller:
    def __init__(self, root, progress_widget, continue_button, skip_button, install_context=None):
        self.root = root
        self.progress_widget = progress_widget
        self.continue_button = continue_button
        self.skip_button = skip_button
        self.auth_cache = {"user": None, "pass": None}
        self.all_installed = True
        self.install_context = install_context

    def _get_ui_utils(self):
        try:
            import ui_utilities
            return ui_utilities
        except ImportError:
            try:
                import scripts.ui_utilities as ui_utilities
                return ui_utilities
            except ImportError:
                return None

    def _try_load_cached_credentials(self):
        target = "intelpypi.intel.com"
        ui = self._get_ui_utils()
        if ui:
            return ui.read_windows_credential(target)
        return None, None

    def get_user_credentials(self, ignore_cache=False):
        if not ignore_cache:
            c_user, c_pass = self._try_load_cached_credentials()
            if c_user and c_pass:
                if c_user != self.auth_cache.get("user") or c_pass != self.auth_cache.get("pass"):
                    self.log(f"Using cached credentials for intelpypi.intel.com...\n")
                    return c_user, c_pass

        ui = self._get_ui_utils()
        if not ui:
            print("Warning: Could not import ui_utilities. Authentication dialog cannot be shown.")
            return None, None
        
        center_toplevel = ui.center_toplevel
        apply_window_dwm = ui.apply_window_dwm
            
        result = {}
        event = threading.Event()
        
        def ask_on_main():
            dialog = tk.Toplevel(self.root)
            dialog.title("Authentication Required")
            dialog.attributes("-topmost", True)
            
            dialog.update_idletasks()
            apply_window_dwm(dialog, is_dialog=True)
            center_toplevel(self.root, dialog)
            
            dialog_style = ttk.Style()
            dialog_style.configure("Auth.TFrame", background="#EFEFEF")
            dialog_style.configure("Auth.TLabel", foreground="black", background="#EFEFEF")
            dialog_style.configure("Auth.TButton", font=("Consolas", 9, "bold"), relief='flat', background="#a9a9a9", foreground="#000000", padding=(2,2))
            dialog_style.map("Auth.TButton", background=[('active','#6fcded')], foreground=[('active','#000000')])
            
            frame = ttk.Frame(dialog, style="Auth.TFrame", padding=10)
            frame.pack(expand=True, fill="both")
            frame.columnconfigure(1, weight=1)

            ttk.Label(frame, text="Package installation failed.\nPlease enter credentials for intelpypi.intel.com:", style="Auth.TLabel").grid(row=0, column=0, columnspan=2, pady=5)
            
            ttk.Label(frame, text="Username:", style="Auth.TLabel").grid(row=1, column=0, sticky="w", padx=5, pady=2)
            user_entry = ttk.Entry(frame, width=30)
            user_entry.grid(row=1, column=1, sticky="ew", padx=5, pady=2)
            user_entry.focus_set()

            ttk.Label(frame, text="Password:", style="Auth.TLabel").grid(row=2, column=0, sticky="w", padx=5, pady=2)
            pass_entry = ttk.Entry(frame, show='*', width=30)
            pass_entry.grid(row=2, column=1, sticky="ew", padx=5, pady=2)

            def on_submit_action(key_event=None): 
                raw_user = user_entry.get().strip()
                if '@' in raw_user:
                    raw_user = raw_user.split('@')[0]
                result['user'] = raw_user
                result['pass'] = pass_entry.get().strip()
                dialog.destroy()
                event.set() 

            def on_cancel_action(key_event=None):
                result['user'] = None
                result['pass'] = None
                dialog.destroy()
                event.set()

            dialog.bind('<Return>', on_submit_action)
            user_entry.bind('<Return>', on_submit_action)
            pass_entry.bind('<Return>', on_submit_action)

            btn_frame = ttk.Frame(frame, style="Auth.TFrame")
            btn_frame.grid(row=3, column=0, columnspan=2, pady=10)
            ttk.Button(btn_frame, text="Submit", style="Auth.TButton", command=on_submit_action).pack(side="left", padx=10)
            ttk.Button(btn_frame, text="Cancel", style="Auth.TButton", command=on_cancel_action).pack(side="left", padx=10)

            dialog.protocol("WM_DELETE_WINDOW", on_cancel_action)
            
        self.root.after(0, ask_on_main)
        event.wait()
        return result.get('user'), result.get('pass')

    def log(self, message, tag=None):
        def _update_ui():
            if not self.progress_widget.winfo_exists(): return
            self.progress_widget.insert(tk.END, message, tag)
            self.progress_widget.see(tk.END)
        self.root.after(0, _update_ui)

    def _uninstall_package(self, package):
        cmd = [sys.executable, "-m", "pip", "uninstall", package, "-y"]
        try:
            subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=0x08000000)
            self.log(f"  Conflicting package '{package}' uninstalled.\n", "success")
        except Exception:
            self.log(f"  Failed to uninstall '{package}'. Please remove manually.\n", "error")

    def _execute_pip_command(self, packages, authenticated=False):
        cmd = [sys.executable, "-m", "pip", "install"]
        cmd.extend(packages)
        cmd.extend(["--disable-pip-version-check", "--no-input", "--timeout", "60", "--retries", "3"])

        safe_pass = None
        if authenticated and self.auth_cache["user"] and self.auth_cache["pass"]:
            safe_user = urllib.parse.quote(self.auth_cache["user"])
            safe_pass = urllib.parse.quote(self.auth_cache["pass"])
            authed_url = f"https://{safe_user}:{safe_pass}@intelpypi.intel.com/pythonsv/production"
            cmd.extend(["-i", authed_url])
        else:
            cmd.extend(["-i", base_index_url])

        process = None
        try:
            process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1, encoding='utf-8', errors='replace', creationflags=0x08000000)
            stdout_lines = []
            for line in iter(process.stdout.readline, ''):
                raw_pass = self.auth_cache["pass"]
                clean_line = line
                if raw_pass: clean_line = clean_line.replace(raw_pass, "****")
                if safe_pass: clean_line = clean_line.replace(safe_pass, "****")
                
                tag = None
                if "error" in clean_line.lower(): tag = "error"
                elif "warning" in clean_line.lower(): tag = "warning"
                self.log(clean_line, tag)
                stdout_lines.append(line)
            
            process.stdout.close()
            process.wait(timeout=300)
            
            return type('obj', (object,), {
                'returncode': process.returncode,
                'stdout': "".join(stdout_lines),
                'stderr': ""
            })()
        except subprocess.TimeoutExpired:
            if process: process.kill()
            return None
        except Exception as e:
            self.log(f"System Error during pip command: {e}\n", "error")
            return None

    def _check_existing_packages(self):
        self.log("Checking for required packages...\n")
        check_script_lines = []
        for pkg in required_packages:
            import_name = IMPORT_MAP.get(pkg, pkg.split('-')[0].split('==')[0])
            check_script_lines.append(f"try: import {import_name}\nexcept ImportError: print('{pkg}')")
        

        
        check_script = "\n".join(check_script_lines)
        result = subprocess.run([sys.executable, "-c", check_script], capture_output=True, text=True, creationflags=0x08000000)
        
        lines = result.stdout.strip().splitlines()
        missing_packages = [line for line in lines if not line.startswith("CONFLICT:")]
        conflicts = [line.split(":")[1] for line in lines if line.startswith("CONFLICT:")]
        
        installed_packages = [pkg for pkg in required_packages if pkg not in missing_packages]
        if installed_packages:
            self.log("Already Installed:\n", "success")
            for pkg in installed_packages:
                self.log(f"  {pkg}\n", "success")
        
        if conflicts:
            self.log("\nResolving conflicts...\n", "warning")
            for pkg in conflicts:
                self._uninstall_package(pkg)

        if missing_packages:
            self.log("\nMissing packages:\n", "error")
            for pkg in missing_packages:
                self.log(f"  {pkg}\n", "error")
        return missing_packages

    def _handle_authenticated_retries(self, missing_packages):
        self.log("Authentication required.\n", "info")
        u, p = self.get_user_credentials()
        if u is None:
            self.log("Authentication cancelled. Packages will not be installed.\n", "error")
            self.all_installed = False
            return

        self.auth_cache["user"] = u
        self.auth_cache["pass"] = p
        any_individual_failure = False
        for pkg in missing_packages:
            success = False
            while not success:
                if not self.progress_widget.winfo_exists(): return
                self.log(f"  Attempting to install {pkg}...\n")
                individual_result = self._execute_pip_command([pkg], authenticated=True)
                
                if individual_result and individual_result.returncode == 0:
                    success = True
                else:
                    individual_err_msg = individual_result.stdout.strip() if individual_result else "Unknown error or timeout"
                    is_individual_auth_error = any(x in individual_err_msg for x in ["401", "403", "Credentials not correct", "User was not found", "Could not find a version", "No matching distribution"])
                    
                    if is_individual_auth_error:
                        self.log(f"  Authentication failed for {pkg}. Requesting new credentials...\n", "error")
                        u_new, p_new = self.get_user_credentials(ignore_cache=True)
                        if u_new is not None:
                            self.auth_cache["user"] = u_new
                            self.auth_cache["pass"] = p_new
                        else:
                            self.log(f"  Login cancelled. Installation aborted.\n", "error")
                            self.all_installed = False
                            return
                    else:
                        self.log(f"  Non-authentication error for {pkg}. Skipping.\n", "error")
                        any_individual_failure = True
                        break
        
        if not any_individual_failure:
            self.all_installed = True

    def run_check(self):
        missing_packages = self._check_existing_packages()
        
        if not missing_packages:
            self.all_installed = True
            self.finalize()
            return

        if self.install_context is not None:
            self.install_context["installed"] = True

        self.log(f"\nAttempting to install missing packages...\n")
        
        c_user, c_pass = self._try_load_cached_credentials()
        authenticated = False
        if c_user and c_pass:
            self.auth_cache["user"] = c_user
            self.auth_cache["pass"] = c_pass
            authenticated = True
            self.log(f"Using cached credentials for intelpypi.intel.com...\n")

        result = self._execute_pip_command(missing_packages, authenticated=authenticated)

        if result and result.returncode == 0:
            self.all_installed = True
        else:
            err_msg = result.stdout.strip() if result else "Unknown error or timeout"
            is_auth_error = any(x in err_msg for x in ["401", "403", "Credentials not correct", "User was not found", "Could not find a version", "No matching distribution"])
            self.log(f"Initial bulk install failed. Attempting individual installs...\n", "error")
            self.all_installed = False

            if is_auth_error:
                self._handle_authenticated_retries(missing_packages)

        self.finalize()

    def finalize(self):
        def _finish_ui():
            if not self.progress_widget.winfo_exists(): return
            
            if self.all_installed:
                self.log("\nAll packages verified.\n", "success")
            else:
                self.log("\nProcess completed with warnings or errors.\n", "error")
            
            if not self.root.winfo_exists(): return

            self.skip_button.pack_forget() 
            self.continue_button.pack(side="left", padx=5)
            self.continue_button.config(state="normal")
        self.root.after(0, _finish_ui)

def install_packages(root, progress_widget, continue_button, skip_button, install_context=None):
    try:
        installer = PackageInstaller(root, progress_widget, continue_button, skip_button, install_context)
        installer.run_check()
    except tk.TclError:
        return
    except Exception as e:
        if root.winfo_exists():
             root.after(0, lambda: messagebox.showerror("Error", f"An unexpected error occurred: {e}", parent=root))