# setup_scheduled_task.ps1 — Crea/actualiza Scheduled Task de Windows
# para que el trainer corra cada 30 minutos en sandbox mode.
#
# Uso (desde PowerShell con permisos normales, NO admin):
#   .\setup_scheduled_task.ps1
#
# Eliminar:
#   Unregister-ScheduledTask -TaskName "Jarvis Trainer" -Confirm:$false

$TaskName = "Jarvis Trainer"
$ProjectRoot = "C:\Users\Emmanuel\Documents\JarvisAI"
$Python = "python"
$Script = "$ProjectRoot\jarvis_trainer\trainer.py"

# Action: ejecutar trainer en sandbox por defecto
$Action = New-ScheduledTaskAction `
    -Execute $Python `
    -Argument "`"$Script`"" `
    -WorkingDirectory $ProjectRoot

# Trigger: cada 30 minutos, indefinidamente
$Trigger = New-ScheduledTaskTrigger -Once -At (Get-Date) `
    -RepetitionInterval (New-TimeSpan -Minutes 30)

# Settings: que no use red restringida, que se pueda correr aunque la PC este en bateria
$Settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 5)

# Principal: correr como el user actual (no admin), solo cuando este logueado
$Principal = New-ScheduledTaskPrincipal `
    -UserId "$env:USERDOMAIN\$env:USERNAME" `
    -LogonType Interactive `
    -RunLevel Limited

# Registrar/sobrescribir
try {
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue
} catch {}

Register-ScheduledTask `
    -TaskName $TaskName `
    -Action $Action `
    -Trigger $Trigger `
    -Settings $Settings `
    -Principal $Principal `
    -Description "Jarvis training loop — sandbox mode, cada 30min" | Out-Null

Write-Host ""
Write-Host "Scheduled Task '$TaskName' registrada." -ForegroundColor Green
Write-Host "Corre cada 30 min en sandbox mode (sin tocar apps reales)."
Write-Host ""
Write-Host "Comandos:"
Write-Host "  Ver:       Get-ScheduledTask -TaskName '$TaskName'"
Write-Host "  Forzar:    Start-ScheduledTask -TaskName '$TaskName'"
Write-Host "  Eliminar:  Unregister-ScheduledTask -TaskName '$TaskName' -Confirm:`$false"
Write-Host ""
Write-Host "Para entrenar EN VIVO (sin sandbox), correr manual:"
Write-Host "  `$env:JARVIS_SANDBOX='0'; python `"$Script`""
