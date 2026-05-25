@echo off
title Build Love 97.5 Music Research EXE
cd /d "%~dp0"

echo ==========================================
echo LOVE 97.5 MUSIC RESEARCH - EXE BUILDER
echo ==========================================
echo.

echo Checking Python...
python --version
IF ERRORLEVEL 1 (
    echo.
    echo Δεν βρέθηκε Python.
    echo Κατέβασε Python από https://www.python.org/downloads/
    echo και βάλε check στο Add Python to PATH.
    pause
    exit /b
)

echo.
echo Installing requirements...
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m pip install pyinstaller

echo.
echo Building EXE...
python -m PyInstaller ^
 --onefile ^
 --name Love975MusicResearch ^
 --add-data "templates;templates" ^
 --add-data "uploads;uploads" ^
 run_love975.py

echo.
echo ==========================================
echo ΕΤΟΙΜΟ!
echo Το EXE βρίσκεται εδώ:
echo dist\Love975MusicResearch.exe
echo ==========================================
echo.
pause
