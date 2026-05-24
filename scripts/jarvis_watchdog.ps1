# jarvis_watchdog.ps1 - reanima TODOS los daemons criticos si estan muertos.
# Corre cada 5 min via schtask Jarvis_Watchdog. Idempotente: no spawna duplicados.
#
# v2 (2026-05-23): expandido tras descubrir que proxy_fast / infinite_ceo /
# tunnel no estaban siendo monitoreados. Ahora cubre los 5 daemons criticos.

$ErrorActionPreference = "SilentlyContinue"
$Root = "C:\Users\Emmanuel\Documents\JarvisAI"
$Python = "C:\CPython310\python.exe"
$Cloudflared = "$Root\scripts\cloudflared.exe"

function Is-PythonRunning($pattern) {
    $procs = Get-CimInstance Win32_Process -Filter "Name='python.exe'" |
        Where-Object { $_.CommandLine -match $pattern }
    return ($procs | Measure-Object).Count -gt 0
}

function Is-ProcessRunning($name) {
    $procs = Get-CimInstance Win32_Process -Filter "Name='$name'"
    return ($procs | Measure-Object).Count -gt 0
}

function Start-PythonDaemon($module, $logname) {
    Start-Process -FilePath $Python `
        -ArgumentList '-m', $module `
        -WorkingDirectory $Root `
        -RedirectStandardOutput "$Root\data\$logname.log" `
        -RedirectStandardError  "$Root\data\$logname.err" `
        -WindowStyle Hidden
}

$logFile = "$Root\data\watchdog.log"
$ts = (Get-Date).ToString("yyyy-MM-dd HH:mm:ss")

# DAEMON 1: claude_proxy_fast (brain OAuth $0) - critico, sin esto todo LLM call falla
if (-not (Is-PythonRunning 'jarvis_bridge\.claude_proxy_fast')) {
    Start-PythonDaemon 'jarvis_bridge.claude_proxy_fast' 'proxy_fast'
    Add-Content -Path $logFile -Value "[$ts] restarted claude_proxy_fast"
    Start-Sleep -Seconds 5
}

# DAEMON 2: API
if (-not (Is-PythonRunning 'jarvis_v2\.api\.jarvis_api')) {
    Start-PythonDaemon 'jarvis_v2.api.jarvis_api' 'api'
    Add-Content -Path $logFile -Value "[$ts] restarted API"
    Start-Sleep -Seconds 5
}

# DAEMON 3: task_worker (procesa cola)
if (-not (Is-PythonRunning 'jarvis_v2\.task_worker')) {
    Start-PythonDaemon 'jarvis_v2.task_worker' 'task_worker'
    Add-Content -Path $logFile -Value "[$ts] restarted task_worker"
}

# DAEMON 4: infinite_ceo (auto-genera objetivos)
if (-not (Is-PythonRunning 'jarvis_v2\.daemons\.infinite_ceo')) {
    Start-PythonDaemon 'jarvis_v2.daemons.infinite_ceo' 'infinite_ceo'
    Add-Content -Path $logFile -Value "[$ts] restarted infinite_ceo"
}

# DAEMON 5: cloudflared tunnel (URL publica)
if (-not (Is-ProcessRunning 'cloudflared.exe')) {
    Start-Process -FilePath $Cloudflared `
        -ArgumentList @('tunnel', '--url', 'http://localhost:5000', '--http2-origin') `
        -RedirectStandardOutput "$Root\data\cloudflared.log" `
        -RedirectStandardError "$Root\data\cloudflared.err" `
        -WindowStyle Hidden
    Add-Content -Path $logFile -Value "[$ts] restarted cloudflared tunnel"
}

# DAEMON 6: localtunnel (URL fija jarvis-emmanuel.loca.lt)
if (-not (Is-ProcessRunning 'node.exe')) {
    # Buscar especificamente lt
    $ltRunning = Get-CimInstance Win32_Process -Filter "Name='node.exe'" |
        Where-Object { $_.CommandLine -match 'localtunnel|lt\.js' }
    if (-not $ltRunning) {
        Start-Process -FilePath 'cmd.exe' `
            -ArgumentList @('/c', "lt --port 5000 --subdomain jarvis-emmanuel > `"$Root\data\localtunnel.log`" 2>&1") `
            -WindowStyle Hidden
        Add-Content -Path $logFile -Value "[$ts] restarted localtunnel"
    }
}

# Health probe API
try {
    $h = Invoke-RestMethod 'http://127.0.0.1:5000/health' -TimeoutSec 3
    if (-not $h.ok) {
        Add-Content -Path $logFile -Value "[$ts] health NOT_OK"
    }
} catch {
    Add-Content -Path $logFile -Value "[$ts] health probe failed: $_"
}

# Health probe proxy OAuth (silencioso si OK)
try {
    $p = Invoke-RestMethod 'http://127.0.0.1:8088/health' -TimeoutSec 3
} catch {
    Add-Content -Path $logFile -Value "[$ts] proxy_fast health failed: $_"
}
