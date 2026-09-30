import os
import sys
import subprocess
import time
from console_utils import enable_ansi_windows, Colors, press_enter, set_console_title, bring_console_to_front, move_console_to_corner, strip_ansi_codes
import warnings
import socket
from datetime import datetime
import msvcrt

try:
    from cryptography.utils import CryptographyDeprecationWarning
except ImportError:
    CryptographyDeprecationWarning = DeprecationWarning

warnings.filterwarnings("ignore", category=DeprecationWarning, module="paramiko")
warnings.filterwarnings("ignore", category=DeprecationWarning, module="cryptography")
warnings.filterwarnings("ignore", category=CryptographyDeprecationWarning)

try:
    import config_manager
except ImportError:
    print(f"{Colors.RED}FATAL ERROR: Could not import 'config_manager'.{Colors.RESET}", file=sys.stderr)
    input("Press Enter to exit...")
    sys.exit(1)

from ui_utilities import terminate_process_by_window_title, ask_open_filename_console

LOG_DIR = os.path.join(config_manager.get_log_dir(), "FTDI_Flash")
if not os.path.exists(LOG_DIR):
    try: os.makedirs(LOG_DIR)
    except OSError: pass

class LiveLogger:
    def __init__(self, flash_type):
        ts = datetime.now().strftime("%Y.%m.%d_%H.%M_")
        self.filename = f"{ts}{flash_type}_InProgress.log"
        self.path = os.path.join(LOG_DIR, self.filename)
        self.file = open(self.path, 'w', encoding='utf-8', buffering=1)
        
    def log_event(self, message):
        self.file.write(f"{message}\n")
        self._hard_flush()

    def log_raw(self, message):
        self.file.write(message)
        self._hard_flush()

    def _hard_flush(self):
        self.file.flush()
        try: os.fsync(self.file.fileno())
        except: pass

    def finalize(self, status):
        self.file.close()
        new_filename = self.filename.replace("_InProgress.log", f"_{status}.log")
        new_path = os.path.join(LOG_DIR, new_filename)
        if os.path.exists(new_path): os.remove(new_path)
        os.rename(self.path, new_path)
        return new_path

    def discard(self):
        self.file.close()
        if os.path.exists(self.path):
            os.remove(self.path)

class FTDIFlashUtility:
    PYTHON_SCRIPT_PATH = os.path.join(config_manager.CI_GIT_BASE, 'scripts', 'oks-fw-flash.py')

    FLASH_MAP = {
        "AGG": "cpld_agg", "SCM": "cpld_scm", "HPM": "cpld_hpm", "BMC": "bmc", "BIOS": "bios"
    }
    FLASH_TYPES = [
        {"Name": "AGG", "Prompt": "Select Aggregator CPLD (.pof) file", "Filter": "POF Files (*.pof)|*agg*.pof"},
        {"Name": "SCM", "Prompt": "Select SCM CPLD (.jic) file", "Filter": "JIC Files (*.jic)|*.jic"},
        {"Name": "HPM", "Prompt": "Select HPM CPLD (.pof) file", "Filter": "POF Files (*.pof)|*hpm*.pof"},
        {"Name": "BMC", "Prompt": "Select BMC (.rom) file", "Filter": "ROM Files (*.rom)|*.rom"},
        {"Name": "BIOS", "Prompt": "Select BIOS (.bin) file", "Filter": "BIN Files (*.bin)|*.bin"}
    ]

    def __init__(self, flash_type, socket_type, file_map_str=None, gfs_node=None):
        self.flash_type = flash_type
        self.socket_type = socket_type
        self.gfs_node = gfs_node
        self.file_map = {}
        if file_map_str:
            try:
                for item in file_map_str.split(';'):
                    if '=' in item:
                        k, v = item.split('=', 1)
                        self.file_map[k] = v
            except: pass
            
        log_name = flash_type.replace(",", ".")
        try:
            self.config = config_manager.load_config()
        except Exception as e:
            self.write_error(f"Failed to load configuration: {e}")
            sys.exit(1)
        self.logger = LiveLogger(log_name)
        enable_ansi_windows()
        self.flash_started = False
        self._register_console_handler()
        move_console_to_corner()

    def _register_console_handler(self):
        try:
            import win32api
            import win32con
            def handler(sig):
                if sig == win32con.CTRL_CLOSE_EVENT:
                    if os.path.exists(self.logger.path):
                        if not self.flash_started:
                            self.logger.discard()
                        else:
                            self.logger.finalize("Canceled")
                    return True
                return False
            win32api.SetConsoleCtrlHandler(handler, True)
        except ImportError:
            pass

    def write_error(self, message): print(f"{Colors.RED}{message}{Colors.RESET}", file=sys.stderr)
    def write_warning(self, message): print(f"{Colors.YELLOW}{message}{Colors.RESET}")
    def write_info(self, message): print(f"{Colors.CYAN}{message}{Colors.RESET}")

    def select_flash_file(self, prompt, file_filter):
        initial_dir = "C:\\"
        last_dir_file = os.path.join(config_manager.get_log_dir(), "last_flash_dir.log")
        if os.path.exists(last_dir_file):
            with open(last_dir_file, 'r') as f:
                d = f.read().strip()
                if os.path.isdir(d): initial_dir = d
        
        filename = ask_open_filename_console(prompt, file_filter, initial_dir)
        
        if not filename:
            self.write_error("Selection cancelled."); sys.exit(0)
        filename = filename.replace('/', os.sep)
        try:
            with open(last_dir_file, 'w') as f: f.write(os.path.dirname(filename))
        except: pass
        return filename

    def _ensure_ci_git_repo(self):
        if not os.path.exists(self.PYTHON_SCRIPT_PATH):
            self.write_warning(f"Flash script not found: {self.PYTHON_SCRIPT_PATH}")
            self.write_info("Attempting to clone/update the ci.git repository...")
            
            update_script_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "update_cigit.py")
            python_exe = os.path.join(self.config.get("PYTHON_PATH", "").strip('"').strip("'"), "python.exe")
            
            if not os.path.exists(update_script_path) or not os.path.exists(python_exe):
                self.write_error("Cannot find update_cigit.py or python.exe. Aborting.")
                press_enter()
                sys.exit(1)
            
            try:
                process = subprocess.Popen([python_exe, update_script_path])
                process.wait()
            except Exception as e:
                self.write_error(f"Failed to run update_cigit.py: {e}")
                press_enter()
                sys.exit(1)

            if not os.path.exists(self.PYTHON_SCRIPT_PATH):
                self.write_error("Flash script still not found after update attempt. Aborting.")
                press_enter()
                sys.exit(1)
            
            self.write_info("\nci.git repository is ready. Continuing with flash operation.")

    def _prepare_environment(self):
        selected_split = self.flash_type.split(',')
        active_labels = []
        for ft in self.FLASH_TYPES:
            name = ft["Name"]
            is_selected = (name in selected_split) or ("FULL" in selected_split and name != "AGG")
            if name == "AGG" and "FULL" in selected_split and self.socket_type == "1s":
                is_selected = False
            if is_selected:
                label = name
                if label in ["SCM", "HPM", "AGG"]: label += " CPLD"
                elif label in ["BMC", "BIOS"]: label += " SPI"
                active_labels.append(label)
        
        title_str = ", ".join(active_labels)
        set_console_title(f"{title_str} - Flash In Progress")
        self.write_info(f"FTDI OKS Flash - {title_str}")
        
        bmccom = str(self.config.get("BMCCOM", "")).strip()
        if bmccom:
            self.write_warning("Please ensure BMC serial connection is closed.")
            terminate_process_by_window_title(bmccom)

        bring_console_to_front()

    def _select_flash_files(self):
        self.logger.log_raw(f"Flash Started (y-m-d h:m): {datetime.now().strftime('%Y-%m-%d %H:%M')}\n" + "-"*45 + "\n")
        selected_types = self.flash_type.split(',')
        flash_files = {}
        log_entries = []
        for ft in self.FLASH_TYPES:
            must_select = (ft["Name"] in selected_types) or ("FULL" in selected_types and ft["Name"] != "AGG")
            
            if ft["Name"] == "AGG" and "FULL" in selected_types and self.socket_type == "1s":
                must_select = False
            
            if must_select:
                if ft["Name"] in self.file_map:
                    file_path = self.file_map[ft["Name"]]
                else:
                    print(f"{ft['Prompt']}...")
                    file_path = self.select_flash_file(ft["Prompt"], ft["Filter"])
                
                flash_files[ft["Name"]] = file_path
                
                label = ft["Name"]
                if label in ["SCM", "HPM", "AGG"]: label += " CPLD"
                elif label in ["BMC", "BIOS"]: label += " SPI"
                log_entries.append((label, os.path.basename(file_path)))
        
        if not flash_files:
            self.write_error("No valid flash types were selected or files chosen.")
            sys.exit(1)
        
        max_len = max(len(entry[0]) for entry in log_entries)
        for label, filename in log_entries:
            self.logger.log_event(f"{label:<{max_len}} : {filename}")
        
        self.logger.log_raw("-"*45 + "\n\n")
        return flash_files, log_entries

    def _build_flash_command(self, flash_files):
        python_exe = os.path.join(self.config.get("PYTHON_PATH", "").strip('"').strip("'"), "python.exe")
        python_args = [self.PYTHON_SCRIPT_PATH]
        
        pdu_user = self.config.get("PDU_USER", "").strip()
        pdu_pass = self.config.get("PDU_PASS", "").strip()
        sut_acs = [self.config[k].strip('"').strip("'") for k in config_manager.get_sorted_sut_keys(self.config) if self.config[k].strip()]

        if pdu_user and pdu_pass and sut_acs:
            for i, sut_ac in enumerate(sut_acs):
                python_args.append("-w")
                if i == 0:
                    python_args.append(f"raritan##{pdu_user}:{pdu_pass}@{sut_ac}")
                else:
                    python_args.append(sut_ac)
        else:
            python_args.extend(["-w", "manual"])

        python_args.extend(["--type", self.socket_type])
        if self.gfs_node and self.gfs_node.lower() != "auto-discover":
            node_val = self.gfs_node.strip()
            try:
                # Attempt to resolve hostname to IP to avoid inet_pton errors in downstream scripts
                node_val = socket.gethostbyname(node_val)
            except (socket.gaierror, socket.herror):
                pass
            python_args.extend(["--gfs-node", node_val])
        for key, map_arg in self.FLASH_MAP.items():
            if key in flash_files:
                python_args.append(f'{map_arg}:{flash_files[key]}')
        python_args.extend(["-c", "OKS DC-SCM"])
        
        return [python_exe, "-u"] + python_args

    def _execute_and_log_flash(self, command, cwd=None):
        try:
            def quote_if_needed(arg):
                if ' ' in arg and not (arg.startswith('"') and arg.endswith('"')):
                    return f'"{arg}"'
                return arg
            
            pdu_pass = self.config.get('PDU_PASS', '')
            safe_command = []
            for arg in command:
                if pdu_pass and pdu_pass in arg:
                    safe_command.append(arg.replace(pdu_pass, '********'))
                else:
                    safe_command.append(arg)

            cmd_string = " ".join(quote_if_needed(c) for c in safe_command)

            self.write_info(f"\nCommand: {cmd_string}\n")
            start_time = time.time()
            process = None
            status = "Unknown"
            try:
                process = subprocess.Popen(command, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1, encoding='utf-8', errors='replace')
                for line in iter(process.stdout.readline, ''):
                    if pdu_pass and pdu_pass in line:
                        line = line.replace(pdu_pass, '********')
                    print(line, end='')
                    self.logger.log_raw(strip_ansi_codes(line))
                process.stdout.close()
                process.wait()
                status = "Success" if process.returncode == 0 else "Failed"
            except KeyboardInterrupt:
                status = "UserInterrupted"
                self.write_warning("\nUser has interrupted flash process.")
                if process:
                    try: process.kill()
                    except: pass
                raise
            except Exception as e:
                self.write_error(f"Execution Error: {e}")
                self.logger.log_event(f"CRASH: {str(e)}")
                status = "Crashed"
            finally:
                duration = time.strftime("%H:%M:%S", time.gmtime(time.time() - start_time))
                print("\n" + "="*40)
                if status == "Success": color = Colors.GREEN
                elif status == "UserInterrupted": color = Colors.YELLOW
                else: color = Colors.RED
                print(f"STATUS: {color}{status}{Colors.RESET}")
                print(f"DURATION: {duration}")
                print("="*40)
                
                self.logger.log_raw("\n" + "-"*45 + "\n")
                self.logger.log_event(f"Result: {status} (Duration: {duration})")
                final_path = self.logger.finalize(status)
                self.write_info(f"Log saved to: {final_path}")
        except Exception as e:
            self.write_error(f"An unexpected error occurred in the flash process: {e}")
            self.logger.log_event(f"CRITICAL FAILURE: {e}")
            self.logger.finalize("Crashed")

    def run(self):
        flash_files = {}
        cwd = None
        try:
            self._ensure_ci_git_repo()
            self._prepare_environment()
            while True:
                flash_files, log_entries = self._select_flash_files()
                bring_console_to_front()

                for label, filename in log_entries:
                    print(f"{label:<8} : {filename}")

                print("\nPress ENTER to continue, SPACE to re-select files, or any other key to exit...")
                key = msvcrt.getch()
                if key == b' ':
                    print("\nRe-selecting files...\n")
                    self.file_map = {}
                    continue
                elif key == b'\r':
                    break
                else:
                    sys.exit(0)
            
            if self.file_map:
                ts = datetime.now().strftime("%Y-%m-%d_%H-%M")
                if not os.path.exists("C:\\BKC"):
                    try: os.makedirs("C:\\BKC")
                    except OSError: pass

                cwd = os.path.join("C:\\BKC", f"From_GFS_{ts}")
                try:
                    os.makedirs(cwd, exist_ok=True)
                except Exception as e:
                    self.write_warning(f"Could not create file directory {cwd}: {e}")
                    cwd = None

            command = self._build_flash_command(flash_files)
            self.flash_started = True
            self._execute_and_log_flash(command, cwd=cwd)

            input("\nProcess Complete. Press Enter to exit")
        except (SystemExit, KeyboardInterrupt) as e:
            if os.path.exists(self.logger.path):
                if not self.flash_started:
                    self.logger.discard()
                else:
                    status = "UserInterrupted" if isinstance(e, KeyboardInterrupt) else "Canceled"
                    self.logger.finalize(status)
            if isinstance(sys.exc_info()[1], SystemExit):
                raise
        except Exception as e:
            if os.path.exists(self.logger.path):
                self.logger.log_event(f"CRASH: {e}")
                self.logger.finalize("Crashed")
            self.write_error(f"Unexpected error: {e}")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="FTDI OKS Flash Utility.")
    parser.add_argument('FlashType', help="A single flash type (e.g., SCM) or a comma-separated list (e.g., SCM,BMC). 'FULL' is also valid.")
    parser.add_argument('SocketType', choices=["1s", "ms"])
    parser.add_argument('--file-map', help="Key=Value;Key=Value map of file paths", default=None)
    parser.add_argument('--gfs-node', help="Optional GFS node address", default=None)
    args = parser.parse_args(sys.argv[1:])
    
    app = FTDIFlashUtility(args.FlashType, args.SocketType, args.file_map, args.gfs_node)
    app.run()