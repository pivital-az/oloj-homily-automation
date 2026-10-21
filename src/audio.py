"""Audio helpers built on ffmpeg/ffprobe (installed by setup_windows.ps1)."""
from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path


def _run(cmd: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, check=True)


def probe_duration_seconds(path: Path) -> float:
    result = _run([
        "ffprobe", "-v", "error", "-show_entries", "format=duration",
        "-of", "json", str(path),
    ])
    return float(json.loads(result.stdout)["format"]["duration"])


def volume_levels(path: Path) -> tuple[float, float]:
    """Return (mean_volume_db, max_volume_db) from ffmpeg volumedetect."""
    result = subprocess.run(
        ["ffmpeg", "-i", str(path), "-af", "volumedetect", "-vn", "-sn", "-dn",
         "-f", "null", "/dev/null" if Path("/dev/null").exists() else "NUL"],
        capture_output=True, text=True,
    )
    text = result.stderr
    mean = re.search(r"mean_volume:\s*(-?[\d.]+) dB", text)
    peak = re.search(r"max_volume:\s*(-?[\d.]+) dB", text)
    if not mean or not peak:
        raise RuntimeError(f"Could not read volume levels for {path}")
    return float(mean.group(1)), float(peak.group(1))


def concat_mp3s(chunks: list[Path], out_path: Path) -> Path:
    """Join recorder chunks (same codec settings) into one service file."""
    if len(chunks) == 1:
        out_path.write_bytes(chunks[0].read_bytes())
        return out_path
    list_file = out_path.with_suffix(".concat.txt")
    list_file.write_text(
        "".join(f"file '{p.as_posix()}'\n" for p in chunks), encoding="utf-8"
    )
    try:
        _run(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0",
              "-i", str(list_file), "-c", "copy", str(out_path)])
    finally:
        list_file.unlink(missing_ok=True)
    return out_path


def clip_mp3(source: Path, start_s: float, end_s: float, out_path: Path,
             pad_before_s: float = 2.0, pad_after_s: float = 2.0,
             loudnorm: bool = True) -> Path:
    """Cut [start-pad, end+pad], re-encoding for a precise cut.
    Re-encoding (not -c copy) is deliberate: copy cuts only land on
    MP3 frame boundaries and clip sentences."""
    start = max(0.0, start_s - pad_before_s)
    duration = (end_s + pad_after_s) - start
    cmd = ["ffmpeg", "-y", "-v", "error", "-ss", f"{start:.2f}",
           "-t", f"{duration:.2f}", "-i", str(source)]
    if loudnorm:
        cmd += ["-af", "loudnorm=I=-16:TP=-1.5:LRA=11"]
    # Speech, not music: mono 128 kbps CBR. Same quality where it
    # matters, ~0.96 MB/min, and it meets podcast bitrate requirements
    # (96-320 kbps) - size discipline matters if episodes are hosted
    # on GitHub Pages (1 GB site limit, see docs/GITHUB_PAGES.md).
    cmd += ["-ac", "1", "-codec:a", "libmp3lame", "-b:a", "128k", str(out_path)]
    _run(cmd)
    return out_path
