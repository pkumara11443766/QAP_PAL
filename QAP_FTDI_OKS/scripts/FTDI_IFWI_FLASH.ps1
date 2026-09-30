#QAP FTDI wrapper for OKS Platform
[void] [System.Reflection.Assembly]::LoadWithPartialName("System.Windows.Forms") 
Add-Type -AssemblyName PresentationFramework

$CONFIG = Get-Content C:\\QAP_FTDI_OKS\\QAP_FTDI_OKS_Config.ini

foreach($line in $CONFIG) {
	if($line -match "SUT_AC1"){$SUT_AC1 = $line.Split('=')[1]}
	if($line -match "SUT_AC2"){$SUT_AC2 = $line.Split('=')[1]}
}

Write-Host "Flash IFWI .bin" -ForegroundColor Cyan

# Detect and close COM230 PuTTY if open
Write-Host "Attempting to close PuTTY window title COM230. `nPlease ensure COM230 connection is closed." -ForegroundColor Yellow
Get-Process | Where-Object { $_.MainWindowTitle -like '*COM230*' } | Stop-Process
Read-Host -Prompt 'Press Enter to continue'

# Select file to flash
Write-Host "Select IFWI .bin file to flash" -ForegroundColor Green
$File = New-Object System.Windows.Forms.OpenFileDialog 
$File.filter = "All Files (*.*)|*.bin"
$null = $File.ShowDialog()
$FilePath = $File.FileName
echo "$FilePath"

# Cancel if no file selected
if (!$FilePath) { 
Write-Host "Selection interrupted. Press any key to exit."
$Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown") | Out-Null
$Host.UI.RawUI.Flushinputbuffer()
Exit
}

# Check for .bin file extension
$Filepath_extension = $FilePath.substring($FilePath.Length - 3)

if ($Filepath_extension -ne "bin") {
    $Confirm_nonBIN_flash = [System.Windows.MessageBox]::Show("Unexpected file type selected, continue with IFWI SPI flash? `n`nExpected file type BIN for IFWI SPI flash","QAP FTDI IFWI SPI",1,16, 'None', 'DefaultDesktopOnly')
}

if ($Confirm_nonBIN_flash -eq "Cancel") {
	Write-Host "User Cancelled"
    exit
}

python c:\intel\ci.git\scripts\oks-fw-flash.py -w raritan`#`#EMR-PVST:P@ssword1234!234@"$SUT_AC1" -w "$SUT_AC2" --type 1s bios:"$FilePath" -c "OKS DC-SCM"

Read-Host -Prompt "Press Enter to exit"