#!/usr/bin/env python3
"""Boot the live ISO headless in QEMU and check the boot splash contract.

Asserts (docs/BOOT-EXPERIENCE.md, milestone B1):
  1. the splash is shown: bright sphere centre on a black screen;
  2. the splash exits cleanly: the sphere is gone and console text is visible;
  3. the session starts: a command typed on tty1 is executed by the
     auto-logged-in user (the guest powers itself off).

Usage: scripts/boot-test.py [ISO] [--shots DIR]
Standard library only. Uses KVM when /dev/kvm is writable, else emulation.
"""

import argparse
import json
import os
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
POWEROFF_TIMEOUT = 40.0
POLL = 0.5
KEYS = {" ": "spc", "\n": "ret"}


class Guest:
    """A QEMU guest driven over QMP."""

    def __init__(self, iso, workdir):
        self.workdir = workdir
        sock = os.path.join(workdir, "qmp.sock")
        accel = ["-enable-kvm", "-cpu", "host"] if os.access("/dev/kvm", os.W_OK) else []
        self.slowdown = 1 if accel else 8
        self.process = subprocess.Popen(
            ["qemu-system-x86_64", "-m", "2048", "-smp", "2", *accel,
             "-display", "none", "-device", "virtio-vga", "-nic", "none",
             "-cdrom", str(iso), "-boot", "d", "-qmp", f"unix:{sock},server,nowait"]
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
            key = {"type": "qcode", "data": KEYS.get(char, char)}
            self.command("send-key", keys=[key])
            time.sleep(0.05)

    def screen(self, keep_as=None):
        path = os.path.join(self.workdir, "screen.ppm")
        self.command("screendump", filename=path)
        time.sleep(0.1)
        data = Path(path).read_bytes()
        if keep_as:
            Path(keep_as).write_bytes(data)
        return Frame(data)

    def wait_for_exit(self, timeout):
        try:
            self.process.wait(timeout)
            return True
        except subprocess.TimeoutExpired:
            return False

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

    def shows_splash(self):
        corner_is_black = self.mean(0, 0, 120, 120) < 3
        return corner_is_black and self.centre_brightness() > 120

    def shows_console(self):
        text_at_top = self.peak(0, 0, min(400, self.width), 60) > 100
        return text_at_top and self.centre_brightness() < 10


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


def run(iso, shots):
    results = {}
    with tempfile.TemporaryDirectory() as workdir:
        guest = Guest(iso, workdir)
        try:
            time.sleep(MENU_WAIT * guest.slowdown)
            guest.type_text("\n")
            results["splash is shown"] = wait_until(
                Frame.shows_splash, guest, SPLASH_TIMEOUT, shots, "splash")
            results["splash exits to a readable console"] = results["splash is shown"] and wait_until(
                Frame.shows_console, guest, EXIT_TIMEOUT, shots, "exit")
            time.sleep(3 * guest.slowdown)
            guest.type_text("systemctl poweroff\n")
            results["session starts (typed command runs)"] = guest.wait_for_exit(
                POWEROFF_TIMEOUT * guest.slowdown)
        finally:
            guest.kill()
    return results


def find_iso():
    candidates = sorted(ROOT.glob("*.iso"))
    if not candidates:
        sys.exit("no ISO found; build first")
    return candidates[0]


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("iso", nargs="?", type=Path)
    parser.add_argument("--shots", type=Path, help="keep screenshots (PPM) in this directory")
    options = parser.parse_args()
    if options.shots:
        options.shots.mkdir(parents=True, exist_ok=True)

    results = run(options.iso or find_iso(), options.shots)
    for name, passed in results.items():
        print(f"{'PASS' if passed else 'FAIL'}  {name}")
    sys.exit(0 if all(results.values()) else 1)


if __name__ == "__main__":
    main()
