import subprocess
import sys
import warnings
import os
import time
import glob
import datetime
import msvcrt
from scripts.console_utils import enable_ansi_windows, press_enter, Colors
from scripts.ssh_utils import SSHManager
from scripts import config_manager

class Y2ProgDetector:
    Y2PROG_PATH = r'C:\Program Files\Intel\Y2Prog CLI\Y2ProgCli.exe'

    def __init__(self):
        enable_ansi_windows()
        self.script_dir = os.path.dirname(os.path.abspath(__file__))
        self.config = self._load_config()
        self.LOG_DIR = config_manager.get_log_dir()
        self.bmc_ip = self.config.get("BMC_IP")
        self.bmc_user = "root"
        self.bmc_pass = self.config.get("BMC_ROOT_PASS")
    
    def _load_config(self):
        if not os.path.exists(config_manager.CONFIG_FILE):
            print(f"{Colors.BOLD_RED}Error: 'config.ini' not found at {config_manager.CONFIG_FILE}{Colors.END}")
            press_enter()
            sys.exit(1)
        return config_manager.load_config()

    def kill_existing_y2prog(self):
        try:
            subprocess.run(['taskkill', '/F', '/IM', 'Y2ProgCli.exe'], 
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=0x08000000)
        except:
            pass

    def log_results(self, sn_list, mdl_list):
        target_log_dir = self.LOG_DIR
        old_logs = glob.glob(os.path.join(target_log_dir, "Y2Prog_Detection_*.txt"))
        for old_log in old_logs:
            try: os.remove(old_log)
            except: pass
        
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        log_file = os.path.join(target_log_dir, f"Y2Prog_Detection_{timestamp}.txt")
        
        def _write_content(path):
            with open(path, "w") as f:
                f.write(f"Y2Prog Detection Log - {datetime.datetime.now()}\n")
                f.write("-" * 40 + "\n")
                for sn, mdl in zip(sn_list, mdl_list):
                    prefix = ""
                    if mdl == '134217728': prefix = "BIOS "
                    elif mdl == '268435456': prefix = "BMC "
                    f.write(f"{prefix}SN: {sn} | Size: {mdl}\n")

        try:
            _write_content(log_file)
            print(f"{Colors.BOLD_GREEN}Results logged to: {log_file}{Colors.END}")
        except Exception as e:
            print(f"{Colors.BOLD_YELLOW}Failed to write log file: {e}{Colors.END}")

    def detect_via_ssh(self):
        print(f"\nEstablishing BMC SSH Connection to {self.bmc_ip}...")
        try:
            with SSHManager(self.bmc_ip, self.bmc_user, self.bmc_pass) as ssh:
                _, stdout, _ = ssh.exec_command("i2ctransfer -y 10 w6@0x51 0x01 0x20 0x09 0x00 0x00 0x00", timeout=3)
                stdout.read()
                print("MUX Command Executed.")
        except Exception as e:
            print(Colors.BOLD_YELLOW + f"SSH Warning: {e}\nProceeding with local detection..." + Colors.END)

    def detect_local(self):
        self.kill_existing_y2prog()
        print("Starting Y2Prog SN Detection...")
        
        if not os.path.exists(self.Y2PROG_PATH):
            print(f"{Colors.BOLD_YELLOW}Error: Y2ProgCli.exe not found at {self.Y2PROG_PATH}{Colors.END}")
            input("Press enter to close...")
            return

        try:
            proc = subprocess.Popen([self.Y2PROG_PATH, 'list'], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, creationflags=0x08000000)
            time.sleep(3)
            out, _ = proc.communicate(input='exit\n', timeout=5)
            tokens = out.split()
        except Exception as e:
            print(f"{Colors.BOLD_YELLOW}Error during hardware list: {e}{Colors.END}")
            tokens = []

        sn = []
        mdl = []
        indices = [i for i, x in enumerate(tokens) if x == 'SerialNumber:']
        
        if not indices:
            print('No serial numbers detected.')
            input("Press Enter to close...")
            return

        for idx in indices:
            if idx + 1 < len(tokens):
                val = tokens[idx + 1].rstrip(',').rstrip(':')
                if len(val) > 4: 
                    sn.append(val)
                    mdl.append('')

        for i in range(len(sn)):
            sub = [self.Y2PROG_PATH, "detect", "--cs", "1", "--sn", sn[i]]
            try:
                proc_det = subprocess.Popen(sub, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, creationflags=0x08000000)
                time.sleep(2)
                res_out, _ = proc_det.communicate(input='exit\n', timeout=10)
                res_tokens = res_out.split()

                if 'Size:' in res_tokens:
                    size_idx = res_tokens.index('Size:')
                    if size_idx + 1 < len(res_tokens):
                        mdl[i] = res_tokens[size_idx + 1]
                        if mdl[i] == '134217728':
                            print(f'{Colors.BOLD_CYAN}BIOS Serial Number: {sn[i]}{Colors.END}')
                        elif mdl[i] == '268435456':
                            print(f'{Colors.BOLD_CYAN}BMC Serial Number: {sn[i]}{Colors.END}')
            except Exception:
                print(f"{Colors.BOLD_YELLOW}Detection for {sn[i]} failed or timed out.{Colors.END}")

        self.log_results(sn, mdl)
        print()
        input("Press enter to close...")

    def run(self):
        print(Colors.BOLD_GREEN + "Y2Prog Serial Number Detection" + Colors.BOLD_CYAN + 
              "\nRunning this script will likely stall the SUT.\nAC cycle SUT afterwards if needed.\n"
              "Ensure BMC is booted and is SSH accessible with root account." + Colors.END)

        print("Press Enter to continue or any other key to exit...")
        if msvcrt.getch() != b'\r':
            sys.exit(0)

        self.detect_via_ssh()
        self.detect_local()

if __name__ == "__main__":
    Y2ProgDetector().run()