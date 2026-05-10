#
# enable_feature.ps1
#
# Habilita la feature "Windows Sandbox" en Windows 10/11 Pro.
# REQUIERE: ejecutar como administrador + reboot.
#
# Click derecho > "Run with PowerShell" como admin.
#

if (-not ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    Write-Host "Este script requiere ejecutarse como ADMINISTRADOR." -ForegroundColor Red
    Write-Host ""
    Write-Host "Como hacerlo:"
    Write-Host "  1. Click derecho en este archivo"
    Write-Host "  2. 'Run with PowerShell' como administrador"
    Write-Host "  (o abrir PowerShell admin y ejecutar este .ps1 manualmente)"
    pause
    exit 1
}

Write-Host "=== Habilitando Windows Sandbox ===" -ForegroundColor Cyan

# Verificar requisitos
$cpu = Get-CimInstance Win32_Processor
$virtualization = $cpu.VirtualizationFirmwareEnabled
if (-not $virtualization) {
    Write-Host ""
    Write-Host "ADVERTENCIA: Virtualizacion (VT-x/AMD-V) no detectada como habilitada." -ForegroundColor Yellow
    Write-Host "Verifica en BIOS/UEFI que la virtualizacion este ON."
    Write-Host ""
}

# Habilitar Windows Sandbox
Write-Host "Activando feature 'Containers-DisposableClientVM'..." -ForegroundColor Cyan
try {
    Enable-WindowsOptionalFeature -Online -FeatureName "Containers-DisposableClientVM" -All -NoRestart
    Write-Host "Feature habilitada." -ForegroundColor Green
} catch {
    Write-Host "Error: $_" -ForegroundColor Red
    exit 1
}

# Tambien activar Hyper-V Platform (recomendado)
Write-Host "Activando 'HypervisorPlatform' (recomendado)..." -ForegroundColor Cyan
try {
    Enable-WindowsOptionalFeature -Online -FeatureName "HypervisorPlatform" -All -NoRestart -ErrorAction SilentlyContinue
    Write-Host "HypervisorPlatform habilitado." -ForegroundColor Green
} catch {
    Write-Host "HypervisorPlatform: $_" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "=== Listo ===" -ForegroundColor Green
Write-Host ""
Write-Host "Reinicia la PC para aplicar los cambios." -ForegroundColor Yellow
Write-Host ""
Write-Host "Despues del reboot, lanzar la sandbox con:"
Write-Host "  cd C:\Users\Emmanuel\Documents\JarvisAI\sandbox_vm"
Write-Host "  .\launch_sandbox.bat"
Write-Host ""

$reboot = Read-Host "Reiniciar ahora? (s/n)"
if ($reboot -eq "s" -or $reboot -eq "S") {
    Restart-Computer -Force
}
