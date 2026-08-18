@echo off
echo === Media Downloader Windows Build ===
echo.

REM Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found. Install Python 3.12+ from https://python.org
    pause
    exit /b 1
)

REM Create venv and install deps
echo [1/4] Installing dependencies...
cd /d "%~dp0..\..\backend"
python -m venv .venv
call .venv\Scripts\activate.bat
pip install -r requirements.txt -q
pip install pyinstaller pywebview -q

REM Build exe
echo [2/4] Building exe...
cd /d "%~dp0"
pyinstaller build.spec --clean --noconfirm

echo.
echo [DONE] Build complete!
echo Output: %~dp0dist\MediaDownloader.exe
echo.
pause
