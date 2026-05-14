@echo off
REM ============================================================================
REM MASTER_FIX.bat - Arregla TODO de forma definitiva
REM
REM User real: "Emmanuel Vega"
REM Password:  xdxd
REM ============================================================================

title Jarvis Master Fix
net session >nul 2>&1
if %errorLevel% NEQ 0 (
    powershell -Command "Start-Process '%~f0' -Verb RunAs"
    exit /b
)

echo ============================================================================
echo                  MASTER FIX - Jarvis VM
echo ============================================================================
echo.

REM -- 1. Quitar PowerToys (crashea constantemente) --
echo [1/8] Desinstalando PowerToys...
winget uninstall --id Microsoft.PowerToys --silent 2>nul
taskkill /F /IM PowerToys.exe 2>nul
taskkill /F /IM PowerToys.Awake.exe 2>nul
echo OK
echo.

REM -- 2. Quitar Discord autostart (roba foco siempre) --
echo [2/8] Quitando Discord autostart...
reg delete "HKCU\Software\Microsoft\Windows\CurrentVersion\Run" /v "Discord" /f >nul 2>&1
reg delete "HKLM\Software\Microsoft\Windows\CurrentVersion\Run" /v "Discord" /f >nul 2>&1
taskkill /F /IM Discord.exe 2>nul
echo OK
echo.

REM -- 3. Auto-logon con USER REAL --
echo [3/8] Auto-logon "Emmanuel Vega" + xdxd...
reg add "HKLM\Software\Microsoft\Windows NT\CurrentVersion\Winlogon" /v AutoAdminLogon /t REG_SZ /d 1 /f >nul
reg add "HKLM\Software\Microsoft\Windows NT\CurrentVersion\Winlogon" /v DefaultUserName /t REG_SZ /d "Emmanuel Vega" /f >nul
reg add "HKLM\Software\Microsoft\Windows NT\CurrentVersion\Winlogon" /v DefaultPassword /t REG_SZ /d "xdxd" /f >nul
reg add "HKLM\Software\Microsoft\Windows NT\CurrentVersion\Winlogon" /v DefaultDomainName /t REG_SZ /d "" /f >nul
reg add "HKLM\Software\Microsoft\Windows NT\CurrentVersion\Winlogon" /v ForceAutoLogon /t REG_SZ /d 1 /f >nul
echo OK
echo.

REM -- 4. Scheduled task con username CORRECTO --
echo [4/8] Scheduled tasks con Emmanuel Vega...
schtasks /delete /tn "JarvisAutoStart" /f >nul 2>&1
schtasks /delete /tn "JarvisHeartbeat" /f >nul 2>&1
schtasks /delete /tn "JarvisAtBoot" /f >nul 2>&1
schtasks /create /tn "JarvisAutoStart" /tr "cmd /c cd /d C:\Jarvis && SOLO_ENTRENA.bat" /sc onlogon /f >nul
schtasks /create /tn "JarvisHeartbeat" /tr "cmd /c tasklist | findstr python.exe >nul || (cd /d C:\Jarvis && SOLO_ENTRENA.bat)" /sc minute /mo 30 /f >nul
echo OK
echo.

REM -- 5. Layout ENG permanente --
echo [5/8] Layout teclado ENG permanente...
powershell -Command "Set-WinUserLanguageList -LanguageList en-US,es-MX -Force; Set-WinUILanguageOverride -Language en-US" 2>nul
echo OK
echo.

REM -- 6. Power nunca duerme --
echo [6/8] Power: nunca duerme...
powercfg /change monitor-timeout-ac 0
powercfg /change standby-timeout-ac 0
powercfg /change hibernate-timeout-ac 0
powercfg /h off 2>nul
echo OK
echo.

REM -- 7. No Windows Update con sesion activa --
echo [7/8] Desactivar reinicios forzados Windows Update...
reg add "HKLM\SOFTWARE\Policies\Microsoft\Windows\WindowsUpdate\AU" /v NoAutoRebootWithLoggedOnUsers /t REG_DWORD /d 1 /f >nul 2>&1
echo OK
echo.

REM -- 8. Lanzar Jarvis AHORA --
echo [8/8] Arrancando Jarvis...
cd /d C:\Jarvis
git stash 2>nul
git pull 2>&1 | findstr /v "warning:"
taskkill /F /IM python.exe 2>nul
timeout /t 2 /nobreak >nul
call SOLO_ENTRENA.bat
