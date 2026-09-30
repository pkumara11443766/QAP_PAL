#!python3
from tkinter import *        
from tkinter.ttk import *
import subprocess
import configparser

config = configparser.ConfigParser()
config.read("QAP_FTDI_OKS_Config.ini")
BIOSCOM = config.get("MYVARS", "BIOSCOM")
BMCCOM = config.get("MYVARS", "BMCCOM")
BMC_IP = config.get("MYVARS", "BMC_IP")
PUTTY_PATH = config.get("MYVARS", "PUTTY_PATH")
PUTTY_LOGS_PATH = config.get("MYVARS", "PUTTY_LOGS_PATH")
PYTHONSV_PATH = config.get("MYVARS", "PYTHONSV_PATH")

root=Tk()
root.title('QAP')
root.configure(bg='#232323', pady='5', padx='18')
root.resizable(False, False)

style=Style()
style.theme_use('default')
style.configure('TLabel', font='consolas 9 bold', background='#232323',  foreground='white')
style.configure('TButton', relief='ridge', font='consolas 9 bold', background='#858585', foreground='black')
style.map('TButton', background=[('active', '#6fcded')])

l=Label(root, text='SUT Power Control', style='TLabel').grid(column=0, row=0, columnspan=2)

def sut_on():
    subprocess.Popen('powershell .\\scripts\\SUT_Power_ON.ps1')
btn=Button(root, text='SUT On', command=sut_on,).grid(column=0, row=1, sticky='nesw', padx=2, pady=2)

def sut_off():
    subprocess.Popen('powershell .\\scripts\\SUT_Power_OFF.ps1')
btn=Button(root, text='SUT Off', command=sut_off).grid(column=1, row=1, sticky='nesw', padx=2, pady=2)

def sut_cycle():
    subprocess.Popen('powershell .\\scripts\\SUT_Power_CYCLE.ps1')
btn=Button(root, text='SUT Power Cycle', command=sut_cycle).grid(column=0, row=2, columnspan=2, sticky='nesw', padx=2, pady=2)

l=Label(root, text='PuTTY Serial COMs', style='TLabel').grid(column=0, row=3, columnspan=2)

def putty_bios():
    subprocess.run(f'start "" "{PUTTY_PATH}" -serial {BIOSCOM} -sercfg 115200,8,n,1,X -sessionlog "{PUTTY_LOGS_PATH}\\BIOS_&D.&M.&Y_&T.log" & exit', shell=True)
btn=Button(root, text='BIOS COM', command=putty_bios).grid(column=0, row=4, sticky='nesw', padx=2, pady=2)

def putty_bmc():
    subprocess.run(f'start "" "{PUTTY_PATH}" -serial {BMCCOM} -sercfg 115200,8,n,1,X -sessionlog "{PUTTY_LOGS_PATH}\\BMC_&D.&M.&Y_&T.log" & exit', shell=True)
btn=Button(root, text='BMC COM', command=putty_bmc).grid(column=1, row=4, sticky='nesw', padx=2, pady=2)

l=Label(root, text='FTDI Flashing', style='TLabel').grid(column=0, row=5, columnspan=2)

def scm_cpld_flash():
    subprocess.Popen('powershell .\\scripts\\FTDI_SCM_CPLD_FLASH.ps1')
btn=Button(root, text='SCM .jic', command=scm_cpld_flash).grid(column=0, row=6, sticky='nesw', padx=2, pady=2)

def hpm_cpld_flash():
    subprocess.Popen('powershell .\\scripts\\FTDI_HPM_CPLD_FLASH.ps1')
btn=Button(root, text='HPM .pof', command=hpm_cpld_flash).grid(column=1, row=6, sticky='nesw', padx=2, pady=2)

def bmc_flash():
    subprocess.Popen('powershell .\\scripts\\FTDI_BMC_FLASH.ps1')
btn=Button(root, text='BMC .rom', command=bmc_flash).grid(column=0, row=7, sticky='nesw', padx=2, pady=2)

def ifwi_flash():
    subprocess.Popen('powershell .\\scripts\\FTDI_IFWI_FLASH.ps1')
btn=Button(root, text='IFWI .bin', command=ifwi_flash).grid(column=1, row=7, sticky='nesw', padx=2, pady=2)

def full_flash():
    subprocess.Popen('powershell .\\scripts\\FTDI_FULL_FLASH.ps1')
btn=Button(root, text='Full CPLD/SPI Flash', command=full_flash).grid(column=0, row=8, columnspan=2, sticky='nesw', padx=2, pady=2)

l=Label(root, text='Miscellaneous', style='TLabel').grid(column=0, row=9, columnspan=2)

def pysv():
    subprocess.Popen(f'python {PYTHONSV_PATH}')
btn=Button(root, text='Launch PythonSV', command=pysv).grid(column=0, row=10, columnspan=2, sticky='nesw', padx=2, pady=2)

def bmc_web():
    subprocess.run(f'start chrome https://{BMC_IP}', shell=True)
btn=Button(root, text='OpenBMC Web UI', command=bmc_web).grid(column=0, row=11, columnspan=2, sticky='nesw', padx=2, pady=2)

def relay():
    subprocess.Popen(f'python scripts\\DecodeChange_Relay.py')
btn=Button(root, text='Relay Control', command=relay).grid(column=0, row=12, columnspan=2, sticky='nesw', padx=2, pady=2)

root.mainloop() 