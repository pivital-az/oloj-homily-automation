"""Format a cleaned homily transcript as a professional blog post.

Light formatting only: the homilist's words are not rewritten. The
formatting adds a title, metadata, short web paragraphs, a pull quote
and (optionally, via the local LLM) subheadings. If no LLM title is
available, the title falls back to "Homily for <date> — <Mass time>" -
accurate and professional, never invented theology.
"""
from __future__ import annotations

import json
import re
from datetime import date, datetime

from config import Settings

BOOKS = [
    "Genesis", "Exodus", "Isaiah", "Jeremiah", "Ezekiel", "Daniel",
    "Sirach", "Psalms", "Proverbs", "Wisdom",
    "Matthew", "Mark", "Luke", "John", "Acts",
    "Romans", "Corinthians", "Galatians", "Ephesians", "Philippians",
    "Colossians", "Thessalonians", "Timothy", "Titus", "Hebrews",
    "James", "Peter", "Revelation",
]


def _yaml(value: str) -> str:
    """Quote a scalar for the front matter. Titles/excerpts come from a
    local LLM or transcript text and may contain quotes - escape them so
    the parish site's YAML parser does not break."""
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def slugify(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return slug or "homily"


def paragraphs_from_segments(segments: list[dict],
                             pause_s: float = 1.4, max_words: int = 90) -> list[str]:
    """Group transcript segments into readable paragraphs: break on a
    real pause in speech, or when a paragraph gets long for the web."""
    paragraphs: list[str] = []
    current: list[str] = []
    prev_end: float | None = None
    words = 0
    for seg in segments:
        gap = (seg["start"] - prev_end) if prev_end is not None else 0.0
        if current and (gap >= pause_s or words >= max_words):
            paragraphs.append(" ".join(current).strip())
            current, words = [], 0
        current.append(seg["text"])
        words += len(seg["text"].split())
        prev_end = seg["end"]
    if current:
        paragraphs.append(" ".join(current).strip())
    return [p for p in paragraphs if p]


def detect_scripture_refs(text: str) -> list[str]:
    refs = []
    for book in BOOKS:
        # e.g. "Matthew 18", "Sirach 28:2", "1 Corinthians 13"
        for m in re.finditer(rf"\b(?:[123]\s+)?{book}\s+\d+(?::\d+(?:-\d+)?)?", text):
            ref = m.group(0)
            if ref not in refs:
                refs.append(ref)
    return refs[:4]


def _llm_title_and_headings(settings: Settings, paragraphs: list[str]) -> tuple[str | None, list[str]]:
    """Ask the local LLM for a title + a heading before some paragraphs.
    Returns (title, headings) where headings[i] may be '' (no heading)."""
    try:
        import requests

        body = "\n\n".join(paragraphs)
        prompt = (
            "Format this Catholic homily as a blog post. Do NOT rewrite it.\n"
            "Reply with ONLY JSON:\n"
            "{\"title\": \"<short thematic title, no quotes>\", "
            "\"headings\": {\"<paragraph number starting at 0>\": \"<short heading>\"}}\n"
            "Give 3-5 headings at most, at natural topic changes.\n\n"
            + "\n\n".join(f"[{i}] {p}" for i, p in enumerate(paragraphs))
        )
        resp = requests.post(
            f"{settings.ollama_host}/api/generate",
            json={"model": settings.ollama_model, "prompt": prompt, "stream": False},
            timeout=600,
        )
        resp.raise_for_status()
        match = re.search(r"\{.*\}", resp.json().get("response", ""), re.DOTALL)
        if not match:
            return None, [""] * len(paragraphs)
        data = json.loads(match.group(0))
        headings = [""] * len(paragraphs)
        for key, value in (data.get("headings") or {}).items():
            idx = int(key)
            if 0 <= idx < len(headings) and str(value).strip():
                headings[idx] = str(value).strip()
        title = str(data.get("title") or "").strip() or None
        _ = body
        return title, headings
    except Exception:
        return None, [""] * len(paragraphs)


def fallback_title(service_date: date, service_start: datetime | None = None) -> str:
    """Title used when no LLM title is available.

    Includes the Mass time when known: with the LLM off, EVERY homily
    used to fall back to the identical "Homily for <date>", so all of a
    Sunday's services shared one title (and one slug). The time keeps
    same-day titles distinct and tells parishioners which Mass it was."""
    base = f"Homily for {service_date.strftime('%B %d, %Y')}"
    if service_start is None:
        return base
    return f"{base} — {service_start.strftime('%I:%M %p').lstrip('0')}"


def build_blog_post(settings: Settings, segments: list[dict],
                    service_date: date, audio_filename: str,
                    service_start: datetime | None = None) -> tuple[str, dict]:
    """Return (markdown_text, meta) for one homily."""
    paragraphs = paragraphs_from_segments(segments)
    full_text = " ".join(paragraphs)
    scripture = detect_scripture_refs(full_text)

    title: str | None = None
    headings = [""] * len(paragraphs)
    if settings.enable_ollama:
        title, headings = _llm_title_and_headings(settings, paragraphs)
    if not title:
        title = fallback_title(service_date, service_start)

    slug = slugify(title)
    excerpt = ""
    for p in paragraphs:
        sentences = re.split(r"(?<=[.!?])\s+", p)
        if len(sentences) >= 1 and len(sentences[0]) > 40:
            excerpt = sentences[0]
            break
    pull_quote = ""
    for p in paragraphs[len(paragraphs) // 3:]:
        for sentence in re.split(r"(?<=[.!?])\s+", p):
            if 60 <= len(sentence) <= 180:
                pull_quote = sentence
                break
        if pull_quote:
            break

    meta = {
        "title": title,
        "date": service_date.isoformat(),
        "church": settings.church_name,
        "scripture": scripture,
        "slug": slug,
        "excerpt": excerpt,
    }

    lines = ["---"]
    lines.append(f"title: {_yaml(title)}")
    lines.append(f"date: {_yaml(service_date.isoformat())}")
    lines.append(f"church: {_yaml(settings.church_name)}")
    if scripture:
        lines.append(f"scripture: {_yaml(', '.join(scripture))}")
    lines.append(f"category: {_yaml(settings.blog_category)}")
    lines.append(f"slug: {_yaml(slug)}")
    lines.append(f"excerpt: {_yaml(excerpt)}")
    lines.append(f"audio: {_yaml(audio_filename)}")
    lines.append("---")
    lines.append("")
    lines.append(f"# {title}")
    lines.append("")
    lines.append(f"*{settings.church_name} | {service_date.strftime('%B %d, %Y')}*")
    if scripture:
        lines.append(f"*Readings referenced: {', '.join(scripture)}*")
    lines.append("")
    if pull_quote:
        lines.append(f'> "{pull_quote}"')
        lines.append("")
    for i, paragraph in enumerate(paragraphs):
        if headings[i]:
            lines.append(f"## {headings[i]}")
            lines.append("")
        lines.append(paragraph)
        lines.append("")
    lines.append("---")
    lines.append("")
    lines.append(f"*Listen to this homily: {audio_filename}*")
    lines.append("")
    return "\n".join(lines), meta
