@echo off
REM ============================================================================
REM  START_JARVIS_FULL.bat - Stack completo autonomo (cerebro + swarm + loop)
REM  Para hostsin VM: aprovecha gemma3:12b local + 10GB RAM disponibles
REM ============================================================================
title Jarvis FULL - cerebro + mouse + video + loop

set JARVIS_DIR=C:\Users\Emmanuel\Documents\JarvisAI
set PY=C:\CPython310\python.exe

REM Cerebro local 100% (sin keys, sin internet)
set JARVIS_LLM_PROVIDER=ollama
set OLLAMA_MODEL=gemma3:12b
set JARVIS_LLM_FALLBACK=gemini_api,gemini_browser
if exist "%JARVIS_DIR%\.env" (for /f "usebackq tokens=*" %%i in ("%JARVIS_DIR%\.env") do set %%i)

REM CFO mas permisivo para acciones autonomas (siempre con gates de seguridad)
set CFO_JUDGE_APPROVE_AT=0.4
set CFO_JUDGE_DENY_BELOW=0.2

REM API server
set JARVIS_API_HOST=127.0.0.1
set JARVIS_API_PORT=5000
set JARVIS_API_TOKEN=jarvis_a8x29kfp3lz7m2qw9bdv

REM Swarm completo: sentinel (vigia) + secretary (mouse social) + creative (video)
set JARVIS_SWARM_ENABLE=sentinel,secretary,creative

REM Heartbeat: cada 2h de idle dispara ideation autonoma
set JARVIS_BOREDOM_HOURS=2

cd /d %JARVIS_DIR%
if not exist data mkdir data

echo ============================================================
echo   JARVIS FULL - lanzando 4 daemons + swarm
echo ============================================================

echo [1/4] Spend Governor (circuit breaker financiero)...
start "JarvisGovernor" /MIN %PY% -m jarvis_v2.cfo.spend_governor 1>data\governor.log 2>&1

echo [2/4] API FastAPI :5000 (recibe /execute)...
start "JarvisAPI" /MIN %PY% -m jarvis_v2.api.jarvis_api 1>data\api.log 2>&1

echo [3/4] Heartbeat (boredom -> ideation autonoma cada 2h)...
start "JarvisHeartbeat" /MIN %PY% -m jarvis_v2.heartbeat_daemon 1>data\heartbeat.log 2>&1

echo [4/4] Swarm Orchestrator (secretary mouse + creative video + sentinel)...
start "JarvisSwarm" /MIN %PY% -m jarvis_v2.swarm.orchestrator 1>data\swarm.log 2>&1

REM Bridge Telegram (opcional, solo si TELEGRAM_BOT_TOKEN seteado)
if defined TELEGRAM_BOT_TOKEN (
    echo [5/5] Telegram C2 bridge...
    start "JarvisTelegram" /MIN %PY% -m jarvis_v2.bridges.telegram_jarvis 1>data\telegram.log 2>&1
)

echo.
echo Jarvis FULL corriendo. Logs en %JARVIS_DIR%\data\*.log
echo   - api.log         (FastAPI requests)
echo   - heartbeat.log   (boredom + ideation autonoma)
echo   - swarm.log       (3 workers: sentinel + secretary + creative)
echo   - governor.log    (CFO circuit breaker)
echo.
exit /b 0
