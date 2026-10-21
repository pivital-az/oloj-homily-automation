"""Locate the homily inside a full-service transcript.

Strategy (rules first, optional local LLM second - never a cloud call):
  1. The homily starts after the Gospel. Find the LAST Gospel closing
     formula before sustained teaching speech ("the gospel of the lord"
     / "praise to you, lord jesus christ"). Using the last one avoids
     clipping the Gospel reading itself when the homily later quotes it
     (the example homily summarises the Gospel parable at length).
  2. The homily ends at the first post-homily liturgy marker: the Creed
     ("i believe in one god"), the prayers of the faithful, or the
     homily's own closing transition ("as we continue with this mass" /
     "as we continue our celebration") - in that last case the homily
     ends at the end of that paragraph.
  3. Sanity checks: duration 3-35 minutes and sustained single-topic
     speech raise/lower a confidence score. Below the configured
     threshold the caller must route the service to review instead of
     publishing.
  4. If Ollama is enabled, the rule-based window is sent (in timestamped
     chunks) to the local LLM, which may tighten the start/end. Any LLM
     failure or unparseable answer falls back to the rules untouched.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass

from config import Settings

GOSPEL_END_MARKERS = (
    "gospel of the lord",
    "praise to you lord jesus christ",
    "praise to you, lord jesus christ",
)
HOMILY_CLOSE_MARKERS = (
    "as we continue with this mass",
    "as we continue our celebration",
    "as we continue this celebration",
)
POST_HOMILY_MARKERS = (
    "i believe in one god",
    "i believe in one, holy, catholic",
    "let us pray for",
    "prayers of the faithful",
    "lord, hear our prayer",
)


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", text.lower().strip())


@dataclass
class HomilySpan:
    start_s: float
    end_s: float
    confidence: float
    method: str
    notes: list[str]

    @property
    def duration_s(self) -> float:
        return self.end_s - self.start_s


def _find_last_marker(segments: list[dict], markers: tuple[str, ...],
                      before_s: float | None = None) -> int | None:
    found = None
    for i, seg in enumerate(segments):
        if before_s is not None and seg["start"] > before_s:
            break
        if any(m in _norm(seg["text"]) for m in markers):
            found = i
    return found


def _find_first_marker(segments: list[dict], markers: tuple[str, ...],
                       from_index: int) -> int | None:
    for i in range(from_index, len(segments)):
        if any(m in _norm(segments[i]["text"]) for m in markers):
            return i
    return None


def detect_homily_rules(segments: list[dict]) -> HomilySpan | None:
    if not segments:
        return None
    notes: list[str] = []
    confidence = 0.35

    gospel_idx = _find_last_marker(segments, GOSPEL_END_MARKERS)
    if gospel_idx is None:
        notes.append("No Gospel closing formula found; using first sustained speech as a guess.")
        start_idx = 0
        confidence -= 0.15
    else:
        start_idx = gospel_idx + 1
        notes.append(f"Start set after Gospel closing at {segments[gospel_idx]['end']:.0f}s.")
        confidence += 0.25
    if start_idx >= len(segments):
        return None

    close_idx = _find_first_marker(segments, HOMILY_CLOSE_MARKERS, start_idx)
    post_idx = _find_first_marker(segments, POST_HOMILY_MARKERS, start_idx)

    if post_idx is not None and (close_idx is None or post_idx < close_idx):
        end_idx = post_idx - 1
        notes.append(f"End set before post-homily marker at {segments[post_idx]['start']:.0f}s.")
        confidence += 0.20
    elif close_idx is not None:
        # Include the closing paragraph the homilist is speaking in.
        end_idx = close_idx
        notes.append(f"End set at homily closing transition at {segments[close_idx]['start']:.0f}s.")
        confidence += 0.20
    else:
        end_idx = len(segments) - 1
        notes.append("No end marker found; homily assumed to run to a later break - review advised.")
        confidence -= 0.10

    if end_idx < start_idx:
        return None

    span = HomilySpan(
        start_s=float(segments[start_idx]["start"]),
        end_s=float(segments[end_idx]["end"]),
        confidence=max(0.0, min(1.0, confidence)),
        method="rules",
        notes=notes,
    )
    minutes = span.duration_s / 60.0
    if 3 <= minutes <= 35:
        span.confidence = min(1.0, span.confidence + 0.10)
        span.notes.append(f"Duration {minutes:.1f} min is in the expected homily range.")
    else:
        span.confidence = max(0.0, span.confidence - 0.20)
        span.notes.append(f"Duration {minutes:.1f} min is OUTSIDE the expected 3-35 min range.")
    return span


def refine_with_ollama(settings: Settings, segments: list[dict],
                       span: HomilySpan) -> HomilySpan:
    """Optional local-LLM tightening of the rule-based window."""
    try:
        import requests

        window = [s for s in segments if span.start_s - 120 <= s["start"] <= span.end_s + 120]
        transcript = "\n".join(f"[{s['start']:.0f}] {s['text']}" for s in window)
        prompt = (
            "You are locating a Catholic homily inside a Mass transcript.\n"
            "The homily is sustained reflective teaching by one speaker, "
            "beginning after the Gospel and ending before the Creed or "
            "the prayers of the faithful. It often opens by referring to "
            "\"today's first reading\" or \"today's Gospel\" and may close "
            "with \"As we continue with this Mass, let us ask...\".\n"
            "Reply with ONLY JSON: {\"start\": <seconds>, \"end\": <seconds>}\n\n"
            f"Timestamped transcript:\n{transcript}"
        )
        resp = requests.post(
            f"{settings.ollama_host}/api/generate",
            json={"model": settings.ollama_model, "prompt": prompt, "stream": False},
            timeout=600,
        )
        resp.raise_for_status()
        match = re.search(r"\{.*\}", resp.json().get("response", ""), re.DOTALL)
        if not match:
            return span
        data = json.loads(match.group(0))
        start, end = float(data["start"]), float(data["end"])
        if 0 <= start < end and (end - start) >= 120:
            return HomilySpan(start, end, min(1.0, span.confidence + 0.10),
                              "rules+ollama", span.notes + ["Window tightened by local LLM."])
    except Exception as exc:  # LLM is optional - never fail the run for it.
        span.notes.append(f"Ollama refinement skipped: {exc}")
    return span


def detect_homily(settings: Settings, segments: list[dict]) -> HomilySpan | None:
    span = detect_homily_rules(segments)
    if span is not None and settings.enable_ollama:
        span = refine_with_ollama(settings, segments, span)
    return span
