@echo off
REM launch_sandbox.bat — Lanza Windows Sandbox con el config de Jarvis.
REM
REM Requiere que Windows Sandbox feature este habilitada.
REM Si no lo esta, correr enable_feature.ps1 (admin + reboot).

setlocal

set WSB=%~dp0jarvis_sandbox.wsb

if not exist "%WSB%" (
    echo ERROR: No encuentro %WSB%
    exit /b 1
)

REM Verifica que WindowsSandbox.exe exista
where WindowsSandbox.exe >nul 2>nul
if errorlevel 1 (
    echo.
    echo ERROR: Windows Sandbox no esta habilitado en este sistema.
    echo Para activarlo (requiere admin + reboot^):
    echo.
    echo   1. Click derecho en sandbox_vm\enable_feature.ps1
    echo   2. "Run with PowerShell" como administrador
    echo   3. Reiniciar la PC
    echo   4. Volver a correr este .bat
    echo.
    pause
    exit /b 1
)

echo Lanzando Jarvis Sandbox...
echo Config: %WSB%
echo.
echo La sandbox aparecera como una ventana separada (PC dentro de la PC).
echo Dentro:
echo   - JarvisAI esta en C:\Users\WDAGUtilityAccount\Desktop\JarvisAI
echo   - El trainer corre cada 5 min en LOOP INFINITO
echo   - Logs en C:\jarvis_sandbox.log y C:\jarvis_iterations.log
echo   - Cierra la ventana = sandbox se BORRA (estado limpio next time)
echo.

start "" WindowsSandbox.exe "%WSB%"

endlocal
