"""Tests for the kernel parameters scripts/boot-test.py adds to each boot.

Every check that types into the tty1 shell needs xsphere.session=console once
the M1 graphical session is installed, otherwise the kiosk owns tty1.
"""

import importlib.util
import unittest
from pathlib import Path

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


if __name__ == "__main__":
    unittest.main()
