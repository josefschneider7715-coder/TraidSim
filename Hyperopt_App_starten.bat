@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo Python-Umgebung wurde nicht gefunden.
    echo Bitte zuerst start_windows.bat ausfuehren oder Python installieren.
    pause
    exit /b 1
)

start "TraidSim" powershell.exe -NoProfile -ExecutionPolicy Bypass -NoExit -File "%~dp0start_hyperopt_app.ps1"
start "" powershell.exe -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -Command "Start-Sleep -Seconds 6; Start-Process 'http://127.0.0.1:8501'"
