@echo off
rem Double-click to open the job board with editing turned on.
rem Starts the local server if it isn't running, then opens the board in your browser.
cd /d "%~dp0"
set URL=http://127.0.0.1:8765/

rem Prefer the "py" launcher: a bare "python" can be the Microsoft Store shortcut.
set PY=python
where py >nul 2>nul && set PY=py -3

curl -s -o nul %URL%
if errorlevel 1 (
  echo Starting the board server...
  start "Job board server - close this window to stop the board" /min %PY% -X utf8 -I tools\board-server.py
  for /l %%i in (1,1,20) do (
    timeout /t 1 /nobreak >nul
    curl -s -o nul %URL% && goto open
  )
  echo The board didn't start. Run this to see why:
  echo   %PY% -X utf8 tools\board-server.py
  pause
  exit /b 1
)
:open
start "" %URL%
