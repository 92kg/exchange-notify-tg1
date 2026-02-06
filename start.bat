@echo off
chcp 65001 > nul
echo ========================================================
echo   Crypto Sentiment Monitor v3.4 - Startup Script
echo ========================================================
echo.

if not exist .venv (
    echo [INFO] Virtual environment not found. Creating...
    python -m venv .venv
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
