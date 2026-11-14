import sys
import unittest
from datetime import date, datetime
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from blog import (
    _clean_quote_candidate,
    _ends_with_terminal_punct,
    build_blog_post,
    detect_scripture_refs,
    fallback_title,
    paragraphs_from_segments,
    slugify,
)
from config import Settings


def seg(start, end, text):
    return {"start": float(start), "end": float(end), "text": text}


def sentence(n_words, end="."):
    return " ".join(["word"] * n_words) + end


class TestEndsWithTerminalPunct(unittest.TestCase):
    def test_plain_endings(self):
        for s in ("It ends here.", "Really?", "Amen!", "And then…"):
            self.assertTrue(_ends_with_terminal_punct(s), s)

    def test_trailing_quote_or_paren_allowed(self):
        self.assertTrue(_ends_with_terminal_punct('He said "Amen."'))
        self.assertTrue(_ends_with_terminal_punct("Go in peace (Amen)."))

    def test_fragment_has_none(self):
        for s in ("the highest perspective", "looking at the world", ""):
            self.assertFalse(_ends_with_terminal_punct(s), s)


class TestParagraphTerminalRule(unittest.TestCase):
    """A paragraph must never break after a fragment that runs on
    into the next segment - that mid-sentence split is the defect in
    all 9 published posts (Nov 6 audit)."""

    def test_fragment_merges_on_past_min_words(self):
        # 5 sentences x 10 words = 50, then an 8-word fragment with no
        # terminal punctuation (58 words), then its continuation.
        # Old code broke before the continuation, stranding the
        # fragment at the end of paragraph 1.
        segments = [
            seg(i * 10, i * 10 + 9, sentence(10)) for i in range(5)
        ] + [
            seg(50, 58, "the highest perspective looking at the world"),
            seg(58, 66, "through the eyes of faith today."),
            seg(66, 76, sentence(10)),
        ]
        paras = paragraphs_from_segments(segments)
        self.assertIn(
            "the highest perspective looking at the world through the eyes of faith today.",
            " ".join(paras),
        )
        self.assertFalse(any(p.rstrip().endswith("world") for p in paras))
        self.assertTrue(all(p.endswith(".") for p in paras))

    def test_breaks_cleanly_past_min_words(self):
        segments = [seg(i * 10, i * 10 + 9, sentence(10)) for i in range(12)]
        paras = paragraphs_from_segments(segments)
        self.assertEqual(len(paras), 2)
        self.assertTrue(all(p.endswith(".") for p in paras))
        self.assertEqual(len(paras[0].split()), 60)

    def test_safety_valve_breaks_unpunctuated_run(self):
        # 25 fragments x 10 words, no terminal punctuation anywhere:
        # without the valve this merges into one 250-word paragraph.
        segments = [seg(i * 10, i * 10 + 9, " ".join(["word"] * 10)) for i in range(25)]
        paras = paragraphs_from_segments(segments)
        self.assertEqual(len(paras), 2)
        self.assertEqual(len(paras[0].split()), 220)
        self.assertEqual(len(paras[1].split()), 30)


class TestScriptureGate(unittest.TestCase):
    """With the LLM off, scripture refs are regex guesses - Nov 1
    11:00 published a wrong 'Readings referenced: John 16' for All
    Saints. The line must be omitted, not guessed."""

    D = date(2026, 11, 1)

    def _segments(self):
        return [seg(0, 30, "In John 16 Jesus tells his disciples these things. "
                           "The Gospel today is Matthew 5, the Beatitudes.")]

    def test_llm_off_omits_scripture_line(self):
        settings = Settings(enable_ollama=False)
        md, meta = build_blog_post(settings, self._segments(), self.D, "homily.mp3")
        self.assertEqual(meta["scripture"], [])
        self.assertNotIn("Readings referenced", md)
        self.assertNotIn("scripture:", md)

    def test_llm_on_keeps_detected_refs(self):
        settings = Settings(enable_ollama=True)
        with patch("blog._llm_title_and_headings", return_value=(None, [""])):
            md, meta = build_blog_post(settings, self._segments(), self.D, "homily.mp3")
        self.assertEqual(meta["scripture"], ["Matthew 5", "John 16"])
        self.assertIn("Readings referenced: Matthew 5, John 16", md)

    def test_detector_still_finds_refs(self):
        self.assertEqual(
            detect_scripture_refs("John 16 and Matthew 5, the Beatitudes."),
            ["Matthew 5", "John 16"],
        )


class TestPullQuote(unittest.TestCase):
    """The picker must skip garbled candidates: no terminal
    punctuation, unbalanced quotes, or an immediately repeated word."""

    D = date(2026, 9, 13)

    def _post(self, paragraphs):
        settings = Settings(enable_ollama=False)
        md, _meta = build_blog_post(
            settings, [seg(0, 1, "x.")], self.D, "homily.mp3",
            cleaned_paragraphs=paragraphs,
        )
        return md

    def _pull_quote(self, md):
        for line in md.splitlines():
            if line.startswith('> "'):
                return line
        return ""

    def test_skips_unbalanced_quote(self):
        md = self._post([
            "Opening paragraph with enough words to fill the first third of the post properly.",
            'He said "the kingdom is like a mustard seed that grows beyond all expectation today.',
            "Forgiveness is the gift we receive first and the gift we are asked to give away.",
        ])
        self.assertIn("Forgiveness is the gift we receive first", self._pull_quote(md))
        self.assertNotIn("mustard seed", self._pull_quote(md))

    def test_skips_repeated_word(self):
        md = self._post([
            "Opening paragraph with enough words to fill the first third of the post properly.",
            "God's mercy is the the gift that keeps on giving to all who ask in faith today.",
            "Forgiveness is the gift we receive first and the gift we are asked to give away.",
        ])
        self.assertIn("Forgiveness is the gift we receive first", self._pull_quote(md))
        self.assertNotIn("the the gift", self._pull_quote(md))

    def test_skips_quote_without_terminal_punct(self):
        md = self._post([
            "Opening paragraph with enough words to fill the first third of the post properly.",
            "This sentence has no ending punctuation and just keeps going on and on today",
            "Forgiveness is the gift we receive first and the gift we are asked to give away.",
        ])
        self.assertIn("Forgiveness is the gift we receive first", self._pull_quote(md))
        self.assertNotIn("no ending punctuation", self._pull_quote(md))

    def test_clean_candidate_checks(self):
        self.assertTrue(_clean_quote_candidate(
            "Forgiveness is the gift we receive first and the gift we give away."))
        self.assertFalse(_clean_quote_candidate("A sentence with no ending"))
        self.assertFalse(_clean_quote_candidate('He said "hello to everyone today.'))
        self.assertFalse(_clean_quote_candidate("God's mercy is the the gift today."))


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
