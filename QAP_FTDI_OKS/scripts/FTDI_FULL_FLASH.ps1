#QAP FTDI wrapper for OKS Platform
[void] [System.Reflection.Assembly]::LoadWithPartialName("System.Windows.Forms") 
Add-Type -AssemblyName PresentationFramework

$CONFIG = Get-Content C:\\QAP_FTDI_OKS\\QAP_FTDI_OKS_Config.ini

foreach($line in $CONFIG) {
	if($line -match "SUT_AC1"){$SUT_AC1 = $line.Split('=')[1]}
	if($line -match "SUT_AC2"){$SUT_AC2 = $line.Split('=')[1]}
}

Write-Host "Flash Full CPLD/SPI" -ForegroundColor Cyan

# Detect and close COM230 PuTTY if open
Write-Host "Attempting to close PuTTY window title COM230. `nPlease ensure COM230 connection is closed." -ForegroundColor Yellow
Get-Process | Where-Object { $_.MainWindowTitle -like '*COM230*' } | Stop-Process
Read-Host -Prompt 'Press Enter to continue'

# Select file to flash
Write-Host "Select SCM CPLD .jic file to flash" -ForegroundColor Green
$File1 = New-Object System.Windows.Forms.OpenFileDialog
$File1.filter = "All Files (*.*)|*.jic"
$null = $File1.ShowDialog()
$SCMFilePath = $File1.FileName
echo "$SCMFilePath"

# Cancel if no file selected
if (!$SCMFilePath) { 
Write-Host "Selection interrupted. Press any key to exit."
$Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown") | Out-Null
$Host.UI.RawUI.Flushinputbuffer()
Exit
}

# Check for .jic file extension
$SCMFilepath_extension = $SCMFilePath.substring($SCMFilePath.Length - 3)

if ($SCMFilepath_extension -ne "jic") {
    $Confirm_nonJIC_flash = [System.Windows.MessageBox]::Show("Unexpected file type selected, continue with SCM CPLD flash? `n`nExpected file type JIC for SCM CPLD flash" , "QAP FTDI SCM CPLD" , 1, 16, 'None', 'DefaultDesktopOnly')
}

if ($Confirm_nonJIC_flash -eq "Cancel") {
	Write-Host "User Cancelled"
    exit
}

# Select file to flash
Write-Host "Select HPM CPLD .pof file to flash" -ForegroundColor Green
$File2 = New-Object System.Windows.Forms.OpenFileDialog
$File2.filter = "All Files (*.*)|*hpm*.pof"
$null = $File2.ShowDialog()
$HPMFilePath = $File2.FileName
echo "$HPMFilePath"

# Cancel if no file selected
if (!$HPMFilePath) { 
Write-Host "Selection interrupted. Press any key to exit."
$Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown") | Out-Null
$Host.UI.RawUI.Flushinputbuffer()
Exit
}

# Check for .pof file extension
$HPMFilepath_extension = $HPMFilePath.substring($HPMFilePath.Length - 3)

if ($HPMFilepath_extension -ne "pof") {
    $Confirm_nonPOF_flash = [System.Windows.MessageBox]::Show("Unexpected file type selected, continue with HPM CPLD flash? `n`nExpected file type POF for HPM CPLD flash" , "QAP FTDI HPM CPLD" , 1, 16, 'None', 'DefaultDesktopOnly')
}

if ($Confirm_nonPOF_flash -eq "Cancel") {
	Write-Host "User Cancelled"
    exit
}

# Select file to flash
Write-Host "Select BMC .rom file to flash" -ForegroundColor Green
$File3 = New-Object System.Windows.Forms.OpenFileDialog
$File3.filter = "All Files (*.*)|*.rom"
$null = $File3.ShowDialog()
$BMCFilePath = $File3.FileName
echo "$BMCFilePath"

# Cancel if no file selected
if (!$BMCFilePath) { 
Write-Host "Selection interrupted. Press any key to exit."
$Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown") | Out-Null
$Host.UI.RawUI.Flushinputbuffer()
Exit
}

# Check for .rom file extension
$BMCFilepath_extension = $BMCFilePath.substring($BMCFilePath.Length - 3)

if ($BMCFilepath_extension -ne "rom") {
    $Confirm_nonROM_flash = [System.Windows.MessageBox]::Show("Unexpected file type selected, continue with BMC SPI flash? `n`nExpected file type ROM for BMC SPI flash","QAP FTDI BMC SPI",1,16, 'None', 'DefaultDesktopOnly')
}

if ($Confirm_nonROM_flash -eq "Cancel") {
	Write-Host "User Cancelled"
    exit
}

# Select file to flash
Write-Host "Select IFWI .bin file to flash" -ForegroundColor Green
$File4 = New-Object System.Windows.Forms.OpenFileDialog
$File4.filter = "All Files (*.*)|*.bin"
$null = $File4.ShowDialog()
$IFWIFilePath = $File4.FileName
echo "$IFWIFilePath"

# Cancel if no file selected
if (!$IFWIFilePath) { 
Write-Host "Selection interrupted. Press any key to exit."
$Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown") | Out-Null
$Host.UI.RawUI.Flushinputbuffer()
Exit
}
echo "python c:\intel\ci.git\scripts\oks-fw-flash.py -w raritan`#`#EMR-PVST:P@ssword1234!234@"$SUT_AC1" -w "$SUT_AC2" --type 1s cpld_scm:"$SCMFilePath" cpld_hpm:"$HPMFilePath" bmc:"$BMCFilePath" bios:"$IFWIFilePath" -c "OKS DC-SCM""

# Check for .bin file extension
$IFWIFilepath_extension = $IFWIFilePath.substring($IFWIFilePath.Length - 3)

if ($IFWIFilepath_extension -ne "bin") {
    $Confirm_nonBIN_flash = [System.Windows.MessageBox]::Show("Unexpected file type selected, continue with IFWI SPI flash? `n`nExpected file type BIN for IFWI SPI flash","QAP FTDI IFWI SPI",1,16, 'None', 'DefaultDesktopOnly')
}

if ($Confirm_nonBIN_flash -eq "Cancel") {
	Write-Host "User Cancelled"
    exit
}

python c:\intel\ci.git\scripts\oks-fw-flash.py -w raritan`#`#EMR-PVST:P@ssword1234!234@"$SUT_AC1" -w "$SUT_AC2" --type 1s cpld_scm:"$SCMFilePath" cpld_hpm:"$HPMFilePath" bmc:"$BMCFilePath" bios:"$IFWIFilePath" -c "OKS DC-SCM"

Read-Host -Prompt "Press Enter to exit"