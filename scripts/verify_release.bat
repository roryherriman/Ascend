@echo off
setlocal EnableDelayedExpansion
cd /d "%~dp0.."

echo ============================================
echo  Ascend - Verify Release Build
echo ============================================
echo.

set PASS=0
set FAIL=0

call :check "dist\Ascend\Ascend.exe exists"                   "if exist dist\Ascend\Ascend.exe (exit /b 0) else (exit /b 1)"
call :check "Qt platform plugin exists"                        "if exist dist\Ascend\_internal\PySide6\plugins\platforms\qwindows.dll (exit /b 0) else (exit /b 1)"
call :check "Icons resource bundled"                           "if exist dist\Ascend\_internal\ascend\resources\icons\dashboard.svg (exit /b 0) else (exit /b 1)"
call :check "Class icons resource bundled"                     "if exist dist\Ascend\_internal\ascend\resources\class_icons (exit /b 0) else (exit /b 1)"
call :check "Demo report fixture bundled"                      "if exist dist\Ascend\_internal\ascend\resources\demo_report.json (exit /b 0) else (exit /b 1)"
call :check ".env absent from dist"                            "if not exist dist\Ascend\.env (exit /b 0) else (exit /b 1)"
call :check ".env absent from dist\_internal"                  "if not exist dist\Ascend\_internal\.env (exit /b 0) else (exit /b 1)"
call :check "No test databases in dist"                        "if not exist dist\Ascend\*.db (exit /b 0) else (exit /b 1)"
call :check "No ascend.db in dist\_internal"                   "if not exist dist\Ascend\_internal\ascend.db (exit /b 0) else (exit /b 1)"

REM Secret scan: grep for anything that looks like a credential in the Python archive
if exist ".venv\Scripts\python.exe" (
    .venv\Scripts\python.exe -c "
import zipfile, pathlib, sys
dist = pathlib.Path('dist/Ascend/_internal')
suspects = []
for z in dist.rglob('*.pkg'):
    with zipfile.ZipFile(z) as zf:
        for name in zf.namelist():
            data = zf.read(name)
            low = data.lower()
            for kw in [b'client_secret', b'accesstoken', b'webhook']:
                if kw in low:
                    suspects.append(name)
                    break
if suspects:
    print('POSSIBLE SECRET REFERENCES:', suspects[:5])
    sys.exit(1)
" 2>nul
    if errorlevel 1 (
        call :fail "Secret scan: no credential strings in bundled Python archive"
    ) else (
        call :pass "Secret scan: no credential strings in bundled Python archive"
    )
) else (
    echo [SKIP] Secret scan requires virtual environment
)

echo.
echo ============================================
echo  Results: !PASS! passed, !FAIL! failed
echo ============================================
if !FAIL! gtr 0 (
    echo Some checks FAILED. Review output above.
    exit /b 1
) else (
    echo All checks passed.
    exit /b 0
)

:check
set DESC=%~1
set CMD=%~2
cmd /c %CMD% >nul 2>&1
if errorlevel 1 (
    call :fail "%DESC%"
) else (
    call :pass "%DESC%"
)
goto :eof

:pass
set /a PASS+=1
echo [PASS] %~1
goto :eof

:fail
set /a FAIL+=1
echo [FAIL] %~1
goto :eof
