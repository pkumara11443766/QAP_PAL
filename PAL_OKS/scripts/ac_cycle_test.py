import os
import sys
import time
import subprocess
import threading

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(SCRIPT_DIR)

try:
    import config_manager
    from ssh_utils import SSHManager
    from console_utils import Colors, enable_ansi_windows
except ImportError as e:
    print(f"Error importing required modules: {e}")
    sys.exit(1)

def get_bios_post_code(ssh):
    try:
        cmd = "i2ctransfer -y 10 w2@0x51 0x40 0x58 r1"
        _, stdout, _ = ssh.exec_command(cmd, timeout=2)
        output = stdout.read().decode().strip()
        if output:
            return int(output, 16)
    except Exception as e:
        print(f"\n{Colors.RED}Error getting POST code. \nCheck BMC root account is set with correct password. {e}{Colors.RESET}")
    return None

def run_ac_cycle(config):
    python_path = config.get("PYTHON_PATH", "").strip('"').strip("'")
    python_exe = os.path.join(python_path, "python.exe")
    raritan_script = "SSH"
    
    sut_acs = [config[k].strip('"').strip("'") for k in config_manager.get_sorted_sut_keys(config)]
    
    if not sut_acs:
        print(f"{Colors.RED}No SUT AC outlets defined in config.{Colors.RESET}")
        return False

    pdu_user = config.get("PDU_USER")
    pdu_pass = config.get("PDU_PASS")
    
    enc_pass = config_manager.encrypt_value(pdu_pass) if pdu_pass else ""
    
    cmd = [
        python_exe, os.path.join(SCRIPT_DIR, "raritan_power_control.py"),
        "cycle", python_exe, raritan_script,
        pdu_user, enc_pass, ",".join(sut_acs)
    ]
    
    print(f"{Colors.CYAN}Executing AC Cycle...{Colors.RESET}")
    try:
        subprocess.run(cmd, check=True)
        return True
    except subprocess.CalledProcessError:
        print(f"{Colors.RED}AC Cycle Failed.{Colors.RESET}")
        return False

def main():
    enable_ansi_windows()
    print(f"{Colors.BOLD_GREEN}AC Cycle Test Script{Colors.RESET}\nWill perform cycle once reaching POST Code 58.\nRequires BMC SSH with root for POST Code detection.")
    
    try:
        config = config_manager.load_config()
    except Exception as e:
        print(f"{Colors.RED}Failed to load config: {e}{Colors.RESET}")
        sys.exit(1)

    bmc_ip = config.get("BMC_IP")
    bmc_user = "root"
    bmc_pass = config.get("BMC_ROOT_PASS")
    
    if not bmc_ip or not bmc_pass:
        print(f"{Colors.RED}BMC credentials missing in config.ini{Colors.RESET}")
        sys.exit(1)

    TARGET_CODE = 0x58
    HANG_TIMEOUT = 300  # 5 minutes in seconds
    
    while True:
        try:
            val = input("Enter number of AC cycles to execute: ").strip()
            TOTAL_CYCLES = int(val)
            if TOTAL_CYCLES > 0: break
            print(f"{Colors.RED}Please enter a number greater than 0.{Colors.RESET}")
        except ValueError:
            print(f"{Colors.RED}Invalid input. Please enter an integer.{Colors.RESET}")
    
    for i in range(1, TOTAL_CYCLES + 1):
        print(f"\n{Colors.BOLD_YELLOW}=== Cycle {i} of {TOTAL_CYCLES} ==={Colors.RESET}")
        
        if not run_ac_cycle(config):
            print("Aborting test due to power control failure.")
            sys.exit(1)
            
        ssh = SSHManager(bmc_ip, bmc_user, bmc_pass)
        connected = False
        polling_phase = True
        
        start_time = time.time()
        stop_event = threading.Event()
        status = {"phase": "polling", "code": 0}
        last_code = None
        last_change_time = time.time()
        
        def update_timer():
            while not stop_event.is_set():
                elapsed = int(time.time() - start_time)
                if elapsed < 60:
                    time_str = f"{elapsed}s"
                else:
                    m, s = divmod(elapsed, 60)
                    time_str = f"{m}m {s}s"
                
                if status["phase"] == "polling":
                    msg = f"\rPolling BMC... Time: {time_str}   "
                elif status["phase"] == "code":
                    msg = f"\rCurrent: {Colors.GREEN}{status['code']:02X}{Colors.RESET}   Time: {time_str}   "
                else:
                    msg = f"\rCurrent: {Colors.RED}ERR{Colors.RESET}   Time: {time_str}   "
                
                sys.stdout.write(msg)
                sys.stdout.flush()
                time.sleep(0.2)
        
        t = threading.Thread(target=update_timer, daemon=True)
        t.start()
        
        while True:
            try:
                if not connected:
                    ssh.connect()
                    connected = True
                
                code = get_bios_post_code(ssh)
                
                if code is not None:
                    if polling_phase:
                        polling_phase = False

                    status["phase"] = "code"
                    status["code"] = code
                    
                    if code != last_code:
                        last_code = code
                        last_change_time = time.time()
                    else:
                        # Same code, check timeout
                        if (time.time() - last_change_time) > HANG_TIMEOUT:
                            stop_event.set()
                            t.join()
                            print(f"\n{Colors.RED}FAIL: System stalled on POST Code {code:02X} for 5 minutes.{Colors.RESET}")
                            break

                    if code == TARGET_CODE:
                        stop_event.set()
                        t.join()
                        print(f"\n{Colors.GREEN}Target reached!{Colors.RESET}")
                        break
                else:
                    connected = False
                    ssh.disconnect()
                    if polling_phase:
                        status["phase"] = "polling"
                    else:
                        status["phase"] = "error"
            
            except KeyboardInterrupt:
                stop_event.set()
                print("\nAborted by user.")
                ssh.disconnect()
                sys.exit(0)
            except Exception:
                connected = False
                if polling_phase:
                    status["phase"] = "polling"
                else:
                    status["phase"] = "error"
            
            time.sleep(0.5)
        
        ssh.disconnect()

    print(f"\n{Colors.BOLD_GREEN}Test Completed Successfully.{Colors.RESET}")

if __name__ == "__main__":
    try:
        main()
    finally:
        input("\nPress Enter to close...")