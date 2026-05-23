# install_voice.ps1 - Instalador del modulo de voz (Iron Man mode).
#
# Diseno honesto: pide confirmacion antes de cada paso destructivo.
# pip install puede bajar ~3 GB de CUDA libs. Schtask /IT requiere usuario
# Windows logueado. Ambas son acciones que ameritan revision humana.
#
# Uso:
#   .\scripts\install_voice.ps1          # interactivo (default)
#   .\scripts\install_voice.ps1 -Yes     # no-prompt (CI mode)

param([switch]$Yes)

$ErrorActionPreference = "Stop"
$Python = "C:\CPython310\python.exe"

function Confirm-Step($label, $cmd) {
    if ($Yes) { return $true }
    Write-Host "`n[install] $label" -ForegroundColor Cyan
    Write-Host "  Comando: $cmd" -ForegroundColor Gray
    $r = Read-Host "  Ejecutar? (y/N)"
    return ($r -eq "y" -or $r -eq "Y")
}

# ============================================================================
# Step 1: pip install
# ============================================================================
$deps = @("faster-whisper>=1.0", "sounddevice>=0.4.6", "pygame>=2.5",
          "keyboard>=0.13", "edge-tts>=6.1", "numpy")
$pipCmd = "$Python -m pip install -U " + ($deps -join " ")

if (Confirm-Step "Instalar deps (~3 GB con CUDA libs)" $pipCmd) {
    Write-Host "[install] pip install (puede tardar 3-10 min)..." -ForegroundColor Yellow
    & $Python -m pip install -U @deps
    if ($LASTEXITCODE -ne 0) {
        Write-Error "pip install fallo. Revisa los logs arriba."
        exit 1
    }
    Write-Host "[install] deps OK" -ForegroundColor Green
} else {
    Write-Host "[install] Skipping pip install" -ForegroundColor Yellow
}

# ============================================================================
# Step 2: schtask Jarvis_VoiceDaemon
# ============================================================================
$taskName = "Jarvis_VoiceDaemon"
$script = "C:\Users\Emmanuel\Documents\JarvisAI\jarvis_v2\daemons\voice_daemon.py"
# /IT = interactive (sesion del usuario, necesario para microfono)
# /RL HIGHEST = privilegios admin
$schtaskCmd = "schtasks /Create /TN `"$taskName`" /TR `"$Python `"$script`"`" /SC ONLOGON /IT /RL HIGHEST /F"

if (Confirm-Step "Registrar schtask '$taskName' (corre al login del usuario)" $schtaskCmd) {
    if (-not (Test-Path $script)) {
        Write-Error "Script no existe: $script"
        exit 1
    }
    & schtasks /Create /TN $taskName /TR "$Python `"$script`"" /SC ONLOGON /IT /RL HIGHEST /F
    if ($LASTEXITCODE -eq 0) {
        Write-Host "[install] schtask registrado" -ForegroundColor Green
    } else {
        Write-Error "schtasks fallo. Codigo: $LASTEXITCODE"
        exit 1
    }
} else {
    Write-Host "[install] Skipping schtask" -ForegroundColor Yellow
}

# ============================================================================
# Step 3: smoke test (opcional)
# ============================================================================
if (Confirm-Step "Smoke test (carga whisper + speak 'Jarvis listo'). 30s aprox" "$Python -c '...'") {
    Write-Host "[install] Smoke test..." -ForegroundColor Yellow
    & $Python -c "import sys; sys.path.insert(0, r'C:\Users\Emmanuel\Documents\JarvisAI'); from jarvis_v2.daemons.voice_daemon import speak, _load_whisper; _load_whisper(); speak('Smoke test exitoso. Modulo de voz listo.')"
    if ($LASTEXITCODE -eq 0) {
        Write-Host "[install] Si escuchaste 'Smoke test exitoso', todo OK." -ForegroundColor Green
    } else {
        Write-Warning "Smoke test no termino limpio. Revisa la salida arriba."
    }
}

Write-Host "`n=== INSTALACION VOICE DAEMON ===" -ForegroundColor Cyan
Write-Host "Para arrancar manualmente AHORA (sin esperar logout/login):"
Write-Host "  $Python -m jarvis_v2.daemons.voice_daemon"
Write-Host ""
Write-Host "Uso:"
Write-Host "  - Mantener F12 presionado y hablar -> graba hasta soltar"
Write-Host "  - (Opcional) export VOICE_WAKE_WORD_ENABLED=1 para escucha continua"
Write-Host "    NOTA: wake word consume CPU+GPU 24/7. Recomendado: solo hotkey."
