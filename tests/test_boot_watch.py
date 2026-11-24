"""Behaviour tests for the boot watch (BOOT-EXPERIENCE.md, section 7 and milestone B3).

The script runs against fake `plymouth` and `systemctl` commands, so the tests
need no root, no systemd and no splash.
"""

import os
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CHROOT = ROOT / "config" / "includes.chroot"
WATCH = CHROOT / "usr" / "lib" / "spheradianos" / "boot-watch"
UNITS = CHROOT / "etc" / "systemd" / "system"

FAKE_PLYMOUTH = """#!/bin/sh
# Answers --ping while the splash "is up"; records a quit and then stops answering.
state="$FAKE_DIR/pings"
case "$1" in
--ping)
	[ -e "$FAKE_DIR/quit" ] && exit 1
	count=$(cat "$state" 2>/dev/null || echo 0)
	[ "$count" -ge "$FAKE_SPLASH_SECONDS" ] && exit 1
	echo $((count + 1)) >"$state"
	exit 0
	;;
quit) touch "$FAKE_DIR/quit" ;;
esac
"""

FAKE_SYSTEMCTL = """#!/bin/sh
case "$1" in
list-units) printf '%s' "$FAKE_FAILED" ;;
list-jobs)
	if [ "$FAKE_JOBS" = changing ]; then
		count=$(cat "$FAKE_DIR/jobs" 2>/dev/null || echo 0)
		echo $((count + 1)) >"$FAKE_DIR/jobs"
		echo "$count some.service start running"
	else
		printf '%s' "$FAKE_JOBS"
	fi
	;;
esac
"""


def executable(path, text):
    path.write_text(text)
    path.chmod(path.stat().st_mode | stat.S_IXUSR)
    return str(path)


class BootWatch(unittest.TestCase):
    def watch(self, splash_seconds, failed="", jobs="", stall_seconds=3):
        """Run the watch against fakes; return (splash was ended, console text)."""
        with tempfile.TemporaryDirectory() as directory:
            fake = Path(directory)
            console = fake / "console"
            console.touch()
            environment = {
                **os.environ,
                "FAKE_DIR": directory,
                "FAKE_SPLASH_SECONDS": str(splash_seconds),
                "FAKE_FAILED": failed,
                "FAKE_JOBS": jobs,
                "SPHERADIAN_PLYMOUTH": executable(fake / "plymouth", FAKE_PLYMOUTH),
                "SPHERADIAN_SYSTEMCTL": executable(fake / "systemctl", FAKE_SYSTEMCTL),
                "SPHERADIAN_SLEEP": "true",
                "SPHERADIAN_CONSOLE": str(console),
                "SPHERADIAN_REPORT": str(fake / "run" / "boot-report"),
                "SPHERADIAN_STALL_SECONDS": str(stall_seconds),
            }
            result = subprocess.run([str(WATCH)], env=environment, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            report = fake / "run" / "boot-report"
            self.assertEqual(report.read_text() if report.exists() else "", console.read_text())
            return (fake / "quit").exists(), console.read_text()

    def test_does_nothing_when_no_splash_is_running_and_nothing_failed(self):
        ended, text = self.watch(splash_seconds=0)
        self.assertFalse(ended)
        self.assertEqual(text, "")

    def test_a_unit_that_failed_as_the_splash_left_is_still_reported(self):
        ended, text = self.watch(splash_seconds=0, failed="late.service loaded failed failed")
        self.assertFalse(ended)  # nothing to end: the splash is already gone
        self.assertIn("a unit failed during startup", text)
        self.assertIn("late.service", text)

    def test_a_healthy_boot_is_left_alone(self):
        ended, text = self.watch(splash_seconds=10, jobs="changing", stall_seconds=3)
        self.assertFalse(ended)
        self.assertEqual(text, "")

    def test_a_failed_unit_ends_the_splash_and_is_named_in_plain_text(self):
        ended, text = self.watch(splash_seconds=50, failed="broken.service loaded failed failed Broken")
        self.assertTrue(ended)
        self.assertIn("a unit failed during startup", text)
        self.assertIn("broken.service", text)
        self.assertIn("journalctl -b", text)

    def test_a_stalled_boot_ends_the_splash_and_says_what_it_waits_for(self):
        ended, text = self.watch(splash_seconds=50, jobs="42 slow.service start running", stall_seconds=3)
        self.assertTrue(ended)
        self.assertIn("no progress for 3 seconds", text)
        self.assertIn("slow.service", text)

    def test_a_slow_boot_that_keeps_progressing_is_not_a_stall(self):
        ended, _ = self.watch(splash_seconds=30, jobs="changing", stall_seconds=3)
        self.assertFalse(ended)

    def test_a_stall_shorter_than_the_limit_is_tolerated(self):
        ended, _ = self.watch(splash_seconds=3, jobs="42 slow.service start running", stall_seconds=20)
        self.assertFalse(ended)


class LoginReport(unittest.TestCase):
    SNIPPET = CHROOT / "etc" / "profile.d" / "spheradianos-boot-report.sh"

    def login(self, report_text):
        with tempfile.TemporaryDirectory() as directory:
            report = Path(directory, "boot-report")
            if report_text is not None:
                report.write_text(report_text)
            result = subprocess.run(
                ["sh", "-eu", "-c", f". {self.SNIPPET}; echo prompt"],
                env={**os.environ, "SPHERADIAN_REPORT": str(report)},
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            return result.stdout

    def test_a_boot_problem_is_shown_at_login(self):
        self.assertEqual(self.login("SpheradianOS: a unit failed\n"), "SpheradianOS: a unit failed\nprompt\n")

    def test_a_healthy_boot_shows_nothing_extra_at_login(self):
        self.assertEqual(self.login(None), "prompt\n")


class Units(unittest.TestCase):
    def test_watch_runs_early_and_only_with_a_splash(self):
        unit = (UNITS / "spheradianos-boot-watch.service").read_text()
        self.assertIn("ExecStart=/usr/lib/spheradianos/boot-watch", unit)
        self.assertIn("ConditionKernelCommandLine=splash", unit)
        self.assertIn("After=plymouth-start.service", unit)
        self.assertTrue((UNITS / "sysinit.target.wants" / "spheradianos-boot-watch.service").is_symlink())
        self.assertTrue(os.access(WATCH, os.X_OK))

    def test_fault_injection_units_are_inert_without_their_kernel_parameter(self):
        for name, parameter in (("fail", "spheradian.test.fail"), ("stall", "spheradian.test.stall")):
            unit = (UNITS / f"spheradianos-test-{name}.service").read_text()
            self.assertIn(f"ConditionKernelCommandLine={parameter}", unit)
            self.assertIn("Before=plymouth-quit.service", unit)


if __name__ == "__main__":
    unittest.main()
