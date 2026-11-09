"""Desktop GUI for the OLOJ homily pipeline (Windows, tkinter).

Launch it from the desktop shortcut created by
scripts\\install_desktop_shortcut.ps1, or by hand:
    .\\scripts\\run_gui.ps1

What it does, and nothing more: it builds the same
scripts\\run_pipeline.ps1 command a person would type, and shows
that command's output live. The pipeline itself - FTP, transcription,
Dropbox publishing, podcast feed, run-log publishing - is unchanged,
so a GUI run and a scheduled run behave identically.

Controls:
  * Mode: Latest Sunday (the scheduled-task default), a single date,
    or a date range. A range runs every Sunday in the range, in one
    pipeline invocation; a range with no Sunday is refused with a
    plain message, because it would otherwise silently do nothing.
  * Force: reprocess services already marked completed in
    data\\state.json. Without it, completed services are skipped.
    This is the repair switch: e.g. single date 2026-09-13 + Force
    reprocesses the Sept 13 services, which is how the Sept 13 11:00
    Dropbox gap is closed (with the legacy-feed fix in spotify_rss,
    the reprocessed 11:00 replaces the old feed item instead of
    duplicating it).
  * Dry run: list the services the run would process, publish nothing.
  * Open recorder interface: opens the DN-900R's web interface in the
    default browser - the recorder at the FTP_HOST address from .env,
    over HTTP. This is where its power/network settings live.
  * Open Dropbox folder: opens the Dropbox web view of the homily
    folder (DROPBOX_HOMILY_DIR from .env), i.e. what was published.

Branding: the window wears the Our Lady of Joy colours - the deep
violet and gold of the parish icon (assets/oloj-icon.png, a gold
microphone in a stained-glass arch) on the warm cream of the
published homily pages, with a Georgia serif header like the site.

Only the standard library is used (tkinter ships with Python), so
there is nothing new to install on the parish laptop.
"""
from __future__ import annotations

import queue
import re
import subprocess
import sys
import threading
import webbrowser
from datetime import date
from pathlib import Path
from urllib.parse import quote

sys.path.insert(0, str(Path(__file__).resolve().parent))

from sunday import sundays_between  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parent.parent
RUN_PIPELINE = REPO_ROOT / "scripts" / "run_pipeline.ps1"
PAGES_LOGS_URL = "https://pivital-az.github.io/oloj-homily-automation/logs/"
DROPBOX_HOME_URL = "https://www.dropbox.com/home"

# Our Lady of Joy branding: deep violet + gold, sampled from the
# parish icon (assets/oloj-icon.png), on the warm cream of the
# published homily pages (docs/index.html).
PARISH_PURPLE = "#240043"
PARISH_GOLD = "#d9a441"
PARISH_CREAM = "#f7f1e3"
PARISH_INK = "#2e2438"
CONSOLE_BG = "#1d0033"
CONSOLE_FG = "#f3e9d2"


def parse_date_str(text: str) -> date:
    """Parse a YYYY-MM-DD date, raising ValueError with a plain
    message (shown in the GUI) instead of a traceback."""
    text = (text or "").strip()
    try:
        return date.fromisoformat(text)
    except ValueError:
        raise ValueError(f"'{text}' is not a valid date - use YYYY-MM-DD.") from None


def recorder_web_url(ftp_host: str) -> str:
    """Web-interface URL for the DN-900R: the FTP host, over HTTP.

    The recorder's web interface lives on the same address as its FTP
    server (FTP_HOST in .env, usually a bare IP like 10.16.10.232).
    A host that already carries a scheme is used as given."""
    host = (ftp_host or "").strip()
    if "://" in host:
        return host.rstrip("/") + "/"
    return f"http://{host}/"


def dropbox_web_url(dropbox_dir) -> str:
    """Dropbox web URL for the local homily folder.

    DROPBOX_HOMILY_DIR is a folder inside the laptop's Dropbox sync
    folder; on the web, the same folder is dropbox.com/home/<path
    below the Dropbox root>. The path below the first component that
    starts with "Dropbox" is that relative path (this also covers
    names like "Dropbox (Personal)"). Anything unrecognized - no
    dir configured, or no Dropbox component in it - falls back to
    the Dropbox home page rather than guessing a wrong folder."""
    if not dropbox_dir:
        return DROPBOX_HOME_URL
    parts = [p for p in re.split(r"[\\/]+", str(dropbox_dir)) if p]
    for i, part in enumerate(parts):
        if part.lower().startswith("dropbox"):
            rest = parts[i + 1:]
            if not rest:
                return DROPBOX_HOME_URL
            return DROPBOX_HOME_URL + "/" + "/".join(quote(p) for p in rest)
    return DROPBOX_HOME_URL


def build_run_args(mode: str, single: str = "", start: str = "",
                   end: str = "", force: bool = False,
                   dry_run: bool = False) -> list[str]:
    """The run_pipeline.ps1 arguments for the GUI's selections.

    Raises ValueError on anything that would make the run do the
    wrong thing or nothing at all: a bad date, a range with no
    Sunday, a start after its end. Mode is one of "latest",
    "single", "range"."""
    args: list[str] = []
    if mode == "latest":
        pass
    elif mode == "single":
        args += ["-Date", parse_date_str(single).isoformat()]
    elif mode == "range":
        start_d = parse_date_str(start)
        end_d = parse_date_str(end)
        if end_d < start_d:
            raise ValueError(f"End date {end_d} is before start date {start_d}.")
        sundays = sundays_between(start_d, end_d)
        if not sundays:
            raise ValueError(
                f"No Sunday in {start_d}..{end_d} - nothing would be processed. "
                "Pick a range containing a Sunday, or use a single date.")
        args += ["-Start", start_d.isoformat(), "-End", end_d.isoformat()]
    else:
        raise ValueError(f"Unknown mode: {mode!r}")
    if dry_run:
        args.append("-DryRun")
    if force:
        args.append("-Force")
    return args


def build_command(mode: str, single: str = "", start: str = "",
                  end: str = "", force: bool = False,
                  dry_run: bool = False) -> list[str]:
    """Full command line the GUI runs (powershell + run_pipeline)."""
    return (["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass",
             "-File", str(RUN_PIPELINE)]
            + build_run_args(mode, single, start, end, force, dry_run))


class Gui:
    def __init__(self, root):
        import tkinter as tk
        from tkinter import scrolledtext, ttk

        self.tk = tk
        self.root = root
        self.proc: subprocess.Popen | None = None
        self.output_queue: queue.Queue[str] = queue.Queue()
        root.title("Our Lady of Joy — Homily Automation")
        root.geometry("800x620")
        icon = REPO_ROOT / "assets" / "oloj-icon.ico"
        if icon.exists():
            try:
                root.iconbitmap(str(icon))
            except Exception:
                pass  # The icon is decoration; never block startup on it.
        self._apply_branding()

        # --- Header: parish banner ---------------------------------
        header = tk.Frame(root, bg=PARISH_PURPLE)
        header.pack(fill="x")
        tk.Label(header, text="OLOJ Homily Automation",
                 bg=PARISH_PURPLE, fg=PARISH_GOLD,
                 font=("Georgia", 16, "bold")).pack(anchor="w", padx=14, pady=(10, 0))
        tk.Label(header, text="Our Lady of Joy Roman Catholic Church · Carefree, AZ",
                 bg=PARISH_PURPLE, fg=PARISH_CREAM,
                 font=("Georgia", 10, "italic")).pack(anchor="w", padx=14, pady=(0, 10))

        frame = ttk.Frame(root, padding=12)
        frame.pack(fill="both", expand=True)

        # --- Mode -------------------------------------------------
        self.mode = tk.StringVar(value="latest")
        ttk.Label(frame, text="What to convert:").pack(anchor="w")
        modes = ttk.Frame(frame)
        modes.pack(anchor="w", pady=(0, 8))
        ttk.Radiobutton(modes, text="Latest Sunday", variable=self.mode,
                        value="latest").pack(side="left", padx=(0, 12))
        ttk.Radiobutton(modes, text="Single date", variable=self.mode,
                        value="single").pack(side="left", padx=(0, 12))
        ttk.Radiobutton(modes, text="Date range", variable=self.mode,
                        value="range").pack(side="left")

        # --- Dates ------------------------------------------------
        dates = ttk.Frame(frame)
        dates.pack(fill="x", pady=(0, 8))
        ttk.Label(dates, text="Date (YYYY-MM-DD):").grid(row=0, column=0, sticky="w")
        self.single_entry = ttk.Entry(dates, width=14)
        self.single_entry.grid(row=0, column=1, padx=6)
        self.single_entry.insert(0, date.today().isoformat())
        ttk.Label(dates, text="Start:").grid(row=1, column=0, sticky="w")
        self.start_entry = ttk.Entry(dates, width=14)
        self.start_entry.grid(row=1, column=1, padx=6)
        ttk.Label(dates, text="End:").grid(row=1, column=2, sticky="w")
        self.end_entry = ttk.Entry(dates, width=14)
        self.end_entry.grid(row=1, column=3, padx=6)
        ttk.Label(frame, text="A range runs every Sunday in it. Sundays are "
                  "the normal case; a single non-Sunday date processes "
                  "that day's recordings.").pack(anchor="w", pady=(0, 8))

        # --- Options ----------------------------------------------
        self.force_var = tk.BooleanVar(value=False)
        self.dry_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(frame, text="Force — reprocess services already "
                        "marked completed", variable=self.force_var).pack(anchor="w")
        ttk.Checkbutton(frame, text="Dry run — list services only, "
                        "publish nothing", variable=self.dry_var).pack(anchor="w")

        # --- Buttons + status --------------------------------------
        buttons = ttk.Frame(frame)
        buttons.pack(fill="x", pady=10)
        self.run_btn = ttk.Button(buttons, text="Run", command=self.on_run,
                                  style="Run.TButton")
        self.run_btn.pack(side="left", padx=(0, 8))
        self.stop_btn = ttk.Button(buttons, text="Stop", command=self.on_stop,
                                   state="disabled")
        self.stop_btn.pack(side="left", padx=(0, 8))
        ttk.Button(buttons, text="Open run logs online",
                   command=lambda: webbrowser.open(PAGES_LOGS_URL)).pack(side="left")
        ttk.Button(buttons, text="Open recorder interface",
                   command=self.on_open_recorder).pack(side="left", padx=(8, 0))
        ttk.Button(buttons, text="Open Dropbox folder",
                   command=self.on_open_dropbox).pack(side="left", padx=(8, 0))
        self.status = ttk.Label(frame, text="Idle.")
        self.status.pack(anchor="w")

        # --- Output ------------------------------------------------
        self.output = scrolledtext.ScrolledText(
            frame, height=22, state="disabled",
            bg=CONSOLE_BG, fg=CONSOLE_FG, insertbackground=PARISH_GOLD,
            font=("Consolas", 10))
        self.output.pack(fill="both", expand=True, pady=(8, 0))

    def _apply_branding(self) -> None:
        """OLOJ colours on the standard widgets (see palette above).

        ttk needs the "clam" theme before it will take custom colours
        on Windows; if a platform refuses the theme switch, the GUI
        still works, just in the platform's default dress."""
        import tkinter as tk
        from tkinter import ttk

        self.root.configure(bg=PARISH_CREAM)
        style = ttk.Style(self.root)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure("TFrame", background=PARISH_CREAM)
        style.configure("TLabel", background=PARISH_CREAM, foreground=PARISH_INK)
        style.configure("TRadiobutton", background=PARISH_CREAM, foreground=PARISH_INK)
        style.configure("TCheckbutton", background=PARISH_CREAM, foreground=PARISH_INK)
        style.configure("TButton", padding=(10, 4))
        style.configure("Run.TButton", background=PARISH_GOLD,
                        foreground=PARISH_PURPLE, font=("Segoe UI", 10, "bold"))
        style.map("Run.TButton",
                  background=[("active", "#eabd63"), ("disabled", "#d8c493")],
                  foreground=[("disabled", "#6f6558")])

    def _append(self, text: str) -> None:
        self.output.configure(state="normal")
        self.output.insert("end", text)
        self.output.see("end")
        self.output.configure(state="disabled")

    def _poll(self) -> None:
        while True:
            try:
                line = self.output_queue.get_nowait()
            except queue.Empty:
                break
            self._append(line)
        if self.proc is not None and self.proc.poll() is None:
            self.root.after(200, self._poll)
        elif self.proc is not None:
            code = self.proc.poll()
            self.proc = None
            self.run_btn.configure(state="normal")
            self.stop_btn.configure(state="disabled")
            self.status.configure(
                text=f"Finished (exit code {code})."
                + (" See the run log on the Pages logs page." if code == 0
                   else " Check the output above and the published run log."))
            self._append(f"\n[gui] Finished with exit code {code}.\n")

    def _reader(self) -> None:
        assert self.proc is not None and self.proc.stdout is not None
        for line in self.proc.stdout:
            self.output_queue.put(line)

    def on_run(self) -> None:
        from tkinter import messagebox
        try:
            cmd = build_command(
                self.mode.get(),
                single=self.single_entry.get(),
                start=self.start_entry.get(),
                end=self.end_entry.get(),
                force=self.force_var.get(),
                dry_run=self.dry_var.get(),
            )
        except ValueError as exc:
            messagebox.showerror("Check the dates", str(exc))
            return
        self._append(f"[gui] Running: {' '.join(cmd)}\n")
        self.status.configure(text="Running… (output below; this takes about 15 minutes per hour-long service)")
        self.run_btn.configure(state="disabled")
        self.stop_btn.configure(state="normal")
        # CREATE_NO_WINDOW: the pipeline's output is piped into this
        # window, so its powershell.exe needs no console of its own -
        # a stray console invites the same close-it-and-kill-the-run
        # accident the pythonw.exe launcher avoids (see run_gui.ps1).
        # The flag only exists on Windows; elsewhere this is 0.
        self.proc = subprocess.Popen(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, cwd=str(REPO_ROOT),
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        threading.Thread(target=self._reader, daemon=True).start()
        self.root.after(200, self._poll)

    def on_stop(self) -> None:
        if self.proc is not None and self.proc.poll() is None:
            self.proc.kill()
            self._append("\n[gui] Stopped by the user. "
                         "Already-completed services stay completed; "
                         "re-run to continue.\n")

    def on_open_recorder(self) -> None:
        """Open the DN-900R web interface (the FTP_HOST address)."""
        from tkinter import messagebox
        try:
            from config import Settings
            host = Settings.load().ftp_host
        except Exception as exc:
            messagebox.showerror("Recorder interface",
                                 f"Could not read the settings: {exc}")
            return
        if not host:
            messagebox.showerror(
                "Recorder interface",
                "FTP_HOST is not set in .env, so the recorder's address "
                "is unknown.")
            return
        webbrowser.open(recorder_web_url(host))

    def on_open_dropbox(self) -> None:
        """Open the Dropbox web view of the published homily folder."""
        from tkinter import messagebox
        try:
            from config import Settings
            dropbox_dir = Settings.load().dropbox_dir
        except Exception as exc:
            messagebox.showerror("Dropbox folder",
                                 f"Could not read the settings: {exc}")
            return
        webbrowser.open(dropbox_web_url(dropbox_dir))


def main() -> int:
    import tkinter as tk
    root = tk.Tk()
    Gui(root)
    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
