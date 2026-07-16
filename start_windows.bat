@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo Erstelle lokale Python-Umgebung...
    python -m venv .venv
)

echo Installiere/aktualisiere Pakete...
".venv\Scripts\python.exe" -m pip install -r requirements.txt

echo Starte TraidSim mit Hyperopt...
call "%~dp0Hyperopt_App_starten.bat"

