@echo off
setlocal
cd /d "%~dp0"
title ARON AI Video Studio V1 FREE
echo ============================================================
echo  ARON AI VIDEO STUDIO V1 - FREE ONLY
echo  Hard spending lock: PHP 0
echo ============================================================
where python >nul 2>nul || (echo [ERROR] Install Python 3.11+ and add it to PATH.&pause&exit /b 1)
where ffmpeg >nul 2>nul
if errorlevel 1 (
  echo [INFO] FFmpeg not found. Generation still works, but exact 1080x1920 export is skipped.
  echo Recommended: winget install --id Gyan.FFmpeg -e
)
if not exist ".venv\Scripts\python.exe" python -m venv .venv
call .venv\Scripts\python.exe -m pip install --upgrade pip
call .venv\Scripts\python.exe -m pip install -r requirements.txt
start "" http://127.0.0.1:5188
call .venv\Scripts\python.exe app.py
pause
