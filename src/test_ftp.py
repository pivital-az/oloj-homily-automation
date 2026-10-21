"""FTP connection test for the recorder - run this BEFORE the pipeline.

Checks, in order, with a clear PASS/FAIL line for each:
  1. TCP reachability of FTP_HOST:FTP_PORT (is the recorder on the LAN
     and is this laptop on the same network?)
  2. FTP login with FTP_USER / FTP_PASSWORD from .env
  3. Directory listing of FTP_REMOTE_DIR
  4. MP3 inventory: how many files parse as recorder chunks
     (MMDDYYYYHHMMSS_*.mp3), their dates, sizes, and how the latest
     Sunday groups into services
  5. With --download: pull ONE file (the newest) into
     work/ftp_test/ and verify the downloaded size matches the
     size the server reported - proof the pull path works end to end.

Values come from .env; any of them can be overridden on the command
line (handy for a first run before .env is filled in):

  python src/test_ftp.py --host 10.16.10.232 --user Admin --password ""
  python src/test_ftp.py --download

Exit code 0 = all checks passed, 1 = a check failed, 2 = bad config.
Nothing is uploaded, renamed, or deleted on the recorder - read-only.
"""
from __future__ import annotations

import argparse
import socket
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from config import Settings
from ftp_client import FtpRecorder
from sunday import files_for_date, group_into_services, latest_sunday, load_tz


def check(label: str, ok: bool, detail: str = "") -> bool:
    print(f"[{'PASS' if ok else 'FAIL'}] {label}" + (f" - {detail}" if detail else ""))
    return ok


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", help="Override FTP_HOST from .env")
    parser.add_argument("--port", type=int, help="Override FTP_PORT from .env")
    parser.add_argument("--user", help="Override FTP_USER from .env")
    parser.add_argument("--password", help="Override FTP_PASSWORD from .env (use \"\" for no password)")
    parser.add_argument("--remote-dir", help="Override FTP_REMOTE_DIR from .env")
    parser.add_argument("--download", action="store_true",
                        help="Also download the newest MP3 and verify its size")
    args = parser.parse_args()

    settings = Settings.load()
    if args.host:
        settings.ftp_host = args.host
    if args.port:
        settings.ftp_port = args.port
    if args.user is not None:
        settings.ftp_user = args.user
    if args.password is not None:
        settings.ftp_password = args.password
    if args.remote_dir:
        settings.ftp_remote_dir = args.remote_dir

    if not settings.ftp_host:
        print("[FAIL] No FTP host - set FTP_HOST in .env or pass --host.")
        return 2

    print(f"Testing FTP: {settings.ftp_host}:{settings.ftp_port} "
          f"user={settings.ftp_user!r} dir={settings.ftp_remote_dir!r}")

    # 1. TCP reachability
    try:
        with socket.create_connection((settings.ftp_host, settings.ftp_port),
                                      timeout=settings.ftp_timeout):
            pass
    except OSError as exc:
        check("TCP connect", False, f"{exc}. Is the laptop on the recorder's "
                                    "network, and is the recorder on?")
        return 1
    check("TCP connect", True)

    # 2-4. Login, list, parse
    try:
        with FtpRecorder(settings) as recorder:
            check("FTP login", True, f"as {settings.ftp_user!r}")
            files = recorder.list_mp3s()
            if not check("List MP3 files", bool(files),
                         f"{len(files)} parseable recorder MP3(s)" if files
                         else "connected, but no files matched MMDDYYYYHHMMSS_*.mp3"):
                return 1

            total_mb = sum((f.size or 0) for f in files) / 1e6
            print(f"       Oldest: {files[0].name} ({files[0].start})")
            print(f"       Newest: {files[-1].name} ({files[-1].start})")
            print(f"       Total:  {total_mb:.1f} MB across {len(files)} file(s)")

            from datetime import datetime
            target = latest_sunday(datetime.now(load_tz(settings.timezone)).date())
            sunday_files = files_for_date(files, target)
            services = group_into_services(sunday_files, settings.service_gap_minutes)
            print(f"       Latest Sunday {target}: {len(sunday_files)} file(s) "
                  f"-> {len(services)} service(s)")
            for service in services:
                print(f"         - {service.label}")

            # 5. Optional single-file pull test
            if args.download:
                newest = files[-1]
                dest_dir = settings.work_dir / "ftp_test"
                local = recorder.download(newest, dest_dir)
                size_ok = (not newest.size) or local.stat().st_size == newest.size
                if not check("Download newest file", size_ok,
                             f"{local} ({local.stat().st_size} bytes, "
                             f"server reported {newest.size})"):
                    return 1
    except Exception as exc:
        check("FTP session", False, str(exc))
        return 1

    verb = "pull from" if args.download else "list"
    print(f"\nFTP test PASSED - the pipeline can reach, read, and {verb} the recorder.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
