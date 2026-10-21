import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from homily_detect import detect_homily_rules


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


if __name__ == "__main__":
    unittest.main()
