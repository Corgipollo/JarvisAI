@echo off
REM ============================================================================
REM SOLO_ENTRENA.bat — Arranca lo MINIMO para que se entrene solo
REM ============================================================================
REM Sin watchdog, sin coach, sin telegram, sin dashboard.
REM Solo:
REM   1. claude_proxy (cerebro gratis :8088)
REM   2. self_improvement (procesa gaps.json, aprende skills)
REM   3. self_optimizer (re-aprende skills debiles)
REM
REM Uso: doble-click en este archivo.
REM ============================================================================

title Jarvis Entrenamiento

set JARVIS_DIR=C:\Jarvis
cd /d %JARVIS_DIR%

echo ============================================================================
echo                   JARVIS - SOLO ENTRENAMIENTO
echo ============================================================================
echo.

REM ----- Verificar Python -----
where python >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python no instalado. Corre START_JARVIS.bat primero.
    pause
    exit /b 1
)

REM ----- Verificar yt-dlp como modulo (no como exe) -----
echo Verificando yt-dlp module...
python -m yt_dlp --version
if errorlevel 1 (
    echo   Instalando yt-dlp...
    python -m pip install --quiet yt-dlp
)

REM ----- Matar procesos viejos colgados -----
echo Limpiando procesos viejos...
taskkill /F /IM python.exe 2>nul

REM ----- Wait 2 sec -----
timeout /t 2 /nobreak >nul

REM ----- Arrancar claude_proxy (CRITICO: cerebro gratis) -----
echo.
echo Arrancando claude_proxy en :8088...
start "Jarvis Proxy" /MIN cmd /c "cd /d %JARVIS_DIR% && python -m uvicorn jarvis_bridge.claude_proxy:app --host 127.0.0.1 --port 8088"
timeout /t 5 /nobreak >nul

REM ----- Health check del proxy -----
echo Verificando proxy...
curl -s -m 5 http://127.0.0.1:8088/health
if errorlevel 1 (
    echo   WARN: proxy aun no responde, continuando igual...
)

REM ----- Arrancar self_improvement (el que aprende) -----
echo.
echo Arrancando self_improvement loop...
start "Jarvis Self-Improvement" cmd /c "cd /d %JARVIS_DIR% && python jarvis_learners\self_improvement.py"
timeout /t 3 /nobreak >nul

REM ----- Arrancar self_optimizer (re-aprende skills debiles) -----
echo Arrancando self_optimizer loop...
start "Jarvis Self-Optimizer" /MIN cmd /c "cd /d %JARVIS_DIR% && python jarvis_learners\self_optimizer.py"

REM ----- Arrancar watchdog (AUTO-HEAL: detecta errores y los arregla solo via Claude) -----
echo Arrancando watchdog (auto-heal errores)...
start "Jarvis Watchdog" /MIN cmd /c "cd /d %JARVIS_DIR% && python jarvis_learners\watchdog.py"

REM ----- Arrancar dialog_killer NATIVO (pywinauto UI Automation, 50ms por dialog) -----
echo Instalando pywinauto si falta...
python -m pip install --quiet pywinauto 2>nul
echo Arrancando dialog_killer NATIVO (cierra dialogs Windows instantaneo)...
start "Jarvis Dialog Killer" /MIN cmd /c "cd /d %JARVIS_DIR% && python jarvis_swarm\dialog_killer_native.py"

REM ----- Arrancar dialog_guardian backup (Claude vision para casos raros) -----
echo Arrancando dialog_guardian (Claude vision backup)...
start "Jarvis Dialog Guardian" /MIN cmd /c "cd /d %JARVIS_DIR% && python jarvis_learners\dialog_guardian.py"

REM ----- Arrancar SWARM agents (21+ cerebros especializados) -----
echo Arrancando swarm core agents (6 cerebros)...
start "Mouse Master" /MIN cmd /c "cd /d %JARVIS_DIR% && python jarvis_swarm\agents_core.py mouse_master"
start "App Explorer" /MIN cmd /c "cd /d %JARVIS_DIR% && python jarvis_swarm\agents_core.py app_explorer"
start "Error Resolver" /MIN cmd /c "cd /d %JARVIS_DIR% && python jarvis_swarm\agents_core.py error_resolver"
start "Code Advisor" /MIN cmd /c "cd /d %JARVIS_DIR% && python jarvis_swarm\agents_core.py code_advisor"
start "Skill Reviewer" /MIN cmd /c "cd /d %JARVIS_DIR% && python jarvis_swarm\agents_core.py skill_reviewer"
start "Curiosity Agent" /MIN cmd /c "cd /d %JARVIS_DIR% && python jarvis_swarm\agents_core.py curiosity"

echo Arrancando META AGENT (auto-construye nuevos cerebros)...
start "META Agent" /MIN cmd /c "cd /d %JARVIS_DIR% && python jarvis_swarm\meta_agent.py"

echo.
echo ============================================================================
echo                   JARVIS ENTRENANDO. CIERRA ESTA VENTANA.
echo ============================================================================
echo.
echo Para ver progreso:
echo   - dir C:\Jarvis\data\skill_library
echo   - type C:\Jarvis\data\self_improvement.log
echo.
echo Self-improvement procesa gaps.json cada 10 min.
echo Cada skill tarda 10-20 min en aprenderse (download video + transcribir + analizar).
echo.
pause
