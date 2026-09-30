import warnings
try:
    from cryptography.utils import CryptographyDeprecationWarning
except ImportError:
    CryptographyDeprecationWarning = UserWarning
warnings.filterwarnings("ignore", category=CryptographyDeprecationWarning)
warnings.filterwarnings("ignore", category=DeprecationWarning)

import sys
import subprocess
import time
import os
import re
from console_utils import enable_ansi_windows, press_enter, Colors

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPT_DIR not in sys.path:
    sys.path.append(SCRIPT_DIR)
try:
    import config_manager
except ImportError:
    print(f"FATAL ERROR: Could not import 'config_manager' required for PDU password decryption. Please ensure it is in the 'scripts' folder.", file=sys.stderr)
    sys.exit(1)
except Exception as e:
    print(f"FATAL ERROR during config_manager import: {e}", file=sys.stderr)
    sys.exit(1)

class RaritanPowerController:
    def __init__(self, python_exe, raritan_script, user, password, no_wait=False):
        self.python_exe = python_exe
        self.raritan_script = raritan_script
        self.user = user
        self.password = password
        self.no_wait = no_wait
        enable_ansi_windows()

    def _wait_for_prompt(self, chan, prompt=">", timeout_dur=8.0):
        accumulated = ""
        start = time.time()
        while time.time() - start < timeout_dur:
            if chan.recv_ready():
                data = chan.recv(4096).decode('utf-8', errors='replace')
                accumulated += data
                
                # Auto-confirm prompts if any
                if any(p in data.lower() for p in ["[y/n]", "confirm", "wish to", "are you sure"]):
                    chan.send("y\n")
                
                if prompt in accumulated:
                    return accumulated
            time.sleep(0.1)
        return accumulated

    def _execute_channel_cmd(self, chan, port, act):
        display_ports = ", ".join([p.strip() for p in port.split(",")])
        ssh_cmd = f"power outlets {port} {act} /y"
        chan.send(f"{ssh_cmd}\n")
        
        # Wait for command output and the next prompt
        output = self._wait_for_prompt(chan, prompt=">", timeout_dur=10.0)
        
        # Check for errors in the output
        if "error" in output.lower() or "fail" in output.lower():
            err_msg = ""
            for line in output.splitlines():
                if "error" in line.lower() or "fail" in line.lower():
                    err_msg = line.strip()
                    break
            if not err_msg:
                err_msg = output.strip()
            raise RuntimeError(f"PDU command error: {err_msg}")
        
        print(f"{Colors.GREEN}Outlet(s) {act.capitalize()}: {display_ports}{Colors.RESET}", flush=True)

    def run_commands_on_host(self, fqdn, actions_list):
        print(f"Connecting to PDU at {fqdn}...", flush=True)
        try:
            from ssh_utils import SSHManager
            with SSHManager(hostname=fqdn, username=self.user, password=self.password) as ssh:
                # Open interactive shell session (allocates PTY)
                channel = ssh.client.invoke_shell()
                channel.settimeout(10.0)
                
                # 1. Wait for the initial shell prompt
                self._wait_for_prompt(channel, prompt=">", timeout_dur=8.0)
                
                # 2. Execute each action sequentially on the same connection
                for item in actions_list:
                    if isinstance(item, tuple) and item[0] == "countdown":
                        self.countdown(item[1])
                        continue
                    port, act = item
                    self._execute_channel_cmd(channel, port, act)
                
                # 3. Send exit command to log out
                channel.send("exit\n")
                
                # 4. Wait for channel to close
                start = time.time()
                while not channel.exit_status_ready() and time.time() - start < 4.0:
                    if channel.recv_ready():
                        channel.recv(4096)  # consume output without printing
                    time.sleep(0.1)
                    
        except Exception as e:
            print(f"\n{Colors.RED}ERROR: Failed to run actions on host {fqdn} via SSH.{Colors.RESET}", flush=True)
            print(f"Details: {e}", flush=True)
            if not self.no_wait:
                press_enter()
            raise

    def countdown(self, seconds):
        for remaining in range(seconds, 0, -1):
            unit = "second" if remaining == 1 else "seconds"
            msg = f"Waiting {remaining} {unit}..."
            if sys.stdout.isatty():
                print(f"\r{Colors.CYAN}{msg}{Colors.RESET}", end="", flush=True)
            else:
                print(msg, flush=True)
            time.sleep(1)
        if sys.stdout.isatty():
            print("\r" + " " * 50 + "\r", end="", flush=True)

    def control_power(self, action, sut_ac_entries, cycle_delay=25):
        sut_ac_pattern = re.compile(r"sut_ac(\d+)", re.IGNORECASE)
        def sort_key(key_val):
            key, _ = key_val
            m = sut_ac_pattern.match(key)
            return int(m.group(1)) if m else 0

        sut_dict = {f"sut_ac{i+1}": val for i, val in enumerate(sut_ac_entries)}

        def group_consecutive_targets(targets):
            groups = []
            for fqdn, port in targets:
                if groups and groups[-1][0] == fqdn:
                    groups[-1][1].append(port)
                else:
                    groups.append((fqdn, [port]))
            return groups

        def sort_ports(ports_list):
            return sorted(ports_list, key=lambda x: (0, int(x)) if str(x).isdigit() else (1, str(x)))

        if action == "cycle":
            sorted_keys = sorted(sut_dict.items(), key=sort_key, reverse=True)
            off_targets = []
            for key, val in sorted_keys:
                if ':' not in val:
                    print(f"{Colors.RED}Skipping invalid entry '{val}' (missing :port){Colors.RESET}", flush=True)
                    continue
                fqdn, port = val.split(":", 1)
                off_targets.append((fqdn.strip(), port.strip()))

            off_groups = group_consecutive_targets(off_targets)

            sorted_keys = sorted(sut_dict.items(), key=sort_key, reverse=False)
            on_targets = []
            for key, val in sorted_keys:
                if ':' not in val:
                    continue
                fqdn, port = val.split(":", 1)
                on_targets.append((fqdn.strip(), port.strip()))

            on_groups = group_consecutive_targets(on_targets)

            if len(off_groups) == 1 and len(on_groups) == 1 and off_groups[0][0] == on_groups[0][0]:
                fqdn = off_groups[0][0]
                off_ports_str = ",".join(sort_ports(off_groups[0][1]))
                on_ports_str = ",".join(sort_ports(on_groups[0][1]))
                self.run_commands_on_host(fqdn, [
                    (off_ports_str, "off"),
                    ("countdown", cycle_delay),
                    (on_ports_str, "on")
                ])
            else:
                unique_fqdns = []
                for fqdn, _ in off_groups + on_groups:
                    if fqdn not in unique_fqdns:
                        unique_fqdns.append(fqdn)
                
                sessions = {}
                try:
                    for fqdn in unique_fqdns:
                        print(f"Connecting to PDU at {fqdn}...", flush=True)
                        from ssh_utils import SSHManager
                        ssh = SSHManager(hostname=fqdn, username=self.user, password=self.password)
                        ssh.connect()
                        chan = ssh.client.invoke_shell()
                        chan.settimeout(10.0)
                        self._wait_for_prompt(chan, prompt=">", timeout_dur=8.0)
                        sessions[fqdn] = (ssh, chan)

                    for fqdn, ports in off_groups:
                        ports_str = ",".join(sort_ports(ports))
                        self._execute_channel_cmd(sessions[fqdn][1], ports_str, "off")

                    self.countdown(cycle_delay)

                    for fqdn, ports in on_groups:
                        ports_str = ",".join(sort_ports(ports))
                        self._execute_channel_cmd(sessions[fqdn][1], ports_str, "on")
                finally:
                    for ssh, chan in sessions.values():
                        try:
                            chan.send("exit\n")
                            start = time.time()
                            while not chan.exit_status_ready() and time.time() - start < 4.0:
                                if chan.recv_ready(): chan.recv(4096)
                                time.sleep(0.1)
                        except: pass
                        try: ssh.disconnect()
                        except: pass
        else:
            reverse_order = action == "off"
            sorted_keys = sorted(sut_dict.items(), key=sort_key, reverse=reverse_order)
            targets = []
            for key, val in sorted_keys:
                if ':' not in val:
                    print(f"{Colors.RED}Skipping invalid entry '{val}' (missing :port){Colors.RESET}", flush=True)
                    continue
                fqdn, port = val.split(":", 1)
                targets.append((fqdn.strip(), port.strip()))

            groups = group_consecutive_targets(targets)

            for fqdn, ports in groups:
                ports_str = ",".join(sort_ports(ports))
                self.run_commands_on_host(fqdn, [(ports_str, action)])



    def ensure_dependencies(self):
        try:
            import paramiko
        except ImportError:
            print(f"{Colors.RED}ERROR: The required 'paramiko' package is not installed.{Colors.RESET}")
            print(f"{Colors.YELLOW}Please run 'setup.pyw' to install required dependencies.{Colors.RESET}")
            press_enter()
            sys.exit(1)

if __name__ == "__main__":
    no_wait = False
    if "--no-wait" in sys.argv:
        no_wait = True
        sys.argv.remove("--no-wait")

    if len(sys.argv) < 7:
        print(f"{Colors.RED}FATAL ERROR: Not enough arguments provided.{Colors.RESET}", file=sys.stderr)
        try: input("\nPress Enter to exit...")
        except: pass
        sys.exit(1)

    action = sys.argv[1].lower()
    python_exe = sys.argv[2]
    raritan_script = sys.argv[3]
    pdu_user = sys.argv[4]
    encrypted_pdu_pass = sys.argv[5]
    sut_ac_str = sys.argv[6]

    try:
        pdu_pass = config_manager.decrypt_value(encrypted_pdu_pass)
    except AttributeError:
        print(f"{Colors.RED}FATAL ERROR: The required 'decrypt_value' function was not found in config_manager.{Colors.RESET}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"{Colors.RED}FATAL ERROR: PDU password decryption failed. Check config_manager.py and config.ini. Details: {e}{Colors.RESET}", file=sys.stderr)
        sys.exit(1)

    sut_ac_entries = [entry.strip() for entry in sut_ac_str.split(",") if entry.strip()]
    
    controller = RaritanPowerController(python_exe, raritan_script, pdu_user, pdu_pass, no_wait=no_wait)
    
    try:
        controller.ensure_dependencies()
        controller.control_power(action, sut_ac_entries)
        sys.exit(0)
    except Exception as e:
        if not isinstance(e, subprocess.CalledProcessError): 
            print(f"{Colors.RED}ERROR during SUT power control!{Colors.RESET}")
            print(str(e))
        if not no_wait:
            press_enter()
        sys.exit(1)