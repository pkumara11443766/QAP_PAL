import sys
import tkinter as tk
from tkinter import scrolledtext, ttk, messagebox
import threading
import os
import ctypes
import shutil

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.join(SCRIPT_DIR, "scripts"))

from scripts.package_installer import install_packages
from scripts.config_editor_ui import ConfigEditorApp
from scripts.ui_utilities import apply_pal_style, apply_window_dwm

def launch_config_editor():
    try:
        import scripts.config_manager as cm

        temp_root = tk.Tk()
        temp_root.overrideredirect(True)
        temp_root.geometry("0x0+0+0")
        temp_root.attributes("-alpha", 0.0)
        temp_root.attributes("-topmost", True)
        temp_root.lift()
        temp_root.focus_force()
        
        try:
            health_warning = cm.check_encryption_health()
            if health_warning:
                messagebox.showwarning("Encryption Key Warning", health_warning, parent=temp_root)

            current_config = cm.load_config()
            if not current_config.get("PYTHON_PATH") or not os.path.exists(os.path.join(current_config["PYTHON_PATH"], "python.exe")):
                while not ConfigEditorApp.ask_for_python_path(cm, parent=temp_root):
                    if not messagebox.askyesno(
                            "Setup Required", 
                            "The Python Folder is critical for setup and must be configured. Would you like to try again?\n\n(Choosing No will close the Setup utility.)",
                            parent=temp_root
                        ):
                        temp_root.destroy()
                        sys.exit(0)
        finally:
            temp_root.destroy()

        cm.close_existing_pal_oks_deferred()
        app_root = tk.Tk()
        
        app_root.update_idletasks()
        apply_window_dwm(app_root)

        app = ConfigEditorApp(app_root)
        app_root.lift()
        app_root.attributes('-topmost', True)
        app_root.after_idle(lambda: app_root.attributes('-topmost', False))
        app_root.focus_force()
        app_root.mainloop()
    except Exception as e:
        import traceback
        error_msg = f"A fatal error occurred after package check (missing dependencies):\n\n{e}\n\n{traceback.format_exc()}"
        try:
            ctypes.windll.user32.MessageBoxW(0, error_msg, "PAL Setup Error: CRITICAL FAILURE", 0x51010)
        except:
            pass

class SetupApp:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Checking Required Python Packages")
        self.root.protocol("WM_DELETE_WINDOW", lambda: self._on_finish_pkg_check(should_continue=True)) 
        
        style = ttk.Style()
        apply_pal_style(style)
        self.root.configure(bg="#232323")
        
        self.root.update_idletasks()
        apply_window_dwm(self.root)

        frame = ttk.Frame(self.root, padding=(10, 10, 10, 0))
        frame.pack(fill="both", expand=True)
        
        self.txt = scrolledtext.ScrolledText(frame, width=80, height=20, background="#333333", foreground="#ffffff", insertbackground="white")
        self.txt.pack(fill="both", expand=True)
        self.txt.tag_configure("success", foreground="#98FB98")
        self.txt.tag_configure("error", foreground="#FF6347")
        
        btn_frame = ttk.Frame(frame)
        btn_frame.pack(fill="x", pady=5)
        centered_btns_container = ttk.Frame(btn_frame)
        centered_btns_container.pack(anchor="center")
        
        self.continue_button = ttk.Button(centered_btns_container, text="Continue Setup", command=lambda: self._on_finish_pkg_check(should_continue=True))
        self.skip_button = ttk.Button(centered_btns_container, text="Skip Package Check", command=lambda: self._on_finish_pkg_check(should_continue=True))
        self.skip_button.pack(side="left", padx=5)
        
        self.install_context = {}

    def run(self):
        threading.Thread(target=lambda: install_packages(self.root, self.txt, self.continue_button, self.skip_button, self.install_context), daemon=True).start()
        self.root.mainloop()

    def _on_finish_pkg_check(self, should_continue):
        self.root.destroy()
        if should_continue:
            if self.install_context.get("installed", False):
                import subprocess
                subprocess.Popen([sys.executable, os.path.abspath(sys.argv[0]), "--skip-check"], creationflags=0x08000000)
                sys.exit(0)

            launch_config_editor()

def _ensure_config_exists():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    config_file = os.path.join(script_dir, 'config.ini')
    template_file = os.path.join(script_dir, 'scripts', 'config.ini.template')
    if not os.path.exists(config_file):
        if os.path.exists(template_file):
            try:
                shutil.copy2(template_file, config_file)
            except Exception as e:
                error_msg = f"CRITICAL FAILURE: Failed to copy config template:\n\n{e}"
                ctypes.windll.user32.MessageBoxW(0, error_msg, "PAL Setup Error", 0x51010)
                sys.exit(1)
        else:
            error_msg = f"CRITICAL FAILURE: Config template not found:\n\n{template_file}"
            ctypes.windll.user32.MessageBoxW(0, error_msg, "PAL Setup Error", 0x51010)
            sys.exit(1)

if __name__=="__main__":
    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("PALSetupUtilityStandalone")
    except Exception as e:
        print(f"Warning: Failed to set AppUserModelID: {e}")
    
    _ensure_config_exists()
    
    if "--skip-check" in sys.argv:
        launch_config_editor()
    else:
        try:
            app = SetupApp()
            app.run()
        except Exception as e:
            import traceback
            error_msg = f"A fatal error occurred during startup:\n\n{e}\n\n{traceback.format_exc()}"
            ctypes.windll.user32.MessageBoxW(0, error_msg, "PAL Setup Error: CRITICAL FAILURE", 0x51010)