# ═══════════════════════════════════════════════════
#   JARVIS AI — Launcher
# ═══════════════════════════════════════════════════

$root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)

Write-Host ""
Write-Host "═══════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host "  J.A.R.V.I.S  //  Starting up..." -ForegroundColor Cyan
Write-Host "═══════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host ""

# ─── 1. Verificar Ollama ───
Write-Host "[1/3] Verificando Ollama..." -ForegroundColor Yellow
$ollamaRunning = $false
try {
    $response = Invoke-RestMethod -Uri "http://localhost:11434/api/tags" -TimeoutSec 2 -ErrorAction Stop
    $ollamaRunning = $true
    Write-Host "  OK: Ollama ya esta corriendo" -ForegroundColor Green
} catch {
    Write-Host "  Iniciando Ollama..." -ForegroundColor Yellow
    $ollama = Get-Command ollama -ErrorAction SilentlyContinue
    if ($ollama) {
        Start-Process ollama -ArgumentList "serve" -WindowStyle Hidden
        Start-Sleep -Seconds 3
        Write-Host "  OK: Ollama iniciado" -ForegroundColor Green
    } else {
        Write-Host "  WARN: Ollama no encontrado. El chat funcionara pero sin IA." -ForegroundColor Yellow
        Write-Host "  Ejecuta setup.ps1 para instalarlo." -ForegroundColor Yellow
    }
}

# ─── 2. Iniciar Backend ───
Write-Host "[2/3] Iniciando backend FastAPI..." -ForegroundColor Yellow
$backendProcess = Start-Process python -ArgumentList "main.py" -WorkingDirectory "$root\backend" -PassThru -WindowStyle Hidden
Start-Sleep -Seconds 2

# Verificar que el backend este vivo
try {
    $health = Invoke-RestMethod -Uri "http://127.0.0.1:8765/api/health" -TimeoutSec 5
    Write-Host "  OK: Backend corriendo en puerto 8765" -ForegroundColor Green
} catch {
    Write-Host "  WARN: Backend aun iniciando..." -ForegroundColor Yellow
}

# ─── 3. Iniciar Electron ───
Write-Host "[3/3] Iniciando Jarvis AI..." -ForegroundColor Yellow
Write-Host ""
Write-Host "  Atajos:" -ForegroundColor White
Write-Host "    Alt+J  = Mostrar/Ocultar Jarvis" -ForegroundColor Cyan
Write-Host "    Alt+V  = Activar voz" -ForegroundColor Cyan
Write-Host ""
Write-Host "═══════════════════════════════════════════════════" -ForegroundColor Green
Write-Host "  JARVIS AI esta listo. Buenas tardes, Emmanuel." -ForegroundColor Green
Write-Host "═══════════════════════════════════════════════════" -ForegroundColor Green
Write-Host ""

# Iniciar Electron (esto bloquea hasta que se cierre)
Push-Location "$root\frontend"
npx electron .
Pop-Location

# ─── Cleanup al cerrar ───
Write-Host ""
Write-Host "Apagando Jarvis..." -ForegroundColor Yellow

if ($backendProcess -and -not $backendProcess.HasExited) {
    Stop-Process -Id $backendProcess.Id -Force -ErrorAction SilentlyContinue
    Write-Host "  Backend detenido" -ForegroundColor Yellow
}

Write-Host "  Jarvis AI apagado. Hasta luego, Emmanuel." -ForegroundColor Cyan
Write-Host ""
