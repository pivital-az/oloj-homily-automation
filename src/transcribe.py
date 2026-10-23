"""Local transcription with faster-whisper (CPU, int8 by default).

Audio is decoded with ffmpeg and passed to the model as samples. That
avoids relying on PyAV's MP3 demuxer, which is the fragile part of the
faster-whisper install on Windows (see requirements.txt pin).

Quality notes (from reviewing real output with Stone, 2026-10-23):
the recorder's audio is QUIET (service means of -44 to -50 dB), and
Whisper + the Silero VAD both lose soft words on quiet input. So the
decode applies a peak-based gain boost, the VAD threshold is lowered
with generous speech padding so word onsets/offsets are not clipped,
and a short liturgical initial_prompt biases the model toward the
vocabulary a homily actually uses.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

import numpy as np

from audio import volume_levels
from config import Settings

_model_cache: dict[str, object] = {}

# Biases decoding toward Mass vocabulary (names, rites, scripture
# terms) - Stone's "stronger prompt" suggestion. Kept short: prompt
# tokens share the model's context window.
INITIAL_PROMPT = (
    "A homily at a Catholic Mass. Scripture, the Gospel, Eucharist, "
    "Communion, parish, priest, deacon, disciples, forgiveness, mercy, Amen."
)

TARGET_PEAK_DB = -1.0
MAX_GAIN_DB = 24.0


def gain_db_for_peak(peak_db: float) -> float:
    """Gain that lifts the loudest peak to TARGET_PEAK_DB, floored at
    0 (never attenuate) and capped so near-silent files are not
    boosted into amplified noise (the volume gate rejects those
    before transcription anyway)."""
    return max(0.0, min(MAX_GAIN_DB, TARGET_PEAK_DB - peak_db))


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


def _decode_16k_mono(path: Path, gain_db: float = 0.0) -> np.ndarray:
    cmd = ["ffmpeg", "-v", "error", "-i", str(path)]
    if gain_db > 0.5:
        cmd += ["-af", f"volume={gain_db:.1f}dB"]
    cmd += ["-f", "f32le", "-ac", "1", "-ar", "16000", "-"]
    raw = subprocess.run(cmd, capture_output=True, check=True).stdout
    return np.frombuffer(raw, dtype=np.float32)


def transcribe_file(settings: Settings, audio_path: Path, model_name: str) -> list[dict]:
    """Return segments: [{start, end, text, no_speech_prob}, ...]"""
    model = _load_model(settings, model_name)
    _mean_db, peak_db = volume_levels(audio_path)
    audio = _decode_16k_mono(audio_path, gain_db=gain_db_for_peak(peak_db))
    segments, _info = model.transcribe(
        audio,
        language=settings.whisper_language or None,
        beam_size=5,
        word_timestamps=True,
        vad_filter=True,
        vad_parameters={
            # Default threshold 0.5 discards borderline (quiet) speech
            # outright - heard as missing words. 0.35 keeps it, and the
            # padding keeps the VAD from clipping word edges.
            "threshold": 0.35,
            "min_speech_duration_ms": 250,
            "min_silence_duration_ms": 500,
            "speech_pad_ms": 600,
        },
        initial_prompt=INITIAL_PROMPT,
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
