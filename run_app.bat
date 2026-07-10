@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\activate.bat" (
    echo [ERROR] Virtual environment not found. Run setup.bat first.
    pause
    exit /b 1
)

call ".venv\Scripts\activate.bat"

rem Development mode: this batch launcher keeps the console window open so you
rem can see log/print output and tracebacks while the GUI runs. The packaged
rem Ascend.exe built by build_windows.bat runs windowed with no
rem console, since it is meant for normal end-user double-click use.
if not exist "logs" mkdir "logs"
set ASCEND_DEV=1

echo Launching Ascend (development mode - console log active)...
python app.py
set EXITCODE=%ERRORLEVEL%

if not "%EXITCODE%"=="0" (
    echo.
    echo Application exited with code %EXITCODE%.
    pause
)

endlocal
