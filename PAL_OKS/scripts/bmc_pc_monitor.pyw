import tkinter as tk
import threading
import time
import sys
import os
import ctypes
from ui_utilities import DockingManager, RECT, setup_custom_titlebar, minimize_window, apply_window_dwm
from console_utils import Colors, enable_ansi_windows
from ssh_utils import SSHManager

class SSHSession:
    def __init__(self, ip, username, password):
        self.ssh_manager = SSHManager(ip, username, password)
        self.connected = False

    def connect(self):
        if self.connected:
            return True
        try:
            self.ssh_manager.connect()
            self.connected = True
            return True
        except Exception:
            self.connected = False
            return False

    def disconnect(self):
        if self.connected:
            self.ssh_manager.disconnect()
            self.connected = False

    def run_i2c_cmd(self, register):
        if not self.connect():
            return None
            
        command = f"i2ctransfer -y 10 w2@0x51 0x40 {register} r1"
        try:
            _, stdout, _ = self.ssh_manager.exec_command(command, timeout=5)
            output = stdout.read().decode().strip()
            return int(output, 16) if output else None
        except (ValueError, Exception):
            self.disconnect()
            return None

class PostCodeMonitor:
    def __init__(self, session):
        self.session = session

    def fetch_data(self):
        cpld_raw = self.session.run_i2c_cmd("0x5c")
        if cpld_raw is None: return None

        bios_raw = self.session.run_i2c_cmd("0x58")
        if bios_raw is None: return None

        return {
            "fpga_err": cpld_raw >> 4,
            "fpga_status": cpld_raw & 0xF,
            "bios_code": bios_raw
        }

class PostCodeApp:
    def __init__(self, root, ip, user, password, parent_geom=None, parent_hwnd=None):
        self.root = root
        self.parent_geom = parent_geom
        self.parent_hwnd = parent_hwnd
        self.root.withdraw()
        self.root.title("POST Code Monitor")
        self.root.configure(bg="black")
        
        self.root.geometry("210x55")
        self.root.resizable(False, False)
        self.root.overrideredirect(True)
        
        self.title_bar = setup_custom_titlebar(self.root, "POST Code Monitor", on_close=self.on_close, on_minimize=lambda: minimize_window(self.root))
        self.root.after(10, self.set_appwindow)

        self.monitor = PostCodeMonitor(SSHSession(ip, user, password))
        self.running = True
        self.last_data = None
        self.fpga_ready = False
        
        self.cycle_count = 0  

        self.status_text = tk.Text(root, height=1, width=23, font=('Consolas', 12, 'bold'),
                                   bg='black', bd=0, highlightthickness=0, state='disabled')
        self.status_text.pack(expand=True)
        
        self.color_fpga = "cyan"
        self.color_bios = "lime"
        
        self.status_text.tag_config("fpga", foreground=self.color_fpga, justify='center')
        self.status_text.tag_config("bios", foreground=self.color_bios, justify='center')
        self.status_text.tag_config("info", foreground="orange", justify='center')
        
        self.status_text.tag_config("bracket_fpga", justify='center')
        self.status_text.tag_config("bracket_bios", justify='center')

        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        threading.Thread(target=self.worker_loop, daemon=True).start()
        self.update_display()
        
        self.docker = DockingManager(self.root, self.parent_hwnd)

    def set_appwindow(self):
        self.root.update_idletasks()
        apply_window_dwm(self.root)
        
        w = self.root.winfo_width()
        h = self.root.winfo_height()
        rect = RECT()
        ctypes.windll.user32.SystemParametersInfoW(48, 0, ctypes.byref(rect), 0)
        
        if self.parent_geom:
            px, py, pw, ph = self.parent_geom
            x = px + pw
            y = py + ph - h
            
            if x + w > rect.right:
                x = px - w
        else:
            x = rect.left
            y = rect.bottom - h
            
        self.root.geometry(f"{w}x{h}+{x}+{y}")
        
        self.root.wm_attributes("-topmost", 1)
        self.root.wm_attributes("-topmost", 0)
        self.root.deiconify()

    def worker_loop(self):
        while self.running:
            self.last_data = self.monitor.fetch_data()
            time.sleep(0.25)

    def update_display(self):
        if not self.running: return
        
        self.cycle_count += 1
        
        if self.cycle_count <= 2:
            fpga_bracket_color = "#004d4d"
            bios_bracket_color = "#006400"
        else:
            fpga_bracket_color = self.color_fpga 
            bios_bracket_color = self.color_bios 
            
        if self.cycle_count >= 22:
            self.cycle_count = 0

        self.status_text.tag_config("bracket_fpga", foreground=fpga_bracket_color)
        
        self.status_text.configure(state='normal')
        self.status_text.delete("1.0", tk.END)

        if self.last_data:
            d = self.last_data
            
            if not self.fpga_ready:
                if (d['fpga_err'] > 1) or (d['fpga_err'] == 1 and d['fpga_status'] >= 0xB):
                    self.fpga_ready = True
            
            self.status_text.insert(tk.END, "FPGA ", "fpga")
            self.status_text.insert(tk.END, "[", "bracket_fpga")
            self.status_text.insert(tk.END, f"{d['fpga_err']:X}.{d['fpga_status']:X}.", "fpga")
            self.status_text.insert(tk.END, "] ", "bracket_fpga")
            
            if self.fpga_ready:
                self.status_text.tag_config("bios", foreground=self.color_bios, overstrike=0)
                self.status_text.tag_config("bracket_bios", foreground=bios_bracket_color, overstrike=0)
                bios_content = f"{d['bios_code']:02X}"
            else:
                self.status_text.tag_config("bios", foreground="#808080", overstrike=1)
                self.status_text.tag_config("bracket_bios", foreground="#808080", overstrike=1)
                bios_content = "  "

            self.status_text.insert(tk.END, "BIOS ", "bios")
            self.status_text.insert(tk.END, "[", "bracket_bios")
            self.status_text.insert(tk.END, bios_content, "bios")
            self.status_text.insert(tk.END, "]", "bracket_bios")
        else:
            self.fpga_ready = False
            self.status_text.insert(tk.END, "POLLING BMC...", "info")

        self.status_text.configure(state='disabled')
        self.root.after(500, self.update_display)

    def on_close(self):
        self.running = False
        self.monitor.session.disconnect()
        self.root.destroy()

def run_cli(ip, user, password):
    session = SSHSession(ip, user, password)
    monitor = PostCodeMonitor(session)
    print(f"{Colors.CYAN}Monitoring BMC: {ip} (Ctrl+C to stop){Colors.RESET}")

    fpga_ready = False
    try:
        while True:
            data = monitor.fetch_data()
            if data:
                if not fpga_ready:
                    if (data['fpga_err'] > 1) or (data['fpga_err'] == 1 and data['fpga_status'] >= 0xB):
                        fpga_ready = True
                
                fpga_str = f"FPGA [{Colors.CYAN}{data['fpga_err']:X}.{data['fpga_status']:X}.{Colors.RESET}]"
                
                if fpga_ready:
                    bios_str = f"BIOS [{Colors.GREEN}{data['bios_code']:02X}{Colors.RESET}]"
                else:
                    bios_str = f"BIOS [  ]"
                
                print(f"\r{fpga_str} {bios_str}  ", end="")
            else:
                fpga_ready = False
                print(f"\r{Colors.YELLOW}[RECONNECTING...]{Colors.RESET}", end="")
            time.sleep(0.25)
    except KeyboardInterrupt:
        print("\nStopped.")
    finally:
        session.disconnect()

def main():
    enable_ansi_windows()
    
    import argparse
    parser = argparse.ArgumentParser(
        description="BMC PC Monitor - Monitor FPGA and BIOS POST codes via SSH.",
        epilog="Example: python bmc_pc_monitor.pyw -ip 192.168.1.100 -u root -p 0penBmc --cli"
    )
    parser.add_argument('-ip', help='BMC IP address')
    parser.add_argument('-u', dest='user', help='BMC Username')
    parser.add_argument('-p', dest='password', help='BMC Password')
    parser.add_argument('--cli', action='store_true', help='Run in CLI mode (no GUI)')
    parser.add_argument('--parent_geom', nargs=4, type=int, help='Parent window geometry: x y w h')
    parser.add_argument('--parent_hwnd', type=int, help='Parent window HWND')
    args = parser.parse_args()

    ip, user, pw = args.ip, args.user, args.password
    if not all([ip, user, pw]):
        try:
            import config_manager
            cfg = config_manager.load_config()
            ip = ip or cfg.get("BMC_IP")
            user = user or "root"
            pw = pw or cfg.get("BMC_ROOT_PASS")
        except ImportError:
            print(f"{Colors.YELLOW}Warning: Could not import config_manager. Dependencies might be missing.{Colors.RESET}")
        except Exception: pass

    if not all([ip, user, pw]):
        print(f"{Colors.RED}Error: Missing credentials (CLI args or config_manager).{Colors.RESET}")
        sys.exit(1)

    if args.cli:
        run_cli(ip, user, pw)
    else:
        import ctypes
        try:
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("BMCPCMonitorStandalone")
        except AttributeError:
            pass
            
        root = tk.Tk()
        PostCodeApp(root, ip, user, pw, parent_geom=args.parent_geom, parent_hwnd=args.parent_hwnd)
        root.mainloop()

if __name__ == "__main__":
    main()