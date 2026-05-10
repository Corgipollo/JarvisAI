#
# setup_inside_sandbox.ps1
#
# Se ejecuta DENTRO de la Windows Sandbox al arrancar (LogonCommand del .wsb).
#
# Tareas:
#   1. Bootstraps Python embeddable (no requiere admin, ~12 MB descarga)
#   2. Instala pip + dependencias minimas (faster-whisper NO, solo lo del trainer)
#   3. Copia JarvisAI mapeado (read-only) a una carpeta writable
#   4. Corre el trainer en modo REAL (estamos aislados, ya no necesitamos sandbox flag)
#   5. Loguea todo a C:\jarvis_sandbox.log
#

$ErrorActionPreference = "Continue"
$LOG = "C:\jarvis_sandbox.log"

function Log($msg) {
    $line = "[$(Get-Date -Format 'HH:mm:ss')] $msg"
    Write-Host $line -ForegroundColor Cyan
    Add-Content -Path $LOG -Value $line
}

Log "=== Jarvis Sandbox Boot ==="
Log "Hostname: $env:COMPUTERNAME"
Log "User: $env:USERNAME"

# Paths dentro de la sandbox
$JARVIS_RO = "C:\Users\WDAGUtilityAccount\Desktop\JarvisAI"
$JARVIS_RW = "C:\JarvisAI"
$PYTHON_DIR = "C:\python"
$PYTHON_EXE = "$PYTHON_DIR\python.exe"

# 1. Copiar JarvisAI a carpeta writable (la mapeada es read-only)
Log "Copiando JarvisAI a $JARVIS_RW (writable)..."
if (-not (Test-Path $JARVIS_RW)) {
    New-Item -ItemType Directory -Path $JARVIS_RW -Force | Out-Null
}
Copy-Item -Path "$JARVIS_RO\*" -Destination $JARVIS_RW -Recurse -Force -ErrorAction SilentlyContinue
Log "Copiado OK."

# 2. Bootstrap Python embeddable
if (-not (Test-Path $PYTHON_EXE)) {
    Log "Descargando Python 3.12 embeddable..."
    $PythonZip = "C:\python_embed.zip"
    $PythonUrl = "https://www.python.org/ftp/python/3.12.7/python-3.12.7-embed-amd64.zip"
    try {
        Invoke-WebRequest -Uri $PythonUrl -OutFile $PythonZip -UseBasicParsing
        Expand-Archive -Path $PythonZip -DestinationPath $PYTHON_DIR -Force
        Log "Python extraido en $PYTHON_DIR"

        # Habilitar import de site-packages en embeddable
        $pthFile = Get-ChildItem "$PYTHON_DIR\python*._pth" | Select-Object -First 1
        if ($pthFile) {
            (Get-Content $pthFile.FullName) -replace '^#import site', 'import site' |
                Set-Content $pthFile.FullName
            Log "_pth file ajustado."
        }

        # Bootstrap pip
        Log "Bootstrap pip..."
        Invoke-WebRequest -Uri "https://bootstrap.pypa.io/get-pip.py" -OutFile "C:\get-pip.py" -UseBasicParsing
        & $PYTHON_EXE "C:\get-pip.py" --no-warn-script-location
        Log "pip OK."
    } catch {
        Log "ERROR descarga Python: $_"
        Write-Host "FALLO descarga Python. Revisa conexion. Saliendo." -ForegroundColor Red
        return
    }
} else {
    Log "Python ya existe en $PYTHON_DIR"
}

# 3. Instalar dependencias del trainer
Log "Instalando dependencias..."
$Deps = @(
    "pyautogui",
    "psutil",
    "pygetwindow",
    "pyyaml",
    "pywin32",
    "requests"
)
foreach ($dep in $Deps) {
    & $PYTHON_EXE -m pip install --no-warn-script-location --quiet $dep 2>&1 | Out-Null
    Log "  instalado: $dep"
}

# 4. Variables de entorno
$env:PYTHONPATH = $JARVIS_RW
$env:JARVIS_SANDBOX = "0"  # estamos en VM real, no necesitamos modo sandbox software

# 5. Correr trainer en loop infinito cada 5 min (mientras la sandbox este viva)
Log "=== Iniciando training loop (cada 5 min) ==="
Set-Location $JARVIS_RW

$IterationLog = "C:\jarvis_iterations.log"
$Iteration = 0

while ($true) {
    $Iteration++
    Log "--- Iteracion #$Iteration ---"
    try {
        & $PYTHON_EXE "$JARVIS_RW\jarvis_trainer\trainer.py" 2>&1 |
            Tee-Object -FilePath $IterationLog -Append
        Log "Iteracion #$Iteration completada."
    } catch {
        Log "Error en iteracion #${Iteration}: $_"
    }

    Log "Esperando 5 minutos para siguiente iteracion..."
    Start-Sleep -Seconds 300
}
