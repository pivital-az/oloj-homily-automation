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

Only the standard library is used (tkinter ships with Python), so
there is nothing new to install on the parish laptop.
"""
from __future__ import annotations

import queue
import subprocess
import sys
import threading
import webbrowser
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from sunday import sundays_between  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parent.parent
RUN_PIPELINE = REPO_ROOT / "scripts" / "run_pipeline.ps1"
PAGES_LOGS_URL = "https://pivital-az.github.io/oloj-homily-automation/logs/"


def parse_date_str(text: str) -> date:
    """Parse a YYYY-MM-DD date, raising ValueError with a plain
    message (shown in the GUI) instead of a traceback."""
    text = (text or "").strip()
    try:
        return date.fromisoformat(text)
    except ValueError:
        raise ValueError(f"'{text}' is not a valid date - use YYYY-MM-DD.") from None


def build_run_args(mode: str, single: str = "", start: str = "",
                   end: str = "", force: bool = False,
                   dry_run: bool = False) -> list[str]:
    """The run_pipeline.ps1 arguments for the GUI's selections.

    Raises ValueError on anything that would make the run do the
    wrong thing or nothing at all: a bad date, a range with no
    Sunday, a start after its end. Mode is one of "latest",
    "single", "range".
    """
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
        root.title("OLOJ Homily Automation")
        root.geometry("760x560")

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
        self.run_btn = ttk.Button(buttons, text="Run", command=self.on_run)
        self.run_btn.pack(side="left", padx=(0, 8))
        self.stop_btn = ttk.Button(buttons, text="Stop", command=self.on_stop,
                                   state="disabled")
        self.stop_btn.pack(side="left", padx=(0, 8))
        ttk.Button(buttons, text="Open run logs online",
                   command=lambda: webbrowser.open(PAGES_LOGS_URL)).pack(side="left")
        self.status = ttk.Label(frame, text="Idle.")
        self.status.pack(anchor="w")

        # --- Output ------------------------------------------------
        self.output = scrolledtext.ScrolledText(frame, height=22, state="disabled")
        self.output.pack(fill="both", expand=True, pady=(8, 0))

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
        self.proc = subprocess.Popen(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, cwd=str(REPO_ROOT),
        )
        threading.Thread(target=self._reader, daemon=True).start()
        self.root.after(200, self._poll)

    def on_stop(self) -> None:
        if self.proc is not None and self.proc.poll() is None:
            self.proc.kill()
            self._append("\n[gui] Stopped by the user. "
                         "Already-completed services stay completed; "
                         "re-run to continue.\n")


def main() -> int:
    import tkinter as tk
    root = tk.Tk()
    Gui(root)
    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
