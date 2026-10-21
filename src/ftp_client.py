"""FTP access to the Denon DN-900R on the local network (read-only use)."""
from __future__ import annotations

import ftplib
import time
from pathlib import Path

from config import Settings
from sunday import RemoteFile, parse_recorder_filename


class FtpRecorder:
    def __init__(self, settings: Settings):
        self.s = settings
        self._ftp: ftplib.FTP | None = None

    def __enter__(self) -> "FtpRecorder":
        # Embedded recorders have small, occasionally unresponsive FTP
        # servers (seen live: one run connects instantly, the next
        # times out at TCP connect). Retry a few times before failing.
        last_exc: Exception | None = None
        for attempt in range(3):
            ftp = ftplib.FTP()
            try:
                ftp.connect(self.s.ftp_host, self.s.ftp_port, timeout=self.s.ftp_timeout)
                ftp.login(self.s.ftp_user, self.s.ftp_password)
                if self.s.ftp_remote_dir and self.s.ftp_remote_dir != "/":
                    ftp.cwd(self.s.ftp_remote_dir)
                self._ftp = ftp
                return self
            except (OSError, ftplib.Error) as exc:
                last_exc = exc
                try:
                    ftp.close()
                except Exception:
                    pass
                if attempt < 2:
                    time.sleep(5)
        raise ConnectionError(
            f"Could not connect to the recorder at {self.s.ftp_host}:{self.s.ftp_port} "
            f"after 3 attempts ({last_exc}). Check the recorder is on and "
            "the laptop is on its network, then re-run."
        ) from last_exc

    def __exit__(self, *exc) -> None:
        if self._ftp:
            try:
                self._ftp.quit()
            except Exception:
                self._ftp.close()

    @property
    def ftp(self) -> ftplib.FTP:
        assert self._ftp is not None, "Use FtpRecorder as a context manager"
        return self._ftp

    def list_mp3s(self) -> list[RemoteFile]:
        sizes: dict[str, int] = {}
        try:
            for name, facts in self.ftp.mlsd():
                if name.lower().endswith(".mp3") and facts.get("type") == "file":
                    sizes[name] = int(facts.get("size", "0"))
        except ftplib.error_perm:
            # Older FTP servers without MLSD: fall back to NLST + SIZE.
            sizes = {}
            for name in self.ftp.nlst():
                if name.lower().endswith(".mp3"):
                    try:
                        sizes[name] = self.ftp.size(name) or 0
                    except ftplib.error_perm:
                        sizes[name] = 0

        out: list[RemoteFile] = []
        for name, size in sizes.items():
            start = parse_recorder_filename(name, self.s.recorder_filename_format)
            if start is None:
                # Unparseable names cannot be matched to a Sunday reliably.
                continue
            out.append(RemoteFile(name=name, size=size, start=start))
        return sorted(out, key=lambda f: f.start)

    def list_mp3s_in(self, directory: str) -> list[RemoteFile] | None:
        """List parseable MP3s in another directory, then return to the
        configured one. Returns None if the directory does not exist.
        Used by the FTP test to probe the DN-900R's usual storage
        folders (/SD1, /SD2, /USB1) when the configured one is empty."""
        try:
            home = self.ftp.pwd()
        except Exception:
            home = "/"
        try:
            self.ftp.cwd(directory)
        except ftplib.error_perm:
            return None
        try:
            return self.list_mp3s()
        finally:
            try:
                self.ftp.cwd(home)
            except Exception:
                pass

    def download(self, remote: RemoteFile, dest_dir: Path) -> Path:
        """Download if missing/different size. Waits until the remote size
        is stable, so a file still being written by the recorder is not
        grabbed half-finished."""
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest = dest_dir / remote.name
        if dest.exists() and remote.size and dest.stat().st_size == remote.size:
            return dest

        self._wait_until_stable(remote)
        tmp = dest.with_suffix(".part")
        with open(tmp, "wb") as fh:
            self.ftp.retrbinary(f"RETR {remote.name}", fh.write)
        tmp.replace(dest)
        return dest

    def _wait_until_stable(self, remote: RemoteFile, checks: int = 3, pause: float = 5.0) -> None:
        try:
            last = self.ftp.size(remote.name)
            for _ in range(checks):
                time.sleep(pause)
                current = self.ftp.size(remote.name)
                if current == last:
                    return
                last = current
        except ftplib.error_perm:
            return  # Server cannot report sizes; proceed with the download.
