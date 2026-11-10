#!/bin/zsh
# Set up this folder on a new Mac: check tools, install the Node dependency, and
# create config.json. Then fill in your own files (see README.md).
set -e
cd "$(dirname "$0")"

echo "== job-search setup =="
for tool in python3 node pdfinfo; do
  if command -v "$tool" >/dev/null 2>&1; then echo "ok:      $tool"
  else echo "MISSING: $tool (needed; pdfinfo comes from poppler: brew install poppler)"; fi
done
if [ -d "/Applications/Google Chrome.app" ]; then echo "ok:      Google Chrome"
else echo "MISSING: Google Chrome (needed to print the PDFs; set chrome_path in config.json if it lives elsewhere)"; fi

cd tools
if [ ! -d node_modules ]; then
  echo "installing the docx package (one time)..."
  npm install
else
  echo "ok:      tools/node_modules"
fi
cd ..

if [ ! -f config.json ]; then
  cp config.example.json config.json
  echo "created config.json from the example: edit it (worker_url, agent.runner)"
else
  echo "ok:      config.json already exists"
fi

if security find-generic-password -s job-alerts-worker -w >/dev/null 2>&1; then
  echo "ok:      Worker key in Keychain (service job-alerts-worker)"
else
  echo "note:    no Worker key in Keychain. LinkedIn alerts won't work until you add one (docs/linkedin-alerts.md)"
fi

for runner in opencode claude; do
  if command -v "$runner" >/dev/null 2>&1; then echo "ok:      $runner CLI"
  else echo "note:    no $runner CLI. If you don't have it, set agent.runner in config.json to \"manual\" (see docs/agents.md)"; fi
done

echo
echo "Done. Next, fill in your own files:"
echo "  resume/master.md        (the format the builders expect is in resume/README.md)"
echo "  AGENTS.md               (who you are, what you want, your rules)"
echo "  applicant-profile.md    (contact details and standard form answers)"
echo "  canned-answers.md       (your approved openers, proof blocks, closers)"
echo "  experience-bank.md      (approved facts beyond the resume)"
echo "  config.json             (worker_url, agent.runner)"
