@echo off
cd /d "%~dp0"
where python >nul 2>nul
if errorlevel 1 (
    echo Python was not found. Please install Python first.
    pause
    exit /b 1
)
if not exist "venv\" python -m venv venv
call venv\Scripts\activate.bat
python -m pip install -r requirements.txt --quiet
start "" http://127.0.0.1:5000
python app.py
pause
