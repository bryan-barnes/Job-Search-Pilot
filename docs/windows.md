# Windows

Everything in this repo runs on Windows. The setup wizard
(`python tools\setup-wizard.py`) knows about Windows and gives you Windows
instructions at every step; this page is the reference for the differences.

## What you need

| Tool | Why | Install |
|---|---|---|
| Python 3.10+ | All the scripts | `winget install Python.Python.3.12` (check "Add to PATH" in the installer) |
| Node.js 18+ | Builds the .docx files | `winget install OpenJS.NodeJS.LTS` |
| Google Chrome | Prints the PDFs | google.com/chrome, normal installer |
| poppler (pdfinfo) | Counts the PDF pages | `winget install oschwartz10612.Poppler` |

After installing, open a **new** terminal window (so the PATH picks up the new tools) and
run `python tools\setup-wizard.py`. The wizard checks each one and tells you if anything
is still missing.

## The differences from Mac

| Mac | Windows |
|---|---|
| `Open Job Board.command` (double-click) | `Open Job Board.bat` (double-click) |
| `zsh setup.sh` quick check | not needed - the wizard does everything |
| Worker key in the Keychain (service `job-alerts-worker`) | Worker key in `config.json` under `worker_token` (the wizard stores it; the file is gitignored, so it's safe) |
| `tools/rebuild-resume.sh` to rebuild the master resume's PDF | the wizard's step 5 does the same test build; or run the two commands below |
| `open <file>` from the board's buttons | `os.startfile` (the board handles this for you) |

The Chrome path is `C:\Program Files\Google\Chrome\Application\chrome.exe`; the wizard
detects it and writes it to `config.json`. If you installed Chrome for one user only, it
lives in `%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe` - put that path in
`config.json` under `chrome_path`.

## Rebuilding the master resume's PDF by hand (Windows)

```
cd tools
npm install                      (one time)
python -I ..\tools\setup-wizard.py   step 5 does the build for you
```

Or without the wizard, the two steps it runs are:

```
node tools\build-resume.js resume\master.md <some-folder>
"<chrome-path>" --headless=new --disable-gpu --no-pdf-header-footer ^
  --print-to-pdf=<some-folder>\Your-Name-Resume.pdf ^
  file:///<some-folder>/Your-Name-Resume.html
pdfinfo <some-folder>\Your-Name-Resume.pdf
```

(Replace `Your-Name` with whatever the first line of `resume/master.md` says, with
non-alphanumeric runs turned into hyphens.)

## Notes

- The board server listens only on `127.0.0.1:8765`, so it's not reachable from other
  machines. Windows Defender won't ask about it because it never accepts outside
  connections.
- `applications/`, `config.json`, and the resume PDFs are gitignored exactly as on Mac.
- If a terminal command complains about "execution policy" for a `.ps1` script, you don't
  need one - everything here is Python, `.bat`, or `.js`.
