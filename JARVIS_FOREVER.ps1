# JARVIS_FOREVER.ps1 — Setup definitivo para que la VM no necesite intervencion NUNCA mas
#
# Hace todo lo necesario para que:
#   - VM arranca sola (auto-logon)
#   - START_JARVIS.bat corre al login (scheduled task)
#   - RDP nativo Win11 habilitado (controlable desde host via mstsc localhost:13389)
#   - Power timeout off (no se duerme)
#   - Servicios Jarvis listos para correr 24/7
#
# Uso (UNA SOLA VEZ, dentro de la VM como admin):
#   .\JARVIS_FOREVER.ps1
#
# Reboota la VM al final.

#Requires -RunAsAdministrator

$ErrorActionPreference = "Continue"
$VerbosePreference = "Continue"

function Banner($msg) {
    Write-Host ""
    Write-Host ("=" * 70) -ForegroundColor Cyan
    Write-Host "  $msg" -ForegroundColor Yellow
    Write-Host ("=" * 70) -ForegroundColor Cyan
}

# ============================================================================
Banner "[1/7] HABILITAR RDP NATIVO WIN11"
# ============================================================================
Set-ItemProperty -Path "HKLM:\System\CurrentControlSet\Control\Terminal Server" `
    -Name fDenyTSConnections -Value 0 -ErrorAction SilentlyContinue
Set-ItemProperty -Path "HKLM:\System\CurrentControlSet\Control\Terminal Server\WinStations\RDP-Tcp" `
    -Name UserAuthentication -Value 0 -ErrorAction SilentlyContinue
Enable-NetFirewallRule -DisplayGroup "Remote Desktop" -ErrorAction SilentlyContinue
Write-Host "  OK RDP habilitado. Conectar desde host: mstsc localhost:13389"

# ============================================================================
Banner "[2/7] DESHABILITAR POWER TIMEOUT"
# ============================================================================
powercfg /change monitor-timeout-ac 0
powercfg /change standby-timeout-ac 0
powercfg /change disk-timeout-ac 0
powercfg /change hibernate-timeout-ac 0
Write-Host "  OK power timeouts en 0 (nunca se duerme)"

# ============================================================================
Banner "[3/7] AUTO-LOGON"
# ============================================================================
$username = $env:USERNAME
$password = Read-Host -AsSecureString "Tu password de Windows para auto-logon (lo guarda en registry encriptado)"
$BSTR = [System.Runtime.InteropServices.Marshal]::SecureStringToBSTR($password)
$plainPwd = [System.Runtime.InteropServices.Marshal]::PtrToStringAuto($BSTR)

$winLogonPath = "HKLM:\Software\Microsoft\Windows NT\CurrentVersion\Winlogon"
Set-ItemProperty -Path $winLogonPath -Name "AutoAdminLogon" -Value "1"
Set-ItemProperty -Path $winLogonPath -Name "DefaultUserName" -Value $username
Set-ItemProperty -Path $winLogonPath -Name "DefaultPassword" -Value $plainPwd
Write-Host "  OK auto-logon configurado para $username"

# ============================================================================
Banner "[4/7] SCHEDULED TASK: ARRANCAR JARVIS AL LOGIN"
# ============================================================================
$action = New-ScheduledTaskAction -Execute "cmd.exe" `
    -Argument "/c cd /d C:\Jarvis && START_JARVIS.bat" `
    -WorkingDirectory "C:\Jarvis"
$trigger = New-ScheduledTaskTrigger -AtLogOn -User $username
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries -ExecutionTimeLimit (New-TimeSpan -Hours 12) `
    -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1)
$principal = New-ScheduledTaskPrincipal -UserId $username -RunLevel Highest -LogonType Interactive

Register-ScheduledTask -TaskName "JarvisAutoStart" `
    -Action $action -Trigger $trigger -Settings $settings -Principal $principal `
    -Description "Arranca Jarvis al login del usuario" -Force | Out-Null

Write-Host "  OK scheduled task JarvisAutoStart creado"

# ============================================================================
Banner "[5/7] INSTALAR GUEST ADDITIONS (si ISO montado)"
# ============================================================================
$gaSetup = "D:\VBoxWindowsAdditions.exe"
if (Test-Path $gaSetup) {
    Write-Host "  Encontrado $gaSetup, instalando silent..."
    Start-Process -FilePath $gaSetup -ArgumentList "/S" -Wait -NoNewWindow
    Write-Host "  OK Guest Additions instalado (reiniciar al final)"
} else {
    Write-Host "  WARN: $gaSetup no existe. Montar ISO Guest Additions desde host primero."
    Write-Host "    Comando host: VBoxManage storageattach Win11Jarvis --storagectl IDE --port 1 --device 0 --type dvddrive --medium VBoxGuestAdditions.iso"
}

# ============================================================================
Banner "[6/7] PORT FORWARDING ALIASES EN LA VM"
# ============================================================================
# Estos firewall rules abren los puertos para que el host pueda forward NAT
New-NetFirewallRule -DisplayName "Jarvis Proxy 8088" -Direction Inbound `
    -Protocol TCP -LocalPort 8088 -Action Allow -ErrorAction SilentlyContinue | Out-Null
New-NetFirewallRule -DisplayName "Jarvis Dashboard 7777" -Direction Inbound `
    -Protocol TCP -LocalPort 7777 -Action Allow -ErrorAction SilentlyContinue | Out-Null
Write-Host "  OK firewall rules para 8088 y 7777"

# ============================================================================
Banner "[7/7] LIMPIAR ESTADO COLGADO"
# ============================================================================
# Matar cualquier python o claude colgado
Get-Process -Name "python", "claude*" -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
Write-Host "  OK procesos colgados terminados"

# ============================================================================
Banner "REBOOT EN 10s PARA APLICAR TODO"
# ============================================================================
Write-Host ""
Write-Host "  Despues del reboot:" -ForegroundColor Green
Write-Host "  1. Auto-logon entra solo a $username" -ForegroundColor Green
Write-Host "  2. Scheduled task arranca START_JARVIS.bat" -ForegroundColor Green
Write-Host "  3. Conecta desde host: mstsc localhost:13389 (user: $username + tu password)" -ForegroundColor Green
Write-Host ""
Write-Host "Reiniciando en 10 segundos... (Ctrl+C para cancelar)"
Start-Sleep -Seconds 10
Restart-Computer -Force
