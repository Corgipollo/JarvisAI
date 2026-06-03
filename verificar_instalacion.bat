@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

:: ============================================================================
:: JARVIS V3 - VERIFICADOR POST-INSTALACION
:: ============================================================================

title Jarvis V3 - Verificación de Instalación

echo.
echo ╔═══════════════════════════════════════════════════════════════════════╗
echo ║           JARVIS V3 - VERIFICACION DE INSTALACION                     ║
echo ╚═══════════════════════════════════════════════════════════════════════╝
echo.

set ERRORS=0
set WARNINGS=0

:: ============================================================================
:: CHECK 1: Python
:: ============================================================================
echo [1/8] 🐍 Verificando Python...

python --version >nul 2>&1
if errorlevel 1 (
    echo    ❌ Python NO encontrado
    set /a ERRORS+=1
) else (
    for /f "tokens=2" %%i in ('python --version 2^>^&1') do (
        echo    ✓ Python %%i detectado
    )
)

:: ============================================================================
:: CHECK 2: Venv
:: ============================================================================
echo [2/8] 📦 Verificando entorno virtual...

cd /d "%~dp0jarvis_v3"

if not exist "venv\" (
    echo    ❌ venv NO encontrado
    set /a ERRORS+=1
) else (
    echo    ✓ venv existe

    if exist "venv\Scripts\python.exe" (
        echo    ✓ Python en venv OK
    ) else (
        echo    ❌ venv corrupto (sin python.exe)
        set /a ERRORS+=1
    )
)

:: ============================================================================
:: CHECK 3: Dependencias Core
:: ============================================================================
echo [3/8] 📚 Verificando dependencias core...

call venv\Scripts\activate.bat 2>nul
if errorlevel 1 (
    echo    ⚠ No se pudo activar venv
    set /a WARNINGS+=1
    goto skip_deps
)

echo    → Verificando anthropic...
python -c "import anthropic" 2>nul
if errorlevel 1 (
    echo    ❌ anthropic NO instalado
    set /a ERRORS+=1
) else (
    echo    ✓ anthropic OK
)

echo    → Verificando mss...
python -c "import mss" 2>nul
if errorlevel 1 (
    echo    ❌ mss NO instalado
    set /a ERRORS+=1
) else (
    echo    ✓ mss OK
)

echo    → Verificando pyautogui...
python -c "import pyautogui" 2>nul
if errorlevel 1 (
    echo    ❌ pyautogui NO instalado
    set /a ERRORS+=1
) else (
    echo    ✓ pyautogui OK
)

echo    → Verificando pywin32...
python -c "import win32gui" 2>nul
if errorlevel 1 (
    echo    ❌ pywin32 NO instalado
    set /a ERRORS+=1
) else (
    echo    ✓ pywin32 OK
)

echo    → Verificando psutil...
python -c "import psutil" 2>nul
if errorlevel 1 (
    echo    ❌ psutil NO instalado
    set /a ERRORS+=1
) else (
    echo    ✓ psutil OK
)

:skip_deps

:: ============================================================================
:: CHECK 4: Archivos Core
:: ============================================================================
echo [4/8] 📄 Verificando archivos core...

set CORE_FILES=run_forever.py supervisor.py sdk_agent.py safety_guard.py

for %%f in (%CORE_FILES%) do (
    if exist "jarvis_v3_core\%%f" (
        echo    ✓ %%f existe
    ) else (
        echo    ❌ %%f NO encontrado
        set /a ERRORS+=1
    )
)

:: ============================================================================
:: CHECK 5: Configuración
:: ============================================================================
echo [5/8] ⚙️ Verificando configuración...

if exist ".env" (
    echo    ✓ .env existe

    findstr /i "ANTHROPIC_API_KEY" .env >nul 2>&1
    if errorlevel 1 (
        echo    ⚠ .env sin ANTHROPIC_API_KEY
        set /a WARNINGS+=1
    )

    findstr /i "sk-ant-api03-\.\.\." .env >nul 2>&1
    if not errorlevel 1 (
        echo    ⚠ .env tiene valores de ejemplo (agregar API keys reales)
        set /a WARNINGS+=1
    )
) else (
    if exist ".env.example" (
        echo    ⚠ .env NO existe (usa .env.example como template)
        set /a WARNINGS+=1
    ) else (
        echo    ❌ .env.example NO existe
        set /a ERRORS+=1
    )
)

:: ============================================================================
:: CHECK 6: Acceso Directo Desktop
:: ============================================================================
echo [6/8] 🎯 Verificando acceso directo...

if exist "%USERPROFILE%\Desktop\Jarvis V3.lnk" (
    echo    ✓ Acceso directo en Desktop existe
) else (
    echo    ⚠ Acceso directo NO encontrado
    set /a WARNINGS+=1
)

:: ============================================================================
:: CHECK 7: GPU CUDA (opcional)
:: ============================================================================
echo [7/8] 🎮 Verificando GPU (opcional)...

python -c "import torch; print('CUDA:', torch.cuda.is_available())" 2>nul | findstr "True" >nul
if not errorlevel 1 (
    echo    ✓ CUDA disponible (GPU acelerado)
) else (
    echo    ⚠ CUDA NO disponible (usará CPU - más lento)
    set /a WARNINGS+=1
)

:: ============================================================================
:: CHECK 8: Permisos
:: ============================================================================
echo [8/8] 🔐 Verificando permisos...

net session >nul 2>&1
if not errorlevel 1 (
    echo    ✓ Ejecutando con permisos elevados
) else (
    echo    ⚠ Sin permisos de admin (puede fallar pywin32)
    set /a WARNINGS+=1
)

:: ============================================================================
:: RESUMEN
:: ============================================================================
echo.
echo ╔═══════════════════════════════════════════════════════════════════════╗
echo ║                           RESUMEN                                     ║
echo ╚═══════════════════════════════════════════════════════════════════════╝
echo.

if %ERRORS% EQU 0 (
    if %WARNINGS% EQU 0 (
        echo    ✅ INSTALACION PERFECTA - Jarvis V3 listo para usar
        echo.
        echo    Próximo paso:
        echo    1. Configura .env con tus API keys
        echo    2. Doble-click en "Jarvis V3" en Desktop
    ) else (
        echo    ⚠ INSTALACION COMPLETA CON ADVERTENCIAS (%WARNINGS% warnings)
        echo.
        echo    Jarvis funcionará, pero revisa los warnings arriba.
    )
) else (
    echo    ❌ INSTALACION INCOMPLETA (%ERRORS% errores, %WARNINGS% warnings)
    echo.
    echo    Ejecuta nuevamente: setup_jarvis.bat
)

echo.
echo ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
echo  Errores: %ERRORS% ^| Warnings: %WARNINGS%
echo ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
echo.

pause
