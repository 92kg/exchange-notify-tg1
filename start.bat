@echo off
chcp 65001 > nul
echo ========================================================
echo   Crypto Sentiment Monitor v3.4 - Startup Script
echo ========================================================
echo.

set PYTHON_CMD=python
where %PYTHON_CMD% >nul 2>nul
if %ERRORLEVEL% neq 0 (
    set PYTHON_CMD=py
    where %PYTHON_CMD% >nul 2>nul
    if %ERRORLEVEL% neq 0 (
        echo [ERROR] Python not found in PATH. Please install Python 3.8+.
        pause
        exit /b 1
    )
)

if not exist .venv (
    echo [INFO] Virtual environment not found. Creating...
    %PYTHON_CMD% -m venv .venv
    echo [INFO] Installing requirements...
    call .venv\Scripts\activate
    pip install -r requirements.txt
) else (
    call .venv\Scripts\activate
)

echo [INFO] Starting Monitor...
echo.
python main.py

pause
