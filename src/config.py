"""Configuration: everything comes from the .env file in the repo root."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def _load_env() -> None:
    try:
        from dotenv import load_dotenv

        load_dotenv(REPO_ROOT / ".env")
    except ImportError:  # minimal fallback parser
        env_file = REPO_ROOT / ".env"
        if env_file.exists():
            for line in env_file.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, value = line.split("=", 1)
                    os.environ.setdefault(key.strip(), value.strip())


def _path(value: str, default: str) -> Path:
    raw = (value or default).strip()
    p = Path(raw)
    return p if p.is_absolute() else (REPO_ROOT / p).resolve()


def _bool(value: str | None, default: bool = False) -> bool:
    if value is None or value == "":
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass
class Settings:
    church_name: str = "Our Lady of Joy"
    timezone: str = "America/Phoenix"

    ftp_host: str = ""
    ftp_port: int = 21
    ftp_user: str = ""
    ftp_password: str = ""
    ftp_remote_dir: str = "/"
    ftp_timeout: int = 30
    recorder_filename_format: str = "%m%d%Y%H%M%S"
    chunk_minutes: int = 10
    service_gap_minutes: int = 20

    base_dir: Path = REPO_ROOT
    models_dir: Path = field(default_factory=lambda: REPO_ROOT / "models")
    work_dir: Path = field(default_factory=lambda: REPO_ROOT / "work")
    review_dir: Path = field(default_factory=lambda: REPO_ROOT / "review")
    log_dir: Path = field(default_factory=lambda: REPO_ROOT / "logs")
    state_file: Path = field(default_factory=lambda: REPO_ROOT / "data" / "state.json")

    dropbox_dir: Path | None = None
    blog_format: str = "md"
    blog_category: str = "Homilies"

    whisper_device: str = "cpu"
    whisper_compute_type: str = "int8"
    whisper_pass1_model: str = "small"
    whisper_pass2_model: str = "medium"
    whisper_language: str = "en"
    whisper_cpu_threads: int = 10
    min_mean_volume_db: float = -50.0
    min_peak_volume_db: float = -30.0
    min_homily_confidence: float = 0.60

    enable_ollama: bool = False
    ollama_host: str = "http://127.0.0.1:11434"
    ollama_model: str = "llama3.1:8b"

    enable_spotify: bool = False
    podcast_title: str = "Our Lady of Joy Homilies"
    podcast_description: str = "Weekly homilies from Our Lady of Joy."
    podcast_author: str = "Our Lady of Joy"
    podcast_language: str = "en-us"
    podcast_category: str = "Religion & Spirituality"
    podcast_subcategory: str = "Christianity"
    podcast_audio_base_url: str = ""
    podcast_feed_base_url: str = ""
    podcast_audio_dir: Path | None = None
    podcast_feed_file: Path | None = None
    podcast_artwork_url: str = ""
    podcast_contact_email: str = ""

    @classmethod
    def load(cls) -> "Settings":
        _load_env()
        g = os.environ.get
        base = _path(g("APP_BASE_DIR", ""), ".")
        s = cls(
            church_name=g("CHURCH_NAME", "Our Lady of Joy"),
            timezone=g("TIMEZONE", "America/Phoenix"),
            ftp_host=g("FTP_HOST", ""),
            ftp_port=int(g("FTP_PORT", "21")),
            ftp_user=g("FTP_USER", ""),
            ftp_password=g("FTP_PASSWORD", ""),
            ftp_remote_dir=g("FTP_REMOTE_DIR", "/") or "/",
            ftp_timeout=int(g("FTP_TIMEOUT_SECONDS", "30")),
            recorder_filename_format=g("RECORDER_FILENAME_FORMAT", "%m%d%Y%H%M%S"),
            chunk_minutes=int(g("CHUNK_MINUTES", "10")),
            service_gap_minutes=int(g("SERVICE_GAP_MINUTES", "20")),
            base_dir=base,
            models_dir=_path(g("MODELS_DIR", ""), "models"),
            work_dir=_path(g("LOCAL_WORK_DIR", ""), "work"),
            review_dir=_path(g("REVIEW_DIR", ""), "review"),
            log_dir=_path(g("LOG_DIR", ""), "logs"),
            state_file=_path(g("STATE_FILE", ""), "data/state.json"),
            dropbox_dir=_path(g("DROPBOX_HOMILY_DIR", ""), "") if g("DROPBOX_HOMILY_DIR") else None,
            blog_format=g("BLOG_FORMAT", "md"),
            blog_category=g("BLOG_CATEGORY", "Homilies"),
            whisper_device=g("WHISPER_DEVICE", "cpu"),
            whisper_compute_type=g("WHISPER_COMPUTE_TYPE", "int8"),
            whisper_pass1_model=g("WHISPER_PASS1_MODEL", "small"),
            whisper_pass2_model=g("WHISPER_PASS2_MODEL", "medium"),
            whisper_language=g("WHISPER_LANGUAGE", "en"),
            whisper_cpu_threads=int(g("WHISPER_CPU_THREADS", "10")),
            min_mean_volume_db=float(g("MIN_MEAN_VOLUME_DB", "-50")),
            min_peak_volume_db=float(g("MIN_PEAK_VOLUME_DB", "-30")),
            min_homily_confidence=float(g("MIN_HOMILY_CONFIDENCE", "0.60")),
            enable_ollama=_bool(g("ENABLE_OLLAMA")),
            ollama_host=g("OLLAMA_HOST", "http://127.0.0.1:11434"),
            ollama_model=g("OLLAMA_MODEL", "llama3.1:8b"),
            enable_spotify=_bool(g("ENABLE_SPOTIFY")),
            podcast_title=g("PODCAST_TITLE", "Our Lady of Joy Homilies"),
            podcast_description=g("PODCAST_DESCRIPTION", "Weekly homilies from Our Lady of Joy."),
            podcast_author=g("PODCAST_AUTHOR", "Our Lady of Joy"),
            podcast_language=g("PODCAST_LANGUAGE", "en-us"),
            podcast_category=g("PODCAST_CATEGORY", "Religion & Spirituality"),
            podcast_subcategory=g("PODCAST_SUBCATEGORY", "Christianity"),
            podcast_audio_base_url=g("PODCAST_AUDIO_BASE_URL", "").rstrip("/"),
            podcast_feed_base_url=g("PODCAST_FEED_BASE_URL", "").rstrip("/"),
            podcast_audio_dir=_path(g("PODCAST_AUDIO_DIR", ""), "") if g("PODCAST_AUDIO_DIR") else None,
            podcast_feed_file=_path(g("PODCAST_FEED_FILE", ""), "") if g("PODCAST_FEED_FILE") else None,
            podcast_artwork_url=g("PODCAST_ARTWORK_URL", ""),
            podcast_contact_email=g("PODCAST_CONTACT_EMAIL", ""),
        )
        for folder in (s.models_dir, s.work_dir, s.review_dir, s.log_dir, s.state_file.parent):
            folder.mkdir(parents=True, exist_ok=True)
        return s

    def validate_for_run(self) -> list[str]:
        problems = []
        if not self.ftp_host:
            problems.append("FTP_HOST is not set in .env")
        if self.dropbox_dir is None:
            problems.append("DROPBOX_HOMILY_DIR is not set in .env (blog posts cannot be published)")
        if self.enable_spotify:
            if not self.podcast_audio_base_url:
                problems.append("ENABLE_SPOTIFY=true but PODCAST_AUDIO_BASE_URL is empty - "
                                "Spotify/RSS episodes need a public HTTPS URL for the MP3s")
            if self.podcast_audio_dir is None or self.podcast_feed_file is None:
                problems.append("ENABLE_SPOTIFY=true but PODCAST_AUDIO_DIR / PODCAST_FEED_FILE is empty")
        return problems

    def model_ref(self, model_name: str) -> str:
        """Prefer a locally downloaded model folder (offline) over a HF name."""
        local = self.models_dir / f"faster-whisper-{model_name}"
        return str(local) if (local / "model.bin").exists() else model_name
