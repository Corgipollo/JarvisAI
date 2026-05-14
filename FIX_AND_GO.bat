@echo off
REM ============================================================================
REM FIX_AND_GO.bat - Repara git roto + cierra PowerToys + relanza Jarvis
REM
REM Si git esta roto (cannot spawn git-remote-https), reinstala Git for Windows.
REM Mata el dialog molesto de PowerToys.Awake.
REM git pull para traer ultimo codigo (incluye dialog_guardian).
REM Relanza SOLO_ENTRENA.
REM ============================================================================

title Jarvis - Fix and Go

echo ============================================================================
echo                  REPARANDO + RELANZANDO JARVIS
echo ============================================================================
echo.

REM 1. Matar PowerToys (el dialog)
echo [1/5] Matando PowerToys (dialog molesto)...
taskkill /F /IM PowerToys.exe 2>nul
taskkill /F /IM PowerToys.Awake.exe 2>nul
taskkill /F /IM PowerToys.AwakeProcess.exe 2>nul
echo OK
echo.

REM 2. Desinstalar PowerToys (no nos sirve y crashea)
echo [2/5] Desinstalando PowerToys (siempre crashea)...
winget uninstall --id Microsoft.PowerToys --silent 2>nul
echo OK
echo.

REM 3. Reinstalar Git (puede estar roto)
echo [3/5] Reparando Git for Windows...
winget install Git.Git --silent --force --accept-package-agreements --accept-source-agreements
echo OK
echo.

REM 4. git pull para traer dialog_guardian.py
echo [4/5] git pull en Jarvis...
cd /d C:\Jarvis
git stash 2>nul
git pull 2>&1
echo.

REM 5. Relanzar SOLO_ENTRENA
echo [5/5] Relanzando Jarvis con dialog_guardian...
taskkill /F /IM python.exe 2>nul
timeout /t 2 /nobreak >nul
call SOLO_ENTRENA.bat
