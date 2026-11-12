# Windows

Everything runs on Windows 10 and 11. The setup wizard gives you Windows instructions at every
step; this page is the reference. (Every change is tested on Windows by the smoke test in
`tests/smoke.py`, which GitHub runs on Windows and Mac.)

## What you need

| Tool | Why | Install |
|---|---|---|
| Python 3.9+ | All the scripts | `winget install Python.Python.3.12`, or the installer from python.org (tick "Add python.exe to PATH") |
| Node.js 18+ | Builds the Word files | `winget install OpenJS.NodeJS.LTS`, or the LTS installer from nodejs.org |
| Google Chrome | Prints the PDFs | google.com/chrome, normal installer |

After installing, open a **new** terminal window (so it sees the new programs), go to the
folder, and run:

```
py tools\setup-wizard.py
```

`py` is the Python launcher that comes with Python. If `py` isn't found, use `python` instead.
If `python` opens the Microsoft Store, Python isn't installed yet (that's a Windows shortcut,
not Python): install it as above.

## Day to day

- Double-click **`Open Job Board.bat`** to open the board. It starts the board server in a
  small minimized window called "Job board server"; closing that window stops the board.
- Your Worker key (if you set up LinkedIn alerts) is stored in `config.json` under
  `worker_token`. That file is never committed. (On a Mac it goes in the Keychain instead.)
- To rebuild your master resume's PDF after editing it: `py tools\rebuild-resume.py`.
- Chrome is found automatically in Program Files or your user's AppData. If yours is
  elsewhere, put the full path to `chrome.exe` in `config.json` under `chrome_path`.

## Notes

- The board server listens only on `127.0.0.1:8765`, so it isn't reachable from other
  computers, and Windows Firewall has nothing to ask about.
- Files are read and written as UTF-8, so names like "Zoë" or "Núñez" work everywhere. If you
  edit your files in Notepad, that's fine (including Notepad's "UTF-8 with BOM").
- If PowerShell complains about "execution policy", you don't need a `.ps1` script:
  everything here is Python, `.bat`, or `.js`.
- If you use the `claude`, `codex`, or `opencode` runner, install it so it's on your PATH (see
  `docs/agents.md`); the board passes it the prompt safely on Windows.
