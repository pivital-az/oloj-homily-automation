import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from homily_detect import detect_homily_rules, find_post_homily_cutoff


def seg(start, end, text):
    return {"start": float(start), "end": float(end), "text": text}


def speech(from_s, to_s, text="The homily teaches about mercy and forgiveness in daily life.", step=30):
    out = []
    t = from_s
    while t < to_s:
        out.append(seg(t, min(t + 25, to_s), text))
        t += step
    return out


def base_through_gospel():
    return [
        seg(0, 20, "A reading from the holy Gospel according to Matthew."),
        seg(880, 905, "Then Peter came to Jesus and asked, Lord, how many times?"),
        seg(906, 926, "This is the Gospel of the Lord. Praise to you, Lord Jesus Christ."),
    ]


class TestEndMarkers(unittest.TestCase):
    def test_creed_split_across_segments(self):
        segments = base_through_gospel() + speech(930, 1700) + [
            seg(1700, 1703, "I believe in one"),
            seg(1703, 1712, "God, the Father almighty, maker of heaven and earth,"),
            seg(1712, 1740, "of all things visible and invisible."),
        ] + speech(1740, 2400, "The Creed continues.")
        span = detect_homily_rules(segments)
        self.assertIsNotNone(span)
        self.assertLessEqual(span.end_s, 1700)
        self.assertGreaterEqual(span.confidence, 0.6)

    def test_apostles_creed_marker(self):
        segments = base_through_gospel() + speech(930, 1600) + [
            seg(1600, 1612, "I believe in God the Father almighty, creator of heaven and earth,"),
        ] + speech(1612, 2200, "and in Jesus Christ his only Son.")
        span = detect_homily_rules(segments)
        self.assertIsNotNone(span)
        self.assertLessEqual(span.end_s, 1600)

    def test_gap_fallback_end(self):
        segments = base_through_gospel() + speech(930, 1680)
        # 45-second silence, then more content (Creed/music region,
        # garbled so no text marker matches).
        segments += speech(1725, 3400, "Unintelligible unison speaking and singing.")
        span = detect_homily_rules(segments)
        self.assertIsNotNone(span)
        self.assertLessEqual(span.end_s, 1680)
        self.assertTrue(any("inferred boundary" in n for n in span.notes))
        self.assertGreaterEqual(span.confidence, 0.6)

    def test_gap_earlier_than_marker_wins(self):
        # The live shape: homily, long silence (untranscribed Creed),
        # then intercessions carrying a marker phrase. The silence is
        # the true end - the marker end would include the Creed.
        segments = base_through_gospel() + speech(930, 1500)
        segments += [seg(1592, 1630, "For the Church, we pray to the Lord. Lord, hear our prayer.")]
        segments += speech(1630, 2400, "More intercessions and liturgy.")
        span = detect_homily_rules(segments)
        self.assertIsNotNone(span)
        self.assertLessEqual(span.end_s, 1500)
        self.assertTrue(any("earlier than the post-homily marker" in n for n in span.notes))

    def test_marker_earlier_than_gap_wins(self):
        # Normal shape: homily, short pause, Creed (marker), then a
        # long musical stretch much later. The marker end must win.
        segments = base_through_gospel() + speech(930, 1500) + [
            seg(1505, 1516, "I believe in one God, the Father almighty,"),
        ] + speech(1516, 1900, "The Creed continues.")
        segments += speech(1990, 2600, "Offertory and Eucharistic prayer.")
        span = detect_homily_rules(segments)
        self.assertIsNotNone(span)
        self.assertLessEqual(span.end_s, 1505)
        self.assertTrue(any("post-homily marker" in n for n in span.notes))

    def test_no_marker_no_gap_stays_low_confidence(self):
        # The live 2026-09-13 07:00 failure shape: solid start, then
        # unbroken segments to the end of the recording.
        segments = base_through_gospel() + speech(930, 3505, step=28)
        span = detect_homily_rules(segments)
        self.assertIsNotNone(span)
        self.assertAlmostEqual(span.confidence, 0.30, places=2)
        self.assertLess(span.confidence, 0.6)


class TestNewPostHomilyMarkers(unittest.TestCase):
    """The Oct 25 and Nov 1 4:00 PM posts bled past the homily into
    the intercessions and parish prayer - none of these phrases was
    a post-homily marker."""

    def test_let_us_pray_to_the_lord_ends_homily(self):
        segments = base_through_gospel() + speech(930, 1500) + [
            seg(1500, 1520, "Let us pray to the Lord. Lord, hear our prayer."),
        ] + speech(1520, 2200, "For the Church, we pray.")
        span = detect_homily_rules(segments)
        self.assertIsNotNone(span)
        self.assertLessEqual(span.end_s, 1500)

    def test_parish_prayer_marker(self):
        segments = base_through_gospel() + speech(930, 1500) + [
            seg(1500, 1530, "Please join us now in our parish prayer for the week."),
        ] + speech(1530, 2200, "Parish prayer continues.")
        span = detect_homily_rules(segments)
        self.assertIsNotNone(span)
        self.assertLessEqual(span.end_s, 1500)

    def test_please_remain_standing_marker(self):
        segments = base_through_gospel() + speech(930, 1500) + [
            seg(1500, 1510, "Please remain standing as we profess our faith."),
        ] + speech(1510, 2200, "The Creed continues.")
        span = detect_homily_rules(segments)
        self.assertIsNotNone(span)
        self.assertLessEqual(span.end_s, 1500)


class TestPostHomilyCutoff(unittest.TestCase):
    """find_post_homily_cutoff is the Pass 2 safety trim: the clip
    end comes from Pass 1, so a late clip end leaves Creed /
    intercessions at the tail of the re-transcribed clip."""

    def test_trims_creed_tail(self):
        segments = speech(0, 600) + [
            seg(600, 620, "I believe in one God, the Father almighty,"),
        ] + speech(620, 780, "The Creed continues.")
        idx = find_post_homily_cutoff(segments)
        self.assertIsNotNone(idx)
        self.assertEqual(segments[idx]["start"], 600)

    def test_ignores_marker_in_first_three_minutes(self):
        # The homilist quoting the Creed early is not the liturgy.
        segments = speech(0, 60) + [
            seg(60, 80, "As we say, I believe in one God, the Father almighty,"),
        ] + speech(80, 900)
        self.assertIsNone(find_post_homily_cutoff(segments))

    def test_ignores_marker_without_sustained_tail(self):
        # A marker with under 60 s after it is a passing mention,
        # not a liturgy section following the homily.
        segments = speech(0, 700) + [
            seg(700, 720, "I believe in one God, the Father almighty,"),
        ]
        self.assertIsNone(find_post_homily_cutoff(segments))

    def test_none_when_no_marker(self):
        self.assertIsNone(find_post_homily_cutoff(speech(0, 900)))

    def test_empty_segments(self):
        self.assertIsNone(find_post_homily_cutoff([]))


if __name__ == "__main__":
    unittest.main()
