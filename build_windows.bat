@echo off
setlocal
cd /d "%~dp0"

echo ============================================
echo  Ascend - Windows Build
echo ============================================
echo NOTE: This is a Phase 1 placeholder build script.
echo Full PyInstaller packaging (icons, resource bundling,
echo portable folder assembly) is completed in Phase 4.
echo.

if not exist ".venv\Scripts\activate.bat" (
    echo [ERROR] Virtual environment not found. Run setup.bat first.
    pause
    exit /b 1
)

call ".venv\Scripts\activate.bat"

echo [1/3] Running tests ...
pytest -q
if errorlevel 1 (
    echo [ERROR] Tests failed. Aborting build.
    pause
    exit /b 1
)

echo [2/3] Building with PyInstaller (folder-based build) ...
pyinstaller --noconfirm --windowed --name Ascend ^
    --paths . ^
    app.py
if errorlevel 1 (
    echo [ERROR] PyInstaller build failed.
    pause
    exit /b 1
)

echo [3/3] Build complete.
echo Output folder: dist\Ascend\
echo Launch dist\Ascend\Ascend.exe to test.
echo.
pause
endlocal
