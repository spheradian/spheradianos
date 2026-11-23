#!/usr/bin/env python3
"""Boot the live ISO headless in QEMU and check the boot splash contract.

Asserts (docs/BOOT-EXPERIENCE.md, milestone B1):
  1. the splash is shown: bright sphere centre on a black screen, and it
     animates (or, with --reduced-motion, stays a still frame);
  2. the splash exits cleanly: the sphere is gone and console text is visible;
  3. the session starts: a command typed on tty1 is executed by the
     auto-logged-in user, and a failure report exists only if a failure was
     injected (--fault fail); with --fault stall, the watchdog ends the splash.

With --uefi the guest boots OVMF and GRUB instead of BIOS and ISOLINUX, with the
ISO attached as a disk, as a USB stick would be.

Usage: scripts/boot-test.py [ISO] [--shots DIR] [--reduced-motion] [--fault fail|stall] [--uefi]
Standard library only. Uses KVM when /dev/kvm is writable, else emulation.
"""

import argparse
import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MENU_WAIT = 4.0
SPLASH_TIMEOUT = 40.0
EXIT_TIMEOUT = 60.0
SESSION_TIMEOUT = 20.0
STALL_HOLD = 8.0  # well past a normal boot, well before the watchdog
WATCHDOG_TIMEOUT = 40.0  # the watchdog fires after 20 s without progress
POLL = 0.5
JOURNAL_TIMEOUT = 120.0  # the guest copies its journal 60 s after reaching multi-user
JOURNAL_END = "=== spheradianos-test-journal: end ==="
KEYS = {" ": "spc", "\n": "ret", "\t": "tab", ".": "dot", "=": "equal", "-": "minus", "/": "slash"}
SHIFTED = {"&": "7", "|": "backslash"}  # US layout, the live image default
REPORT = "/run/spheradianos/boot-report"
MOTION_SAMPLES = 6
OVMF_CODE = Path("/usr/share/OVMF/OVMF_CODE_4M.fd")
OVMF_VARS = Path("/usr/share/OVMF/OVMF_VARS_4M.fd")
GRUB_MENU_TIMEOUT = 15.0


class Guest:
    """A QEMU guest driven over QMP."""

    def __init__(self, iso, workdir, uefi=False):
        self.workdir = workdir
        self.uefi = uefi
        self.serial_log = Path(workdir) / "serial.log"
        sock = os.path.join(workdir, "qmp.sock")
        qemu = shutil.which("qemu-system-x86_64")
        if not qemu:
            raise RuntimeError("qemu-system-x86_64 not found in PATH")
        accel = ["-enable-kvm", "-cpu", "host"] if os.access("/dev/kvm", os.W_OK) else []
        self.slowdown = 1 if accel else 8
        medium = ["-cdrom", str(iso), "-boot", "d"]
        if uefi:
            # The firmware writes its variable store, so each boot gets a fresh copy.
            variables = os.path.join(workdir, "OVMF_VARS.fd")
            Path(variables).write_bytes(OVMF_VARS.read_bytes())
            # A disk, not QEMU's emulated CD drive: OVMF reads that so slowly that
            # GRUB needs about 45 s to load the kernel from it.
            medium = [
                "-drive",
                f"if=pflash,format=raw,readonly=on,file={OVMF_CODE}",
                "-drive",
                f"if=pflash,format=raw,file={variables}",
                "-drive",
                f"file={iso},if=virtio,format=raw,readonly=on",
            ]
        # Fixed executable resolved via PATH and explicit argv list without a shell.
        self.process = subprocess.Popen(  # noqa: S603
            [
                qemu,
                "-m",
                "2048",
                "-smp",
                "2",
                *accel,
                "-display",
                "none",
                "-device",
                "virtio-vga",
                "-nic",
                "none",
                *medium,
                "-qmp",
                f"unix:{sock},server,nowait",
                # The image copies the session journal to this port when it sees the
                # fw_cfg entry below (config/includes.chroot/usr/lib/spheradianos/test-journal).
                "-serial",
                f"file:{self.serial_log}",
                "-fw_cfg",
                "name=opt/spheradianos/test-journal,string=1",
            ]
        )
        self.channel = self._connect(sock)
        self.channel.readline()
        self.command("qmp_capabilities")

    @staticmethod
    def _connect(path):
        for _ in range(50):
            try:
                client = socket.socket(socket.AF_UNIX)
                client.connect(path)
                return client.makefile("rw")
            except OSError:
                time.sleep(0.1)
        raise RuntimeError("QEMU did not open its control socket")

    def command(self, name, **arguments):
        self.channel.write(json.dumps({"execute": name, "arguments": arguments}) + "\n")
        self.channel.flush()
        while True:
            reply = json.loads(self.channel.readline())
            if "return" in reply or "error" in reply:
                return reply

    def press(self, *names):
        self.command("send-key", keys=[{"type": "qcode", "data": name} for name in names])

    def type_text(self, text):
        for char in text:
            names = ["shift", SHIFTED[char]] if char in SHIFTED else [KEYS.get(char, char)]
            self.command("send-key", keys=[{"type": "qcode", "data": name} for name in names])
            time.sleep(0.05)

    def screen(self, keep_as=None):
        path = os.path.join(self.workdir, "screen.ppm")
        self.command("screendump", filename=path)
        time.sleep(0.1)
        data = Path(path).read_bytes()
        if keep_as:
            Path(keep_as).write_bytes(data)
        return Frame(data)

    def kill(self):
        if self.process.poll() is None:
            self.process.kill()
            self.process.wait()


class Frame:
    """A binary PPM screenshot with a few brightness probes."""

    def __init__(self, data):
        fields = data.split(None, 4)
        if fields[0] != b"P6":
            raise ValueError("unexpected screendump format")
        self.width, self.height = int(fields[1]), int(fields[2])
        self.pixels = fields[4]
        self.data = data

    def summary(self):
        """A one-line description of the screen, for logs when a check times out."""
        return (
            f"{self.width}x{self.height}, "
            f"corner {self.mean(0, 0, 120, 120):.1f}, "
            f"centre {self.centre_brightness():.1f}, "
            f"top-text peak {self.peak(0, 0, min(400, self.width), 60)}, "
            f"whole-screen mean {self.mean(0, 0, self.width, self.height):.1f}"
        )

    def mean(self, left, top, width, height):
        total = 0
        for y in range(top, top + height):
            start = (y * self.width + left) * 3
            total += sum(self.pixels[start : start + width * 3])
        return total / (width * height * 3)

    def peak(self, left, top, width, height):
        return max(
            max(self.pixels[(y * self.width + left) * 3 : (y * self.width + left + width) * 3])
            for y in range(top, top + height)
        )

    def centre_brightness(self):
        return self.mean(self.width // 2 - 8, self.height // 2 - 8, 16, 16)

    def seed_area(self):
        """Pixels of a small square around the centre, where only the seed draws.

        In the reduced-motion theme the seed never changes, although lattice
        regions may still change colour as the boot progresses.
        """
        half = min(self.width, self.height) // 40
        left, top = self.width // 2 - half, self.height // 2 - half
        span = 2 * half * 3
        rows = []
        for row in range(2 * half):
            start = ((top + row) * self.width + left) * 3
            rows.append(self.pixels[start : start + span])
        return b"".join(rows)

    def shows_splash(self):
        corner_is_black = self.mean(0, 0, 120, 120) < 3
        return corner_is_black and self.centre_brightness() > 120 and not self.shows_firmware_logo()

    def shows_firmware_logo(self):
        """OVMF's logo is also bright at the centre, but it is a solid white box
        that reaches 28 px above the centre, where the splash's glow has faded."""
        return self.mean(self.width // 2 - 90, self.height // 2 - 28, 180, 4) > 128

    def shows_grub_menu(self):
        """GRUB's text menu: dark centre, help text in the band above the bottom edge."""
        band_top = self.height * 85 // 100
        help_text = self.peak(0, band_top, self.width, self.height * 95 // 100 - band_top) > 100
        return help_text and self.centre_brightness() < 10

    def shows_console(self):
        text_at_top = self.peak(0, 0, min(400, self.width), 60) > 100
        return text_at_top and self.centre_brightness() < 10

    def shows_output_at_bottom(self):
        return self.peak(0, self.height - 40, 200, 30) > 100


def wait_until(predicate, guest, timeout, shots, label):
    deadline = time.time() + timeout * guest.slowdown
    count = 0
    frame = None
    while time.time() < deadline:
        keep = shots / f"{label}-{count:03d}.ppm" if shots else None
        frame = guest.screen(keep)
        if predicate(frame):
            return True
        count += 1
        time.sleep(POLL)
    report_timeout(label, frame)
    return False


def report_timeout(label, frame):
    """Say what was on screen when a check gave up; CI keeps no recording of the guest.

    With SPHERADIAN_TEST_FAILURE_SHOTS set, the last screenshot is also kept there.
    """
    if frame is None:
        print(f"{label}: timed out before any screenshot", file=sys.stderr)
        return
    print(f"{label}: timed out; last screen: {frame.summary()}", file=sys.stderr)
    folder = os.environ.get("SPHERADIAN_TEST_FAILURE_SHOTS")
    if folder:
        path = Path(folder)
        path.mkdir(parents=True, exist_ok=True)
        saved = path / f"{time.strftime('%H%M%S')}-{label}.ppm"
        saved.write_bytes(frame.data)
        print(f"{label}: last screen saved to {saved}", file=sys.stderr)


def splash_moves(guest):
    """True if the seed changes between screenshots, False if it stays identical.

    None when the splash ended before two comparable screenshots were taken.
    Without KVM the guest draws far fewer frames per second, so the gap between
    screenshots grows with the slowdown.
    """
    previous, verdict, taken = None, None, 0
    for _ in range(MOTION_SAMPLES):
        frame = guest.screen()
        if not frame.shows_splash():
            break
        taken += 1
        seed = frame.seed_area()
        if previous is not None:
            if seed != previous:
                return True
            verdict = False
        previous = seed
        time.sleep(0.25 * guest.slowdown)
    reason = "the splash ended" if verdict is None else "the seed did not change"
    print(f"motion check: {reason} after {taken} splash screenshot(s)", file=sys.stderr)
    return verdict


SESSION_UNIT = ROOT / "config" / "includes.chroot" / "etc" / "systemd" / "system" / "spheradian-session.service"


def boot_parameters(console=False, reduced_motion=False, fault=None, session_installed=False):
    """Return the extra kernel parameters for one boot.

    Fault checks type into the tty1 shell, so once the M1 kiosk session is
    installed they need the console session as well, or the kiosk owns tty1.
    """
    parameters = []
    if console or (fault and session_installed):
        parameters.append("spheradian.session=console")
    if reduced_motion:
        parameters.append("spheradian.motion=reduced")
    if fault:
        parameters.append(f"spheradian.test.{fault}")
    return parameters


def run(iso, shots, reduced_motion=False, fault=None, uefi=False, console=False):
    """Boot once and return {assertion: passed}."""
    session_installed = SESSION_UNIT.exists()
    parameters = boot_parameters(console, reduced_motion, fault, session_installed)
    graphical_m1 = not console and not fault and session_installed
    results = {}
    with tempfile.TemporaryDirectory() as workdir:
        guest = Guest(iso, workdir, uefi)
        try:
            if parameters and uefi:
                results["Esc opens the hidden GRUB menu"] = open_grub_menu(guest, shots)
                if not results["Esc opens the hidden GRUB menu"]:
                    return results
                append_grub_parameters(guest, parameters)
            elif parameters:
                # Send space + backspace during BIOS POST -> ISOLINUX window so the
                # 0.5s timeout is cancelled at "boot:" without filling the input buffer.
                wait_secs = 8.0 if guest.slowdown > 1 else MENU_WAIT
                deadline = time.monotonic() + wait_secs
                while time.monotonic() < deadline:
                    guest.command("send-key", keys=[{"type": "qcode", "data": "spc"}])
                    time.sleep(0.05)
                    guest.command("send-key", keys=[{"type": "qcode", "data": "backspace"}])
                    time.sleep(0.20)
                guest.type_text("live-amd64 " + " ".join(parameters) + "\n")
            results["splash is shown"] = wait_until(
                Frame.shows_splash, guest, SPLASH_TIMEOUT, shots, "splash"
            )
            if not results["splash is shown"]:
                return results
            if fault == "stall":
                check_stall(guest, shots, results)
                return results
            moves = splash_moves(guest)
            if reduced_motion:
                results["reduced motion: splash is a still frame"] = moves is False
            elif not fault:
                results["splash animates"] = moves is True
            if graphical_m1:
                # The kiosk owns tty1, so the screen cannot prove the session runs (a
                # restart loop left it black, and early boot text once passed for it).
                # Ask the guest's journal instead (config/.../spheradianos/test-journal).
                running, client = session_state(wait_for_journal(guest, JOURNAL_TIMEOUT))
                if client:
                    print(f"graphical session shows: {client}", file=sys.stderr)
                results["the graphical session is running"] = running
                return results
            name = (
                "a failed unit ends the splash with text on the console"
                if fault
                else "splash exits to a readable console"
            )
            results[name] = wait_until(Frame.shows_console, guest, EXIT_TIMEOUT, shots, "exit")
            time.sleep(3 * guest.slowdown)
            # Only a real shell runs this, and "yes" fills the screen only when
            # the failure report is where it should be: present after an injected
            # failure, absent after a healthy boot.
            if fault:
                guest.type_text(f"test -e {REPORT} && yes\n")
                name = "session starts and the failure was reported in plain text"
            else:
                guest.type_text(f"test -e {REPORT} || yes\n")
                name = "session starts and a healthy boot reports no failure"
            results[name] = wait_until(Frame.shows_output_at_bottom, guest, SESSION_TIMEOUT, shots, "session")
        finally:
            guest.kill()
            report_serial_log(results, guest.serial_log)
    return results


def wait_for_journal(guest, timeout):
    """Return the guest serial log once the journal copy is complete, or what there is."""
    deadline = time.time() + timeout * guest.slowdown
    while True:
        text = (
            guest.serial_log.read_bytes().decode("utf-8", errors="replace")
            if guest.serial_log.exists()
            else ""
        )
        if JOURNAL_END in text or time.time() >= deadline:
            return text
        time.sleep(POLL)


def session_state(journal):
    """Return (running, client) for spheradian-session from the guest journal copy.

    Running means systemd reports it active and it never exited, so a restart
    loop caught between two attempts does not pass. The client is what cage shows.
    """
    if "spheradian-session.service: Main process exited" in journal:
        return False, None
    status = journal.split("=== spheradianos-test-journal: unit states ===", 1)[-1]
    if "Active: active (running)" not in status:
        return False, None
    if "cage -s -- /usr/bin/foot" in status:
        return True, "foot (fallback)"
    if "/usr/bin/spheradian" in status:
        return True, "spheradian"
    return True, None


def report_serial_log(results, path):
    """Print what the guest wrote to its serial port, but only when a check failed."""
    if all(results.values()):
        return
    content = path.read_bytes() if path.exists() else b""
    if not content.strip():
        print("no guest serial log (the session journal was not copied)", file=sys.stderr)
        return
    print("--- guest serial log ---", file=sys.stderr)
    print(content.decode("utf-8", errors="replace").rstrip(), file=sys.stderr)
    print("--- end of guest serial log ---", file=sys.stderr)


def open_grub_menu(guest, shots):
    """Tap Esc until GRUB shows its menu (ADR-002: the menu is hidden, timeout 0).

    Shift, which GRUB reads with keystatus, is not seen under OVMF in QEMU, so
    Esc is what works here.
    """
    deadline = time.time() + GRUB_MENU_TIMEOUT * guest.slowdown
    count = 0
    while time.time() < deadline:
        # GRUB looks for a key at one instant only, so keep taps close together
        # and take a screenshot only between bursts.
        for _ in range(10):
            guest.press("esc")
            time.sleep(0.02)
        keep = shots / f"menu-{count:03d}.ppm" if shots else None
        if guest.screen(keep).shows_grub_menu():
            return True
        count += 1
    return False


def append_grub_parameters(guest, parameters):
    """Edit the default entry and boot it with extra kernel parameters.

    "e" opens the entry on its first line, "setparams"; the kernel line is two
    lines down, after a blank one. F10 boots the edited entry.
    """
    time.sleep(0.5)  # let any Esc still queued reach the menu, where it does nothing
    guest.type_text("e")
    time.sleep(0.5)
    for key in ("down", "down", "end"):
        guest.press(key)
        time.sleep(0.05)
    guest.type_text(" " + " ".join(parameters))
    guest.press("f10")


def check_stall(guest, shots, results):
    """A boot that stops progressing keeps its splash, then yields to text."""
    # Not scaled by the slowdown: boot-watch counts its 20 s limit with the guest's
    # `sleep 1`, which follows wall-clock time even without KVM, so 8 s x 8 would
    # wait past the watchdog.
    time.sleep(STALL_HOLD)
    results["a stalled boot keeps the splash at first"] = guest.screen().shows_splash()
    results["the watchdog ends the splash with text on the console"] = wait_until(
        Frame.shows_console, guest, WATCHDOG_TIMEOUT, shots, "watchdog"
    )


def find_iso():
    candidates = sorted(ROOT.glob("*.iso"))
    if not candidates:
        sys.exit("no ISO found; build first")
    return candidates[0]


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("iso", nargs="?", type=Path)
    parser.add_argument("--shots", type=Path, help="keep screenshots (PPM) in this directory")
    parser.add_argument(
        "--reduced-motion",
        action="store_true",
        help="boot with spheradian.motion=reduced and expect a still splash",
    )
    parser.add_argument(
        "--fault",
        choices=("fail", "stall"),
        help="inject a failed unit or a stalled boot and expect text diagnostics",
    )
    parser.add_argument("--uefi", action="store_true", help="boot OVMF and GRUB instead of BIOS and ISOLINUX")
    parser.add_argument(
        "--console",
        action="store_true",
        help="boot with spheradian.session=console to test the tty1 shell path",
    )
    options = parser.parse_args()
    if options.shots:
        options.shots.mkdir(parents=True, exist_ok=True)

    results = run(
        options.iso or find_iso(),
        options.shots,
        options.reduced_motion,
        options.fault,
        uefi=options.uefi,
        console=options.console,
    )
    for name, passed in results.items():
        print(f"{'PASS' if passed else 'FAIL'}  {name}")
    sys.exit(0 if all(results.values()) else 1)


if __name__ == "__main__":
    main()
