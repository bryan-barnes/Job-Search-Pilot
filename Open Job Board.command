#!/bin/bash
# Opens the job board with editing turned on.
#   Mac: double-click this file.
#   Linux: run it from a terminal in this folder:  ./"Open Job Board.command"
# Starts the local server if it isn't running, then opens the board in your browser.
cd "$(dirname "$0")" || exit 1
URL="http://127.0.0.1:${JOB_BOARD_PORT:-8765}/"
up() {
  if command -v curl >/dev/null 2>&1; then curl -s -o /dev/null "$URL"
  else python3 -c "import urllib.request as u; u.urlopen('$URL', timeout=2)" 2>/dev/null; fi
}
if ! up; then
  nohup python3 -X utf8 -I tools/board-server.py > board.log 2>&1 &
  disown 2>/dev/null
  for i in $(seq 1 25); do up && break; sleep 0.2; done
  if ! up; then
    echo "The board didn't start. Here's why (from board.log):"; tail -5 board.log; exit 1
  fi
fi
if [ "$(uname)" = "Darwin" ]; then
  open "$URL"
elif command -v xdg-open >/dev/null 2>&1 && xdg-open "$URL" >/dev/null 2>&1; then
  :
else
  echo "The board is running. Open $URL in your browser."
fi
