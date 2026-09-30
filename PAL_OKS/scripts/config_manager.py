import os
import sys
import configparser
import subprocess
from cryptography.fernet import Fernet

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__)) 
CONFIG_FILE = os.path.abspath(os.path.join(SCRIPT_DIR, os.pardir, "config.ini"))
KEY_FILE = os.path.join(SCRIPT_DIR, "encryption_key.key")
ENCRYPTED_KEYS = ["BMC_ROOT_PASS", "BMC_DEBUGUSER_PASS", "PDU_PASS"]
CI_GIT_BASE = r"C:\Intel\ci.git"
LOG_DIR = r"C:\PAL_Logs"

VALID_CONFIG_KEYS = [
    "SUT_TYPE", "PAL_WIN_X", "PAL_WIN_Y", "WEBCAM", 
    "CAMERA_ROTATION", "CAMERA_ZOOM", "CAMERA_OFFSET_X", "CAMERA_OFFSET_Y", 
    "CAMERA_WIN_X", "CAMERA_WIN_Y", "CAMERA_WIN_W", "CAMERA_WIN_H",
    "ENABLED_RELAYS", "RELAY_NAMES",
    "RELAYCOM", "BMCCOM", "BIOSCOM",
    "PUTTY_PATH", "PUTTY_LOGS_PATH",
    "PYTHON_PATH", "PYTHONSV_PATH",
    "BMC_IP", "BMC_ROOT_PASS", "BMC_DEBUGUSER_PASS",
    "PDU_USER", "PDU_PASS"
]

def get_log_dir():
    if not os.path.exists(LOG_DIR):
        try: os.makedirs(LOG_DIR)
        except OSError: pass
            
    if os.path.exists(LOG_DIR) and os.access(LOG_DIR, os.W_OK):
        return LOG_DIR
    
    local_logs = os.path.abspath(os.path.join(SCRIPT_DIR, os.pardir, "logs"))
    if not os.path.exists(local_logs):
        try: os.makedirs(local_logs)
        except OSError: pass
    return local_logs

def check_encryption_health():
    if not os.path.exists(CONFIG_FILE):
        return None

    key_exists = os.path.exists(KEY_FILE)
    config = configparser.ConfigParser()
    config.read(CONFIG_FILE, encoding='utf-8-sig')

    if "MYVARS" in config:
        for key, value in config["MYVARS"].items():
            if key.upper() in ENCRYPTED_KEYS and value and value.startswith('gAAAAA'):
                if not key_exists:
                    return ("Encryption key is missing, but encrypted passwords exist in config.ini.\n\n"
                            "Passwords cannot be decrypted and will appear blank.\n\n"
                            "Please re-enter and save all passwords in the setup utility to generate a new key.")
                
                if not decrypt_value(value):
                     return ("Encryption key exists but failed to decrypt passwords.\n"
                             "The key may have been regenerated while old encrypted passwords remain.\n\n"
                             "Please re-enter and save all passwords in the setup utility.")
    return None

def load_key():
    if not os.path.exists(KEY_FILE):
        return None
    with open(KEY_FILE, "rb") as key_file:
        return key_file.read()

def generate_key():
    try:
        key = Fernet.generate_key()
        with open(KEY_FILE, "wb") as key_file:
            key_file.write(key)
    except Exception:
        pass

def encrypt_value(data):
    key = load_key()
    if not key:
        generate_key()
        key = load_key()
        if not key:
            print("FATAL: Could not load or generate encryption key. Saving password as plain text.", file=sys.stderr)
            return data
    
    f = Fernet(key)
    return f.encrypt(data.encode()).decode()

def decrypt_value(token):
    if not token or not token.startswith('gAAAAA'):
        return token

    key = load_key()
    if not key:
        return ""
        
    f = Fernet(key)
    try:
        return f.decrypt(token.encode()).decode()
    except Exception:
        return ""

def close_existing_pal_oks_deferred():
    try:
        import psutil
    except ImportError:
        print("Warning: psutil not available. Skipping existing PAL_OKS check.")
        return
        
    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            if proc.info['name'].lower() not in ['python.exe', 'pythonw.exe']:
                continue
                
            cmdline = proc.info['cmdline']
            if cmdline and any("pal_oks.pyw" in part.lower() for part in cmdline):
                proc.terminate()
                proc.wait(timeout=5)
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.TimeoutExpired):
            continue

def create_pal_shortcut(script_path, python_path, parent=None):
    from tkinter import messagebox
    try:
        import win32com.client
    except ImportError:
        messagebox.showerror("Error", "win32com.client not found. Please ensure pywin32 is installed.", parent=parent)
        return

    ui_utilities = None
    try:
        import ui_utilities
    except ImportError:
        try: import scripts.ui_utilities as ui_utilities
        except ImportError: pass

    try:
        pythonw_exe = os.path.join(python_path, "pythonw.exe")
        if not os.path.exists(pythonw_exe):
            messagebox.showerror("Error", f"pythonw.exe not found in:\n{python_path}", parent=parent)
            return

        if not os.path.exists(script_path):
            messagebox.showerror("Error", f"PAL_OKS.pyw not found at:\n{script_path}", parent=parent)
            return

        folder = os.path.dirname(script_path)
        ico_path = os.path.join(folder, "PAL.ico")
        icon_file = ico_path if os.path.exists(ico_path) else pythonw_exe

        shortcut_name = "PAL_OKS Shortcut.lnk"
        shortcut_path = os.path.join(folder, shortcut_name)
        
        shell = win32com.client.Dispatch("WScript.Shell")
        shortcut = shell.CreateShortcut(shortcut_path)
        shortcut.TargetPath = pythonw_exe
        shortcut.Arguments = f'"{script_path}"'
        shortcut.WorkingDirectory = folder
        shortcut.IconLocation = f"{icon_file},0"
        shortcut.Save()

        pttb_path = os.path.join(folder, "scripts", "pttb.exe")
        if os.path.exists(pttb_path):
            try:
                subprocess.run([pttb_path, shortcut_path], check=True, creationflags=0x08000000)
                if ui_utilities:
                    ui_utilities.show_autoclose_message("Shortcut Created", f"Shortcut created & Pinned.\n{shortcut_path}", timeout=1500, parent=parent)
                else:
                    messagebox.showinfo("Shortcut Created", f"Shortcut created & Pinned.\n{shortcut_path}", parent=parent)
            except subprocess.CalledProcessError:
                messagebox.showwarning("Pinning Failed", "Shortcut created, but failed to pin to taskbar.\n(pttb.exe returned error)", parent=parent)
        else:
            messagebox.showwarning("Pin to Taskbar", "pttb.exe not found. Shortcut created but not pinned.", parent=parent)
            if ui_utilities:
                ui_utilities.show_autoclose_message("Shortcut Created", f"Shortcut created in application folder.\n{shortcut_path}", timeout=1500, parent=parent)
            else:
                messagebox.showinfo("Shortcut Created", f"Shortcut created in application folder.\n{shortcut_path}", parent=parent)

    except Exception as e:
        messagebox.showerror("Error", f"Failed to create shortcut:\n{e}", parent=parent)

def load_config():
    config = configparser.ConfigParser()
    config.optionxform = str
    config_data = {k: "" for k in VALID_CONFIG_KEYS}

    if os.path.exists(CONFIG_FILE):
        config.read(CONFIG_FILE, encoding='utf-8-sig')
        if "MYVARS" in config:
            for key, value in config["MYVARS"].items():
                key_upper = key.upper()
                if value and key_upper in ENCRYPTED_KEYS:
                    value = decrypt_value(value)
                
                if key_upper in config_data or key_upper.startswith("SUT_AC"):
                    config_data[key_upper] = value
                    
    return config_data


def save_config(values):
    config = configparser.ConfigParser()
    config.optionxform = str
    
    values_to_save = values.copy()
    
    if values_to_save.get("WEBCAM", "").lower() == "no":
        cam_keys = ["CAMERA_ROTATION", "CAMERA_ZOOM", "CAMERA_OFFSET_X", "CAMERA_OFFSET_Y", 
                    "CAMERA_WIN_X", "CAMERA_WIN_Y", "CAMERA_WIN_W", "CAMERA_WIN_H"]
        for k in cam_keys:
            if k in values_to_save:
                del values_to_save[k]

    if not values_to_save.get("RELAYCOM", "").strip():
        for k in ["ENABLED_RELAYS", "RELAY_NAMES"]:
            if k in values_to_save:
                del values_to_save[k]

    for key, value in values_to_save.items():
        if value and key.upper() in ENCRYPTED_KEYS:
            values_to_save[key] = encrypt_value(value)

    ordered_keys = [
        "PAL_WIN_X", "PAL_WIN_Y",
        "SUT_TYPE",
        "WEBCAM",
        "CAMERA_ROTATION", "CAMERA_ZOOM", "CAMERA_OFFSET_X", "CAMERA_OFFSET_Y", 
        "CAMERA_WIN_X", "CAMERA_WIN_Y", "CAMERA_WIN_W", "CAMERA_WIN_H",
        "RELAYCOM",
        "ENABLED_RELAYS", "RELAY_NAMES",
        "BMCCOM", "BIOSCOM",
        "PUTTY_PATH", "PUTTY_LOGS_PATH", "PYTHON_PATH", "PYTHONSV_PATH",
        "BMC_IP", "BMC_ROOT_PASS", "BMC_DEBUGUSER_PASS",
        "PDU_USER", "PDU_PASS"
    ]
    
    final_dict = {}
    
    for key in ordered_keys:
        if key in values_to_save:
            final_dict[key] = values_to_save.pop(key)
            
    sut_keys = sorted([k for k in values_to_save.keys() if k.upper().startswith("SUT_AC")], 
                      key=lambda x: int(x.upper().replace("SUT_AC", "")) if x.upper().replace("SUT_AC", "").isdigit() else 999)
    for key in sut_keys:
        final_dict[key] = values_to_save.pop(key)
        
    final_dict.update(values_to_save)

    config["MYVARS"] = final_dict
    
    with open(CONFIG_FILE, "w", encoding='utf-8-sig') as f:
        config.write(f)
        
    _trim_trailing_blank_lines(CONFIG_FILE)

def _trim_trailing_blank_lines(filepath):
    try:
        with open(filepath, "r+", encoding='utf-8-sig') as f:
            lines = f.readlines()
            while lines and lines[-1].strip() == "":
                lines.pop()
            f.seek(0)
            f.writelines(lines)
            f.truncate()
    except Exception:
        pass

def get_sorted_sut_keys(config_data, filter_empty=True):
    keys = [k for k in config_data.keys() if k.upper().startswith("SUT_AC")]
    if filter_empty:
        keys = [k for k in keys if config_data[k]]
    
    return sorted(
        keys,
        key=lambda x: int(x.upper().replace("SUT_AC", "")) if x.upper().replace("SUT_AC", "").isdigit() else 999
    )