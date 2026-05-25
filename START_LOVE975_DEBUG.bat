@echo off
title Love 97.5 Music Research - DEBUG START
cd /d "%~dp0"

echo.
echo ==========================================
echo LOVE 97.5 MUSIC RESEARCH - DEBUG START
echo ==========================================
echo.
echo Current folder:
echo %cd%
echo.

echo Checking Python...
python --version
IF ERRORLEVEL 1 (
    echo.
    echo ERROR: Δεν βρέθηκε Python με την εντολή python.
    echo Θα δοκιμάσω με py...
    py --version
    IF ERRORLEVEL 1 (
        echo.
        echo ΔΕΝ ΒΡΕΘΗΚΕ PYTHON.
        echo Πρεπει να εγκαταστησεις Python απο python.org
        echo και να τσεκαρεις Add Python to PATH.
        echo.
        pause
        exit /b
    )
    echo.
    echo Installing requirements with py...
    py -m pip install -r requirements.txt
    echo.
    echo Starting server with py...
    start http://127.0.0.1:5000/admin
    py app.py
    echo.
    echo Ο server σταματησε ή εμφανιστηκε σφαλμα.
    pause
    exit /b
)

echo.
echo Installing requirements...
python -m pip install -r requirements.txt
IF ERRORLEVEL 1 (
    echo.
    echo ERROR: Δεν μπορεσαν να εγκατασταθουν τα requirements.
    echo Δοκιμασε Run as Administrator.
    echo.
    pause
    exit /b
)

echo.
echo Starting server...
echo Αν δεις "Running on http://127.0.0.1:5000", εισαι ΟΚ.
echo.
start http://127.0.0.1:5000/admin
python app.py

echo.
echo Ο server σταματησε ή εμφανιστηκε σφαλμα.
pause
