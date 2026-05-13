@echo off
REM ============================================================================
REM AUTOSTART.bat - Hace que Jarvis VM nunca pare
REM
REM Configura:
REM   1. Auto-logon Windows con password "xdxd"
REM   2. Scheduled task que arranca SOLO_ENTRENA.bat al login
REM   3. Power: nunca duerme, nunca apaga
REM   4. Si Windows se reinicia (BSOD, update, etc), entra solo y arranca Jarvis
REM
REM Uso: doble click (o desde cmd admin: AUTOSTART.bat)
REM Ejecutar UNA SOLA VEZ.
REM ============================================================================

title Jarvis Autostart Setup

REM Verificar admin
net session >nul 2>&1
if %errorLevel% NEQ 0 (
    echo Necesita admin. Re-abriendo...
    powershell -Command "Start-Process '%~f0' -Verb RunAs"
    exit /b
)

echo ============================================================================
echo                  JARVIS AUTOSTART - SETUP DEFINITIVO
echo ============================================================================
echo.

REM ---- 1. Auto-logon Windows ----
echo [1/4] Auto-logon Windows (user: emman, pwd: xdxd)...
reg add "HKLM\Software\Microsoft\Windows NT\CurrentVersion\Winlogon" /v AutoAdminLogon /t REG_SZ /d 1 /f >nul
reg add "HKLM\Software\Microsoft\Windows NT\CurrentVersion\Winlogon" /v DefaultUserName /t REG_SZ /d emman /f >nul
reg add "HKLM\Software\Microsoft\Windows NT\CurrentVersion\Winlogon" /v DefaultPassword /t REG_SZ /d xdxd /f >nul
reg add "HKLM\Software\Microsoft\Windows NT\CurrentVersion\Winlogon" /v DefaultDomainName /t REG_SZ /d "" /f >nul
REM Quitar requerimiento de credenciales en reinicio
reg add "HKLM\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Winlogon" /v ForceAutoLogon /t REG_SZ /d 1 /f >nul
echo    OK
echo.

REM ---- 2. Power: nunca dormir ----
echo [2/4] Power: nunca duerme...
powercfg /change monitor-timeout-ac 0
powercfg /change standby-timeout-ac 0
powercfg /change disk-timeout-ac 0
powercfg /change hibernate-timeout-ac 0
powercfg /h off
echo    OK
echo.

REM ---- 3. Scheduled task: arrancar Jarvis al login ----
echo [3/4] Scheduled task JarvisAutoStart...
schtasks /delete /tn "JarvisAutoStart" /f >nul 2>&1
schtasks /create /tn "JarvisAutoStart" ^
    /tr "cmd /c \"cd /d C:\Jarvis && SOLO_ENTRENA.bat\"" ^
    /sc onlogon /ru emman /rl highest /f >nul

REM Backup task: arranca tambien al boot (sin login) por si auto-logon falla
schtasks /delete /tn "JarvisAtBoot" /f >nul 2>&1
schtasks /create /tn "JarvisAtBoot" ^
    /tr "cmd /c \"cd /d C:\Jarvis && SOLO_ENTRENA.bat\"" ^
    /sc onstart /ru SYSTEM /rl highest /f >nul

REM Otro backup: cada 30 min revisa si Jarvis corre, si no, lo lanza
schtasks /delete /tn "JarvisHeartbeat" /f >nul 2>&1
schtasks /create /tn "JarvisHeartbeat" ^
    /tr "cmd /c \"tasklist | findstr python.exe >nul || (cd /d C:\Jarvis && SOLO_ENTRENA.bat)\"" ^
    /sc minute /mo 30 /ru emman /rl highest /f >nul
echo    OK - tareas: JarvisAutoStart (login), JarvisAtBoot (boot), JarvisHeartbeat (cada 30min)
echo.

REM ---- 4. Disable update auto-restart si es posible ----
echo [4/4] Desactivar reinicios forzados de Windows Update...
reg add "HKLM\SOFTWARE\Policies\Microsoft\Windows\WindowsUpdate\AU" /v NoAutoRebootWithLoggedOnUsers /t REG_DWORD /d 1 /f >nul 2>&1
echo    OK
echo.

echo ============================================================================
echo                  SETUP COMPLETO
echo ============================================================================
echo.
echo Lo que va a pasar:
echo   - Si reinicia Windows: entra solo con emman/xdxd
echo   - Al entrar al desktop, JarvisAutoStart arranca SOLO_ENTRENA.bat
echo   - Si SOLO_ENTRENA muere, JarvisHeartbeat lo relanza en max 30 min
echo   - Si Windows Update reinicia: no fuerza con sesion activa
echo   - VM nunca se duerme (monitor/standby/disk/hibernate todo en 0)
echo.
echo Test: cierra sesion (Win+L) y entra de nuevo. Debe arrancar Jarvis solo.
echo.
pause
