@echo off
REM Atajo de bienvenida — pone START_JARVIS.bat en el desktop con icono
REM y registra "Iniciar Jarvis" en el menu contextual derecho.

setlocal
title Jarvis - Primera vez

echo Configurando atajos de inicio rapido...

REM Crear shortcut en el desktop
set SHORTCUT=%USERPROFILE%\Desktop\Iniciar Jarvis.lnk
set TARGET=%~dp0START_JARVIS.bat

powershell -Command ^
  "$ws = New-Object -ComObject WScript.Shell; ^
   $s = $ws.CreateShortcut('%SHORTCUT%'); ^
   $s.TargetPath = '%TARGET%'; ^
   $s.WorkingDirectory = '%~dp0'; ^
   $s.IconLocation = 'C:\Windows\System32\shell32.dll, 27'; ^
   $s.Description = 'Arranca todo Jarvis con un click'; ^
   $s.Save()"

echo.
echo  ✓ Atajo creado en Escritorio: "Iniciar Jarvis"
echo.
echo  Ahora doble click en el atajo del Desktop y arranca todo.
echo.
pause
endlocal
