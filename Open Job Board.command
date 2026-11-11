#!/bin/zsh
# Double-click to open the job board with editing turned on.
# Starts the local server if it isn't running, then opens the board in your browser.
cd "$(dirname "$0")"
URL="http://127.0.0.1:8765/"
if ! curl -s -o /dev/null "$URL"; then
  nohup python3 -X utf8 -I tools/board-server.py > board.log 2>&1 &!
  for i in {1..25}; do curl -s -o /dev/null "$URL" && break; sleep 0.2; done
  if ! curl -s -o /dev/null "$URL"; then
    echo "The board didn't start. Here's why (from board.log):"; tail -5 board.log; exit 1
  fi
fi
open "$URL"
