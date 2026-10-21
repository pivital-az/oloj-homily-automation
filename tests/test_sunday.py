"""Unit tests for the Sunday / grouping / filename logic.

Run:  .venv\\Scripts\\python.exe -m unittest discover -s tests -v
No FTP, models, or network are needed for these.
"""
import sys
import unittest
from datetime import date, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from sunday import (RemoteFile, files_for_date, group_into_services,
                    latest_sunday, parse_recorder_filename)


def rf(name: str, start: datetime, size: int = 9_600_000) -> RemoteFile:
    return RemoteFile(name=name, size=size, start=start)


class TestLatestSunday(unittest.TestCase):
    def test_wednesday_goes_back_to_sunday(self):
        # Wednesday 2026-10-21 -> Sunday 2026-10-18
        self.assertEqual(latest_sunday(date(2026, 10, 21)), date(2026, 10, 18))

    def test_sunday_is_itself(self):
        self.assertEqual(latest_sunday(date(2026, 10, 18)), date(2026, 10, 18))

    def test_monday_goes_back_one_day(self):
        self.assertEqual(latest_sunday(date(2026, 10, 19)), date(2026, 10, 18))

    def test_saturday_goes_back_six_days(self):
        self.assertEqual(latest_sunday(date(2026, 10, 24)), date(2026, 10, 18))


class TestFilenameParsing(unittest.TestCase):
    def test_dn900r_name(self):
        dt = parse_recorder_filename("10182026080000_DN-900R.mp3")
        self.assertEqual(dt, datetime(2026, 10, 18, 8, 0, 0))

    def test_unparseable_name(self):
        self.assertIsNone(parse_recorder_filename("random-audio.mp3"))


class TestGrouping(unittest.TestCase):
    def test_two_services_one_sunday(self):
        files = [
            rf("a.mp3", datetime(2026, 10, 18, 8, 0)),
            rf("b.mp3", datetime(2026, 10, 18, 8, 10)),
            rf("c.mp3", datetime(2026, 10, 18, 8, 20)),
            rf("d.mp3", datetime(2026, 10, 18, 11, 0)),
            rf("e.mp3", datetime(2026, 10, 18, 11, 10)),
        ]
        services = group_into_services(files_for_date(files, date(2026, 10, 18)), gap_minutes=20)
        self.assertEqual(len(services), 2)
        self.assertEqual(len(services[0].files), 3)
        self.assertEqual(len(services[1].files), 2)
        self.assertEqual(services[0].service_id, "2026-10-18_0800")
        self.assertEqual(services[1].service_id, "2026-10-18_1100")

    def test_other_dates_are_excluded(self):
        files = [
            rf("a.mp3", datetime(2026, 10, 18, 8, 0)),
            rf("b.mp3", datetime(2026, 10, 17, 17, 30)),  # Saturday vigil - not the target Sunday
        ]
        self.assertEqual(len(files_for_date(files, date(2026, 10, 18))), 1)


if __name__ == "__main__":
    unittest.main()
