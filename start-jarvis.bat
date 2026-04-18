@echo off
title Jarvis AI Launcher
echo ========================================
echo   JARVIS AI — Iniciando...
echo ========================================
echo.

:: Verificar Ollama
tasklist /fi "imagename eq ollama.exe" 2>NUL | find /i "ollama.exe" >NUL
if errorlevel 1 (
    echo [+] Iniciando Ollama...
    start "" "C:\Users\Emmanuel\AppData\Local\Programs\Ollama\ollama.exe" serve
    timeout /t 3 /nobreak >NUL
) else (
    echo [OK] Ollama ya esta corriendo
)

:: Verificar si backend ya corre
curl -s http://127.0.0.1:8766/api/health >NUL 2>&1
if errorlevel 1 (
    echo [+] Iniciando Backend FastAPI...
    cd /d "C:\Users\Emmanuel\Documents\JarvisAI\backend"
    start "Jarvis-Backend" /min cmd /c "python main.py --no-browser"
    echo [+] Esperando backend...
    timeout /t 5 /nobreak >NUL
) else (
    echo [OK] Backend ya esta corriendo
)

:: Abrir Jarvis como Chrome App (ventana standalone)
echo [+] Abriendo Jarvis UI...
start "" "C:\Program Files\Google\Chrome\Application\chrome.exe" ^
    --app=http://127.0.0.1:8766 ^
    --window-size=420,550 ^
    --window-position=8,8 ^
    --disable-infobars ^
    --user-data-dir="C:\Users\Emmanuel\AppData\Local\JarvisApp" ^
    --class=JarvisAI

:: Iniciar hotkey listener (Alt+J para toggle)
echo [+] Activando hotkey global (Alt+J)...
start "" /min powershell -ExecutionPolicy Bypass -File "C:\Users\Emmanuel\Documents\JarvisAI\scripts\hotkey.ps1"

echo.
echo ========================================
echo   JARVIS AI ACTIVO
echo   Alt+J = Mostrar/Ocultar Jarvis
echo   Jarvis corre en http://127.0.0.1:8766
echo ========================================
