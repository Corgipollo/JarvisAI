@echo off
REM install_ga.bat - Find and install VirtualBox Guest Additions silently
REM Avoids ESP-LAA layout chars; can be triggered via Tab autocomplete

setlocal
echo Buscando Guest Additions ISO mounted drive...
for %%d in (D E F G H I) do (
  if exist "%%d:\VBoxWindowsAdditions-amd64.exe" (
    echo Encontrado en %%d:
    echo Lanzando instalador silencioso...
    "%%d:\VBoxWindowsAdditions-amd64.exe" /S
    echo Instalado. Recordatorio: reboot manual desde VirtualBox.
    goto :done
  )
  if exist "%%d:\VBoxWindowsAdditions.exe" (
    echo Encontrado en %%d:
    "%%d:\VBoxWindowsAdditions.exe" /S
    goto :done
  )
)
echo NO se encontro la ISO de Guest Additions montada en ninguna unidad.
echo Devices menu -^> Insert Guest Additions CD image y reintenta.

:done
endlocal
pause
