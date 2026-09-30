#SUT Power Off via Raritan
[void] [System.Reflection.Assembly]::LoadWithPartialName("System.Windows.Forms")
Add-Type -AssemblyName PresentationFramework

$CONFIG = Get-Content C:\\QAP_FTDI_OKS\\QAP_FTDI_OKS_Config.ini
foreach($line in $CONFIG) {
	if($line -match "PYTHON_PATH"){$PYTHON_PATH = $line.Split('=')[1]}
}

Write-Host "SUT Power Off" -ForegroundColor Cyan

python $PYTHON_PATH\Lib\site-packages\pysvtools\raritan\RaritanPower.py -x C:\QAP_FTDI_OKS\raritan.xml -a off

Write-Host "SUT Powered Off Successfully" -ForegroundColor Green
Start-Sleep -Seconds 2
Exit