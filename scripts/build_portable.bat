@echo off
setlocal
cd /d "%~dp0.."

echo ============================================
echo  Ascend - Build Portable Folder
echo ============================================
echo.

REM -- Activate virtual environment -------------------------------------------
if not exist ".venv\Scripts\activate.bat" (
    echo [ERROR] Virtual environment not found.
    echo Run setup.bat first to create the environment and install dependencies.
    pause
    exit /b 1
)
call ".venv\Scripts\activate.bat"

REM -- Install / verify build-only dependencies --------------------------------
echo [1/6] Installing build dependencies ...
pip install -q -r requirements-build.txt
if errorlevel 1 (
    echo [ERROR] Failed to install build dependencies.
    pause
    exit /b 1
)

REM -- Run tests ---------------------------------------------------------------
echo [2/6] Running tests ...
set QT_QPA_PLATFORM=offscreen
pytest -q --tb=short
if errorlevel 1 (
    echo [ERROR] Tests failed. Aborting build.
    pause
    exit /b 1
)
set QT_QPA_PLATFORM=

REM -- Generate Windows version-info resource ----------------------------------
echo [3/6] Generating version info ...
python scripts\generate_version_info.py
if errorlevel 1 (
    echo [ERROR] Version info generation failed.
    pause
    exit /b 1
)

REM -- Build with PyInstaller --------------------------------------------------
echo [4/6] Building with PyInstaller ...
pyinstaller --noconfirm Ascend.spec
if errorlevel 1 (
    echo [ERROR] PyInstaller build failed.
    pause
    exit /b 1
)

REM -- Validate Qt platform plugin loaded --------------------------------------
echo [5/6] Validating build output ...
if not exist "dist\Ascend\Ascend.exe" (
    echo [ERROR] dist\Ascend\Ascend.exe not found after build.
    pause
    exit /b 1
)
if not exist "dist\Ascend\_internal\PySide6\plugins\platforms\qwindows.dll" (
    echo [WARNING] Qt platform plugin qwindows.dll not found at expected path.
    echo           The build may still work - check dist\Ascend\ manually.
)

REM -- Produce ZIP archive and checksums ---------------------------------------
echo [6/6] Packaging portable ZIP ...
for /f "tokens=*" %%v in ('python -c "from ascend.metadata import APP_VERSION; print(APP_VERSION)"') do set VERSION=%%v
set ARCHIVE=Ascend-Portable-%VERSION%.zip

REM Use PowerShell to zip the dist\Ascend folder
powershell -NoProfile -Command "Compress-Archive -Path 'dist\Ascend\*' -DestinationPath '%ARCHIVE%' -Force"
if errorlevel 1 (
    echo [WARNING] ZIP archive creation failed. The dist\Ascend\ folder is still usable.
) else (
    echo Created: %ARCHIVE%
    REM Generate SHA-256 checksum
    powershell -NoProfile -Command ^
        "$hash = (Get-FileHash '%ARCHIVE%' -Algorithm SHA256).Hash; " ^
        "\"$hash  %ARCHIVE%\" | Out-File -Encoding ascii 'SHA256SUMS.txt' -Append"
    echo Checksum appended to SHA256SUMS.txt
)

echo.
echo ============================================
echo  BUILD COMPLETE
echo ============================================
echo Portable folder : dist\Ascend\
echo Portable ZIP    : %ARCHIVE%
echo.
echo To test: run dist\Ascend\Ascend.exe
echo To build installer: run scripts\build_installer.bat
echo.
pause
endlocal
