# brave_inject_cdp.ps1 - Inyecta --remote-debugging-port=9222 en TODOS los shortcuts de Brave
# Idempotente: si ya tiene el flag, no duplica.
$ErrorActionPreference = "Continue"
$CDP_FLAG = "--remote-debugging-port=9222"

Write-Output "=== Brave CDP injector $(Get-Date -Format 'HH:mm:ss') ==="

# Localizaciones tipicas de shortcuts Brave
$shortcutPaths = @(
    "$env:USERPROFILE\Desktop\*Brave*.lnk",
    "$env:PUBLIC\Desktop\*Brave*.lnk",
    "$env:APPDATA\Microsoft\Windows\Start Menu\Programs\*Brave*.lnk",
    "$env:PROGRAMDATA\Microsoft\Windows\Start Menu\Programs\*Brave*.lnk",
    "$env:APPDATA\Microsoft\Internet Explorer\Quick Launch\User Pinned\TaskBar\*Brave*.lnk",
    "$env:APPDATA\Microsoft\Internet Explorer\Quick Launch\User Pinned\TaskBar\TaskBar\*Brave*.lnk"
)

$wsh = New-Object -ComObject WScript.Shell
$modified = 0
$alreadyOk = 0

foreach ($pattern in $shortcutPaths) {
    Get-ChildItem $pattern -ErrorAction SilentlyContinue | ForEach-Object {
        $lnkPath = $_.FullName
        try {
            $sc = $wsh.CreateShortcut($lnkPath)
            $args = $sc.Arguments
            if ($args -match [regex]::Escape($CDP_FLAG)) {
                Write-Output "  [SKIP] ya tiene CDP: $lnkPath"
                $alreadyOk += 1
            } else {
                $newArgs = if ($args) { "$args $CDP_FLAG" } else { $CDP_FLAG }
                $sc.Arguments = $newArgs
                $sc.Save()
                Write-Output "  [PATCH] $lnkPath -> args='$newArgs'"
                $modified += 1
            }
        } catch {
            Write-Output "  [ERR] $lnkPath - $($_.Exception.Message)"
        }
    }
}

Write-Output ""
Write-Output "Resumen: $modified shortcuts modificados, $alreadyOk ya tenian CDP"

# Kill Brave existente
$braveProcs = Get-Process -Name "brave" -ErrorAction SilentlyContinue
if ($braveProcs) {
    Write-Output "Cerrando $($braveProcs.Count) procesos de Brave..."
    $braveProcs | Stop-Process -Force -ErrorAction SilentlyContinue
    Start-Sleep 3
} else {
    Write-Output "Brave no esta corriendo, OK."
}

# Re-abrir usando uno de los shortcuts modificados (toma el primero del Desktop)
$relaunch = Get-ChildItem "$env:USERPROFILE\Desktop\*Brave*.lnk" -ErrorAction SilentlyContinue | Select-Object -First 1
if (-not $relaunch) {
    $relaunch = Get-ChildItem "$env:APPDATA\Microsoft\Windows\Start Menu\Programs\*Brave*.lnk" -ErrorAction SilentlyContinue | Select-Object -First 1
}
if ($relaunch) {
    Write-Output "Re-lanzando Brave: $($relaunch.FullName)"
    Start-Process -FilePath $relaunch.FullName
    Start-Sleep 5
} else {
    # Fallback: directo al exe
    $exe = "$env:PROGRAMFILES\BraveSoftware\Brave-Browser\Application\brave.exe"
    if (Test-Path $exe) {
        Write-Output "Re-lanzando Brave directo: $exe $CDP_FLAG"
        Start-Process -FilePath $exe -ArgumentList $CDP_FLAG
        Start-Sleep 5
    } else {
        Write-Output "WARN: no encontre brave.exe"
    }
}

# Verificar puerto 9222 listening
Start-Sleep 3
$cdp = Get-NetTCPConnection -LocalPort 9222 -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1
if ($cdp) {
    Write-Output "OK: CDP listening on :9222 (PID $($cdp.OwningProcess))"
} else {
    Write-Output "FAIL: nada en :9222 todavia. Espera 5s mas y revisa con: Get-NetTCPConnection -LocalPort 9222"
}

Write-Output "=== DONE ==="
