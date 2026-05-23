# install_researcher.ps1 - Registra Jarvis_AutoResearch en Task Scheduler.
# Cada 12 horas ejecuta auto_researcher.py con privilegios altos.
# Idempotente: /F sobreescribe si ya existe.

$ErrorActionPreference = "Stop"

$taskName = "Jarvis_AutoResearch"
$python = "C:\CPython310\python.exe"
$script = "C:\Users\Emmanuel\Documents\JarvisAI\jarvis_v2\daemons\auto_researcher.py"

if (-not (Test-Path $python)) {
    Write-Error "Python no encontrado en $python"
    exit 1
}
if (-not (Test-Path $script)) {
    Write-Error "Script no encontrado en $script"
    exit 1
}

$action = "$python `"$script`""
$result = schtasks /Create /TN $taskName /TR $action /SC HOURLY /MO 12 /F /RL HIGHEST 2>&1

Write-Output $result
Write-Output ""
Write-Output "=== Verificacion ==="
schtasks /Query /TN $taskName /FO LIST 2>&1 | Select-Object -First 8
