"""Publishing.

Dropbox rule (from the parish): a file added to DROPBOX_HOMILY_DIR shows
up on the parish site. Writing there IS publishing, so:
  * work happens in LOCAL_WORK_DIR / REVIEW_DIR first;
  * a post is only copied to Dropbox when it is finished and passed its
    checks, and the copy is atomic (write to a temp name in the same
    folder, then rename), so the site never sees a half-written file.
"""
from __future__ import annotations

import os
import shutil
from pathlib import Path

from config import Settings


def atomic_write(dest: Path, content: str) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_name(dest.name + ".tmp")
    tmp.write_text(content, encoding="utf-8")
    os.replace(tmp, dest)
    return dest


def atomic_copy(source: Path, dest: Path) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_name(dest.name + ".tmp")
    shutil.copyfile(source, tmp)
    os.replace(tmp, dest)
    return dest


def publish_to_dropbox(settings: Settings, folder_name: str,
                       blog_markdown: str, blog_filename: str,
                       homily_mp3: Path, transcript_text: str) -> Path:
    if settings.dropbox_dir is None:
        raise RuntimeError("DROPBOX_HOMILY_DIR is not set - cannot publish.")
    target_dir = settings.dropbox_dir / folder_name
    target_dir.mkdir(parents=True, exist_ok=True)
    atomic_write(target_dir / blog_filename, blog_markdown)
    atomic_copy(homily_mp3, target_dir / homily_mp3.name)
    atomic_write(target_dir / "homily_transcript.txt", transcript_text)
    return target_dir


def save_to_review(settings: Settings, folder_name: str, reason: str,
                   files: dict[str, str | Path]) -> Path:
    """Anything that must NOT be published lands here, with the reason."""
    target_dir = settings.review_dir / folder_name
    target_dir.mkdir(parents=True, exist_ok=True)
    atomic_write(target_dir / "REVIEW_REASON.txt", reason + "\n")
    for name, content in files.items():
        if isinstance(content, Path):
            if content.exists():
                shutil.copyfile(content, target_dir / name)
        else:
            atomic_write(target_dir / name, content)
    return target_dir
