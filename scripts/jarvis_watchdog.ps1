# jarvis_watchdog.ps1 - relanza daemons API + worker si estan muertos.
# Corre cada 5 min via Task Scheduler. Idempotente: no spawna duplicados.
$ErrorActionPreference = "SilentlyContinue"
$Root = "C:\Users\Emmanuel\Documents\JarvisAI"
$Python = "C:\CPython310\python.exe"

function Is-Running($pattern) {
    $procs = Get-CimInstance Win32_Process -Filter "Name='python.exe'" |
        Where-Object { $_.CommandLine -match $pattern }
    return ($procs | Measure-Object).Count -gt 0
}

function Start-Daemon($module, $logname) {
    Start-Process -FilePath $Python `
        -ArgumentList '-m', $module `
        -WorkingDirectory $Root `
        -RedirectStandardOutput "$Root\data\$logname.log" `
        -RedirectStandardError  "$Root\data\$logname.err" `
        -WindowStyle Hidden
}

$logFile = "$Root\data\watchdog.log"
$ts = (Get-Date).ToString("yyyy-MM-dd HH:mm:ss")

if (-not (Is-Running 'jarvis_v2\.api\.jarvis_api')) {
    Start-Daemon 'jarvis_v2.api.jarvis_api' 'api'
    Add-Content -Path $logFile -Value "[$ts] restarted API"
    Start-Sleep -Seconds 5
}

if (-not (Is-Running 'jarvis_v2\.task_worker')) {
    Start-Daemon 'jarvis_v2.task_worker' 'task_worker'
    Add-Content -Path $logFile -Value "[$ts] restarted worker"
}

# Health probe (silencioso si OK)
try {
    $h = Invoke-RestMethod 'http://127.0.0.1:5000/health' -TimeoutSec 3
    if (-not $h.ok) {
        Add-Content -Path $logFile -Value "[$ts] health NOT_OK"
    }
} catch {
    Add-Content -Path $logFile -Value "[$ts] health probe failed: $_"
}
