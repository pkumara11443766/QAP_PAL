#QAP FTDI wrapper for OKS Platform
[void] [System.Reflection.Assembly]::LoadWithPartialName("System.Windows.Forms")
Add-Type -AssemblyName PresentationFramework

$CONFIG = Get-Content C:\\QAP_FTDI_OKS_2S\\QAP_FTDI_OKS_2S_Config.ini

foreach($line in $CONFIG) {
	if($line -match "SUT_AC1"){$SUT_AC1 = $line.Split('=')[1]}
	if($line -match "SUT_AC2"){$SUT_AC2 = $line.Split('=')[1]}
	if($line -match "SUT_AC3"){$SUT_AC3 = $line.Split('=')[1]}
	if($line -match "SUT_AC4"){$SUT_AC4 = $line.Split('=')[1]}
	if($line -match "SUT_AC5"){$SUT_AC5 = $line.Split('=')[1]}
	if($line -match "PDU_USER"){$PDU_USER = $line.Split('=')[1]}
    if($line -match "PDU_PASS"){$PDU_PASS = $line.Split('=')[1]}	
}

Write-Host "Flash SCM CPLD .jic" -ForegroundColor Cyan

# Detect and close COM230 PuTTY if open
Write-Host "Attempting to close PuTTY window title COM230. `nPlease ensure COM230 connection is closed." -ForegroundColor Yellow
Get-Process | Where-Object { $_.MainWindowTitle -like '*COM230*' } | Stop-Process
Read-Host -Prompt 'Press Enter to continue'

# Select file to flash
Write-Host "Select SCM CPLD .jic file to flash" -ForegroundColor Green
$File = New-Object System.Windows.Forms.OpenFileDialog
$File.filter = "All Files (*.*)|*.jic"
$null = $File.ShowDialog()
$FilePath = $File.FileName
echo "$FilePath"

if (!$FilePath) { 
Write-Host "Selection interrupted. Press any key to exit."
$Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown") | Out-Null
$Host.UI.RawUI.Flushinputbuffer()
Exit
}

# Additional check to see if file extension is .jic, else throw warning and ask before proceeding
$Filepath_extension = $FilePath.substring($FilePath.Length - 3)

if ($Filepath_extension -ne "jic") {
    $Confirm_nonJIC_flash = [System.Windows.MessageBox]::Show("Unexpected file type selected, continue with SCM CPLD flash? `n`nExpected file type JIC for SCM CPLD flash","QAP FTDI SCM CPLD",1,16, 'None', 'DefaultDesktopOnly')
}

if ($Confirm_nonJIC_flash -eq "Cancel") {
	Write-Host "User Cancelled"
    exit
}

python c:\intel\ci.git\scripts\oks-fw-flash.py -w raritan`#`#"$PDU_USER":"$PDU_PASS"`@"$SUT_AC1" -w "$SUT_AC2" -w "$SUT_AC3"  -w "$SUT_AC4"  -w "$SUT_AC5" --type ms cpld_scm:"$FilePath" -c "OKS DC-SCM"

Read-Host -Prompt "Press Enter to exit"