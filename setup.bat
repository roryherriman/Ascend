@echo off
setlocal enabledelayedexpansion
cd /d "%~dp0"

echo ============================================
echo  Ascend - Setup
echo ============================================
echo.

where python >nul 2>nul
if errorlevel 1 (
    echo [ERROR] Python was not found on PATH.
    echo Please install Python 3.11+ from https://www.python.org/downloads/
    echo and make sure "Add python.exe to PATH" is checked during install.
    pause
    exit /b 1
)

echo [1/5] Creating virtual environment in .venv ...
if not exist ".venv" (
    python -m venv .venv
    if errorlevel 1 (
        echo [ERROR] Failed to create the virtual environment.
        pause
        exit /b 1
    )
) else (
    echo       .venv already exists, skipping creation.
)

echo [2/5] Activating virtual environment ...
call ".venv\Scripts\activate.bat"
if errorlevel 1 (
    echo [ERROR] Failed to activate the virtual environment.
    pause
    exit /b 1
)

echo [3/5] Upgrading pip ...
python -m pip install --upgrade pip
if errorlevel 1 (
    echo [ERROR] Failed to upgrade pip.
    pause
    exit /b 1
)

echo [4/5] Installing requirements ...
pip install -r requirements.txt
if errorlevel 1 (
    echo [ERROR] Failed to install requirements.
    pause
    exit /b 1
)

echo [5/5] Running tests ...
pytest -q
if errorlevel 1 (
    echo.
    echo [WARNING] Some tests failed. Review the output above.
    echo You can still try launching the app with run_app.bat.
) else (
    echo.
    echo All tests passed.
)

echo.
echo ============================================
echo  Setup complete
echo ============================================
echo To launch the application, double-click run_app.bat
echo (or run "run_app.bat" from this folder).
echo.
pause
endlocal
