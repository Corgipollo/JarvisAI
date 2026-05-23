# ntp_resync.ps1 - fuerza sync NTP. Previene clock drift que causa Binance -1021.
# Corre cada 6h via Task Scheduler.
$ErrorActionPreference = "SilentlyContinue"
$logFile = "C:\Users\Emmanuel\Documents\JarvisAI\data\ntp_resync.log"
$ts = (Get-Date).ToString("yyyy-MM-dd HH:mm:ss")

$result = & w32tm /resync /force 2>&1 | Out-String
Add-Content -Path $logFile -Value "[$ts] $($result.Trim())"
