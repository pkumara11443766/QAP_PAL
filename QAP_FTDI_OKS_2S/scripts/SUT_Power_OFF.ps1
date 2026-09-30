#SUT Power Off via Raritan
[void] [System.Reflection.Assembly]::LoadWithPartialName("System.Windows.Forms")
Add-Type -AssemblyName PresentationFramework

$CONFIG = Get-Content C:\\QAP_FTDI_OKS_2S\\QAP_FTDI_OKS_2S_Config.ini
foreach($line in $CONFIG) {
	if($line -match "PYTHON_PATH"){$PYTHON_PATH = $line.Split('=')[1]}
}

Write-Host "SUT Power Off" -ForegroundColor Cyan

Start-Process -NoNewWindow cmd.exe "/c python $PYTHON_PATH\Lib\site-packages\pysvtools\raritan\RaritanPower.py -x C:\QAP_FTDI_OKS_2S\raritan_aggregator.xml -a off"
Start-Process -NoNewWindow cmd.exe "/c python $PYTHON_PATH\Lib\site-packages\pysvtools\raritan\RaritanPower.py -x C:\QAP_FTDI_OKS_2S\raritan_mainboard1.xml -a off"
Start-Process -NoNewWindow cmd.exe "/c python $PYTHON_PATH\Lib\site-packages\pysvtools\raritan\RaritanPower.py -x C:\QAP_FTDI_OKS_2S\raritan_mainboard2.xml -a off"

Exit