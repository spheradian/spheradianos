"""Checks for the splash time-budget measurement (BOOT-EXPERIENCE.md 6.1).

Run from the repository root: python3 -m unittest discover -s tests -v
Standard library only, no QEMU, no root. The boots themselves run in
scripts/boot-budget.py.
"""

import importlib.util
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CHROOT = ROOT / "config" / "includes.chroot"
UNITS = CHROOT / "etc" / "systemd" / "system"
PROBE = CHROOT / "usr" / "lib" / "spheradianos" / "boot-timing"


def load_budget():
    spec = importlib.util.spec_from_file_location("boot_budget", ROOT / "scripts" / "boot-budget.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


budget = load_budget()

LIVE_CFG = """\
label live-amd64
\tmenu label ^SpheradianOS Live (amd64)
\tmenu default
\tlinux /live/vmlinuz
\tinitrd /live/initrd.img
\tappend boot=live components quiet splash initrd=/live/initrd.img username=spheradian

label live-amd64-failsafe
\tlinux /live/vmlinuz
\tappend boot=live components nosplash vga=788
"""


class CommandLine(unittest.TestCase):
    def test_the_default_entry_command_line_is_read_without_the_initrd(self):
        self.assertEqual(
            budget.default_append(LIVE_CFG),
            ["boot=live", "components", "quiet", "splash", "username=spheradian"],
        )

    def test_a_missing_entry_is_an_error(self):
        with self.assertRaises(ValueError):
            budget.default_append(LIVE_CFG, "live-arm64")

    def test_the_two_variants_differ_only_in_the_splash_switch(self):
        self.assertEqual(budget.VARIANTS[budget.SPLASH_ON], [])
        self.assertEqual(budget.VARIANTS[budget.SPLASH_OFF], ["plymouth.enable=0"])


class Report(unittest.TestCase):
    def test_the_probe_line_is_read_in_milliseconds(self):
        text = "noise\nspheradian-timing userspace=1328395 finish=4344900 session=4327944\nmore"
        self.assertEqual(
            budget.parse_timing(text),
            {"userspace": 1328.395, "finish": 4344.9, "session": 4327.944},
        )

    def test_no_line_or_an_unrecorded_timestamp_is_no_report(self):
        self.assertIsNone(budget.parse_timing("spheradian-tim"))
        self.assertIsNone(budget.parse_timing("spheradian-timing userspace=1 finish=2 session=0\n"))


class Statistics(unittest.TestCase):
    def test_variants_alternate_and_switch_which_leads(self):
        order = budget.schedule(4)
        self.assertEqual(order.count(budget.SPLASH_ON), 4)
        self.assertEqual(order.count(budget.SPLASH_OFF), 4)
        self.assertEqual(order[0], budget.SPLASH_ON)
        self.assertEqual(order[2], budget.SPLASH_OFF)

    def test_the_interval_brackets_a_known_difference(self):
        off = [4000.0 + (i % 7) * 15 for i in range(20)]
        on = [value + 100 for value in off]
        low, high = budget.median_difference_interval(on, off)
        self.assertLessEqual(low, 100)
        self.assertGreaterEqual(high, 100)
        self.assertLess(high - low, 100)

    def test_the_interval_is_reproducible(self):
        on, off = [5.0, 9.0, 7.0, 6.0], [1.0, 4.0, 2.0, 3.0]
        self.assertEqual(
            budget.median_difference_interval(on, off), budget.median_difference_interval(on, off)
        )

    def test_the_verdict_needs_the_whole_interval_on_one_side(self):
        self.assertEqual(budget.verdict((20, 140), 150), "within budget")
        self.assertEqual(budget.verdict((160, 300), 150), "over budget")
        self.assertTrue(budget.verdict((80, 160), 150).startswith("unresolved"))
        self.assertTrue(budget.verdict((160, 160), 150, boots=1).startswith("unresolved"))


class Probe(unittest.TestCase):
    def test_the_probe_is_inert_without_its_kernel_parameter(self):
        unit = (UNITS / "spheradianos-test-timing.service").read_text()
        self.assertIn("ConditionKernelCommandLine=spheradian.test.timing", unit)
        self.assertIn("ExecStart=/usr/lib/spheradianos/boot-timing", unit)
        # Type=exec lets the boot finish while the probe waits for it.
        self.assertIn("Type=exec", unit)
        self.assertTrue((UNITS / "multi-user.target.wants" / "spheradianos-test-timing.service").is_symlink())
        self.assertTrue(os.access(PROBE, os.X_OK))

    def test_the_measurement_layers_every_probe_file(self):
        for name in budget.PROBE_FILES:
            self.assertTrue((CHROOT / name).exists() or (CHROOT / name).is_symlink(), name)

    def test_the_probe_writes_one_line_the_measurement_can_read(self):
        with tempfile.TemporaryDirectory() as root:
            tools = Path(root, "bin")
            tools.mkdir()
            fakes = {
                "systemd-analyze": "exit 0\n",
                "systemctl": (
                    'case "$*" in\n'
                    "  *UserspaceTimestampMonotonic*) echo 1300000 ;;\n"
                    "  *FinishTimestampMonotonic*) echo 4300000 ;;\n"
                    "  *getty@tty1*) echo 4280000 ;;\n"
                    "esac\n"
                ),
            }
            for name, body in fakes.items():
                path = tools / name
                path.write_text("#!/bin/sh\n" + body)
                path.chmod(0o755)
            port = Path(root, "serial")
            environment = dict(
                os.environ, PATH=f"{tools}:{os.environ['PATH']}", SPHERADIAN_TIMING_PORT=str(port)
            )
            result = subprocess.run([str(PROBE)], env=environment, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(
                budget.parse_timing(port.read_text()),
                {"userspace": 1300.0, "finish": 4300.0, "session": 4280.0},
            )

    def test_the_probe_gives_up_if_the_boot_never_finishes(self):
        with tempfile.TemporaryDirectory() as root:
            tools = Path(root, "bin")
            tools.mkdir()
            analyze = tools / "systemd-analyze"
            analyze.write_text("#!/bin/sh\nexit 1\n")
            analyze.chmod(0o755)
            environment = dict(
                os.environ,
                PATH=f"{tools}:{os.environ['PATH']}",
                SPHERADIAN_TIMING_PORT=str(Path(root, "serial")),
                SPHERADIAN_TIMING_TRIES="2",
            )
            result = subprocess.run([str(PROBE)], env=environment, capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertFalse(Path(root, "serial").exists())


if __name__ == "__main__":
    unittest.main()
