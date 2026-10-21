"""Local transcription with faster-whisper (CPU, int8 by default).

Audio is decoded with ffmpeg and passed to the model as samples. That
avoids relying on PyAV's MP3 demuxer, which is the fragile part of the
faster-whisper install on Windows (see requirements.txt pin).
"""
from __future__ import annotations

import subprocess
from pathlib import Path

import numpy as np

from config import Settings

_model_cache: dict[str, object] = {}


def _load_model(settings: Settings, model_name: str):
    from faster_whisper import WhisperModel

    ref = settings.model_ref(model_name)
    if ref not in _model_cache:
        _model_cache[ref] = WhisperModel(
            ref,
            device=settings.whisper_device,
            compute_type=settings.whisper_compute_type,
            cpu_threads=settings.whisper_cpu_threads,
        )
    return _model_cache[ref]


def _decode_16k_mono(path: Path) -> np.ndarray:
    cmd = ["ffmpeg", "-v", "error", "-i", str(path),
           "-f", "f32le", "-ac", "1", "-ar", "16000", "-"]
    raw = subprocess.run(cmd, capture_output=True, check=True).stdout
    return np.frombuffer(raw, dtype=np.float32)


def transcribe_file(settings: Settings, audio_path: Path, model_name: str) -> list[dict]:
    """Return segments: [{start, end, text, no_speech_prob}, ...]"""
    model = _load_model(settings, model_name)
    audio = _decode_16k_mono(audio_path)
    segments, _info = model.transcribe(
        audio,
        language=settings.whisper_language or None,
        beam_size=5,
        word_timestamps=True,
        vad_filter=True,
        vad_parameters={"min_silence_duration_ms": 500},
        condition_on_previous_text=False,
        no_speech_threshold=0.6,
    )
    return [
        {
            "start": float(s.start),
            "end": float(s.end),
            "text": s.text.strip(),
            "no_speech_prob": float(s.no_speech_prob),
        }
        for s in segments
        if s.text.strip()
    ]


def segments_to_text(segments: list[dict]) -> str:
    return " ".join(s["text"] for s in segments).strip()
