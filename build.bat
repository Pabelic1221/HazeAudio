@echo off
setlocal
cd /d "%~dp0"

echo === HazeAudio: build ===
where py >nul 2>nul
if errorlevel 1 goto nopython

if not exist .venv py -3.12 -m venv .venv
if errorlevel 1 goto nopython
call .venv\Scripts\activate.bat

python -m pip install --upgrade pip
rem Build from the pinned lock file when it exists (reproducible), otherwise from requirements.txt
if exist requirements.lock pip install -r requirements.lock
if not exist requirements.lock pip install -r requirements.txt
if errorlevel 1 goto fail
if not exist requirements.lock pip freeze > requirements.lock

pyinstaller --noconfirm --clean --windowed --name HazeAudio --icon icon.ico --add-data "icon.ico;." haze_audio.py
if errorlevel 1 goto fail

echo.
echo Built: dist\HazeAudio\HazeAudio.exe
set "ISCC=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
if exist "%ISCC%" "%ISCC%" installer.iss
if not exist "%ISCC%" echo Inno Setup not found - skipped installer. Get it free at jrsoftware.org to make Setup.exe
echo.
pause
exit /b 0

:nopython
echo Python 3.12 (64-bit) is required. Install it from python.org, tick "Add python.exe to PATH", then run this again.
pause
exit /b 1

:fail
echo Build failed - see messages above.
pause
exit /b 1
