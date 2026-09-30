# Author: Malachi Thorne
# Date: 9/2/2022
# Updated for OKS 9/23/2025 by Jonathan Finite
# Goal: Detect chip type attached to Y2Prog SN

import subprocess
import sys
import warnings
from cryptography.utils import CryptographyDeprecationWarning
warnings.filterwarnings("ignore", category=CryptographyDeprecationWarning)
import paramiko
import configparser
import msvcrt

class color:
    CYAN = '\033[1;36;48m'
    GREEN = '\033[1;32;48m'
    YELLOW = '\033[1;33;48m'
    END = '\033[1;37;0m'

config = configparser.ConfigParser()
config.read("QAP_FTDI_OKS_2S_Config.ini")
BMC_IP = config.get("MYVARS", "BMC_IP")
BMC_USER = config.get("MYVARS", "BMC_USER")
BMC_PASS = config.get("MYVARS", "BMC_PASS")

print(color.GREEN + "Y2Prog Serial Number Detection" + color.CYAN + "\nRunning this script may stall the SUT\nAC cycle SUT afterwards if needed\nEnsure BMC is booted for BIOS detection" + color.END)
print("Press Enter to continue or any other key to exit...")
if msvcrt.getch() == b'\r':  # Check if Enter key is pressed
    print("\nEstablishing BMC SSH Connection")
else:
    sys.exit(1)

try:
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(BMC_IP, username=BMC_USER, password=BMC_PASS)
    stdin, stdout, stderr = client.exec_command("i2ctransfer -y 10 w6@0x51 0x01 0x20 0x09 0x00 0x00 0x00")
    print(stdout.read().decode())
    client.close()

except Exception as e:
    print(color.YELLOW + "SSH to BMC Failed. This is required for BIOS Chip detection.\nIf MUX has been enabled via BMC then detection is still possible.\nCheck QAP_FTDI_OKS_2S_Config.ini configuration.\nEnsure that SSH to BMC is functional with config settings." + color.END)
    print("Press Enter to continue or any other key to exit...")
    if msvcrt.getch() == b'\r':  # Check if Enter key is pressed
        print()
    else:
        sys.exit(1)

def Y2ProgInfo():
    # Grab serial numbers of Y2Progs
    output = subprocess.Popen(['C:\Program Files\Intel\Y2Prog CLI\Y2ProgCli.exe','list'],shell=True, stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
    out,err = output.communicate()
    x = out.split()
    # print(out)

    sn = []
    mdl = []
    occurrences = lambda s, x: (i for i,e in enumerate(x) if e == s)
    sn = list(occurrences('SerialNumber:', x))
    for i in range(len(sn)):
        var = sn[i] + 1
        sn[i] = x[var][0:-1]
        mdl.append('')
        # Print detected serial numbers
        num = i +1
        #print(f'SN{num}: {sn[i]}')
    
    # Checks serial number blanks and gives troubleshooting     
    blank = []
    if sn == blank:
        print('No serial numbers detected.')
        print('Check if Y2Progs are connected to host.')
        input("Press Enter to close...")
        return None

    # Pull Chip Size
    for i in range(len(sn)):
        # Setting array for Popen to process in next step
        subArray = ["C:\Program Files\Intel\Y2Prog CLI\Y2ProgCli.exe","detect",'--cs','1','--sn',f'{sn[i]}']
        
        # Getting output of Y2Prog to strip chip size
        output = subprocess.Popen(subArray[0:6],shell=True, stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
        out,err = output.communicate()
        #print(out)
        x = out.split()
        if 'Size:' in x:
            spot = x.index('Size:') + 1
            mdl[i] = x[spot]
        
        # Reports which serial number belongs to which chip based on chip size
        if mdl[i] == '134217728':
            print(f'BIOS Serial Number: {sn[i]}')
        if mdl[i] == '268435456':
            print(f'BMC Serial Number: {sn[i]}')
    
    if mdl[0] not in  ["134217728", "268435456"]:
        print('\nChip Size is not able to be detected.')
        print('Check if host is on and Y2Progs are connected.')
        input("Press Enter to close...")
        return None
    
    print()
    input("Press enter to close...")
    
    return sn,mdl

Y2ProgInfo()
