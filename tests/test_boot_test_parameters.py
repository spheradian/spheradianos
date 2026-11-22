"""Tests for the kernel parameters scripts/boot-test.py adds to each boot.

Every check that types into the tty1 shell needs xsphere.session=console once
the M1 graphical session is installed, otherwise the kiosk owns tty1.
"""

import contextlib
import importlib.util
import io
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parent.parent


def load_boot_test():
    path = REPO_ROOT / "scripts" / "boot-test.py"
    spec = importlib.util.spec_from_file_location("boot_test", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


boot_test = load_boot_test()


class BootParameterTests(unittest.TestCase):
    def test_default_boot_adds_nothing(self) -> None:
        self.assertEqual(boot_test.boot_parameters(session_installed=True), [])
        self.assertEqual(boot_test.boot_parameters(session_installed=False), [])

    def test_console_flag_selects_the_console_session(self) -> None:
        self.assertEqual(
            boot_test.boot_parameters(console=True, session_installed=True),
            ["xsphere.session=console"],
        )

    def test_faults_use_the_console_session_when_the_kiosk_is_installed(self) -> None:
        for fault in ("fail", "stall"):
            with self.subTest(fault=fault):
                self.assertEqual(
                    boot_test.boot_parameters(fault=fault, session_installed=True),
                    ["xsphere.session=console", f"xsphere.test.{fault}"],
                )

    def test_faults_without_the_kiosk_keep_the_m0_command_line(self) -> None:
        self.assertEqual(
            boot_test.boot_parameters(fault="fail", session_installed=False),
            ["xsphere.test.fail"],
        )

    def test_console_is_never_added_twice(self) -> None:
        self.assertEqual(
            boot_test.boot_parameters(
                console=True, reduced_motion=True, fault="fail", session_installed=True
            ),
            ["xsphere.session=console", "xsphere.motion=reduced", "xsphere.test.fail"],
        )


def ppm(width, height, value):
    return f"P6\n{width} {height}\n255\n".encode() + bytes([value]) * (width * height * 3)


class FakeGuest:
    slowdown = 1

    def __init__(self, data):
        self.data = data

    def screen(self, keep_as=None):
        return boot_test.Frame(self.data)


class TimeoutEvidenceTests(unittest.TestCase):
    """A check that times out must say what was on screen (CI keeps no video)."""

    def wait_for_nothing(self, folder=None):
        guest = FakeGuest(ppm(400, 300, 7))
        environment = {"XSPHERE_TEST_FAILURE_SHOTS": folder} if folder else {}
        stderr = io.StringIO()
        with (
            mock.patch.dict(os.environ, environment, clear=False),
            mock.patch.object(boot_test, "POLL", 0),
            contextlib.redirect_stderr(stderr),
        ):
            if not folder:
                os.environ.pop("XSPHERE_TEST_FAILURE_SHOTS", None)
            passed = boot_test.wait_until(lambda frame: False, guest, 0.05, None, "exit")
        return passed, stderr.getvalue()

    def test_timeout_prints_a_summary_of_the_last_screen(self) -> None:
        passed, stderr = self.wait_for_nothing()
        self.assertFalse(passed)
        self.assertIn("exit: timed out", stderr)
        self.assertIn("400x300", stderr)
        self.assertIn("centre 7.0", stderr)

    def test_timeout_saves_the_last_screen_when_asked(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            folder = str(Path(tmpdir) / "failures")
            passed, stderr = self.wait_for_nothing(folder)
            saved = sorted(Path(folder).glob("*-exit.ppm"))
            self.assertFalse(passed)
            self.assertEqual(len(saved), 1)
            self.assertEqual(saved[0].read_bytes(), ppm(400, 300, 7))
            self.assertIn(str(saved[0]), stderr)


if __name__ == "__main__":
    unittest.main()
