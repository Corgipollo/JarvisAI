@echo off
REM start_jarvis_v2.bat - Lanza todos los daemons de Jarvis v2 en paralelo

title Jarvis v2 - Orchestrator

set JARVIS_DIR=C:\Users\Emmanuel\Documents\JarvisAI
set PY=C:\CPython310\python.exe

cd /d %JARVIS_DIR%

echo ============================================================
echo           JARVIS v2 - LANZANDO DAEMONS
echo ============================================================
echo.

echo [1/3] Spend Governor (circuit breaker)...
start "JarvisGovernor" /MIN %PY% "%JARVIS_DIR%\jarvis_v2\cfo\spend_governor.py"
timeout /t 2 /nobreak >nul

echo [2/3] Heartbeat (boredom + autonomous ideation)...
start "JarvisHeartbeat" /MIN %PY% "%JARVIS_DIR%\jarvis_v2\heartbeat_daemon.py"
timeout /t 2 /nobreak >nul

echo [3/3] Voice Daemon (wake word + dispatch)...
start "JarvisVoice" %PY% "%JARVIS_DIR%\jarvis_v2\voice\voice_daemon.py"

echo.
echo ============================================================
echo Jarvis v2 corriendo. Cierra esta ventana cuando termines.
echo - Voice: di "jarvis" + comando
echo - Status: "dime como vas"
echo - Stop task: "cancela"
echo ============================================================
pause
