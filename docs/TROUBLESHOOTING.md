# Troubleshooting

## Setup: "Python was not found; run without arguments to install from the Microsoft Store"

That message comes from the **Microsoft Store stub** — Windows ships
fake `python.exe`/`py.exe` app-execution aliases (in
`%LOCALAPPDATA%\Microsoft\WindowsApps`) that print that text instead
of running Python. Current versions of `setup_windows.ps1` detect and
ignore the stub. If you still land here:

1. Settings → Apps → Advanced app settings → **App execution aliases** —
   turn OFF `python.exe` and `python3.exe`.
2. Install Python from https://www.python.org/downloads/ (tick
   **"Add python.exe to PATH"**), or re-run the setup script, which
   installs Python 3.12 via winget.
3. Open a **new** PowerShell window and re-run
   `.\scripts\setup_windows.ps1`.

## Setup: Python installer fails with exit code 1603 (winget exit -1978335226)

1603 is the Windows Installer generic "fatal error during
installation." The download and hash check succeeded — the installer
itself refused. Most common causes, in order:

1. **A partial/broken earlier Python install is registered** (for
   example, from an interrupted setup). Remedy: reboot, then
   Settings → Apps → Installed apps → uninstall any **Python 3.12**
   and **Python Launcher** entries, then re-run setup. The setup
   script also tries this automatically (uninstall + `--force`
   retry) before giving up.
2. **A pending reboot / pending Windows install.** Reboot the laptop
   and re-run setup before trying anything else.
3. Something deeper — the real reason is in the Python installer's
   own log: open `%TEMP%` (Win+R, type `%TEMP%`), find the newest
   `Python 3.12.x (64-bit)_*.log`, and look at the last error lines
   (search for `error` / `0x`). The winget wrapper log path printed
   in the failure message points at winget's own diagnostics folder.

Manual fallback that bypasses winget: download
`python-3.12.10-amd64.exe` from python.org, run it, tick
**"Add python.exe to PATH"**, install for the current user, then
re-run `setup_windows.ps1` (it will find this Python and skip ahead
to the venv step).

## Setup or pipeline: "ffmpeg is not recognized" right after installing

winget updated the *registered* PATH, but the already-open
PowerShell window keeps its old PATH — winget even prints "Path
environment variable modified; restart your shell." The pipeline
wrappers (`run_pipeline.ps1`, `test_ftp.ps1`, `install_models.ps1`,
`publish_pages.ps1`) refresh PATH from the registry when they start,
and any new PowerShell window or scheduled-task run has it. When in
doubt: close and reopen PowerShell.

## ".venv\Scripts\python.exe is not recognized" during setup

The virtual environment was never (or only partially) created —
usually a side effect of the two Python issues above. Current setup
deletes and recreates an incomplete `.venv` and verifies
`.venv\Scripts\python.exe` exists before continuing. Fix Python
(see above), then re-run setup.

## FTP test failures (`.\scripts\test_ftp.ps1 -Download`)

The test prints one PASS/FAIL per layer — the first FAIL is the layer
to fix:

| Failing check | Likely cause |
| --- | --- |
| TCP connect | Laptop not on the recorder's network (check Wi-Fi/Ethernet), recorder off, wrong `FTP_HOST` |
| FTP login | Wrong `FTP_USER`/`FTP_PASSWORD` in `.env` (this recorder: user `Admin`, empty password) |
| List MP3 files | Wrong `FTP_REMOTE_DIR`, or the recorder's card has no recordings yet |
| Download newest file | Local disk/permissions issue in `work\ftp_test`, or the file is still being written on the recorder |
