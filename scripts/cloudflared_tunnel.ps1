# cloudflared_tunnel.ps1 - Mantiene el quick tunnel activo + escribe URL a disco.
#
# Quick tunnels (sin cuenta) generan URL random nueva cada vez que arrancan.
# Para producccion: usar named tunnel con dominio propio (requires Cloudflare login).
# Este script reinicia el tunnel si muere y publica la URL en data/public_url.txt
# para que otros componentes la lean.
#
# Registrar como schtask Jarvis_Tunnel para uptime 24/7:
#   schtasks /Create /TN Jarvis_Tunnel /TR "powershell -NoProfile -WindowStyle Hidden
#     -File C:\Users\Emmanuel\Documents\JarvisAI\scripts\cloudflared_tunnel.ps1"
#     /SC ONSTART /RL HIGHEST /F

$ErrorActionPreference = "SilentlyContinue"
$Bin = "C:\Users\Emmanuel\Documents\JarvisAI\scripts\cloudflared.exe"
$Log = "C:\Users\Emmanuel\Documents\JarvisAI\data\cloudflared.log"
$ErrLog = "C:\Users\Emmanuel\Documents\JarvisAI\data\cloudflared.err"
$UrlFile = "C:\Users\Emmanuel\Documents\JarvisAI\data\public_url.txt"
$TargetUrl = "http://localhost:5000"

# Mata cualquier instancia previa
Get-CimInstance Win32_Process -Filter "Name='cloudflared.exe'" |
    ForEach-Object { Stop-Process -Id $_.ProcessId -Force }
Start-Sleep -Seconds 2

# Limpia logs viejos
Clear-Content $Log -ErrorAction SilentlyContinue
Clear-Content $ErrLog -ErrorAction SilentlyContinue

# Arranca cloudflared
Start-Process -FilePath $Bin `
    -ArgumentList @('tunnel', '--url', $TargetUrl) `
    -RedirectStandardOutput $Log `
    -RedirectStandardError $ErrLog `
    -WindowStyle Hidden -PassThru | Out-Null

# Espera y extrae la URL publica del log
Start-Sleep -Seconds 12
$logContent = (Get-Content $ErrLog -ErrorAction SilentlyContinue) -join "`n"
$urlMatch = [regex]::Match($logContent, "https://[a-z0-9\-]+\.trycloudflare\.com")
if ($urlMatch.Success) {
    $url = $urlMatch.Value
    Set-Content -Path $UrlFile -Value $url -Encoding UTF8
    Write-Output "tunnel URL: $url -> $UrlFile"
} else {
    Write-Error "No se pudo extraer URL del log"
    exit 1
}
