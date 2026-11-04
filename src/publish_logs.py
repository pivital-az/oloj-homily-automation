"""Publish sanitized run logs to the GitHub Pages site.

Why: the laptop's run logs (logs/run-*.log) are the only record of
what a Sunday run actually did - which services completed, which went
to review, and why a run failed. They live only on the laptop, so a
failed unattended run (Oct 25, Nov 1) could not be diagnosed from
outside. This module copies them, sanitized, into docs/logs (the
Pages site), where publish_pages.ps1 commits and pushes them.

PUBLIC-SITE WARNING: docs/ is served publicly on GitHub Pages.
Logs are therefore REDACTED before they are copied - see
sanitize_log_text. Never publish the raw logs/ folder, and never add
a log line containing a credential: the sanitizer is a safety net,
not a substitute for not logging secrets.

Usage (from the repo root, with the venv):
    .venv\\Scripts\\python.exe src\\publish_logs.py [--keep N]
run_pipeline.ps1 runs this automatically after every real (non-dry)
run, before publish_pages.ps1, so a failed run's log is published
too - that is the whole point.
"""
from __future__ import annotations

import argparse
import html
import os
import re
from pathlib import Path

from config import REPO_ROOT, Settings

DEFAULT_KEEP = 30

_IPV4_RE = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")
_PROFILE_RE = re.compile(r"C:\\Users\\[^\\/\s\"']+", re.IGNORECASE)
_PROFILE_FWD_RE = re.compile(r"C:/Users/[^/\s\"']+", re.IGNORECASE)
_EMAIL_RE = re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.]+\b")
_PASSWORD_RE = re.compile(r"(?i)(password\s*=\s*)\S+")
_TARGET_RE = re.compile(r"Target Sunday(?:\(s\))?:\s*(\d{4}-\d{2}-\d{2})")
_COMPLETED_RE = re.compile(r"Service \S+: completed")
_REVIEW_RE = re.compile(r"Service \S+: review")
_FAILED_RE = re.compile(r"Service \S+ FAILED")


def sanitize_log_text(text: str, settings: Settings | None = None) -> str:
    """Redact anything in a run log that must not go on a public page.

    Redacted: IPv4 addresses (the recorder's local address appears in
    FTP error messages), the Windows user-profile path (which names
    the laptop account), email addresses, and anything that looks like
    a password assignment. The recorder's configured host is also
    replaced literally, in case it is a hostname rather than an IP.
    Everything else - service ids, volumes, detection notes, error
    messages, Dropbox folder *names* - is kept, because that is what
    makes the log useful for troubleshooting.
    """
    out = text
    if settings is not None and settings.ftp_host:
        out = out.replace(settings.ftp_host, "[recorder-host]")
    out = _IPV4_RE.sub("[ip-redacted]", out)
    # Replacement via a function, not a string: a string replacement
    # would parse "\U" in "C:\Users\..." as a regex escape and crash.
    out = _PROFILE_RE.sub(lambda m: r"C:\Users\[user]", out)
    out = _PROFILE_FWD_RE.sub(lambda m: "C:/Users/[user]", out)
    out = _EMAIL_RE.sub("[email-redacted]", out)
    out = _PASSWORD_RE.sub(r"\1[redacted]", out)
    return out


def parse_log_summary(text: str) -> dict:
    """Small machine-readable summary for the logs index page."""
    target = _TARGET_RE.search(text)
    return {
        "target_sunday": target.group(1) if target else "",
        "completed": len(_COMPLETED_RE.findall(text)),
        "review": len(_REVIEW_RE.findall(text)),
        "failed": len(_FAILED_RE.findall(text)),
    }


def logs_dest_dir(settings: Settings) -> Path:
    """Where published logs live: next to feed.xml (docs/logs), or
    docs/logs in the repo when no podcast feed file is configured."""
    if settings.podcast_feed_file is not None:
        return settings.podcast_feed_file.parent / "logs"
    return REPO_ROOT / "docs" / "logs"


def _index_html(entries: list[dict], keep: int = DEFAULT_KEEP) -> str:
    rows = []
    for e in entries:
        rows.append(
            "<tr><td><a href=\"{file}\">{file}</a></td>"
            "<td>{target}</td><td>{completed}</td><td>{review}</td>"
            "<td>{failed}</td><td>{size_kb}</td></tr>".format(
                file=html.escape(e["file"]),
                target=html.escape(e["target_sunday"] or "—"),
                completed=e["completed"], review=e["review"],
                failed=e["failed"], size_kb=e["size_kb"],
            )
        )
    body = "\n".join(rows) if rows else (
        "<tr><td colspan=\"6\">No run logs published yet.</td></tr>"
    )
    return (
        "<!DOCTYPE html>\n<html lang=\"en\">\n<head>\n<meta charset=\"utf-8\">\n"
        "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">\n"
        "<title>Our Lady of Joy Homilies — Run Logs</title>\n"
        "<style>body{font-family:Georgia,serif;margin:2rem auto;max-width:52rem;"
        "padding:0 1rem;color:#222;line-height:1.6}"
        "table{border-collapse:collapse}td,th{border:1px solid #ccc;"
        "padding:.3rem .6rem;text-align:left}</style>\n</head>\n<body>\n"
        "<h1>Run Logs</h1>\n"
        "<p>One log per pipeline run, newest first. Logs are sanitized "
        "before publishing: IP addresses, the laptop account name, "
        "email addresses, and passwords are redacted. The newest "
        f"{keep} runs are kept; older logs are pruned.</p>\n"
        "<p><a href=\"../\">Back to Our Lady of Joy Homilies</a></p>\n"
        "<table>\n<tr><th>Log</th><th>Target Sunday</th>"
        "<th>Completed</th><th>Review</th><th>Failed</th>"
        "<th>Size (KB)</th></tr>\n"
        f"{body}\n</table>\n</body>\n</html>\n"
    )


def publish_logs(settings: Settings, keep: int = DEFAULT_KEEP) -> list[str]:
    """Copy (sanitized) run logs into the Pages docs/logs folder.

    Returns the filenames now present in docs/logs, newest first.
    Prunes to the newest `keep` logs so the Pages site does not grow
    without bound - logs are small, but a log per run, forever, is not
    free on a 1 GB site. Pruned files are deleted from docs/logs, so
    the next publish_pages run stages their deletion too.
    """
    if keep < 1:
        keep = 1
    dest_dir = logs_dest_dir(settings)
    dest_dir.mkdir(parents=True, exist_ok=True)

    sources = sorted(settings.log_dir.glob("run-*.log")) if settings.log_dir.exists() else []
    for src in sources:
        text = src.read_text(encoding="utf-8", errors="replace")
        dest = dest_dir / src.name
        sanitized = sanitize_log_text(text, settings)
        if not dest.exists() or dest.read_text(encoding="utf-8", errors="replace") != sanitized:
            dest.write_text(sanitized, encoding="utf-8")

    published = sorted(
        (p for p in dest_dir.glob("run-*.log") if p.is_file()),
        key=lambda p: p.name, reverse=True,
    )
    for stale in published[keep:]:
        stale.unlink()
    published = published[:keep]

    entries = []
    for p in published:
        summary = parse_log_summary(p.read_text(encoding="utf-8", errors="replace"))
        entries.append({
            "file": p.name,
            "target_sunday": summary["target_sunday"],
            "completed": summary["completed"],
            "review": summary["review"],
            "failed": summary["failed"],
            "size_kb": round(p.stat().st_size / 1024, 1),
        })
    (dest_dir / "index.html").write_text(_index_html(entries, keep=keep), encoding="utf-8")
    return [e["file"] for e in entries]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--keep", type=int,
                        default=int(os.environ.get("LOG_PUBLISH_KEEP", str(DEFAULT_KEEP))),
                        help=f"Newest run logs to keep on the Pages site (default {DEFAULT_KEEP})")
    args = parser.parse_args()
    settings = Settings.load()
    published = publish_logs(settings, keep=args.keep)
    print(f"[logs] Published {len(published)} run log(s) to {logs_dest_dir(settings)}")
    for name in published[:3]:
        print(f"[logs]   {name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
