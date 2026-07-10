@echo off
REM Convenience wrapper — delegates to the full build pipeline.
REM For a clean build:     scripts\clean_build.bat
REM For portable only:     scripts\build_portable.bat
REM For installer:         scripts\build_installer.bat
REM For release verify:    scripts\verify_release.bat
call scripts\build_portable.bat
