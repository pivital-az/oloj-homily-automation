"""Unit tests for the desktop GUI's command building (src/gui.py).

Only the pure argument builders are tested - no window is created,
so no display is needed.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from gui import (build_command, build_run_args, dropbox_web_url,
                 recorder_web_url)


class TestBuildRunArgs(unittest.TestCase):
    def test_latest_has_no_date_args(self):
        self.assertEqual(build_run_args("latest"), [])

    def test_single_date(self):
        self.assertEqual(build_run_args("single", single="2026-09-13"),
                         ["-Date", "2026-09-13"])

    def test_range(self):
        self.assertEqual(
            build_run_args("range", start="2026-09-01", end="2026-09-30"),
            ["-Start", "2026-09-01", "-End", "2026-09-30"])

    def test_range_with_no_sunday_is_refused(self):
        # 2026-09-07 (Mon) .. 2026-09-11 (Fri): no Sunday, so a run
        # would silently do nothing - the GUI must say so instead.
        with self.assertRaises(ValueError):
            build_run_args("range", start="2026-09-07", end="2026-09-11")

    def test_range_start_after_end_is_refused(self):
        with self.assertRaises(ValueError):
            build_run_args("range", start="2026-09-30", end="2026-09-01")

    def test_bad_date_is_refused(self):
        with self.assertRaises(ValueError):
            build_run_args("single", single="13/09/2026")

    def test_force_and_dry_run_flags(self):
        args = build_run_args("single", single="2026-09-13",
                              force=True, dry_run=True)
        self.assertIn("-Force", args)
        self.assertIn("-DryRun", args)

    def test_command_wraps_run_pipeline(self):
        cmd = build_command("single", single="2026-09-13", force=True)
        self.assertTrue(any(c.endswith("run_pipeline.ps1") for c in cmd))
        self.assertIn("-Date", cmd)
        self.assertIn("-Force", cmd)


class TestLinkUrls(unittest.TestCase):
    def test_recorder_url_from_bare_ip(self):
        self.assertEqual(recorder_web_url("10.16.10.232"),
                         "http://10.16.10.232/")

    def test_recorder_url_keeps_existing_scheme(self):
        self.assertEqual(recorder_web_url("http://10.16.10.232"),
                         "http://10.16.10.232/")

    def test_dropbox_url_below_dropbox_root(self):
        self.assertEqual(
            dropbox_web_url(r"C:\Users\AudioVisual\Dropbox\OLOJ\Homilies"),
            "https://www.dropbox.com/home/OLOJ/Homilies")

    def test_dropbox_url_quotes_spaces(self):
        self.assertEqual(
            dropbox_web_url(r"C:\Users\AudioVisual\Dropbox\Our Lady of Joy\Homilies"),
            "https://www.dropbox.com/home/Our%20Lady%20of%20Joy/Homilies")

    def test_dropbox_url_falls_back_to_home(self):
        self.assertEqual(dropbox_web_url(None), "https://www.dropbox.com/home")
        self.assertEqual(dropbox_web_url(r"C:\Users\AudioVisual\Dropbox"),
                         "https://www.dropbox.com/home")
        self.assertEqual(dropbox_web_url(r"D:\Elsewhere\Homilies"),
                         "https://www.dropbox.com/home")


if __name__ == "__main__":
    unittest.main()
