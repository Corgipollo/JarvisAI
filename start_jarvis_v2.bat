@echo off
REM ============================================================================
REM  START_JARVIS_V2.bat - Daemons v2 con env vars + sin pause (Scheduled Task)
REM ============================================================================
title Jarvis v2 - Orchestrator

set JARVIS_DIR=C:\Users\Emmanuel\Documents\JarvisAI
set PY=C:\CPython310\python.exe

REM Env vars v2 (cerebro + thresholds)
set JARVIS_LLM_PROVIDER=gemini_api
set GEMINI_API_KEY=AIzaSyB6yNdHWk_w2ht0YIGy1D7Q1uhpz3t34hQ
set JARVIS_LLM_FALLBACK=gemini_browser,ollama
set CFO_JUDGE_APPROVE_AT=0.4
set CFO_JUDGE_DENY_BELOW=0.3
set JARVIS_API_HOST=127.0.0.1
set JARVIS_API_PORT=5000
set JARVIS_API_TOKEN=jarvis_a8x29kfp3lz7m2qw9bdv
set OLLAMA_URL=http://localhost:11434
set OLLAMA_MODEL=llama3.2:latest
set JARVIS_SWARM_ENABLE=sentinel

cd /d %JARVIS_DIR%
if not exist data mkdir data

echo ============================================================
echo           JARVIS v2 - LANZANDO DAEMONS
echo ============================================================

echo [1/4] Spend Governor (circuit breaker)...
start "JarvisGovernor" /MIN %PY% -m jarvis_v2.cfo.spend_governor 1>data\governor.log 2>&1

echo [2/4] API FastAPI :5000 (recibe /execute)...
start "JarvisAPI" /MIN %PY% -m jarvis_v2.api.jarvis_api 1>data\api.log 2>&1

echo [3/4] Heartbeat (boredom + autonomous ideation)...
start "JarvisHeartbeat" /MIN %PY% -m jarvis_v2.heartbeat_daemon 1>data\heartbeat.log 2>&1

echo [4/4] Voice Daemon (wake word + dispatch)...
start "JarvisVoice" /MIN %PY% -m jarvis_v2.voice.voice_daemon 1>data\voice.log 2>&1

echo.
echo Jarvis v2 daemons lanzados en background.
echo Logs en %JARVIS_DIR%\data\*.log
exit /b 0
