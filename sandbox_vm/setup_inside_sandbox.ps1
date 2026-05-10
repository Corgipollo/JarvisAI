#
# setup_inside_sandbox.ps1 — Bootstrap completo + training loop infinito.
#
# Pedido por Emmanuel 2026-05-09:
#   "que nunca pare de entrenar hasta que pueda hacer todo super rapido y
#    bien hecho como una persona"
#
# Flujo:
#   1. Bootstrap Python embeddable
#   2. Instalar deps Python
#   3. Instalar apps reales via winget (Chrome, Spotify, Telegram, Discord,
#      VSCode, Obsidian, Brave) — opcion B del user
#   4. Loop INFINITO: trainer cada 3 minutos, persistiendo learnings al
#      JarvisAI mapeado (ReadOnly=false en .wsb)
#

$ErrorActionPreference = "Continue"
$LOG = "C:\jarvis_sandbox.log"

function Log($msg) {
    $line = "[$(Get-Date -Format 'HH:mm:ss')] $msg"
    Write-Host $line -ForegroundColor Cyan
    Add-Content -Path $LOG -Value $line
}

Log "=== Jarvis Sandbox Boot (training loop infinito) ==="

# Paths
$JARVIS_HOST = "C:\Users\WDAGUtilityAccount\Desktop\JarvisAI"  # mapeado read-write
$PYTHON_DIR = "C:\python"
$PYTHON_EXE = "$PYTHON_DIR\python.exe"

# ============================================================================
# 1. Bootstrap Python embeddable
# ============================================================================
if (-not (Test-Path $PYTHON_EXE)) {
    Log "Descargando Python 3.12 embeddable..."
    $PythonZip = "C:\python_embed.zip"
    $PythonUrl = "https://www.python.org/ftp/python/3.12.7/python-3.12.7-embed-amd64.zip"
    try {
        Invoke-WebRequest -Uri $PythonUrl -OutFile $PythonZip -UseBasicParsing
        Expand-Archive -Path $PythonZip -DestinationPath $PYTHON_DIR -Force
        Log "Python extraido en $PYTHON_DIR"

        # Habilitar import site-packages
        $pthFile = Get-ChildItem "$PYTHON_DIR\python*._pth" | Select-Object -First 1
        if ($pthFile) {
            (Get-Content $pthFile.FullName) -replace '^#import site', 'import site' |
                Set-Content $pthFile.FullName
        }

        # Bootstrap pip
        Log "Bootstrap pip..."
        Invoke-WebRequest -Uri "https://bootstrap.pypa.io/get-pip.py" -OutFile "C:\get-pip.py" -UseBasicParsing
        & $PYTHON_EXE "C:\get-pip.py" --no-warn-script-location | Out-Null
        Log "pip OK."
    } catch {
        Log "ERROR descarga Python: $_"
        return
    }
} else {
    Log "Python ya existe en $PYTHON_DIR"
}

# ============================================================================
# 2. Instalar dependencias Python
# ============================================================================
Log "Instalando deps Python..."
$Deps = @("pyautogui", "psutil", "pygetwindow", "pyyaml", "pywin32", "requests")
foreach ($dep in $Deps) {
    & $PYTHON_EXE -m pip install --no-warn-script-location --quiet $dep 2>&1 | Out-Null
}
Log "Deps Python instaladas."

# ============================================================================
# 3. Instalar apps reales via winget (opcion B)
# ============================================================================
Log "=== Instalando apps reales via winget ==="

# Verificar winget
$wingetPath = (Get-Command winget -ErrorAction SilentlyContinue).Path
if (-not $wingetPath) {
    Log "winget no detectado. Saltando instalacion de apps. (Tasks built-in seguiran funcionando)"
} else {
    Log "winget encontrado: $wingetPath"

    # Apps a instalar — silent + accept terms
    $AppsToInstall = @(
        @{Id="Google.Chrome"; Name="Chrome"},
        @{Id="Spotify.Spotify"; Name="Spotify"},
        @{Id="Telegram.TelegramDesktop"; Name="Telegram"},
        @{Id="Discord.Discord"; Name="Discord"},
        @{Id="Microsoft.VisualStudioCode"; Name="VSCode"},
        @{Id="Obsidian.Obsidian"; Name="Obsidian"},
        @{Id="Brave.Brave"; Name="Brave"}
    )

    foreach ($app in $AppsToInstall) {
        Log "Instalando $($app.Name)..."
        try {
            & winget install --id $app.Id --silent --accept-package-agreements --accept-source-agreements --disable-interactivity 2>&1 | Out-Null
            Log "  $($app.Name): OK"
        } catch {
            Log "  $($app.Name): fallo ($_)"
        }
    }
    Log "=== Instalacion apps completada ==="
}

# ============================================================================
# 4. Pre-scan Windows: el trainer necesita el inventory
# ============================================================================
Log "Generando inventory inicial de Windows..."
Set-Location $JARVIS_HOST
& $PYTHON_EXE "$JARVIS_HOST\backend\integrations\windows_intel.py" all 2>&1 |
    Select-Object -Last 10 | ForEach-Object { Log "  $_" }

# ============================================================================
# 5. LOOP INFINITO de training — nunca para
# ============================================================================
Log ""
Log "=================================================="
Log "  TRAINING LOOP INFINITO — cada 3 minutos"
Log "  No se detiene hasta que cierres la sandbox"
Log "=================================================="
Log ""

$env:PYTHONPATH = $JARVIS_HOST
$env:JARVIS_SANDBOX = "0"  # estamos en VM aislada — no necesitamos modo software-sandbox

$IterationLog = "$JARVIS_HOST\data\jarvis_iterations.log"
$Iteration = 0

while ($true) {
    $Iteration++
    $StartTime = Get-Date
    Log ""
    Log "================ ITERACION #$Iteration ================"

    try {
        & $PYTHON_EXE "$JARVIS_HOST\jarvis_trainer\trainer.py" 2>&1 |
            ForEach-Object { Log "  $_" }
    } catch {
        Log "ERROR iteracion #${Iteration}: $_"
    }

    $Elapsed = ((Get-Date) - $StartTime).TotalSeconds
    Log "Iteracion #$Iteration termino en $([math]::Round($Elapsed, 1))s"
    Log "Esperando 3 minutos para siguiente iteracion..."
    Start-Sleep -Seconds 180
}
