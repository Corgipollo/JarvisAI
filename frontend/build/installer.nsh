; Custom NSIS script for Jarvis AI installer
; Checks for Python 3.11 and installs if needed

!macro customInit
  ; Check if Python 3.11 is installed
  ReadRegStr $0 HKLM "SOFTWARE\Python\PythonCore\3.11\InstallPath" ""
  ${If} $0 == ""
    MessageBox MB_YESNO "Python 3.11 is required but not found. Do you want to download it now?" IDYES download IDNO cancel
    download:
      ExecShell "open" "https://www.python.org/downloads/release/python-3110/"
      MessageBox MB_OK "Please install Python 3.11, then run this installer again."
      Abort
    cancel:
      MessageBox MB_OK "Installation cancelled. Jarvis AI requires Python 3.11 to run."
      Abort
  ${EndIf}
!macroend

!macro customInstall
  ; Create .env from template if it doesn't exist
  IfFileExists "$INSTDIR\resources\.env" skip_env_copy
    CopyFiles "$INSTDIR\resources\.env.example" "$INSTDIR\resources\.env"
  skip_env_copy:

  ; Install Python dependencies
  DetailPrint "Installing Python dependencies..."
  nsExec::ExecToLog 'python -m pip install --upgrade pip'
  nsExec::ExecToLog 'python -m pip install -r "$INSTDIR\resources\backend\requirements.txt"'
!macroend

!macro customUnInstall
  ; Clean up any created files
  Delete "$INSTDIR\resources\.env"
  RMDir /r "$INSTDIR\resources\backend\__pycache__"
!macroend
