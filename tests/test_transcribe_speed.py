"""Unit tests for the Pass 1 speed knobs in src/transcribe.py.

No model, ffmpeg, or audio file is needed: the model loader, volume
probe, and decoder are stubbed, and the test asserts only what
transcribe_file *passes* to faster-whisper - beam size and word
timestamps - plus that its returned segments are unchanged in shape.
"""
import sys
import unittest
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import transcribe
from config import Settings


class _Segment:
    def __init__(self, start, end, text):
        self.start = start
        self.end = end
        self.text = text
        self.no_speech_prob = 0.1


class _Model:
    def __init__(self):
        self.kwargs = None

    def transcribe(self, audio, **kwargs):
        self.kwargs = kwargs
        return [_Segment(0.0, 5.0, "In the name of the Father.")], None


class TestTranscribeSpeedKnobs(unittest.TestCase):
    def setUp(self):
        self.model = _Model()
        self._orig = (transcribe._load_model, transcribe.volume_levels,
                      transcribe._decode_16k_mono)
        transcribe._load_model = lambda settings, name: self.model
        transcribe.volume_levels = lambda path: (-20.0, -5.0)
        transcribe._decode_16k_mono = lambda path, gain_db=0.0: np.zeros(16000, dtype=np.float32)

    def tearDown(self):
        (transcribe._load_model, transcribe.volume_levels,
         transcribe._decode_16k_mono) = self._orig

    def test_pass1_settings_are_greedy_without_word_timestamps(self):
        transcribe.transcribe_file(Settings(), Path("x.mp3"), "small",
                                   beam_size=1, word_timestamps=False)
        self.assertEqual(self.model.kwargs["beam_size"], 1)
        self.assertIs(self.model.kwargs["word_timestamps"], False)

    def test_defaults_preserve_pass2_quality_settings(self):
        # Default call (beam 5) is what Pass 2 relies on for its
        # published wording; only word timestamps are dropped there.
        segments = transcribe.transcribe_file(Settings(), Path("x.mp3"), "large-v3-turbo")
        self.assertEqual(self.model.kwargs["beam_size"], 5)
        self.assertIs(self.model.kwargs["word_timestamps"], True)
        self.assertEqual(segments, [{"start": 0.0, "end": 5.0,
                                     "text": "In the name of the Father.",
                                     "no_speech_prob": 0.1}])


class TestBaseModelOption(unittest.TestCase):
    def test_base_is_installable_but_not_default(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "install_models",
            Path(__file__).resolve().parent.parent / "scripts" / "install_models.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        self.assertIn("base", mod.MODELS)
        self.assertEqual(mod.MODELS["base"], "Systran/faster-whisper-base")
        self.assertEqual(set(mod.models_to_download(None)), {"small", "large-v3-turbo"})
        self.assertEqual(mod.models_to_download("base"),
                         {"base": "Systran/faster-whisper-base"})

    def test_turbo_is_the_default_pass2_model_from_mobiuslabsgmbh(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "install_models",
            Path(__file__).resolve().parent.parent / "scripts" / "install_models.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        # Systran publishes no turbo repo - faster-whisper fetches it
        # from mobiuslabsgmbh; a Systran repo id here would fail the download.
        self.assertEqual(mod.MODELS["large-v3-turbo"],
                         "mobiuslabsgmbh/faster-whisper-large-v3-turbo")
        self.assertIn("large-v3-turbo", mod.models_to_download(None))


if __name__ == "__main__":
    unittest.main()
