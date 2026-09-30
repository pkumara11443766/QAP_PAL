#SUT Power Cycle via Raritan
$count = 0
while ($count -le 50)
{
	Write-Host "Iteration $count"
	Write-Host "Issue Power cycle and wait till system boots to EFI shell"
	& .\SUT_Power_CYCLE.ps1
	Start-Sleep -Seconds 1200
	$count++
}
 
Exit