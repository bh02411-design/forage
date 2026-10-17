@echo off
setlocal
cd /d "%~dp0"
where py >nul 2>nul
if %errorlevel% equ 0 (
    py -3 -c "import sys; assert sys.version_info >= (3,10)" >nul 2>nul
    if not errorlevel 1 (
        py -3 launcher.py --background --open
        if not errorlevel 1 goto end
    )
)
where python >nul 2>nul
if %errorlevel% equ 0 (
    python -c "import sys; assert sys.version_info >= (3,10)" >nul 2>nul
    if not errorlevel 1 (
        python launcher.py --background --open
        if not errorlevel 1 goto end
    )
)
echo Forage could not start. Install Python 3.10+ including pythonw.exe.
echo See the data folder's forage.log for tray startup errors.
pause
:end
