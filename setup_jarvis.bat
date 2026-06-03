@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

:: ============================================================================
:: JARVIS V3 - ONE-CLICK INSTALLER
:: Emmanuel Pedraza - 2026-06-02
:: ============================================================================

title Jarvis V3 Installer - Setup in Progress...

echo.
echo ╔═══════════════════════════════════════════════════════════════════════╗
echo ║                    JARVIS V3 - ONE-CLICK INSTALLER                    ║
echo ║                                                                       ║
echo ║  Este instalador configura Jarvis V3 completamente:                  ║
echo ║  • Verifica Python 3.10+                                             ║
echo ║  • Crea entorno virtual                                              ║
echo ║  • Instala dependencias                                              ║
echo ║  • Genera .env template                                              ║
echo ║  • Crea acceso directo en Desktop                                    ║
echo ╚═══════════════════════════════════════════════════════════════════════╝
echo.
timeout /t 2 /nobreak >nul

:: ============================================================================
:: STEP 1: Verificar Python 3.10+
:: ============================================================================
echo [1/6] 🔍 Verificando Python 3.10+...

python --version >nul 2>&1
if errorlevel 1 (
    echo.
    echo ❌ ERROR: Python NO encontrado en PATH
    echo.
    echo Por favor instala Python 3.10 o superior desde:
    echo https://www.python.org/downloads/
    echo.
    echo IMPORTANTE: Durante instalación marca "Add Python to PATH"
    echo.
    pause
    exit /b 1
)

for /f "tokens=2" %%i in ('python --version 2^>^&1') do set PYTHON_VERSION=%%i
echo    ✓ Python %PYTHON_VERSION% detectado

:: Extraer version major.minor
for /f "tokens=1,2 delims=." %%a in ("%PYTHON_VERSION%") do (
    set MAJOR=%%a
    set MINOR=%%b
)

if %MAJOR% LSS 3 (
    echo    ❌ ERROR: Python 3.10+ requerido, tienes %PYTHON_VERSION%
    pause
    exit /b 1
)

if %MAJOR% EQU 3 if %MINOR% LSS 10 (
    echo    ❌ ERROR: Python 3.10+ requerido, tienes %PYTHON_VERSION%
    pause
    exit /b 1
)

echo    ✓ Versión válida: %PYTHON_VERSION%
echo.

:: ============================================================================
:: STEP 2: Crear venv si no existe
:: ============================================================================
echo [2/6] 📦 Configurando entorno virtual...

cd /d "%~dp0jarvis_v3"
if errorlevel 1 (
    echo    ❌ ERROR: No se encuentra carpeta jarvis_v3
    echo    Ruta esperada: %~dp0jarvis_v3
    pause
    exit /b 1
)

if not exist "venv\" (
    echo    → Creando nuevo venv...
    python -m venv venv
    if errorlevel 1 (
        echo    ❌ ERROR: Falló creación de venv
        pause
        exit /b 1
    )
    echo    ✓ Venv creado exitosamente
) else (
    echo    ✓ Venv ya existe, reutilizando
)

:: Activar venv
call venv\Scripts\activate.bat
if errorlevel 1 (
    echo    ❌ ERROR: No se pudo activar venv
    pause
    exit /b 1
)
echo    ✓ Venv activado
echo.

:: ============================================================================
:: STEP 3: Upgrade pip
:: ============================================================================
echo [3/6] 🔧 Actualizando pip...
python -m pip install --upgrade pip --quiet
if errorlevel 1 (
    echo    ⚠ Warning: pip upgrade falló, continuando...
) else (
    echo    ✓ pip actualizado
)
echo.

:: ============================================================================
:: STEP 4: Instalar dependencias
:: ============================================================================
echo [4/6] 📥 Instalando dependencias Jarvis V3...
echo    Esto puede tardar 3-5 minutos...
echo.

:: UFO requirements (core Windows automation)
if exist "ufo\requirements.txt" (
    echo    → Instalando UFO requirements...
    pip install -r ufo\requirements.txt --quiet
    if errorlevel 1 (
        echo    ⚠ Warning: Algunas dependencias UFO fallaron, continuando...
    ) else (
        echo    ✓ UFO requirements instalados
    )
)

:: AppAgent requirements (visual perception)
if exist "appagent\requirements.txt" (
    echo    → Instalando AppAgent requirements...
    pip install -r appagent\requirements.txt --quiet
    if errorlevel 1 (
        echo    ⚠ Warning: Algunas dependencias AppAgent fallaron, continuando...
    ) else (
        echo    ✓ AppAgent requirements instalados
    )
)

:: Core dependencies adicionales (Claude SDK)
echo    → Instalando core dependencies...
pip install anthropic mss psutil pyautogui pillow --quiet
if errorlevel 1 (
    echo    ⚠ Warning: Algunas dependencias core fallaron
) else (
    echo    ✓ Core dependencies instalados
)

:: Windows-specific
pip install pywin32 --quiet
if errorlevel 1 (
    echo    ⚠ Warning: pywin32 falló
) else (
    echo    ✓ pywin32 instalado
)

echo.
echo    ✓ Instalación de dependencias completada
echo.

:: ============================================================================
:: STEP 5: Generar .env.template
:: ============================================================================
echo [5/6] 📝 Generando .env.template...

set ENV_TEMPLATE=%~dp0jarvis_v3\.env.template

(
echo # ============================================================================
echo # JARVIS V3 - CONFIGURACION DE AMBIENTE
echo # ============================================================================
echo # Generado automaticamente por setup_jarvis.bat - %date% %time%
echo #
echo # INSTRUCCIONES:
echo # 1. Copia este archivo a .env
echo # 2. Rellena tus API keys reales
echo # 3. NUNCA commitees .env a git
echo # ============================================================================
echo.
echo # -----------------------------------------------------------------------------
echo # CLAUDE API (cerebro premium - requerido para SDK)
echo # -----------------------------------------------------------------------------
echo # Obtener en: https://console.anthropic.com/settings/keys
echo # Jarvis usa tu suscripción Claude Max = $0 por modelo
echo ANTHROPIC_API_KEY=sk-ant-api03-...
echo.
echo # -----------------------------------------------------------------------------
echo # CEREBROS GRATUITOS (fallback cuando Claude no disponible^)
echo # -----------------------------------------------------------------------------
echo.
echo # Google Gemini Free API (1500 requests/día^)
echo # Obtener en: https://aistudio.google.com/app/apikey
echo GEMINI_API_KEY=AIza...
echo.
echo # Cerebras Fast AI (gratis, ultra-rápido^)
echo # Obtener en: https://cloud.cerebras.ai/
echo CEREBRAS_API_KEY=csk-...
echo.
echo # OpenAI (opcional, solo si quieres usarlo^)
echo OPENAI_API_KEY=sk-...
echo.
echo # -----------------------------------------------------------------------------
echo # JARVIS V3 CONFIG
echo # -----------------------------------------------------------------------------
echo.
echo # Routing de cerebros (prioridad: claude ^> free ^> ollama^)
echo BRAIN_PRIORITY=claude,gemini,cerebras,ollama
echo.
echo # Ollama base URL (si usas Ollama local^)
echo OLLAMA_BASE_URL=http://localhost:11434
echo.
echo # Nivel de logs (DEBUG, INFO, WARNING, ERROR^)
echo LOG_LEVEL=INFO
echo.
echo # Puerto para API si la usas
echo JARVIS_PORT=8000
echo.
echo # -----------------------------------------------------------------------------
echo # HARDWARE OPTIMIZATION
echo # -----------------------------------------------------------------------------
echo.
echo # Faster-whisper device (cuda si tienes RTX, cpu sino^)
echo WHISPER_DEVICE=cuda
echo.
echo # Faster-whisper model (tiny, base, small, medium, large^)
echo WHISPER_MODEL=base
echo.
echo # -----------------------------------------------------------------------------
echo # TELEGRAM INTEGRATION (opcional^)
echo # -----------------------------------------------------------------------------
echo.
echo # Bot token de @BotFather
echo TELEGRAM_BOT_TOKEN=
echo.
echo # Tu chat ID para notificaciones
echo TELEGRAM_CHAT_ID=
echo.
echo # -----------------------------------------------------------------------------
echo # SAFETY GUARDS
echo # -----------------------------------------------------------------------------
echo.
echo # Activar safety guard para run_code (true/false^)
echo SAFETY_GUARD_ENABLED=true
echo.
echo # Max intentos antes de escalar a humano
echo MAX_RETRY_ATTEMPTS=3
echo.
echo # ============================================================================
echo # FIN CONFIGURACION
echo # ============================================================================
) > "%ENV_TEMPLATE%"

if exist "%ENV_TEMPLATE%" (
    echo    ✓ .env.template creado en: jarvis_v3\.env.template
    echo.
    echo    ⚠ IMPORTANTE: Copia .env.template a .env y agrega tus API keys
) else (
    echo    ❌ ERROR: No se pudo crear .env.template
)
echo.

:: ============================================================================
:: STEP 6: Crear acceso directo en Desktop
:: ============================================================================
echo [6/6] 🎯 Creando acceso directo en Desktop...

set DESKTOP=%USERPROFILE%\Desktop
set SHORTCUT_NAME=Jarvis V3.lnk
set TARGET=%~dp0jarvis_v3\venv\Scripts\python.exe
set ARGS=%~dp0jarvis_v3\jarvis_v3_core\run_forever.py
set ICON=%~dp0jarvis_v3\jarvis_v3_core\jarvis_icon.ico

:: Crear VBScript para generar shortcut (PowerShell puede estar bloqueado)
set VBS_SCRIPT=%TEMP%\create_jarvis_shortcut.vbs

(
echo Set oWS = WScript.CreateObject^("WScript.Shell"^)
echo sLinkFile = "%DESKTOP%\%SHORTCUT_NAME%"
echo Set oLink = oWS.CreateShortcut^(sLinkFile^)
echo oLink.TargetPath = "%TARGET%"
echo oLink.Arguments = """%ARGS%"""
echo oLink.WorkingDirectory = "%~dp0jarvis_v3\jarvis_v3_core"
echo oLink.Description = "Jarvis V3 - Asistente Personal AI"
echo oLink.WindowStyle = 1
echo oLink.Save
) > "%VBS_SCRIPT%"

cscript //nologo "%VBS_SCRIPT%" >nul 2>&1
if errorlevel 1 (
    echo    ⚠ No se pudo crear acceso directo automáticamente
    echo    Puedes crearlo manualmente:
    echo    Target: %TARGET%
    echo    Args: "%ARGS%"
) else (
    echo    ✓ Acceso directo creado: Desktop\%SHORTCUT_NAME%
)

del "%VBS_SCRIPT%" >nul 2>&1
echo.

:: ============================================================================
:: RESUMEN FINAL
:: ============================================================================
echo.
echo ╔═══════════════════════════════════════════════════════════════════════╗
echo ║                    ✅ INSTALACION COMPLETADA                          ║
echo ╚═══════════════════════════════════════════════════════════════════════╝
echo.
echo 📋 PROXIMOS PASOS:
echo.
echo    1. Configura tus API keys:
echo       cd jarvis_v3
echo       copy .env.template .env
echo       notepad .env
echo.
echo    2. Obtén API keys gratuitas:
echo       • Gemini: https://aistudio.google.com/app/apikey
echo       • Cerebras: https://cloud.cerebras.ai/
echo       • Claude: https://console.anthropic.com/settings/keys
echo.
echo    3. Lanza Jarvis:
echo       • Doble-click en "Jarvis V3" en tu Desktop
echo       O desde terminal:
echo       cd jarvis_v3\jarvis_v3_core
echo       ..\venv\Scripts\python run_forever.py
echo.
echo    4. Para instalar Ollama local (opcional):
echo       https://ollama.com/download
echo.
echo 📁 UBICACION: %~dp0jarvis_v3
echo 🔑 CONFIG: %~dp0jarvis_v3\.env.template
echo 🚀 LAUNCHER: Desktop\Jarvis V3.lnk
echo.
echo ╔═══════════════════════════════════════════════════════════════════════╗
echo ║  Jarvis V3 listo para usar. Configura .env y ejecuta!                ║
echo ╚═══════════════════════════════════════════════════════════════════════╝
echo.

pause
