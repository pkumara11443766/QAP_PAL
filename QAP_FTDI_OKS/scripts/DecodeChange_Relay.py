import serial
import time
import subprocess
import os
import configparser

config = configparser.ConfigParser()
config.read("C:\\QAP_FTDI_OKS\\QAP_FTDI_OKS_Config.ini")
RELAYCOM = config.get("MYVARS", "RELAYCOM")

class Relays:
    Power_Button = 0
    Reset_Button = 0
    Kill_Switch = 0
    TPM = 0
    Clear_CMOS = 0
    BMC_Force_Update = 0
    NMI_Button = 0
    BMC_Init = 0
    
    relayList = [
        'Power_Button',
        'Reset_Button',
        'Kill_Switch',
        'TPM',
        'Clear_CMOS',
        'BMC_Force_Update',
        'NMI_Button',
        'BMC_Init'
        ]
        
def ReadRelayState():
    timeout_start = time.time()
    s = serial.Serial(f'{RELAYCOM}', 19200, timeout=8)
    s.write([0x5B])
    read_val = s.read()
    return(read_val)
    s.close()

def DecodeRelayState():
    current_state = ReadRelayState()
    current_string = bin(int.from_bytes(current_state,'big'))[2:].zfill(8)
    
    Relays.Power_Button = current_string[7]
    Relays.Reset_Button = current_string[6]
    Relays.Kill_Switch = current_string[5]
    Relays.TPM = current_string[4]
    Relays.Clear_CMOS = current_string[3]
    Relays.BMC_Force_Update = current_string[2]
    Relays.NMI_Button = current_string[1]
    Relays.BMC_Init = current_string[0]
    
def SelectChangeRelay(selected_relay=0):

    PrintRelays()
    print("\n")
    for i in range(len(Relays.relayList)): 
        print("Type {} to select {} relay".format(i,Relays.relayList[i]))
    
    selected_relay = int(input("Select relay to swtich:"))
    
    print("\nType 0 to power off relay")
    print("Type 1 to power on relay")
    
    relay_action = int(input("Select relay action:"))
    
    if selected_relay == 0 and relay_action == 0:
        write_value = [0x6F]
    elif selected_relay == 0 and relay_action == 1:
        write_value = [0x65]
    elif selected_relay == 1 and relay_action == 0:
        write_value = [0x70]
    elif selected_relay == 1 and relay_action == 1:
        write_value = [0x66]
    elif selected_relay == 2 and relay_action == 0:
        write_value = [0x71]
    elif selected_relay == 2 and relay_action == 1:
        write_value = [0x67]
    elif selected_relay == 3 and relay_action == 0:
        write_value = [0x72]
    elif selected_relay == 3 and relay_action == 1:
        write_value = [0x68]
    elif selected_relay == 4 and relay_action == 0:
        write_value = [0x73]
    elif selected_relay == 4 and relay_action == 1:
        write_value = [0x69]
    elif selected_relay == 5 and relay_action == 0:
        write_value = [0x74]
    elif selected_relay == 5 and relay_action == 1:
        write_value = [0x6A]
    elif selected_relay == 6 and relay_action == 0:
        write_value = [0x75]
    elif selected_relay == 6 and relay_action == 1:
        write_value = [0x6B]
    elif selected_relay == 7 and relay_action == 0:
        write_value = [0x76]
    elif selected_relay == 7 and relay_action == 1:
        write_value = [0x6C]
    else:
        print("Invalid selection")
        
    
    #List Of Values all Relays
    ####  Relay 1 Enable    0x65    
    ####  Relay 1 Disable   0x6F    
    ####  Relay 2 Enable    0x66    
    ####  Relay 2 Disable   0x70    
    ####  Relay 3 Enable    0x67    
    ####  Relay 3 Disable   0x71    
    ####  Relay 4 Enable    0x68    
    ####  Relay 4 Disable   0x72    
    ####  Relay 5 Enable    0x69    
    ####  Relay 5 Disable   0x73    
    ####  Relay 6 Enable    0x6A    
    ####  Relay 6 Disable   0x74    
    ####  Relay 7 Enable    0x6B    
    ####  Relay 7 Disable   0x75    
    ####  Relay 8 Enable    0x6C    
    ####  Relay 8 Disable   0x76   

    s = serial.Serial(f'{RELAYCOM}', 19200, timeout=8)
    s.write(write_value)
    s.close()

def PrintRelays():
    DecodeRelayState()
    print("Relay state 0 = disabled")
    print("Relay state 1 = enabled \n")
    print("Currently Relay States:")
    print("Power_Button relay state " + Relays.Power_Button)
    print("Reset_Button relay state " + Relays.Reset_Button)
    print("Kill_Switch relay state " + Relays.Kill_Switch)
    print("TPM relay state " + Relays.TPM)
    print("Clear_CMOS relay state " + Relays.Clear_CMOS)
    print("BMC_Force_Update relay state " + Relays.BMC_Force_Update)
    print("NMI_Button relay state " + Relays.NMI_Button)
    print("BMC_Init relay state " + Relays.BMC_Init)

# TODO: cleanup script and add a looping function. Add 
SelectChangeRelay()
    