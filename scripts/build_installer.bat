@echo off
setlocal
cd /d "%~dp0.."

echo ============================================
echo  Ascend - Build Windows Installer
echo ============================================
echo.

REM -- Verify portable build exists --------------------------------------------
if not exist "dist\Ascend\Ascend.exe" (
    echo [ERROR] Portable build not found at dist\Ascend\Ascend.exe
    echo Run scripts\build_portable.bat first.
    pause
    exit /b 1
)

REM -- Locate Inno Setup compiler ----------------------------------------------
set ISCC=
if exist "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" (
    set ISCC=C:\Program Files (x86)\Inno Setup 6\ISCC.exe
) else if exist "C:\Program Files\Inno Setup 6\ISCC.exe" (
    set ISCC=C:\Program Files\Inno Setup 6\ISCC.exe
)

if "%ISCC%"=="" (
    echo [ERROR] Inno Setup 6 not found.
    echo Download from https://jrsoftware.org/isdl.php and install, then re-run.
    pause
    exit /b 1
)

REM -- Get version from metadata -----------------------------------------------
if not exist ".venv\Scripts\activate.bat" (
    echo [ERROR] Virtual environment not found. Run setup.bat first.
    pause
    exit /b 1
)
call ".venv\Scripts\activate.bat"
for /f "tokens=*" %%v in ('python -c "from ascend.metadata import APP_VERSION; print(APP_VERSION)"') do set VERSION=%%v

echo Building installer for Ascend v%VERSION% ...
echo.

REM -- Compile installer -------------------------------------------------------
"%ISCC%" /DAppVersion=%VERSION% "installer\ascend.iss"
if errorlevel 1 (
    echo [ERROR] Inno Setup compilation failed.
    pause
    exit /b 1
)

REM -- Checksum ----------------------------------------------------------------
set INSTALLER=installer\Output\Ascend-Setup-%VERSION%.exe
if exist "%INSTALLER%" (
    powershell -NoProfile -Command ^
        "$hash = (Get-FileHash '%INSTALLER%' -Algorithm SHA256).Hash; " ^
        "\"$hash  Ascend-Setup-%VERSION%.exe\" | Out-File -Encoding ascii 'SHA256SUMS.txt' -Append"
    echo Installer checksum appended to SHA256SUMS.txt
)

echo.
echo ============================================
echo  INSTALLER BUILD COMPLETE
echo ============================================
echo Installer: %INSTALLER%
echo.
pause
endlocal
