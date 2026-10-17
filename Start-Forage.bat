@echo off
setlocal
cd /d "%~dp0"
where py >nul 2>nul
if %errorlevel% equ 0 (
    py -3 -c "import sys; assert sys.version_info >= (3,10)" >nul 2>nul
    if not errorlevel 1 (
        py -3 launcher.py --open
        goto end
    )
)
where python >nul 2>nul
if %errorlevel% equ 0 (
    python -c "import sys; assert sys.version_info >= (3,10)" >nul 2>nul
    if not errorlevel 1 (
        python launcher.py --open
        goto end
    )
)
echo.
echo Forage needs Python 3.10 or newer.
echo Install Python from https://www.python.org/downloads/windows/
echo Enable the Python launcher or Add Python to PATH during setup.
echo Then double-click Start-Forage.bat again.
echo.
:end
pause
