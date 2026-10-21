"""Download the local models this pipeline needs into MODELS_DIR.

Models (all run locally, nothing is sent to a cloud transcription API):
  * faster-whisper "small"  - Pass 1: transcribe a whole service to
    locate the homily.  HF repo: Systran/faster-whisper-small
  * faster-whisper "medium" - Pass 2: re-transcribe only the homily
    clip for the published transcript.
    HF repo: Systran/faster-whisper-medium

The optional Ollama LLM is pulled separately by install_models.ps1
(it is a Windows app with its own model store, not a folder here).

Usage:
    .venv\\Scripts\\python.exe scripts\\install_models.py [--models-dir PATH]
                                                           [--only small|medium]
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

MODELS = {
    "small": "Systran/faster-whisper-small",
    "medium": "Systran/faster-whisper-medium",
}


def download(name: str, repo_id: str, models_dir: Path) -> Path:
    from huggingface_hub import snapshot_download

    target = models_dir / f"faster-whisper-{name}"
    target.mkdir(parents=True, exist_ok=True)
    print(f"[models] {name}: {repo_id} -> {target}")
    snapshot_download(repo_id=repo_id, local_dir=str(target))
    marker = target / "model.bin"
    if not marker.exists():
        raise SystemExit(f"[models] ERROR: {marker} missing after download of {name}.")
    print(f"[models] {name}: OK ({marker.stat().st_size / 1e6:.0f} MB model.bin)")
    return target


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--models-dir",
        default=os.environ.get("MODELS_DIR", "models"),
        help="Folder that holds the model folders (default: ./models or $MODELS_DIR)",
    )
    parser.add_argument("--only", choices=sorted(MODELS), default=None)
    args = parser.parse_args()

    models_dir = Path(args.models_dir)
    if not models_dir.is_absolute():
        models_dir = (Path.cwd() / models_dir).resolve()
    models_dir.mkdir(parents=True, exist_ok=True)

    wanted = {args.only: MODELS[args.only]} if args.only else MODELS
    for name, repo_id in wanted.items():
        download(name, repo_id, models_dir)

    print("[models] Done. The pipeline resolves models from this folder "
          "first, so transcription works offline after this step.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
