@echo off
cd /d "%~dp0"
python -m pip install -r requirements.txt
start http://127.0.0.1:5000/admin
python run_love975.py
pause
