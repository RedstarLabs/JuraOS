
@echo off
setlocal
set "ROOT=%~dp0"
set "PYTHON=%ROOT%.venv\Scripts\python.exe"

where py >nul 2>nul
if errorlevel 1 (
    where python >nul 2>nul
    if errorlevel 1 (
        echo Python 3 ist nicht installiert oder nicht im PATH.
        echo Bitte Python 3.10 oder neuer installieren und erneut starten.
        pause
        exit /b 1
    )
    set "PY_CMD=python"
) else (
    set "PY_CMD=py -3"
)

if not exist "%PYTHON%" (
    %PY_CMD% -m venv "%ROOT%.venv"
    if errorlevel 1 (
        echo Konnte die Python-Umgebung nicht erstellen.
        pause
        exit /b 1
    )
)

"%PYTHON%" -c "import PySide6, pypdf" >nul 2>nul
if errorlevel 1 (
    echo Installiere JuraOS-Abhaengigkeiten. Das kann beim ersten Start etwas dauern.
    "%PYTHON%" -m pip install --upgrade pip
    if errorlevel 1 goto :install_error

    "%PYTHON%" -m pip install -r "%ROOT%requirements.txt"
    if errorlevel 1 goto :install_error
)

cd /d "%ROOT%"
"%PYTHON%" "%ROOT%scripts\juraos_sorter_gui.py"
set "APP_EXIT=%ERRORLEVEL%"

if not "%APP_EXIT%"=="0" (
    echo JuraOS wurde mit Fehlercode %APP_EXIT% beendet.
    pause
)

exit /b %APP_EXIT%

:install_error
echo Installation fehlgeschlagen. Bitte Internetverbindung und Python pruefen.
pause
exit /b 1
