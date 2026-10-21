"""OLOJ homily automation - one run.

Default behaviour (what the scheduled task runs):
  1. Connect to the DN-900R over FTP (local network).
  2. List MP3 chunks, keep only those whose filename date is the
     LATEST SUNDAY (America/Phoenix by default).
  3. Group those chunks into services (there can be several Masses on
     one Sunday) - ALL services for that Sunday are converted.
  4. Per service: download new chunks -> stitch -> volume gate ->
     transcribe whole service (small) -> locate homily -> clip ->
     re-transcribe clip (medium) -> format blog post ->
     publish to Dropbox (parish site) -> add podcast episode (RSS ->
     Spotify, if enabled).
  5. Anything failing a gate goes to REVIEW_DIR with a reason file and
     is NOT published. Completed services are recorded in state.json
     and skipped on later runs.

Usage:
  python src/main.py                     # latest Sunday
  python src/main.py --date 2026-10-18   # a specific Sunday
  python src/main.py --dry-run           # list + group only, no downloads
  python src/main.py --force             # reprocess even if completed
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parent))

from audio import clip_mp3, concat_mp3s, volume_levels
from blog import build_blog_post, slugify
from config import Settings
from ftp_client import FtpRecorder
from homily_detect import detect_homily
from publish import publish_to_dropbox, save_to_review
from spotify_rss import add_episode as spotify_add_episode
from state import State
from sunday import Service, files_for_date, group_into_services, latest_sunday
from transcribe import segments_to_text, transcribe_file


def setup_logging(settings: Settings) -> logging.Logger:
    log_file = settings.log_dir / f"run-{datetime.now().strftime('%Y%m%d-%H%M%S')}.log"
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        handlers=[logging.FileHandler(log_file, encoding="utf-8"),
                  logging.StreamHandler(sys.stdout)],
    )
    return logging.getLogger("homily")


def process_service(settings: Settings, log: logging.Logger, state: State,
                    service: Service, local_chunks: list[Path]) -> str:
    sid = service.service_id
    folder = f"{service.service_date.isoformat()}_{service.start.strftime('%H%M')}"
    work = settings.work_dir / folder
    work.mkdir(parents=True, exist_ok=True)
    log.info("Service %s: %d chunk(s)", sid, len(local_chunks))

    full_mp3 = concat_mp3s(local_chunks, work / "service_full.mp3")

    mean_db, peak_db = volume_levels(full_mp3)
    log.info("Volume: mean %.1f dB, peak %.1f dB", mean_db, peak_db)
    if mean_db < settings.min_mean_volume_db or peak_db < settings.min_peak_volume_db:
        reason = (f"Audio level gate failed: mean {mean_db:.1f} dB, peak {peak_db:.1f} dB "
                  f"(thresholds mean >= {settings.min_mean_volume_db}, peak >= {settings.min_peak_volume_db}). "
                  "Likely a silent / very low-gain recording. Not transcribed "
                  "(Whisper hallucinates on silence) and NOT published.")
        save_to_review(settings, folder, reason, {"service_full.mp3": full_mp3})
        state.mark_service(sid, "review", {"reason": "volume_gate"})
        return "review"

    log.info("Pass 1: transcribing full service (%s)...", settings.whisper_pass1_model)
    full_segments = transcribe_file(settings, full_mp3, settings.whisper_pass1_model)
    (work / "full_segments.json").write_text(json.dumps(full_segments, indent=2), encoding="utf-8")
    if not full_segments:
        save_to_review(settings, folder, "Pass 1 transcription produced no speech segments.",
                       {"service_full.mp3": full_mp3})
        state.mark_service(sid, "review", {"reason": "no_speech"})
        return "review"

    span = detect_homily(settings, full_segments)
    if span is None or span.confidence < settings.min_homily_confidence:
        reason = ("Homily detection confidence too low to publish automatically. "
                  f"Span: {span}; threshold {settings.min_homily_confidence}.")
        save_to_review(settings, folder, reason,
                       {"full_segments.json": json.dumps(full_segments, indent=2),
                        "service_full.mp3": full_mp3})
        state.mark_service(sid, "review", {"reason": "low_confidence"})
        return "review"
    log.info("Homily located: %.0f-%.0f s (%.1f min), confidence %.2f via %s",
             span.start_s, span.end_s, span.duration_s / 60, span.confidence, span.method)
    for note in span.notes:
        log.info("  detect: %s", note)

    homily_mp3 = clip_mp3(full_mp3, span.start_s, span.end_s, work / "homily.mp3")

    log.info("Pass 2: re-transcribing homily clip (%s)...", settings.whisper_pass2_model)
    homily_segments = transcribe_file(settings, homily_mp3, settings.whisper_pass2_model)
    transcript_text = segments_to_text(homily_segments)
    (work / "homily_segments.json").write_text(json.dumps(homily_segments, indent=2), encoding="utf-8")

    service_dt = datetime.combine(service.service_date, service.start.time())
    blog_md, meta = build_blog_post(settings, homily_segments, service.service_date, homily_mp3.name)
    dated_mp3 = work / f"{service.service_date.isoformat()}_{slugify(meta['title'])}.mp3"
    homily_mp3.replace(dated_mp3)
    homily_mp3 = dated_mp3
    # The blog post references the audio filename - keep them in sync.
    # Only the two exact spots blog.py writes (front-matter line and the
    # "Listen to this homily" line); never a blanket replace, which could
    # mangle transcript prose that happens to mention the filename.
    old_name = "homily.mp3"
    blog_md = blog_md.replace(f'audio: "{old_name}"', f'audio: "{homily_mp3.name}"')
    blog_md = blog_md.replace(f"*Listen to this homily: {old_name}*",
                              f"*Listen to this homily: {homily_mp3.name}*")

    publish_folder = f"{service.service_date.isoformat()}_{slugify(meta['title'])}"
    published_dir = publish_to_dropbox(
        settings, publish_folder, blog_md, f"{slugify(meta['title'])}.md",
        homily_mp3, transcript_text,
    )
    log.info("Published to Dropbox/parish site: %s", published_dir)

    episode_url = None
    if settings.enable_spotify:
        episode_url = spotify_add_episode(
            settings, homily_mp3, meta["title"],
            meta.get("excerpt") or meta["title"], service_dt,
            guid_key=f"oloj-{sid}-{slugify(meta['title'])}",
        )

    state.mark_service(sid, "completed", {
        "title": meta["title"],
        "homily_start_s": span.start_s,
        "homily_end_s": span.end_s,
        "confidence": span.confidence,
        "dropbox_folder": str(published_dir),
        "spotify_episode_url": episode_url,
    })
    return "completed"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--date", help="Sunday to process, YYYY-MM-DD (default: latest Sunday)")
    parser.add_argument("--dry-run", action="store_true",
                        help="List FTP files for the target Sunday and show service grouping only")
    parser.add_argument("--force", action="store_true",
                        help="Reprocess services already marked completed")
    args = parser.parse_args()

    settings = Settings.load()
    log = setup_logging(settings)
    state = State(settings.state_file)

    tz = ZoneInfo(settings.timezone)
    today_local = datetime.now(tz).date()
    target = date.fromisoformat(args.date) if args.date else latest_sunday(today_local)
    if target.weekday() != 6:
        log.warning("Target date %s is a %s, not a Sunday - continuing because it was requested explicitly.",
                    target, target.strftime("%A"))
    log.info("Target Sunday: %s (today local: %s)", target, today_local)

    problems = settings.validate_for_run()
    if problems and not args.dry_run:
        for problem in problems:
            log.error("Config: %s", problem)
        return 2

    with FtpRecorder(settings) as recorder:
        all_files = recorder.list_mp3s()
        log.info("Recorder holds %d parseable MP3 chunk(s).", len(all_files))
        sunday_files = files_for_date(all_files, target)
        services = group_into_services(sunday_files, settings.service_gap_minutes)
        log.info("%d chunk(s) match %s -> %d service(s).", len(sunday_files), target, len(services))
        for service in services:
            log.info("  %s", service.label)

        if args.dry_run:
            log.info("Dry run - nothing downloaded or processed.")
            return 0

        for service in services:
            if state.service_done(service.service_id) and not args.force:
                log.info("Skipping %s - already completed (use --force to redo).", service.service_id)
                continue
            chunk_dir = settings.work_dir / "downloads" / service.service_id
            local_chunks = [recorder.download(f, chunk_dir) for f in service.files]
            try:
                outcome = process_service(settings, log, state, service, local_chunks)
                log.info("Service %s: %s", service.service_id, outcome)
            except Exception as exc:
                log.exception("Service %s FAILED: %s", service.service_id, exc)
                state.mark_service(service.service_id, "failed", {"error": str(exc)})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
