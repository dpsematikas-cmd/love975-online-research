@echo off
title Love 97.5 Music Research - START WITH PY
cd /d "%~dp0"
py -m pip install -r requirements.txt
start http://127.0.0.1:5000/admin
py app.py
pause
