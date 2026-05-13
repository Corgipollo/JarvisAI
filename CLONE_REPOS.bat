@echo off
REM ============================================================================
REM CLONE_REPOS.bat - Clona los 3 repos chinos de computer-use agents
REM
REM Para que el user no tenga que tipear URLs con / : que el layout ESP rompe.
REM
REM Uso: doble-click o desde cmd: CLONE_REPOS.bat
REM ============================================================================

title Jarvis - Clone External Repos

set REPOS_DIR=C:\repos

echo ============================================================================
echo                  CLONANDO REPOS DE COMPUTER-USE AGENTS
echo ============================================================================
echo.

if not exist %REPOS_DIR% mkdir %REPOS_DIR%
cd /d %REPOS_DIR%

echo [1/3] UI-TARS-desktop (ByteDance) - app Electron lista...
if not exist UI-TARS-desktop (
    git clone https://github.com/bytedance/UI-TARS-desktop
) else (
    cd UI-TARS-desktop && git pull && cd ..
)
echo.

echo [2/3] OS-Atlas (OS-Copilot) - modelos grounding 7B...
if not exist OS-Atlas (
    git clone https://github.com/OS-Copilot/OS-Atlas
) else (
    cd OS-Atlas && git pull && cd ..
)
echo.

echo [3/3] MobileAgent (Alibaba X-PLUG) - 3 agentes pipeline...
if not exist MobileAgent (
    git clone https://github.com/X-PLUG/MobileAgent
) else (
    cd MobileAgent && git pull && cd ..
)
echo.

echo ============================================================================
echo                  REPOS CLONADOS
echo ============================================================================
echo.
echo Ubicacion: %REPOS_DIR%
dir /b
echo.
echo NOTA: Estos repos requieren modelos pesados (7B params) que sin GPU
echo van a ser MUY lentos. La VM no tiene GPU passthrough.
echo.
echo Lo util AHORA mismo:
echo   - Revisar codigo de UI-TARS-desktop/apps/ para ver UI patterns
echo   - Importar dataset GUI-Odyssey de HuggingFace via python:
echo       python -c "from datasets import load_dataset; d=load_dataset('OpenGVLab/GUI-Odyssey')"
echo.
pause
