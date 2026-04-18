@echo off
:: Check for Administrator privileges
net session >nul 2>&1
if %errorLevel% neq 0 (
    echo Requesting Administrator privileges (required for game input)...
    powershell -Command "Start-Process '%~dpnx0' -Verb RunAs"
    exit /b
)

echo ========================================
echo   WWM Music Auto-Player Launcher
echo ========================================
echo.
cd /d "%~dp0"

REM Check if Python is available
python --version >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Python not found!
    echo.
    echo Please install Python 3.8+ from https://python.org
    echo Make sure to check "Add Python to PATH" during installation.
    echo.
    pause
    exit /b 1
)

REM Check if core dependencies are installed
python -c "import pynput; import mido" >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [INFO] Installing core dependencies...
    echo.
    pip install -r requirements.txt
    echo.
    if %ERRORLEVEL% NEQ 0 (
        echo [ERROR] Failed to install dependencies!
        echo Please run manually: pip install -r requirements.txt
        echo.
        pause
        exit /b 1
    )
    echo [OK] Dependencies installed successfully!
    echo.
)

echo Starting application...
echo.

REM Launch with standard python (console will be auto-hidden by script immediately)
REM This ensures better compatibility with games requiring elevated privileges
python main.py
