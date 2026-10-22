import sys
import unittest
from datetime import date, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from main import dated_audio_name, publish_folder_name
from sunday import RemoteFile, Service


def service_at(hour: int) -> Service:
    start = datetime(2026, 9, 13, hour, 0)
    return Service(
        service_date=date(2026, 9, 13),
        start=start,
        files=[RemoteFile(name="x.mp3", size=1, start=start)],
    )


class TestSameTitleNoOverwrite(unittest.TestCase):
    """Stone's scenario: three homilies in one day, same title."""

    TITLE = "The Grace of Forgiveness"

    def test_audio_names_unique_per_service(self):
        names = {dated_audio_name(service_at(h), self.TITLE) for h in (7, 9, 11)}
        self.assertEqual(len(names), 3)
        self.assertIn("2026-09-13_0700_the-grace-of-forgiveness.mp3", names)
        self.assertIn("2026-09-13_1100_the-grace-of-forgiveness.mp3", names)

    def test_dropbox_folders_unique_per_service(self):
        folders = {publish_folder_name(service_at(h), self.TITLE) for h in (7, 9, 11)}
        self.assertEqual(len(folders), 3)

    def test_same_service_is_idempotent(self):
        # Reprocessing the SAME service must reuse its own names
        # (overwrite itself, never a sibling).
        self.assertEqual(dated_audio_name(service_at(9), self.TITLE),
                         dated_audio_name(service_at(9), self.TITLE))
        self.assertEqual(publish_folder_name(service_at(9), self.TITLE),
                         publish_folder_name(service_at(9), self.TITLE))


if __name__ == "__main__":
    unittest.main()
