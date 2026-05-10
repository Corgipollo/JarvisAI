# setup_scheduled_task.ps1 - Crea/actualiza Scheduled Task de Windows
# para que el trainer corra cada 30 minutos en sandbox mode (host).

$TaskName = "Jarvis Trainer"
$ProjectRoot = "C:\Users\Emmanuel\Documents\JarvisAI"
$Python = "python"
$Script = "$ProjectRoot\jarvis_trainer\trainer.py"

$Action = New-ScheduledTaskAction -Execute $Python -Argument ('"' + $Script + '"') -WorkingDirectory $ProjectRoot

$Trigger = New-ScheduledTaskTrigger -Once -At (Get-Date) -RepetitionInterval (New-TimeSpan -Minutes 30)

$Settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable -ExecutionTimeLimit (New-TimeSpan -Minutes 5)

$Principal = New-ScheduledTaskPrincipal -UserId ($env:USERDOMAIN + '\' + $env:USERNAME) -LogonType Interactive -RunLevel Limited

try {
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue
} catch {}

Register-ScheduledTask -TaskName $TaskName -Action $Action -Trigger $Trigger -Settings $Settings -Principal $Principal -Description "Jarvis training loop - sandbox mode, cada 30min" | Out-Null

Write-Host ""
Write-Host "Scheduled Task '$TaskName' registrada." -ForegroundColor Green
Write-Host "Corre cada 30 min en sandbox mode (sin tocar apps reales)."
Write-Host ""
Write-Host "Comandos utiles:"
Write-Host "  Ver:      Get-ScheduledTask -TaskName 'Jarvis Trainer'"
Write-Host "  Forzar:   Start-ScheduledTask -TaskName 'Jarvis Trainer'"
Write-Host "  Eliminar: Unregister-ScheduledTask -TaskName 'Jarvis Trainer' -Confirm:" + "`$false"
