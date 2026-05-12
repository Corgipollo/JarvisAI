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

echo.
echo ============================================================================
echo  [4.5/9] INSTALANDO APPS QUE JARVIS VA A USAR (idempotente)
echo ============================================================================
echo.

REM ---- Cache de apps ya instaladas (1 sola llamada a winget list) ----
echo   Detectando apps ya instaladas...
set "INSTALLED_CACHE=%TEMP%\jarvis_installed.txt"
winget list --accept-source-agreements > "%INSTALLED_CACHE%" 2>nul
echo   OK cache generado en %INSTALLED_CACHE%

REM Helper inline: si app ya esta en cache, skip; sino install
REM Uso: call :try_install "Nombre legible" "ID.del.paquete"
goto :skip_helper

:try_install
findstr /I /C:"%~2" "%INSTALLED_CACHE%" >nul 2>&1
if not errorlevel 1 (
    echo   [SKIP] %~1 ya instalado
    goto :eof
)
echo   [INSTALL] %~1...
winget install --id %~2 --accept-package-agreements --accept-source-agreements --silent --disable-interactivity 2>nul
goto :eof

:skip_helper

REM Navegadores
call :try_install "Google Chrome" "Google.Chrome"
call :try_install "Brave Browser" "Brave.Brave"
call :try_install "Firefox" "Mozilla.Firefox"

REM Editores y code
call :try_install "Visual Studio Code" "Microsoft.VisualStudioCode"
call :try_install "Notepad++" "Notepad++.Notepad++"

REM Comunicacion
call :try_install "Telegram Desktop" "Telegram.TelegramDesktop"
call :try_install "Discord" "Discord.Discord"
call :try_install "WhatsApp" "WhatsApp.WhatsApp"
call :try_install "Zoom" "Zoom.Zoom"

REM Video / Audio
call :try_install "CapCut Desktop" "Bytedance.CapCut"
call :try_install "OBS Studio" "OBSProject.OBSStudio"
call :try_install "VLC media player" "VideoLAN.VLC"
call :try_install "Spotify" "Spotify.Spotify"

REM Notes
call :try_install "Obsidian" "Obsidian.Obsidian"
call :try_install "Notion" "Notion.Notion"

REM Utilidades
call :try_install "7-Zip" "7zip.7zip"
call :try_install "PowerToys" "Microsoft.PowerToys"
call :try_install "Windows Terminal" "Microsoft.WindowsTerminal"
call :try_install "GIMP" "GIMP.GIMP"
call :try_install "Antigravity Claude IDE" "Anthropic.Antigravity"

echo.
echo   Apps procesadas (ya instaladas: SKIP, faltantes: INSTALL).
echo.

echo ============================================================================
echo  [4.6/9] AUTO-CONFIGURANDO apps (extensiones VS Code, Git, etc.)
echo ============================================================================
echo.

REM Git config (necesario para commits)
echo   * Git config (user/email)...
git config --global user.name "Jarvis VM" 2>nul
git config --global user.email "jarvis@vm.local" 2>nul
git config --global init.defaultBranch main 2>nul
git config --global pull.rebase false 2>nul

REM VS Code extensiones esenciales
echo   * VS Code extensiones (Python, GitLens, Pylance, etc.)...
where code >nul 2>&1
if not errorlevel 1 (
    call code --install-extension ms-python.python --force >nul 2>&1
    call code --install-extension ms-python.vscode-pylance --force >nul 2>&1
    call code --install-extension eamodio.gitlens --force >nul 2>&1
    call code --install-extension ms-vscode.live-server --force >nul 2>&1
    call code --install-extension dbaeumer.vscode-eslint --force >nul 2>&1
    call code --install-extension esbenp.prettier-vscode --force >nul 2>&1
    call code --install-extension ms-azuretools.vscode-docker --force >nul 2>&1
    call code --install-extension yzhang.markdown-all-in-one --force >nul 2>&1
    call code --install-extension PKief.material-icon-theme --force >nul 2>&1
)

REM Windows Terminal: setear default profile a PowerShell 7
echo   * Windows Terminal config...
where pwsh >nul 2>&1
if errorlevel 1 (
    winget install --id Microsoft.PowerShell --silent --disable-interactivity 2>nul
)

REM PowerToys auto-start
echo   * PowerToys autostart...
schtasks /create /tn "PowerToys" /tr "%LOCALAPPDATA%\PowerToys\PowerToys.exe" /sc onlogon /rl highest /f 2>nul

REM Setear Brave como default browser por flag (alternativa: Chrome)
echo   * Brave como default browser (silent)...
where brave.exe >nul 2>&1
if not errorlevel 1 (
    reg add "HKEY_CURRENT_USER\Software\Brave\PreFlightCheck" /v "SetDefaultBrowser" /t REG_DWORD /d 1 /f >nul 2>&1
)

REM Desactivar Bing/sugerencias web en Windows Search (para que apps locales se prioricen)
echo   * Windows Search optimizado (sin Bing online)...
reg add "HKEY_CURRENT_USER\Software\Policies\Microsoft\Windows\Explorer" /v "DisableSearchBoxSuggestions" /t REG_DWORD /d 1 /f >nul 2>&1

REM Mostrar extensiones de archivo (mejor para Jarvis)
echo   * Mostrar extensiones de archivo...
reg add "HKEY_CURRENT_USER\Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced" /v "HideFileExt" /t REG_DWORD /d 0 /f >nul 2>&1

REM Mostrar archivos ocultos (Jarvis necesita acceder a %APPDATA% y similar)
reg add "HKEY_CURRENT_USER\Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced" /v "Hidden" /t REG_DWORD /d 1 /f >nul 2>&1

REM Deshabilitar UAC para Jarvis (en sandbox VM, es seguro y evita popups)
echo   * Deshabilitar UAC en VM (seguro porque es sandbox)...
reg add "HKEY_LOCAL_MACHINE\SOFTWARE\Microsoft\Windows\CurrentVersion\Policies\System" /v "EnableLUA" /t REG_DWORD /d 0 /f >nul 2>&1

REM ============================================================================
REM Saltar/ocultar activacion Windows (user no tiene licencia, VM es sandbox)
REM ============================================================================
echo   * Ocultando nag de 'Activar Windows'...

REM Extender periodo de gracia 30 dias (se puede 'rearm' 3 veces = 90 dias)
slmgr /rearm >nul 2>&1

REM Ocultar el watermark "Activate Windows" en escritorio
reg add "HKEY_CURRENT_USER\Control Panel\Desktop" /v "PaintDesktopVersion" /t REG_DWORD /d 0 /f >nul 2>&1

REM Deshabilitar notificaciones "Activate Windows now"
reg add "HKEY_LOCAL_MACHINE\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Activation" /v "Manual" /t REG_DWORD /d 1 /f >nul 2>&1
reg add "HKEY_LOCAL_MACHINE\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Activation" /v "NotificationDisabled" /t REG_DWORD /d 1 /f >nul 2>&1

REM Desactivar servicio de notificacion de activacion
sc config "wlidsvc" start= disabled >nul 2>&1

REM Permitir personalizacion sin activacion (algunos settings se ocultan sin license)
reg add "HKEY_LOCAL_MACHINE\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Windows Activation Technologies" /v "DisableActivationFeatureNotice" /t REG_DWORD /d 1 /f >nul 2>&1

REM Saltar OOBE si todavia esta en proceso
reg add "HKEY_LOCAL_MACHINE\SOFTWARE\Microsoft\Windows\CurrentVersion\OOBE" /v "DisablePrivacyExperience" /t REG_DWORD /d 1 /f >nul 2>&1

echo   Windows sin activar — watermark oculto, sin notificaciones molestas.
echo   (Limitaciones menores: no personalizar wallpaper desde Settings, no
echo    cambiar accent colors. Pero TODO lo demas funciona indefinidamente.)

REM Reiniciar Explorer para aplicar cambios
echo   * Aplicando cambios (reinicio explorer)...
taskkill /f /im explorer.exe >nul 2>&1
timeout /t 1 /nobreak >nul
start explorer.exe

echo.
echo   Auto-configuracion completa.
echo.

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
    pytesseract pillow imagehash ^
    faster-whisper edge-tts ^
    requests playwright python-telegram-bot anthropic yt-dlp ^
    beautifulsoup4 lxml

REM Verificar que yt-dlp funciona via -m antes de seguir
python -m yt_dlp --version >nul 2>&1
if errorlevel 1 (
    echo   WARN: yt-dlp module no responde, reinstalando...
    python -m pip install --force-reinstall --quiet yt-dlp
)

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

REM Telegram bot (si config_telegram.json existe)
if exist "%JARVIS_DIR%\config_telegram.json" (
    echo   * Telegram bot...
    start "Jarvis Telegram Bot" /MIN cmd /c "cd /d %JARVIS_DIR% && python jarvis_bridge\telegram_bot.py"
    start "Jarvis Telegram Notifier" /MIN cmd /c "cd /d %JARVIS_DIR% && python jarvis_bridge\telegram_notifier.py"
)

REM State backup auto cada 5 skills
start "Jarvis State Backup" /MIN cmd /c "cd /d %JARVIS_DIR% && python jarvis_bridge\state_backup.py"

REM Self-optimizer (cada 60 min revisa metricas y ajusta)
start "Jarvis Self-Optimizer" /MIN cmd /c "cd /d %JARVIS_DIR% && python jarvis_learners\self_optimizer.py"

REM Proactive suggester (cada 30 min sugiere tareas)
start "Jarvis Proactive" /MIN cmd /c "cd /d %JARVIS_DIR% && python jarvis_learners\proactive_suggester.py"

REM Watchdog (cada 3 min monitorea salud + restart auto)
start "Jarvis Watchdog" /MIN cmd /c "cd /d %JARVIS_DIR% && python jarvis_learners\watchdog.py"

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

REM ----- AUTO-LAUNCH Claude CLI con SUPER_PROMPT -----
echo === [10/10] Verificando login Claude CLI ===
where claude >nul 2>&1
if errorlevel 1 (
    echo   Claude CLI no instalado correctamente. Saliendo.
    pause
    exit /b 1
)

REM Test rapido: si claude no esta logueado, pedirlo
claude -p "ok" --dangerously-skip-permissions 2>&1 | findstr /C:"Not logged in" >nul
if not errorlevel 1 (
    echo.
    echo   Claude CLI NO esta logueado. Ejecutando: claude login
    echo   Se abrira un navegador para autenticacion OAuth.
    echo.
    claude login
)

echo.
echo === LANZANDO CLAUDE CON SUPER_PROMPT (automático) ===
echo.
cd /d "%JARVIS_DIR%"
python AUTO_TALK_TO_CLAUDE.py

REM Cuando Claude termine la sesion, los servicios siguen corriendo
echo.
echo === SESION CLAUDE TERMINADA ===
echo Los 4 servicios siguen vivos en background:
echo   - claude_proxy   :8088
echo   - dashboard      :7777
echo   - self_improvement
echo   - coach
echo.
echo Para verlos: Win+T (taskbar) - iconos minimizados "Jarvis ..."
echo Para detenerlos: cierra esas ventanas minimizadas.
echo.
pause
endlocal
