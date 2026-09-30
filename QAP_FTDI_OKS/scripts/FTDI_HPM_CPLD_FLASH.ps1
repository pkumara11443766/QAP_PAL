#QAP FTDI wrapper for OKS Platform
[void] [System.Reflection.Assembly]::LoadWithPartialName("System.Windows.Forms")
Add-Type -AssemblyName PresentationFramework

$CONFIG = Get-Content C:\\QAP_FTDI_OKS\\QAP_FTDI_OKS_Config.ini

foreach($line in $CONFIG) {
	if($line -match "SUT_AC1"){$SUT_AC1 = $line.Split('=')[1]}
	if($line -match "SUT_AC2"){$SUT_AC2 = $line.Split('=')[1]}
}

Write-Host "Flash HPM CPLD .pof" -ForegroundColor Cyan

# Detect and close COM230 PuTTY if open
Write-Host "Attempting to close PuTTY window title COM230. `nPlease ensure COM230 connection is closed." -ForegroundColor Yellow
Get-Process | Where-Object { $_.MainWindowTitle -like '*COM230*' } | Stop-Process
Read-Host -Prompt 'Press Enter to continue'

# Select file to flash
Write-Host "Select HPM CPLD .pof file to flash" -ForegroundColor Green
$File = New-Object System.Windows.Forms.OpenFileDialog 
$File.filter = "All Files (*.*)|*hpm*.pof"
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

# Check for .pof file extension
$Filepath_extension = $FilePath.substring($FilePath.Length - 3)

if ($Filepath_extension -ne "pof") {
    $Confirm_nonPOF_flash = [System.Windows.MessageBox]::Show("Unexpected file type selected, continue with HPM CPLD flash? `n`nExpected file type POF for HPM CPLD flash","QAP FTDI HPM CPLD",1,16, 'None', 'DefaultDesktopOnly')
}

if ($Confirm_nonPOF_flash -eq "Cancel") {
	Write-Host "User Cancelled"
    exit
}

python c:\intel\ci.git\scripts\oks-fw-flash.py -w raritan`#`#EMR-PVST:P@ssword1234!234@"$SUT_AC1" -w "$SUT_AC2" --type 1s cpld_hpm:"$FilePath" -c "OKS DC-SCM"

Read-Host -Prompt "Press Enter to exit"