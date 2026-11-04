"""Unit tests for sanitized run-log publishing (src/publish_logs.py).

No FTP, models, network, or git is needed. Logs are written to a
temporary directory and published to a temporary docs/logs folder.
"""
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from config import Settings
from publish_logs import publish_logs, sanitize_log_text


def _settings(tmp: Path) -> Settings:
    log_dir = tmp / "logs"
    log_dir.mkdir()
    return Settings(
        log_dir=log_dir,
        podcast_feed_file=tmp / "docs" / "feed.xml",
        ftp_host="10.16.10.99",
    )


SAMPLE = """2026-11-01 19:00:00 INFO Target Sunday: 2026-11-01 (today local: 2026-11-01)
2026-11-01 19:01:00 INFO Could not connect to the recorder at 10.16.10.99:21 after 3 attempts
2026-11-01 19:01:30 INFO Also unreachable: 192.168.1.77
2026-11-01 19:02:00 INFO Published to Dropbox/parish site: C:\\Users\\AudioVisual\\Dropbox\\Homilies\\2026-11-01_0900_x
2026-11-01 19:03:00 INFO Contact audiovisual@oloj.org about password=hunter2
2026-11-01 19:04:00 INFO Service 2026-11-01_0900: completed
2026-11-01 19:05:00 INFO Service 2026-11-01_1100: review
"""


class TestSanitize(unittest.TestCase):
    def test_redacts_ip_profile_email_password(self):
        settings = Settings(ftp_host="10.16.10.99")
        out = sanitize_log_text(SAMPLE, settings)
        self.assertNotIn("10.16.10.99", out)
        self.assertNotIn("AudioVisual", out)
        self.assertNotIn("audiovisual@oloj.org", out)
        self.assertNotIn("hunter2", out)
        self.assertIn("[ip-redacted]", out)  # the non-host IP
        self.assertIn("[recorder-host]", out)  # the configured host
        self.assertIn(r"C:\Users\[user]", out)
        self.assertIn("[email-redacted]", out)
        # Troubleshooting content survives redaction.
        self.assertIn("2026-11-01_0900", out)
        self.assertIn("completed", out)


class TestPublishLogs(unittest.TestCase):
    def test_publishes_sanitized_and_prunes_to_keep(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            settings = _settings(tmp)
            for name in ("run-20261101-190000.log", "run-20261102-190000.log",
                         "run-20261103-190000.log"):
                (settings.log_dir / name).write_text(SAMPLE, encoding="utf-8")
            published = publish_logs(settings, keep=2)
            self.assertEqual(published, ["run-20261103-190000.log",
                                         "run-20261102-190000.log"])
            dest = tmp / "docs" / "logs"
            self.assertFalse((dest / "run-20261101-190000.log").exists())
            text = (dest / "run-20261103-190000.log").read_text(encoding="utf-8")
            self.assertNotIn("10.16.10.99", text)
            index = (dest / "index.html").read_text(encoding="utf-8")
            self.assertIn("run-20261103-190000.log", index)
            self.assertIn("2026-11-01", index)  # target Sunday from the log
            self.assertIn("2 runs are kept", index)


if __name__ == "__main__":
    unittest.main()
