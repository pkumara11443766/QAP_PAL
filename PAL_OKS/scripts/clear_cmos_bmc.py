import sys
import os
import subprocess
import time

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(SCRIPT_DIR)

try:
    import config_manager
    from ssh_utils import SSHManager
    from console_utils import enable_ansi_windows, Colors, press_enter
except ImportError as e:
    print(f"Error importing required modules: {e}")
    input("Press Enter to exit...")
    sys.exit(1)

def main():
    enable_ansi_windows()
    print(f"{Colors.CYAN}This will attempt to SSH to the BMC as root and issue the i2ctransfer command to clear CMOS.{Colors.RESET}")
    print(f"{Colors.CYAN}This will perform an AC Power Cycle after issuing this command.{Colors.RESET}")
    
    try:
        input(f"\n{Colors.YELLOW}Press Enter to continue...{Colors.RESET}")
    except KeyboardInterrupt:
        sys.exit(0)

    try:
        config = config_manager.load_config()
    except Exception as e:
        print(f"{Colors.RED}Failed to load config: {e}{Colors.RESET}")
        press_enter()
        sys.exit(1)

    bmc_ip = config.get("BMC_IP")
    bmc_user = "root"
    bmc_pass = config.get("BMC_ROOT_PASS")

    if not bmc_ip or not bmc_pass:
        print(f"{Colors.RED}BMC IP or Root Password missing in config.ini{Colors.RESET}")
        press_enter()
        sys.exit(1)

    print(f"\n{Colors.GREEN}Connecting to BMC ({bmc_ip})...{Colors.RESET}")
    
    cmd = "i2ctransfer -y 10 w6@0x51 0x46 0x78 0x00 0x00 0x00 0x00"
    
    try:
        with SSHManager(bmc_ip, bmc_user, bmc_pass) as ssh:
            print(f"Executing: {cmd}")
            stdin, stdout, stderr = ssh.exec_command(cmd)
            exit_status = stdout.channel.recv_exit_status()
            
            out = stdout.read().decode().strip()
            err = stderr.read().decode().strip()
            
            if exit_status != 0:
                print(f"{Colors.RED}Command failed with exit code {exit_status}{Colors.RESET}")
                if err: print(f"Error: {err}")
                press_enter()
                sys.exit(1)
            else:
                print(f"{Colors.GREEN}Command executed successfully.{Colors.RESET}")
                if out: print(out)
                
    except Exception as e:
        print(f"{Colors.RED}SSH Connection failed: {e}{Colors.RESET}")
        press_enter()
        sys.exit(1)

    print(f"\n{Colors.CYAN}Initiating AC Power Cycle...{Colors.RESET}")
    
    python_path = config.get("PYTHON_PATH", "").strip('"').strip("'")
    python_exe = os.path.join(python_path, "python.exe")
    raritan_script = "SSH"
    
    sut_acs = [config[k].strip('"').strip("'") for k in config_manager.get_sorted_sut_keys(config)]
    
    if not sut_acs:
        print(f"{Colors.RED}No SUT AC outlets defined in config.{Colors.RESET}")
        press_enter()
        sys.exit(1)


    pdu_user = config.get("PDU_USER")
    pdu_pass = config.get("PDU_PASS")
    enc_pass = config_manager.encrypt_value(pdu_pass) if pdu_pass else ""

    raritan_cmd = [
        python_exe, os.path.join(SCRIPT_DIR, "raritan_power_control.py"),
        "cycle", python_exe, raritan_script,
        pdu_user, enc_pass, ",".join(sut_acs)
    ]
    
    try:
        subprocess.run(raritan_cmd, check=True)
    except subprocess.CalledProcessError:
        print(f"{Colors.RED}AC Cycle Failed.{Colors.RESET}")
        press_enter()
        sys.exit(1)
    except Exception as e:
        print(f"{Colors.RED}Failed to launch power control: {e}{Colors.RESET}")
        press_enter()
        sys.exit(1)

    print(f"\n{Colors.GREEN}Operation Complete.{Colors.RESET}")
    time.sleep(3)

if __name__ == "__main__":
    main()