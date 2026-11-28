"""Tests for the kernel parameters scripts/boot-test.py adds to each boot.

Every check that types into the tty1 shell needs spheradian.session=console once
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
            ["spheradian.session=console"],
        )

    def test_faults_use_the_console_session_when_the_kiosk_is_installed(self) -> None:
        for fault in ("fail", "stall"):
            with self.subTest(fault=fault):
                self.assertEqual(
                    boot_test.boot_parameters(fault=fault, session_installed=True),
                    ["spheradian.session=console", f"spheradian.test.{fault}"],
                )

    def test_faults_without_the_kiosk_keep_the_m0_command_line(self) -> None:
        self.assertEqual(
            boot_test.boot_parameters(fault="fail", session_installed=False),
            ["spheradian.test.fail"],
        )

    def test_console_is_never_added_twice(self) -> None:
        self.assertEqual(
            boot_test.boot_parameters(
                console=True, reduced_motion=True, fault="fail", session_installed=True
            ),
            ["spheradian.session=console", "spheradian.motion=reduced", "spheradian.test.fail"],
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
        environment = {"SPHERADIAN_TEST_FAILURE_SHOTS": folder} if folder else {}
        stderr = io.StringIO()
        with (
            mock.patch.dict(os.environ, environment, clear=False),
            mock.patch.object(boot_test, "POLL", 0),
            contextlib.redirect_stderr(stderr),
        ):
            if not folder:
                os.environ.pop("SPHERADIAN_TEST_FAILURE_SHOTS", None)
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


class SerialLogTests(unittest.TestCase):
    """A failed boot prints what the guest wrote to its serial port."""

    def report(self, results, content):
        with tempfile.TemporaryDirectory() as tmpdir:
            log = Path(tmpdir) / "serial.log"
            if content is not None:
                log.write_bytes(content)
            stderr = io.StringIO()
            with contextlib.redirect_stderr(stderr):
                boot_test.report_serial_log(results, log)
        return stderr.getvalue()

    def test_a_passing_boot_prints_nothing(self) -> None:
        self.assertEqual(self.report({"splash is shown": True}, b"journal line\n"), "")

    def test_a_failed_boot_prints_the_serial_log(self) -> None:
        stderr = self.report({"splash is shown": False}, b"cage: failed to start a session\n")
        self.assertIn("guest serial log", stderr)
        self.assertIn("cage: failed to start a session", stderr)

    def test_a_failed_boot_without_a_serial_log_says_so(self) -> None:
        self.assertIn("no guest serial log", self.report({"x": False}, None))
        self.assertIn("no guest serial log", self.report({"x": False}, b""))

    def test_undecodable_bytes_do_not_break_the_report(self) -> None:
        stderr = self.report({"x": False}, b"ok \xff\xfe end\n")
        self.assertIn("ok", stderr)
        self.assertIn("end", stderr)


RUNNING_KIOSK = """=== spheradianos-test-journal: session units ===
[   73.5] spheradianos (-session)[918]: pam_unix(login:session): session opened for user spheradian
=== spheradianos-test-journal: unit states ===
\u25cf spheradian-session.service - SpheradianOS M1 Prototype Session (Wayland Kiosk + Fallback)
     Active: active (running) since Sun 2026-11-22 19:50:30 UTC; 58s ago
     CGroup: /spheradian-session.slice/spheradian-session.service
             \u251c\u2500920 /bin/sh /usr/lib/spheradianos/spheradian-session
             \u251c\u2500925 cage -s -- /usr/bin/spheradian
             \u2514\u2500930 /usr/bin/spheradian
=== spheradianos-test-journal: kernel graphics ===
=== spheradianos-test-journal: end ===
"""

SCOPED_KIOSK = """=== spheradianos-test-journal: session units ===
=== spheradianos-test-journal: unit states ===
\u25cf spheradian-session.service - SpheradianOS M1 Prototype Session (Wayland Kiosk + Fallback)
     Active: active (running) since Mon 2026-11-23 02:44:46 UTC; 58s ago
   Main PID: 893 (spheradian-session)
     CGroup: /spheradian.slice/spheradian-session.slice/spheradian-session.service
             \u2023 893 /bin/sh /usr/lib/spheradianos/spheradian-session
=== spheradianos-test-journal: session processes ===
/bin/sh /usr/lib/spheradianos/spheradian-session
cage -s -- /usr/bin/spheradian
/usr/bin/spheradian
Xwayland :0 -rootless -core
=== spheradianos-test-journal: kernel graphics ===
=== spheradianos-test-journal: end ===
"""


class SessionStateTests(unittest.TestCase):
    """The graphical boot passes only if the kiosk session really runs."""

    def test_a_running_kiosk_with_spheradian(self) -> None:
        self.assertEqual(boot_test.session_state(RUNNING_KIOSK), (True, "spheradian"))

    def test_spheradian_in_the_logind_scope_is_found_in_the_process_list(self) -> None:
        # pam_systemd moves cage and its client out of the unit's cgroup, so
        # systemctl status shows only the launcher; the guest lists them instead.
        journal = SCOPED_KIOSK
        self.assertEqual(boot_test.session_state(journal), (True, "spheradian"))

    def test_foot_in_the_logind_scope_is_found_in_the_process_list(self) -> None:
        journal = SCOPED_KIOSK.replace("/usr/bin/spheradian", "/usr/bin/foot")
        self.assertEqual(boot_test.session_state(journal), (True, "foot (fallback)"))

    def test_a_running_kiosk_on_the_fallback_terminal(self) -> None:
        journal = RUNNING_KIOSK.replace("cage -s -- /usr/bin/spheradian", "cage -s -- /usr/bin/foot")
        journal = journal.replace("930 /usr/bin/spheradian", "930 /usr/bin/foot")
        self.assertEqual(boot_test.session_state(journal), (True, "foot (fallback)"))

    def test_a_restart_loop_is_not_running(self) -> None:
        journal = RUNNING_KIOSK.replace(
            "session opened for user spheradian\n",
            "session opened for user spheradian\n"
            "[   73.6] spheradianos systemd[1]: spheradian-session.service: Main process exited, "
            "code=exited, status=1/FAILURE\n",
        )
        self.assertEqual(boot_test.session_state(journal)[0], False)

    def test_a_session_waiting_to_restart_is_not_running(self) -> None:
        journal = RUNNING_KIOSK.replace(
            "Active: active (running)", "Active: activating (auto-restart) (Result: exit-code)"
        )
        self.assertEqual(boot_test.session_state(journal), (False, None))

    def test_no_journal_is_not_running(self) -> None:
        self.assertEqual(boot_test.session_state(""), (False, None))


FALLBACK_JOURNAL = """=== spheradianos-test-journal: session units ===
[   73.5] spheradianos (-session)[918]: pam_unix(login:session): session opened for user spheradian
[   73.6] spheradianos spheradian-session[920]: spheradian-session: starting spheradian
[   73.9] spheradianos spheradian-session[930]: [INFO  spheradian] Starting Spheradian v0.0.1
[   74.1] spheradianos spheradian-session[930]: No compatible GPU adapter found
[   74.2] spheradianos spheradian-session[920]: spheradian-session: spheradian exited with status 134, \
falling back to foot
[   74.3] spheradianos spheradian-session[940]: foot: some unrelated foot line
=== spheradianos-test-journal: unit states ===
"""


class SpheradianAttemptTests(unittest.TestCase):
    """When the kiosk falls back to foot, the boot test shows why spheradian exited."""

    def test_the_attempt_is_cut_from_start_to_fallback(self) -> None:
        attempt = boot_test.spheradian_attempt(FALLBACK_JOURNAL)
        self.assertIn("starting spheradian", attempt[0])
        self.assertIn("No compatible GPU adapter found", "\n".join(attempt))
        self.assertIn("falling back to foot", attempt[-1])
        self.assertNotIn("unrelated foot line", "\n".join(attempt))

    def test_no_attempt_without_the_launcher_marker(self) -> None:
        self.assertEqual(boot_test.spheradian_attempt(RUNNING_KIOSK), [])

    def test_an_attempt_that_never_fell_back_runs_to_the_end_of_the_section(self) -> None:
        journal = FALLBACK_JOURNAL.split("[   74.2]")[0] + "=== spheradianos-test-journal: unit states ===\n"
        attempt = boot_test.spheradian_attempt(journal)
        self.assertIn("No compatible GPU adapter found", attempt[-1])


if __name__ == "__main__":
    unittest.main()


class IsolinuxMenuKeyTests(unittest.TestCase):
    """The key that reveals the hidden menu must be harmless once it is shown.

    Screenshots lag the guest, so a key can land after the menu is already up.
    In syslinux's menu a space pages down (com32/menu/menumain.c, case ' '),
    which selected the fail-safe entry: its command line has no quiet splash,
    so the splash never showed and the boot failed in about half the runs.
    """

    # Keys that change the selected entry in a shown syslinux menu.
    MOVES_SELECTION = {"spc", "down", "up", "pgdn", "pgup", "left", "right", "end", "minus", "kp_add"}

    class MenuGuest:
        slowdown = 1

        def __init__(self, shown_after):
            self.shown_after = shown_after
            self.pressed = []

        def press(self, *names):
            self.pressed.extend(names)

        def screen(self, keep_as=None):
            shown = len(self.pressed) >= self.shown_after
            return mock.Mock(shows_isolinux_menu=mock.Mock(return_value=shown))

    def test_menu_keys_never_move_the_selection(self) -> None:
        guest = self.MenuGuest(shown_after=2)
        with mock.patch.object(boot_test.time, "sleep"):
            self.assertTrue(boot_test.open_isolinux_menu(guest, None))
        self.assertTrue(guest.pressed)
        self.assertFalse(self.MOVES_SELECTION & set(guest.pressed), guest.pressed)
