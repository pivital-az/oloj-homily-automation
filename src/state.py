"""Processed-state tracking (JSON). Makes runs idempotent:
a service that already completed is skipped, and remote files are not
re-downloaded or re-published on the next scheduled run."""
from __future__ import annotations

import json
from pathlib import Path


class State:
    def __init__(self, path: Path):
        self.path = path
        self.data: dict = {"services": {}}
        if path.exists():
            try:
                self.data = json.loads(path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                self.data = {"services": {}}
        self.data.setdefault("services", {})

    def service_done(self, service_id: str) -> bool:
        return self.data["services"].get(service_id, {}).get("status") == "completed"

    def mark_service(self, service_id: str, status: str, details: dict) -> None:
        self.data["services"][service_id] = {"status": status, **details}
        self.save()

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(self.data, indent=2), encoding="utf-8")
        tmp.replace(self.path)
