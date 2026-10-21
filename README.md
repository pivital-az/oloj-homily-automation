# oloj-homily-automation

**Our Lady of Joy** — pull the Sunday services from the Denon DN-900R
recorder over FTP, extract and transcribe each homily locally, publish
the homily as a parish blog post (Dropbox), and add it as a podcast
episode (RSS → Spotify).

All processing runs **locally on the parish Windows laptop**
(i5-1334U / 16 GB RAM / Iris Xe — CPU-only, int8). No audio is sent to
a cloud transcription or AI service. The only outbound steps are the
two publishing steps: Dropbox (parish site) and the podcast feed.

## How a run works

1. **FTP** — list MP3 chunks on the recorder; keep only chunks whose
   filename date (`MMDDYYYYHHMMSS_DN-900R.mp3`) is the **latest Sunday**.
2. **Group into services** — chunks 10 minutes apart are one service; a
   gap over `SERVICE_GAP_MINUTES` starts the next one. **All services
   from that Sunday are converted**, each producing its own homily,
   blog post, and episode.
3. **Download new chunks** (size-stable check, so a file still being
   written is never grabbed), stitch them into one service MP3.
4. **Volume gate** — a near-silent recording (mean < -50 dB by default)
   goes to `review\` with a reason file. It is never transcribed
   (Whisper hallucinates on silence) and never published.
5. **Pass 1 transcription** — `faster-whisper` **small**, CPU int8,
   whole service, with timestamps.
6. **Find the homily** — rule-based: after the Gospel closing, before
   the Creed / prayers of the faithful, with a duration sanity check
   and a confidence score. Optional local Ollama LLM can tighten the
   window (`ENABLE_OLLAMA`). Below `MIN_HOMILY_CONFIDENCE`, the service
   goes to `review\` instead of being published.
7. **Clip + Pass 2** — ffmpeg clip (re-encoded, loudness-normalised),
   then `faster-whisper` **medium** on the clip only for the final
   transcript quality.
8. **Blog post** — light professional formatting only (title,
   metadata for Our Lady of Joy, no homilist name, short web
   paragraphs, pull quote, Scripture references, excerpt). Written to
   the Dropbox folder **atomically** — adding a file there publishes
   it on the parish site.
9. **Spotify** — *via podcast RSS* (see `docs/SPOTIFY.md`: Spotify has
   no API to upload an MP3). The episode is added to the podcast feed;
   Spotify ingests it automatically after a one-time feed submission.
   The free hosting option is this repo's own GitHub Pages site
   (`docs/` folder) — see `docs/GITHUB_PAGES.md` for setup and the
   ~1 GB / ~65–100 episode capacity limit.
10. **State** — `data\state.json` marks the service completed, so
    scheduled re-runs skip it. Failures are logged to `logs\`.

Typical end-to-end time on the target laptop: ~25–40 minutes for a
70-minute service, unattended.

## Quick start (Windows, PowerShell)

> **Start here — before any `git` command.** A fresh laptop does not
> have git yet, so it cannot `git clone` this repo to get the setup
> script that installs git. Break the circle with winget, which ships
> with Windows 10/11:

```powershell
# 0. Install Git FIRST (PowerShell, no git required for this step)
winget install --id Git.Git --exact --accept-package-agreements --accept-source-agreements

#    Then CLOSE PowerShell and open a NEW one, so git is on PATH. Verify:
git --version
```

No winget? Two other git-free ways in: on the GitHub repo page use
**Code → Download ZIP** and extract it (skip the clone below, `cd` into
the extracted folder instead) — or fetch the one-file bootstrap, which
does the winget install, the clone, and the setup in order:

```powershell
Invoke-WebRequest -Uri "https://raw.githubusercontent.com/pivital-az/oloj-homily-automation/main/scripts/bootstrap_windows.ps1" -OutFile "$HOME\bootstrap_windows.ps1"
powershell -ExecutionPolicy Bypass -File "$HOME\bootstrap_windows.ps1"
```

Then, with git installed:

```powershell
git clone https://github.com/pivital-az/oloj-homily-automation.git
cd oloj-homily-automation

# 1. Install Python / FFmpeg (if missing; also Git, harmless if already
#    there), create folders (including .\models), create .venv,
#    install packages, seed .env
powershell -ExecutionPolicy Bypass -File .\scripts\setup_windows.ps1

# 2. Fill in .env  (FTP address + credentials, DROPBOX_HOMILY_DIR, ...)
notepad .env

# 3. Download the models into .\models  (small + medium, ~2 GB total)
.\scripts\install_models.ps1                # add -IncludeOllamaModel if using Ollama

# 4. Test the FTP connection to the recorder (uses the .env values).
#    PASS/FAIL per check: reachable -> login -> list -> parsed chunks
#    -> latest-Sunday grouping.  Add -Download to also pull the newest
#    file into work\ftp_test and verify its size.  Any value can be
#    overridden, e.g. first run before .env is filled in:
.\scripts\test_ftp.ps1 -Download
# .\scripts\test_ftp.ps1 -FtpHost <recorder-ip> -FtpUser <user> -FtpPassword "" -Download

# 5. See what would be processed for the latest Sunday (no downloads)
.\scripts\run_pipeline.ps1 -DryRun

# 6. One real run
.\scripts\run_pipeline.ps1

# 7. Background automation (Task Scheduler - Windows' cron):
#    Sundays 19:00 + Mondays 07:00 catch-up + a run 5 min after logon
.\scripts\install_service.ps1
```

**Restart-proof:** the scheduled tasks are stored by Windows and the
Task Scheduler service starts automatically at boot, so nothing needs
turning back on after a restart. If the laptop was off at a scheduled
time, `StartWhenAvailable` fires the missed run as soon as it is back,
and the logon catch-up task runs the (idempotent) pipeline 5 minutes
after the next sign-in — so a laptop that was off all Sunday still
processes that Sunday the next time anyone opens it. Tasks are also
allowed to run on battery and retry 3 times on failure. One limit:
with the default per-user install, a run can only start while that
user is logged on (see comments in `scripts\install_service.ps1` for
the auto-logon / SYSTEM alternatives).

Remove the automation with `.\scripts\uninstall_service.ps1`.

## Troubleshooting

Setup or FTP problems (Microsoft Store Python stub, installer error
1603, ffmpeg PATH, FTP check failures): see
[`docs/TROUBLESHOOTING.md`](docs/TROUBLESHOOTING.md).

## Layout

| Path | What it is |
|---|---|
| `scripts\setup_windows.ps1` | One-time install of tools, folders, venv, `.env` |
| `scripts\install_models.ps1` / `.py` | Download Whisper models into `.\models` |
| `scripts\run_pipeline.ps1` | Run one pass (what the scheduled tasks call) |
| `scripts\bootstrap_windows.ps1` | Cold start on a laptop with no git: installs Git via winget, clones, runs setup |
| `scripts\test_ftp.ps1` + `src\test_ftp.py` | FTP connection test: reachability, login, listing, grouping, optional 1-file pull |
| `scripts\install_service.ps1` | Register the Sunday/Monday/logon scheduled tasks (restart-proof) |
| `scripts\publish_pages.ps1` | Commit + push new episodes to GitHub Pages |
| `.env.example` | Every setting, documented. Copy to `.env` |
| `src\main.py` | One run: FTP → group → transcribe → clip → publish |
| `src\sunday.py` | Latest-Sunday math, filename parsing, service grouping |
| `src\homily_detect.py` | Homily location (rules + optional local LLM) |
| `src\blog.py` | Professional blog formatting (no rewriting) |
| `src\spotify_rss.py` | Podcast RSS episode publishing (→ Spotify) |
| `docs\SPOTIFY.md` | Why Spotify is RSS, and the one-time feed setup |
| `tests\` | Unit tests for the Sunday/grouping logic |

## Other commands

```powershell
.\scripts\run_pipeline.ps1 -Date 2026-10-18   # a specific Sunday
.\scripts\run_pipeline.ps1 -Force             # redo already-completed services
.venv\Scripts\python.exe -m unittest discover -s tests -v
```

## Safety rules built in

- Near-silent audio → `review\`, never published.
- Low homily-detection confidence → `review\`, never published.
- Dropbox writes are atomic and happen only at the very end.
- Re-runs are idempotent: completed services and existing RSS
  episodes (by GUID) are not duplicated.
- The real `.env` (FTP password, any API secrets) is gitignored.
