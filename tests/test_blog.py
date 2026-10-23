import sys
import unittest
from datetime import date, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from blog import fallback_title, slugify


class TestFallbackTitle(unittest.TestCase):
    """With the LLM off, every homily gets the fallback title. The
    2026-09-13 run proved the old date-only fallback made all three
    Masses share one title/slug and overwrite each other."""

    D = date(2026, 9, 13)

    def test_same_day_titles_differ_by_mass_time(self):
        titles = {fallback_title(self.D, datetime(2026, 9, 13, h, 0)) for h in (7, 9, 11)}
        self.assertEqual(len(titles), 3)
        self.assertIn("Homily for September 13, 2026 — 7:00 AM", titles)
        self.assertIn("Homily for September 13, 2026 — 4:00 PM",
                      {fallback_title(self.D, datetime(2026, 9, 13, 16, 0))})

    def test_same_day_slugs_differ(self):
        slugs = {slugify(fallback_title(self.D, datetime(2026, 9, 13, h, 0)))
                 for h in (7, 9, 11)}
        self.assertEqual(len(slugs), 3)

    def test_no_time_keeps_plain_fallback(self):
        self.assertEqual(fallback_title(self.D), "Homily for September 13, 2026")


if __name__ == "__main__":
    unittest.main()
