@echo off
REM ============================================================================
REM  START_JARVIS.bat — Un solo click adentro de la VM y todo arranca
REM ============================================================================
REM  Uso: doble click en este archivo (ya copiado a C:\Jarvis o desde shared
REM       folder \\VBoxSvr\JarvisAI\)
REM
REM  Hace:
REM    1. Instala Python/Node/Git/Tesseract si no estan (winget)
REM    2. Clona/actualiza el repo Jarvis
REM    3. Instala dependencias Python
REM    4. Instala Claude CLI (npm) + Playwright Chromium
REM    5. Copia el SUPER_PROMPT al clipboard
REM    6. Arranca los 4 servicios en background:
REM       - claude_proxy :8088
REM       - web_server   :7777
REM       - self_improvement loop
REM       - coach loop
REM    7. Abre el dashboard en browser
REM    8. Sigue ejecutando lo que el coach decida
REM ============================================================================

setlocal enabledelayedexpansion
title Jarvis Auto-Setup
color 0B

echo.
echo ============================================================================
echo                  JARVIS AUTO-SETUP — un solo paso
echo ============================================================================
echo.

REM ----- Verificar admin -----
net session >nul 2>&1
if %errorLevel% NEQ 0 (
    echo Este script necesita PERMISOS DE ADMIN para instalar dependencias.
    echo Re-abriendo como admin...
    powershell -Command "Start-Process '%~f0' -Verb RunAs"
    exit /b
)

REM ----- Variables -----
set JARVIS_DIR=C:\Jarvis
set SHARED_DIR=\\VBoxSvr\JarvisAI
set REPO_URL=https://github.com/Corgipollo/JarvisAI.git

echo [1/9] Instalando Python 3.11...
where python >nul 2>&1
if errorlevel 1 (
    winget install --id Python.Python.3.11 --accept-package-agreements --accept-source-agreements --silent
) else (
    echo   Python ya instalado.
)

echo [2/9] Instalando Node.js LTS...
where node >nul 2>&1
if errorlevel 1 (
    winget install --id OpenJS.NodeJS.LTS --accept-package-agreements --accept-source-agreements --silent
) else (
    echo   Node ya instalado.
)

echo [3/9] Instalando Git...
where git >nul 2>&1
if errorlevel 1 (
    winget install --id Git.Git --accept-package-agreements --accept-source-agreements --silent
) else (
    echo   Git ya instalado.
)

echo [4/9] Instalando Tesseract OCR...
if not exist "C:\Program Files\Tesseract-OCR\tesseract.exe" (
    winget install --id UB-Mannheim.TesseractOCR --accept-package-agreements --accept-source-agreements --silent
) else (
    echo   Tesseract ya instalado.
)

REM Refrescar PATH despues de winget
call refreshenv >nul 2>&1
set "PATH=%PATH%;%LOCALAPPDATA%\Programs\Python\Python311;%LOCALAPPDATA%\Programs\Python\Python311\Scripts;C:\Program Files\nodejs;C:\Program Files\Git\cmd"

echo [5/9] Clonando o actualizando repo Jarvis...
if exist "%JARVIS_DIR%\.git" (
    cd /d "%JARVIS_DIR%"
    git pull 2>&1
) else (
    REM Intentar primero shared folder, sino git clone
    if exist "%SHARED_DIR%\backend" (
        echo   Copiando desde shared folder...
        robocopy "%SHARED_DIR%" "%JARVIS_DIR%" /MIR /NFL /NDL /NJH /NJS /XD ".git" "node_modules" "__pycache__" "data\tutorial_cache" "data\role_content_cache"
    ) else (
        echo   Clonando desde GitHub...
        git clone %REPO_URL% "%JARVIS_DIR%"
    )
    cd /d "%JARVIS_DIR%"
)

echo [6/9] Instalando dependencias Python (puede tardar 3-5 min)...
python -m pip install --upgrade pip --quiet
python -m pip install --quiet ^
    pyautogui psutil pygetwindow pyyaml pywin32 ^
    fastapi uvicorn ^
    pytesseract pillow ^
    faster-whisper edge-tts ^
    requests playwright python-telegram-bot anthropic yt-dlp ^
    beautifulsoup4 lxml

echo [7/9] Instalando Claude CLI + Playwright Chromium...
where claude >nul 2>&1
if errorlevel 1 (
    call npm install -g @anthropic-ai/claude-code 2>&1
)
python -m playwright install chromium 2>&1 | findstr /v "already installed"

echo.
echo ============================================================================
echo                  SETUP COMPLETO. ARRANCANDO SERVICIOS...
echo ============================================================================
echo.

echo [8/9] Copiando SUPER_PROMPT al clipboard...
if exist "%JARVIS_DIR%\SUPER_PROMPT_VM.md" (
    powershell -Command "Get-Content '%JARVIS_DIR%\SUPER_PROMPT_VM.md' -Raw | Set-Clipboard"
    echo   SUPER_PROMPT copiado. Pegalo en Claude/Antigravity con Ctrl+V.
)

echo [9/9] Arrancando servicios en background...

REM Claude proxy
start "Jarvis Proxy" /MIN cmd /c "cd /d %JARVIS_DIR% && python -m uvicorn jarvis_bridge.claude_proxy:app --host 127.0.0.1 --port 8088"
timeout /t 3 /nobreak >nul

REM Web dashboard
start "Jarvis Dashboard" /MIN cmd /c "cd /d %JARVIS_DIR% && python -m uvicorn jarvis_core.web_server:app --host 127.0.0.1 --port 7777"
timeout /t 3 /nobreak >nul

REM Self-improvement loop
start "Jarvis Self-Improvement" /MIN cmd /c "cd /d %JARVIS_DIR% && set JARVIS_SANDBOX=0&& python jarvis_learners\self_improvement.py"

REM Coach
start "Jarvis Coach" /MIN cmd /c "cd /d %JARVIS_DIR% && python jarvis_learners\coach.py"

timeout /t 3 /nobreak >nul

echo.
echo ============================================================================
echo                  JARVIS VIVO. ABRIENDO DASHBOARD...
echo ============================================================================
echo.

REM Abrir dashboard en browser
start "" "http://localhost:7777"

echo.
echo === ESTADO ===
echo   Claude Proxy:       http://localhost:8088/health
echo   Dashboard:          http://localhost:7777
echo   Self-improvement:   procesando gaps.json
echo   Coach:              decidiendo curriculum cada 15min
echo   SUPER_PROMPT:       en tu clipboard (Ctrl+V para pegar en Claude)
echo.
echo === SIGUIENTE PASO ===
echo   1. Login en Claude CLI:  claude login    (1 sola vez, OAuth)
echo   2. Abre Claude CLI o Antigravity
echo   3. Pega el SUPER_PROMPT (Ctrl+V) y enviar
echo   4. Claude adentro tomara el control y entrenara solo
echo.
echo Esta ventana se cerrara en 30 segundos. Los servicios siguen corriendo
echo en background. Para verlos: Win+T (taskbar) — los iconos con "Jarvis ..."
echo.
timeout /t 30 /nobreak
endlocal
