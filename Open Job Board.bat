@echo off
rem Double-click to open the job board with editing turned on.
rem Starts the local server if it isn't running, then opens the board in your browser.
cd /d "%~dp0"
set URL=http://127.0.0.1:8765/
curl -s -o nul %URL%
if errorlevel 1 (
  echo Starting the board server...
  start "job-board" /min python -I tools\board-server.py
  timeout /t 2 /nobreak >nul
)
start "" %URL%
