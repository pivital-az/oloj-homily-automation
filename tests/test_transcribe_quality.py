import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from blog import paragraphs_from_segments
from transcribe import gain_db_for_peak


def seg(start, end, text):
    return {"start": start, "end": end, "text": text}


class TestGain(unittest.TestCase):
    def test_quiet_service_gets_boost(self):
        # The 07:00 Sept 13 service peaked at -20.8 dB.
        self.assertAlmostEqual(gain_db_for_peak(-20.8), 19.8, places=1)

    def test_never_attenuates(self):
        self.assertEqual(gain_db_for_peak(0.0), 0.0)
        self.assertEqual(gain_db_for_peak(-0.5), 0.0)

    def test_capped_for_near_silence(self):
        self.assertEqual(gain_db_for_peak(-76.0), 24.0)


class TestParagraphs(unittest.TestCase):
    def test_breaks_at_sentences_not_dramatic_pauses(self):
        # A 2-second pause after a 3-word fragment must not strand it
        # as its own paragraph (the old rule did exactly this).
        segments = [
            seg(0, 4, "Forgiveness is that attribute of the stronger."),
            seg(6, 8, "It is their nature."),  # 2s gap before this one in old terms
            seg(8, 20, "Go on with your good nature and follow God's love "
                       "in all things, today and every day of your life, "
                       "with courage and perseverance and openness of heart "
                       "to the people around you who need your mercy most."),
        ]
        paras = paragraphs_from_segments(segments)
        self.assertEqual(len(paras), 1)
        self.assertTrue(paras[0].startswith("Forgiveness"))

    def test_sentences_inside_one_segment_are_found(self):
        text = ("Let it be. You do not have to carry it forever. "
                "Surrender. Let God take it from your heart today.")
        paras = paragraphs_from_segments([seg(0, 30, text)])
        self.assertEqual(len(paras), 1)  # short text stays one paragraph
        self.assertIn("Surrender.", paras[0])

    def test_long_text_breaks_into_bounded_paragraphs(self):
        sentence = "Forgiveness sets the prisoner free at last. "
        segments = [seg(i * 10, i * 10 + 9, sentence * 4) for i in range(12)]
        paras = paragraphs_from_segments(segments)
        self.assertGreaterEqual(len(paras), 3)
        for p in paras:
            self.assertLessEqual(len(p.split()), 130)
            self.assertTrue(p.endswith("."))

    def test_paragraphs_capitalized(self):
        paras = paragraphs_from_segments([seg(0, 5, "the pain remains in our heart.")])
        self.assertTrue(paras[0].startswith("The pain"))


if __name__ == "__main__":
    unittest.main()
