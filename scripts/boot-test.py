#!/usr/bin/env python3
"""Boot the live ISO headless in QEMU and check the boot splash contract.

Asserts (docs/BOOT-EXPERIENCE.md, milestone B1):
  1. the splash is shown: bright sphere centre on a black screen, and it
     animates (or, with --reduced-motion, stays a still frame);
  2. the splash exits cleanly: the sphere is gone and console text is visible;
  3. the session starts: a command typed on tty1 is executed by the
     auto-logged-in user, and a failure report exists only if a failure was
     injected (--fault fail); with --fault stall, the watchdog ends the splash.

Usage: scripts/boot-test.py [ISO] [--shots DIR] [--reduced-motion] [--fault fail|stall]
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
KEYS = {" ": "spc", "\n": "ret", "\t": "tab", ".": "dot", "=": "equal", "-": "minus", "/": "slash"}
SHIFTED = {"&": "7", "|": "backslash"}  # US layout, the live image default
REPORT = "/run/xsphereos/boot-report"
MOTION_SAMPLES = 6


class Guest:
    """A QEMU guest driven over QMP."""

    def __init__(self, iso, workdir):
        self.workdir = workdir
        sock = os.path.join(workdir, "qmp.sock")
        qemu = shutil.which("qemu-system-x86_64")
        if not qemu:
            raise RuntimeError("qemu-system-x86_64 not found in PATH")
        accel = ["-enable-kvm", "-cpu", "host"] if os.access("/dev/kvm", os.W_OK) else []
        self.slowdown = 1 if accel else 8
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
                "-cdrom",
                str(iso),
                "-boot",
                "d",
                "-qmp",
                f"unix:{sock},server,nowait",
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
        return corner_is_black and self.centre_brightness() > 120

    def shows_console(self):
        text_at_top = self.peak(0, 0, min(400, self.width), 60) > 100
        return text_at_top and self.centre_brightness() < 10

    def shows_output_at_bottom(self):
        return self.peak(0, self.height - 40, 200, 30) > 100


def wait_until(predicate, guest, timeout, shots, label):
    deadline = time.time() + timeout * guest.slowdown
    count = 0
    while time.time() < deadline:
        keep = shots / f"{label}-{count:03d}.ppm" if shots else None
        if predicate(guest.screen(keep)):
            return True
        count += 1
        time.sleep(POLL)
    return False


def splash_moves(guest):
    """True if the seed changes between screenshots, False if it stays identical.

    None when the splash ended before two comparable screenshots were taken.
    """
    previous, verdict = None, None
    for _ in range(MOTION_SAMPLES):
        frame = guest.screen()
        if not frame.shows_splash():
            break
        seed = frame.seed_area()
        if previous is not None:
            if seed != previous:
                return True
            verdict = False
        previous = seed
        time.sleep(0.25)
    return verdict


def run(iso, shots, reduced_motion=False, fault=None):
    """Boot once and return {assertion: passed}."""
    parameters = []
    if reduced_motion:
        parameters.append("xsphere.motion=reduced")
    if fault:
        parameters.append(f"xsphere.test.{fault}")
    results = {}
    with tempfile.TemporaryDirectory() as workdir:
        guest = Guest(iso, workdir)
        try:
            if parameters:
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
    return results


def check_stall(guest, shots, results):
    """A boot that stops progressing keeps its splash, then yields to text."""
    # boot-watch counts its stall limit with guest `sleep 1`, which tracks wall-clock
    # time even under TCG emulation, so scaling STALL_HOLD by the slowdown (64 s)
    # overshoots the 20 s watchdog. Stay safely inside the stall window instead.
    hold_secs = 16.0 if guest.slowdown > 1 else STALL_HOLD
    time.sleep(hold_secs)
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
        help="boot with xsphere.motion=reduced and expect a still splash",
    )
    parser.add_argument(
        "--fault",
        choices=("fail", "stall"),
        help="inject a failed unit or a stalled boot and expect text diagnostics",
    )
    options = parser.parse_args()
    if options.shots:
        options.shots.mkdir(parents=True, exist_ok=True)

    results = run(options.iso or find_iso(), options.shots, options.reduced_motion, options.fault)
    for name, passed in results.items():
        print(f"{'PASS' if passed else 'FAIL'}  {name}")
    sys.exit(0 if all(results.values()) else 1)


if __name__ == "__main__":
    main()
