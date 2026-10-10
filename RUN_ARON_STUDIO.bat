@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (echo Run SETUP_AND_RUN.bat first.&pause&exit /b 1)
start "" http://127.0.0.1:5188
call .venv\Scripts\python.exe app.py
pause
