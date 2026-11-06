"""Download the local models this pipeline needs into MODELS_DIR.

Models (all run locally, nothing is sent to a cloud transcription API):
  * faster-whisper "small"  - Pass 1: transcribe a whole service to
    locate the homily.  HF repo: Systran/faster-whisper-small
  * faster-whisper "large-v3-turbo" - Pass 2: re-transcribe only
    the homily clip for the published transcript. Near-large-v3
    accuracy at about medium speed (809M params, 4-layer decoder).
    HF repo: mobiuslabsgmbh/faster-whisper-large-v3-turbo - note
    this is NOT a Systran repo: Systran publishes no turbo model,
    faster-whisper fetches it from mobiuslabsgmbh.
  * faster-whisper "medium" - still downloadable with --only medium
    as a fallback Pass 2 model.
    HF repo: Systran/faster-whisper-medium
  * faster-whisper "base"   - OPTIONAL Pass 1 speed option only:
    a smaller, faster model for detection (Pass 1 never publishes
    its transcript). It is NOT downloaded by default - the default
    stays small, and base must be tested on a saved service before
    it is set as WHISPER_PASS1_MODEL. Download it with --only base.
    HF repo: Systran/faster-whisper-base

The optional Ollama LLM is pulled separately by install_models.ps1
(it is a Windows app with its own model store, not a folder here).

Usage:
    .venv\\Scripts\\python.exe scripts\\install_models.py [--models-dir PATH]
                                                           [--only small|medium|base|large-v3-turbo]
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

MODELS = {
    "small": "Systran/faster-whisper-small",
    "medium": "Systran/faster-whisper-medium",
    "base": "Systran/faster-whisper-base",
    "large-v3-turbo": "mobiuslabsgmbh/faster-whisper-large-v3-turbo",
}

# What a plain run downloads. "base" is deliberately excluded: it is
# an opt-in Pass 1 experiment, not the pipeline default.
DEFAULT_MODELS = ("small", "large-v3-turbo")


def models_to_download(only: str | None) -> dict[str, str]:
    """The {name: repo} set for a run: one model with --only, else
    the defaults. Kept separate from main() so it is unit-testable
    without downloading anything."""
    if only is not None:
        return {only: MODELS[only]}
    return {name: MODELS[name] for name in DEFAULT_MODELS}


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

    wanted = models_to_download(args.only)
    for name, repo_id in wanted.items():
        download(name, repo_id, models_dir)

    print("[models] Done. The pipeline resolves models from this folder "
          "first, so transcription works offline after this step.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
