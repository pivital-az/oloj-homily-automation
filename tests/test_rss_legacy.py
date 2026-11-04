"""Unit tests for legacy-episode replacement in src/spotify_rss.py.

Regression test for the Sept 13 11:00 gap: a pre-fix episode (title
and MP3 name without the service start time) must be replaced - not
duplicated - when the same service is reprocessed, and its orphaned
MP3 must be deleted.
"""
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from config import Settings
from spotify_rss import add_episode


class TestLegacyReplacement(unittest.TestCase):
    def test_reprocessing_replaces_legacy_item_and_deletes_old_mp3(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            audio_dir = tmp / "docs" / "audio"
            audio_dir.mkdir(parents=True)
            feed_file = tmp / "docs" / "feed.xml"
            settings = Settings(
                podcast_audio_dir=audio_dir,
                podcast_feed_file=feed_file,
                podcast_audio_base_url="https://example.test/audio",
                podcast_feed_base_url="https://example.test",
            )
            # Legacy feed item, as published before start times were
            # added to titles: different GUID and MP3 name, same
            # service (2026-09-13 11:00).
            old_mp3 = audio_dir / "2026-09-13_homily-for-september-13-2026.mp3"
            old_mp3.write_bytes(b"old")
            feed_file.write_text(
                "<?xml version='1.0' encoding='utf-8'?>\n"
                "<rss version=\"2.0\"><channel>"
                "<title>Our Lady of Joy Homilies</title>"
                "<item><title>Homily for September 13, 2026</title>"
                "<description>x</description>"
                "<pubDate>Sun, 13 Sep 2026 11:00:00 -0700</pubDate>"
                "<guid isPermaLink=\"false\">oloj-2026-09-13_1100-homily-for-september-13-2026</guid>"
                "<enclosure url=\"https://example.test/audio/2026-09-13_homily-for-september-13-2026.mp3\" "
                "length=\"3\" type=\"audio/mpeg\" /></item>"
                "</channel></rss>", encoding="utf-8")
            new_mp3 = tmp / "2026-09-13_1100_homily-for-september-13-2026-11-00-am.mp3"
            new_mp3.write_bytes(b"new")
            add_episode(settings, new_mp3,
                        "Homily for September 13, 2026 — 11:00 AM",
                        "excerpt", datetime(2026, 9, 13, 11, 0),
                        "oloj-2026-09-13_1100-homily-for-september-13-2026-11-00-am")
            feed = feed_file.read_text(encoding="utf-8")
            self.assertEqual(feed.count("<item>"), 1)
            self.assertIn("oloj-2026-09-13_1100-homily-for-september-13-2026-11-00-am", feed)
            self.assertNotIn("oloj-2026-09-13_1100-homily-for-september-13-2026</guid>", feed)
            self.assertFalse(old_mp3.exists())
            self.assertTrue((audio_dir / new_mp3.name).exists())


if __name__ == "__main__":
    unittest.main()
