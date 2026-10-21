"""Sunday-date and service-grouping logic.

Recorder files are chunks, e.g. DN-900R files are 10 minutes each:
    10182026080000_DN-900R.mp3   (starts Sun 2026-10-18 08:00)
    10182026081000_DN-900R.mp3   (starts 08:10, same service)
    10182026110000_DN-900R.mp3   (starts 11:00, a different service)

Files for the *latest Sunday* are grouped into services: chunks whose
start times follow the previous chunk within SERVICE_GAP_MINUTES belong
to the same service; a larger gap starts a new service. "All services
from the latest Sunday" therefore means one output per group, not one
output per Sunday and not one output per file.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta

# 14 digits (timestamp) followed by _<anything>.mp3
FILENAME_RE = re.compile(r"^(?P<stamp>\d{14})_.+\.mp3$", re.IGNORECASE)


@dataclass
class RemoteFile:
    name: str
    size: int | None
    start: datetime  # naive local time (parish timezone) from the filename

    @property
    def key(self) -> str:
        return f"{self.name}:{self.size}"


@dataclass
class Service:
    service_date: date
    start: datetime
    files: list[RemoteFile] = field(default_factory=list)

    @property
    def service_id(self) -> str:
        return self.start.strftime("%Y-%m-%d_%H%M")

    @property
    def label(self) -> str:
        return f"{self.service_date.isoformat()} {self.start.strftime('%H:%M')} service ({len(self.files)} file(s))"


def parse_recorder_filename(name: str, fmt: str = "%m%d%Y%H%M%S") -> datetime | None:
    match = FILENAME_RE.match(name)
    if not match:
        return None
    try:
        return datetime.strptime(match.group("stamp"), fmt)
    except ValueError:
        return None


def latest_sunday(today: date) -> date:
    """Most recent Sunday on or before `today` (Mon=0 ... Sun=6)."""
    days_since_sunday = (today.weekday() + 1) % 7
    return today - timedelta(days=days_since_sunday)


def files_for_date(files: list[RemoteFile], target: date) -> list[RemoteFile]:
    return sorted([f for f in files if f.start.date() == target], key=lambda f: f.start)


def group_into_services(files: list[RemoteFile], gap_minutes: int = 20) -> list[Service]:
    """Group time-ordered chunks for one date into services."""
    services: list[Service] = []
    for f in sorted(files, key=lambda x: x.start):
        if services:
            prev = services[-1].files[-1]
            gap = (f.start - prev.start).total_seconds() / 60.0
            if gap <= gap_minutes:
                services[-1].files.append(f)
                continue
        services.append(Service(service_date=f.start.date(), start=f.start, files=[f]))
    return services
