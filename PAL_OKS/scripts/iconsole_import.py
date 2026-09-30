import requests
import time
import os
from console_utils import enable_ansi_windows, Colors
import urllib3
import sys
import getpass
import msvcrt
import socket

script_dir = os.path.dirname(os.path.abspath(__file__))

try:
    import config_manager
except ImportError as e:
    print(f"FATAL ERROR: Could not import config_manager. Error: {e}")
    sys.exit(1)

try:
    from ui_utilities import read_windows_credential
except ImportError:
    def read_windows_credential(target): return None, None

class IConsoleImporter:
    AUTH_URL = "https://pse-console-auth.intel.com/api/v1/aad/login"
    CLOUD_URL = "https://pse-console-cloud.intel.com/api/v1/onboarding/system-info"

    def __init__(self):
        self.headers = {"accept": "application/json", "Content-Type": "application/json"}
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        enable_ansi_windows()

    def get_pse_token(self):
        while True:
            current_user = os.getlogin()
            use_cred_manager = (current_user.lower() == "lab_raspdcg")
            auth_pass = None
            used_saved_cred = False

            if use_cred_manager:
                auth_email = input("Enter your Intel email (leave blank to use saved credentials): ").strip()
                if not auth_email:
                    target_credential = "EVF_NUC"
                    c_user, c_pass = read_windows_credential(target_credential)
                    if c_user and c_pass:
                        if "@" in c_user:
                            auth_email = c_user
                        else:
                            auth_email = c_user + "@intel.com"
                        auth_pass = c_pass
                        used_saved_cred = True
                        print(Colors.CYAN + "Using credentials from Windows Credential Manager." + Colors.RESET)
                    else:
                        print(Colors.YELLOW + "No saved credentials found.\nEnsure EVF_NUC is present in Credential Manager." + Colors.RESET)
                        continue
                else:
                    if "@" not in auth_email:
                        auth_email += "@intel.com"
                    auth_pass = getpass.getpass("Enter your password: ").strip()
            else:
                auth_email = input("Enter your Intel email: ").strip()
                if "@" not in auth_email:
                    auth_email += "@intel.com"
                auth_pass = getpass.getpass("Enter your password: ").strip()

            try:
                print(Colors.CYAN + "Connecting..." + Colors.RESET)
                response = requests.post(
                    self.AUTH_URL,
                    headers=self.headers,
                    json={"email": auth_email, "password": auth_pass},
                    proxies={"http": None, "https": None},
                    verify=False
                )

                if response.status_code == 200:
                    print(Colors.GREEN + "Connected!" + Colors.RESET)
                    pse_token = response.json()
                    return pse_token.get("access_token")
                else:
                    if used_saved_cred:
                        print(Colors.YELLOW + "EVF_NUC found in Credential Manager but authentication failed.\nPlease check user and password." + Colors.RESET)
                    else:
                        print(Colors.RED + f"Authentication failed (status {response.status_code})." + Colors.RESET)

                    print("Press ENTER to exit or any other key to retry...", end="", flush=True)
                    key = msvcrt.getch()
                    print()
                    if key == b'\r':
                        raise Exception("User cancelled authentication.")
                    print("\nRe-enter credentials...\n")
            except requests.RequestException as e:
                print(Colors.RED + f"Connection error: {e}" + Colors.RESET)
                print("Press ENTER to exit or any other key to retry...", end="", flush=True)
                key = msvcrt.getch()
                print()
                if key == b'\r':
                    raise Exception("User cancelled authentication.")
                print("\nRe-enter credentials...\n")

    def get_system_info(self, system_id, auth_token, max_retries=3, delay=2):
        url = f"{self.CLOUD_URL}/{system_id}"
        headers = {"accept": "application/json", "Authorization": f"Bearer {auth_token}"}

        for attempt in range(max_retries):
            try:
                response = requests.get(url, headers=headers, proxies={"http": None, "https": None}, verify=False)
                if response.status_code == 200:
                    return response.json()
                else:
                    print(f"Attempt {attempt+1}: Status {response.status_code}, retrying...")
            except requests.RequestException as e:
                print(f"Attempt {attempt+1}: Error {e}, retrying...")
            time.sleep(delay)
        raise Exception("Failed to fetch system info after multiple retries.")

    def extract_sut_ports(self, pse_info):
        sut_pdu_fqdn_list = []
        for pdu in pse_info.get("pdu", []):
            fqdn = pdu.get("fqdn")
            for outlet in pdu.get("outlets", []):
                if outlet.get("device_name") == "SUT":
                    sut_pdu_fqdn_list.append(f"{fqdn}:{outlet.get('outlet')}")
        return sut_pdu_fqdn_list

    def extract_ports_map(self, pse_info):
        ports_map = {}
        for instr in pse_info.get("instrumentation", []):
            name = instr.get("name")
            port = instr.get("port")
            if name == "RELAY_MODULE" and port:
                ports_map["relaycom"] = f"COM{port}"
            elif name == "BMC_SERIAL" and port:
                ports_map["bmccom"] = f"COM{port}"
            elif name == "BIOS_SERIAL" and port:
                ports_map["bioscom"] = f"COM{port}"
        return ports_map

    def update_config(self, bmc_ip, sut_pdu_fqdn_list, ports_map):
        try:
            current_config = config_manager.load_config()
        except Exception as e:
            raise Exception(f"Failed to load current configuration using config_manager: {e}")

        if 'SUT_TYPE' not in current_config:
            current_config['SUT_TYPE'] = '1s' 

        if bmc_ip:
            current_config['BMC_IP'] = bmc_ip
            
        for key, val in ports_map.items():
            if val:
                current_config[key.upper()] = val

        keys_to_delete = [
            k for k in current_config.keys() if k.upper().startswith("SUT_AC")
        ]
        for key in keys_to_delete:
            del current_config[key]
            
        for i, val in enumerate(sut_pdu_fqdn_list, start=1):
            current_config[f"SUT_AC{i}"] = val

        port_lines = [f"Relay = {ports_map.get('relaycom','<not found>')}",
                      f"BMC   = {ports_map.get('bmccom','<not found>')}",
                      f"BIOS  = {ports_map.get('bioscom','<not found>')}"]
        sut_lines = [f"AC{i} = {sut_pdu_fqdn_list[i-1]}" if i-1 < len(sut_pdu_fqdn_list) else f"AC{i} = <not found>"
                     for i in range(1, max(2, len(sut_pdu_fqdn_list))+1)]
        bmc_line = [f"{bmc_ip}" if bmc_ip else "<not found>"]
        
        print(Colors.CYAN + "="*50 + Colors.RESET)
        print(Colors.GREEN + "Ports detected:" + Colors.RESET)
        for line in port_lines:
            print("  " + line)
        print(Colors.GREEN + "BMC detected:" + Colors.RESET)
        for line in bmc_line:
            print("  " + line)
        print(Colors.GREEN + "SUT AC outlets detected:" + Colors.RESET)
        for line in sut_lines:
            print("  " + line)
        print(Colors.CYAN + "="*50 + Colors.RESET)

        if not any(ports_map.values()):
            print(Colors.YELLOW + "WARNING: No COM port info detected!" + Colors.RESET)
        if not bmc_ip:
            print(Colors.YELLOW + "WARNING: No BMC IP detected!" + Colors.RESET)
        if not sut_pdu_fqdn_list:
            print(Colors.YELLOW + "WARNING: No SUT AC outlets detected!" + Colors.RESET)

        try:
            config_manager.save_config(current_config)
        except Exception as e:
            raise Exception(f"Failed to save configuration using config_manager: {e}")

        resolved_config_path = os.path.abspath(config_manager.CONFIG_FILE)
        print(f"Configuration file updated: {resolved_config_path}")

    def run(self):
        try:
            print("This relies on System Entry info in iConsole.\nhttps://console.intel.com/ops/onboarding/system-entry\n")
            print("If values exist, this will update:")
            print("Relay, BMC, and BIOS COMs.")
            print("BMC IP or FQDN.")
            print("SUT AC outlets.\n")

            systemid = ""
            current_user = os.getlogin().lower()
            use_auto_id = (current_user == "lab_raspdcg")

            if use_auto_id:
                prompt_text = "Enter iConsole SUT SysID (leave blank to auto-generate): "
            else:
                prompt_text = "Enter iConsole SUT SysID: "

            while not systemid:
                sut_sysid_input = input(prompt_text).strip()

                if use_auto_id and not sut_sysid_input:
                    mini_pc_hostname = socket.gethostname().lower()
                    
                    if len(mini_pc_hostname) >= 5 and mini_pc_hostname[-5].endswith('n'):
                        sut_sysid = mini_pc_hostname[:-5] + 's' + mini_pc_hostname[-4:]
                        print(Colors.CYAN + f"Auto-generated SUT SysID: {sut_sysid}" + Colors.RESET)
                        systemid = sut_sysid
                    else:
                        print(Colors.YELLOW + f"WARNING: Hostname '{mini_pc_hostname}' does not match auto-generate pattern (e.g., '...anXXXX' or '...nXXXX'). Manual entry required." + Colors.RESET)
                        prompt_text = "Enter iConsole SUT SysID: "
                        continue
                
                elif sut_sysid_input:
                    systemid = sut_sysid_input
                
                else:
                    print(Colors.YELLOW + "SUT SysID cannot be empty. Please enter a valid ID." + Colors.RESET)

            token = self.get_pse_token()

            pse_info = self.get_system_info(systemid, token)

            bmc_ip = pse_info.get("bmc")
            sut_pdu_fqdn_list = self.extract_sut_ports(pse_info)
            ports_map = self.extract_ports_map(pse_info)

            self.update_config(bmc_ip, sut_pdu_fqdn_list, ports_map)

        except Exception as e:
            print(Colors.YELLOW + f"\nError generating configuration: {e}" + Colors.RESET)

if __name__ == "__main__":
    importer = IConsoleImporter()
    importer.run()