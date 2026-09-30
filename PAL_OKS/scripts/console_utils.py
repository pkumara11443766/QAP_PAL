import os
import time
import sys
import re
import ctypes

class Colors:
    CYAN = "\033[96m"
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RESET = "\033[0m"
    
    BOLD_CYAN = '\033[1;36m'
    BOLD_GREEN = '\033[1;32m'
    BOLD_YELLOW = '\033[1;33m'
    BOLD_RED = '\033[1;31m'
    END = '\033[1;37;0m'
    BG_BLACK = "\033[40m"

def enable_ansi_windows():
    if os.name != 'nt': return
    try:
        kernel32 = ctypes.windll.kernel32
        kernel32.SetConsoleMode(kernel32.GetStdHandle(-11), 7)
    except:
        pass

def press_enter(prompt="\nPress Enter to exit..."):
    try:
        input(prompt)
    except EOFError:
        pass

def set_console_title(title):
    if os.name == 'nt':
        try:
            ctypes.windll.kernel32.SetConsoleTitleW(title)
        except: pass

def bring_console_to_front():
    if os.name != 'nt': return
    time.sleep(0.2)
    try:
        import win32gui
        import win32con
        hwnd = ctypes.windll.kernel32.GetConsoleWindow()
        if hwnd:
            win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
            win32gui.SetWindowPos(hwnd, win32con.HWND_TOPMOST, 0, 0, 0, 0, win32con.SWP_NOMOVE | win32con.SWP_NOSIZE)
            win32gui.SetWindowPos(hwnd, win32con.HWND_NOTOPMOST, 0, 0, 0, 0, win32con.SWP_NOMOVE | win32con.SWP_NOSIZE)
            win32gui.SetForegroundWindow(hwnd)
    except ImportError:
        pass 
    except Exception:
        pass

def move_console_to_corner():
    if os.name != 'nt': return
    try:
        import win32gui
        import win32con
        hwnd = ctypes.windll.kernel32.GetConsoleWindow()
        if hwnd:
            win32gui.SetWindowPos(hwnd, 0, 0, 0, 0, 0, win32con.SWP_NOSIZE | win32con.SWP_NOZORDER)
    except ImportError:
        pass
    except Exception:
        pass

def strip_ansi_codes(text):
    ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
    return ansi_escape.sub('', text)