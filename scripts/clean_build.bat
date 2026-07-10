@echo off
setlocal
cd /d "%~dp0.."

echo ============================================
echo  Ascend - Clean Build Output
echo ============================================
echo Removing build/, dist/, version_info.txt ...
echo NOTE: User data in %%LOCALAPPDATA%%\Ascend is never touched.
echo.

if exist "build\" (
    rmdir /s /q "build"
    echo Removed: build\
)
if exist "dist\" (
    rmdir /s /q "dist"
    echo Removed: dist\
)
if exist "version_info.txt" (
    del /q "version_info.txt"
    echo Removed: version_info.txt
)
if exist "Ascend-Portable*.zip" (
    del /q "Ascend-Portable*.zip"
    echo Removed: Ascend-Portable*.zip
)

echo.
echo Clean complete.
endlocal
