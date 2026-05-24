# setup_named_tunnel.ps1 - Migra de quick tunnel a named tunnel con dominio propio.
#
# REQUISITOS PREVIOS (Emmanuel hace estos 3 pasos UNA vez):
#   1. Comprar dominio en https://dash.cloudflare.com/?to=/:account/registrar
#      (sugerencias: jarvis-v2.io, jarvis-ai.mx, jarvix.mx). ~$12 USD/anio.
#   2. Ejecutar:    .\scripts\cloudflared.exe tunnel login
#      (abre browser -> elige zone -> guarda cert.pem en ~/.cloudflared/)
#   3. Ejecutar este script con el dominio comprado como parametro:
#      .\scripts\setup_named_tunnel.ps1 -Domain jarvis-v2.io
#
# Este script:
#   - Crea named tunnel 'jarvis-prod'
#   - Configura route DNS automatico subdomain @ apex al tunnel
#   - Escribe config.yml para uvicorn proxy
#   - Mata quick tunnel actual y lanza el named
#   - Actualiza schtask Jarvis_Tunnel para usar el named
#   - Actualiza data/public_url.txt al dominio nuevo

param(
    [Parameter(Mandatory=$true)]
    [string]$Domain  # ej. jarvis-v2.io (sin https://)
)

$ErrorActionPreference = "Stop"
$Bin = "C:\Users\Emmanuel\Documents\JarvisAI\scripts\cloudflared.exe"
$ConfigDir = "$env:USERPROFILE\.cloudflared"
$ConfigYml = "$ConfigDir\config.yml"
$TunnelName = "jarvis-prod"

if (-not (Test-Path $Bin)) {
    Write-Error "cloudflared.exe no encontrado en $Bin"
    exit 1
}

# Verificar login previo
if (-not (Test-Path "$ConfigDir\cert.pem")) {
    Write-Host ""
    Write-Host "ERROR: No estas logueado en Cloudflare." -ForegroundColor Red
    Write-Host "Ejecuta primero:" -ForegroundColor Yellow
    Write-Host "  $Bin tunnel login" -ForegroundColor Cyan
    Write-Host "Eso abre tu browser, selecciona la zona $Domain y descarga cert.pem"
    exit 1
}

Write-Host "=== Crear named tunnel '$TunnelName' ===" -ForegroundColor Cyan
$createOutput = & $Bin tunnel create $TunnelName 2>&1
Write-Host $createOutput

# Extraer Tunnel ID (UUID) del output
$tunnelId = ($createOutput | Select-String -Pattern "Created tunnel.*with id ([a-f0-9\-]+)").Matches.Groups[1].Value
if (-not $tunnelId) {
    # Tunnel ya existia, listar y extraer ID existente
    $listOutput = & $Bin tunnel list 2>&1
    $tunnelId = ($listOutput | Select-String -Pattern "^([a-f0-9\-]{36})\s+$TunnelName").Matches.Groups[1].Value
    if (-not $tunnelId) {
        Write-Error "No se pudo obtener tunnel ID"
        exit 1
    }
    Write-Host "Tunnel '$TunnelName' ya existia. ID: $tunnelId" -ForegroundColor Yellow
} else {
    Write-Host "Tunnel creado. ID: $tunnelId" -ForegroundColor Green
}

# Generar config.yml
Write-Host "`n=== Escribir $ConfigYml ===" -ForegroundColor Cyan
$config = @"
tunnel: $tunnelId
credentials-file: $ConfigDir\$tunnelId.json

ingress:
  - hostname: $Domain
    service: http://localhost:5000
  - hostname: www.$Domain
    service: http://localhost:5000
  - service: http_status:404
"@
Set-Content -Path $ConfigYml -Value $config -Encoding UTF8
Write-Host $config

# Route DNS apex + www
Write-Host "`n=== DNS route apex $Domain ===" -ForegroundColor Cyan
& $Bin tunnel route dns $TunnelName $Domain 2>&1
Write-Host "`n=== DNS route www.$Domain ===" -ForegroundColor Cyan
& $Bin tunnel route dns $TunnelName "www.$Domain" 2>&1

# Mata quick tunnel actual
Write-Host "`n=== Kill quick tunnel anterior ===" -ForegroundColor Cyan
Get-CimInstance Win32_Process -Filter "Name='cloudflared.exe'" | ForEach-Object {
    Write-Host "kill PID $($_.ProcessId)"
    Stop-Process -Id $_.ProcessId -Force
}
Start-Sleep -Seconds 2

# Actualiza el script wrapper para correr named en lugar de quick
$tunnelScript = "C:\Users\Emmanuel\Documents\JarvisAI\scripts\cloudflared_tunnel.ps1"
$newWrapper = @"
# cloudflared_tunnel.ps1 (NAMED MODE - dominio $Domain)
`$ErrorActionPreference = "SilentlyContinue"
`$Bin = "C:\Users\Emmanuel\Documents\JarvisAI\scripts\cloudflared.exe"
`$Log = "C:\Users\Emmanuel\Documents\JarvisAI\data\cloudflared.log"
`$ErrLog = "C:\Users\Emmanuel\Documents\JarvisAI\data\cloudflared.err"
`$UrlFile = "C:\Users\Emmanuel\Documents\JarvisAI\data\public_url.txt"

Get-CimInstance Win32_Process -Filter "Name='cloudflared.exe'" |
    ForEach-Object { Stop-Process -Id `$_.ProcessId -Force }
Start-Sleep -Seconds 2

Start-Process -FilePath `$Bin ``
    -ArgumentList @('tunnel', 'run', '$TunnelName') ``
    -RedirectStandardOutput `$Log ``
    -RedirectStandardError `$ErrLog ``
    -WindowStyle Hidden -PassThru | Out-Null

Start-Sleep -Seconds 8
Set-Content -Path `$UrlFile -Value 'https://$Domain' -Encoding UTF8
Write-Output "named tunnel running -> https://$Domain"
"@
Set-Content -Path $tunnelScript -Value $newWrapper -Encoding UTF8
Write-Host "Wrapper actualizado: $tunnelScript" -ForegroundColor Green

# Lanza el named tunnel
Write-Host "`n=== Launch named tunnel ===" -ForegroundColor Cyan
& $tunnelScript

# Actualiza el archivo URL
Set-Content -Path 'C:\Users\Emmanuel\Documents\JarvisAI\data\public_url.txt' `
    -Value "https://$Domain" -Encoding UTF8

# Reinicia schtask Jarvis_Tunnel (apunta al script actualizado)
Write-Host "`n=== Actualizar schtask Jarvis_Tunnel ===" -ForegroundColor Cyan
& schtasks /Create /TN "Jarvis_Tunnel" `
    /TR "powershell.exe -NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File `"$tunnelScript`"" `
    /SC ONSTART /RL HIGHEST /F

Write-Host "`n=== DONE ===" -ForegroundColor Green
Write-Host "Dominio: https://$Domain" -ForegroundColor Yellow
Write-Host "Test:    Invoke-RestMethod https://$Domain/health" -ForegroundColor Yellow
Write-Host ""
Write-Host "Esperar 1-2 min para que DNS propague."
Write-Host "Una vez OK, configurar Stripe webhook endpoint en:"
Write-Host "  https://$Domain/api/v1/billing/webhook"
