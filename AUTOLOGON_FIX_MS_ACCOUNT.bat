@echo off
REM ============================================================================
REM AUTOLOGON_FIX_MS_ACCOUNT.bat - Auto-logon para Windows con cuenta Microsoft + PIN
REM
REM Windows 11 con cuenta Microsoft + PIN NO auto-login con metodo clasico
REM (DefaultPassword en registry). Necesita DOS cosas:
REM
REM 1. Disable "Require sign-in" en netplwiz (Users must enter username and pwd)
REM 2. Usar Sysinternals Autologon.exe (oficial, maneja MS accounts)
REM
REM Uso: ejecutar como ADMIN. Mete tu password de cuenta MS (no PIN).
REM ============================================================================

title Jarvis Autologon Fix MS Account

net session >nul 2>&1
if %errorLevel% NEQ 0 (
    powershell -Command "Start-Process '%~f0' -Verb RunAs"
    exit /b
)

echo ============================================================================
echo                  AUTO-LOGON FIX para cuenta Microsoft
echo ============================================================================
echo.

REM ----- Quitar el "require password on wakeup" -----
echo [1/4] Quitando requerimiento password al despertar...
reg add "HKLM\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Winlogon" /v PasswordExpiryWarning /t REG_DWORD /d 0 /f >nul
powercfg /SETACVALUEINDEX SCHEME_CURRENT SUB_NONE CONSOLELOCK 0 2>nul
powercfg /SETDCVALUEINDEX SCHEME_CURRENT SUB_NONE CONSOLELOCK 0 2>nul
echo OK
echo.

REM ----- Disable lockscreen y require sign-in -----
echo [2/4] Disable lock screen y sign-in requirement...
reg add "HKLM\SOFTWARE\Policies\Microsoft\Windows\Personalization" /v NoLockScreen /t REG_DWORD /d 1 /f >nul
reg add "HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\Authentication\LogonUI\UserSwitch" /v Enabled /t REG_DWORD /d 1 /f >nul
echo OK
echo.

REM ----- Descargar Sysinternals Autologon (oficial Microsoft) -----
echo [3/4] Descargando Sysinternals Autologon...
set ALDIR=C:\Jarvis\autologon
if not exist %ALDIR% mkdir %ALDIR%
cd /d %ALDIR%

if not exist Autologon64.exe (
    powershell -Command "Invoke-WebRequest -Uri 'https://download.sysinternals.com/files/AutoLogon.zip' -OutFile 'AutoLogon.zip'" 2>&1
    powershell -Command "Expand-Archive -Force AutoLogon.zip -DestinationPath ."
)

if exist Autologon64.exe (
    echo OK
) else (
    echo ERROR: no pude descargar Autologon. Intenta manual desde
    echo https://learn.microsoft.com/en-us/sysinternals/downloads/autologon
)
echo.

REM ----- Configurar autologon con cuenta Microsoft -----
echo [4/4] Configurando autologon...
echo.
echo INSTRUCCION: el siguiente programa va a pedir credenciales.
echo Pon:
echo   Username:  Emmanuel Vega   (o tu email MS si Windows lo pide)
echo   Password:  xdxd            (NO el PIN, el password REAL de la cuenta MS)
echo   Domain:    (dejar vacio)
echo.
echo Presiona una tecla para abrirlo...
pause >nul

if exist Autologon64.exe (
    Autologon64.exe /AcceptEula
)

echo.
echo ============================================================================
echo  Despues de configurar, REINICIA y vera si funciona auto-logon.
echo  Si NO funciona con xdxd, prueba con tu password completa de la cuenta MS
echo  (la que usas en login.microsoft.com)
echo ============================================================================
echo.
pause
