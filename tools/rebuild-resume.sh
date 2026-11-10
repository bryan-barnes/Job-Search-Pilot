#!/bin/zsh
# Rebuild the one-page resume (.docx + .pdf) from resume/master.md and report the page count.
# The output base name is derived from the resume's "# Name" line (e.g. Alex-Q-Doe-Resume.pdf).
set -e
TOOLS=${0:A:h}
ROOT=${TOOLS:h}
MASTER="$ROOT/resume/master.md"
NAME=$(sed -n 's/^# //p' "$MASTER" | head -1)
if [ -z "$NAME" ]; then
  echo "No '# Name' line in $MASTER (it must be the first line)."
  exit 1
fi
STEM=$(echo "$NAME" | tr -cs 'A-Za-z0-9' '-' | sed 's/-*$//; s/^-*//')
BASE="${STEM}-Resume"
OUT=$(mktemp -d)
node "$TOOLS/build-resume.js" "$MASTER" "$OUT"
sleep 1
"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" --headless=new --disable-gpu --no-pdf-header-footer \
  --print-to-pdf="$OUT/$BASE.pdf" "file://$OUT/$BASE.html" 2>/dev/null
pdfinfo "$OUT/$BASE.pdf" | grep Pages
cp "$OUT/$BASE.docx" "$OUT/$BASE.pdf" "$ROOT/resume/"
echo "Saved to $ROOT/resume/$BASE.pdf and $BASE.docx"
