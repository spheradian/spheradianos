#!/usr/bin/env python3
"""Measure what the boot splash adds to boot time, against its 150 ms budget.

Budget (docs/BOOT-EXPERIENCE.md 6.1): the splash may add at most 150 ms of
wall-clock boot time compared with a boot without it.

Method: boot the ISO in KVM-accelerated QEMU many times, alternating between
the normal command line and the same command line with plymouth.enable=0, the
switch that turns the splash off. Each boot reports its own systemd timestamps
on a serial port (xsphereos-test-timing.service, enabled by
xsphere.test.timing), so the measured span is from the kernel's start to the
tty1 session start, at microsecond resolution. The firmware, the bootloader and
QEMU itself are left out: they do not depend on the splash and were most of the
noise in the earlier screenshot-based comparison.

The kernel is started directly by QEMU (-kernel) with the default boot entry's
command line read from the ISO, so no keys need to be typed into a menu. A
small extra squashfs layer holding the repository's probe is added to a copy
of the ISO, so images built before the probe existed can be measured too.

The verdict uses a 95% bootstrap interval for the difference of the medians:
within budget if its upper end is at most the budget, over budget if its lower
end is above it, otherwise (or with fewer than five boots per variant)
unresolved: run more boots.

With --reduced-motion the splash boots use the still theme
(xsphere.motion=reduced), which separates the animation's cost from the cost
of having a splash at all.

Usage: scripts/boot-budget.py [ISO] [--runs N] [--budget-ms MS] [--reduced-motion] [--json FILE]
Needs qemu-system-x86_64, xorriso, mksquashfs and a writable /dev/kvm.
Standard library only otherwise. Exit status: 0 within budget, 1 over budget,
2 unresolved, 3 a boot did not report.
"""

import argparse
import json
import os
import random
import re
import shutil
import statistics
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CHROOT = ROOT / "config" / "includes.chroot"
PROBE_FILES = (
    "usr/lib/xsphereos/boot-timing",
    "etc/systemd/system/xsphereos-test-timing.service",
    "etc/systemd/system/multi-user.target.wants/xsphereos-test-timing.service",
)
PROBE_LAYER = "/live/zz-xsphereos-timing.squashfs"
BOOT_ENTRY = "live-amd64"
SPLASH_ON, SPLASH_OFF = "splash on", "splash off"
VARIANTS = {SPLASH_ON: [], SPLASH_OFF: ["plymouth.enable=0"]}
BOOT_TIMEOUT = 120.0
RESAMPLES = 4000
MIN_BOOTS = 5  # per variant; fewer give no verdict
TIMING_LINE = re.compile(r"xsphere-timing((?: \w+=\d+)+)")


def default_append(live_cfg, entry=BOOT_ENTRY):
    """The kernel command line of one ISOLINUX entry."""
    block = re.search(rf"(?ms)^label {re.escape(entry)}\s*$(.*?)(?=^label |\Z)", live_cfg)
    if not block:
        raise ValueError(f"no boot entry {entry!r}")
    append = re.search(r"(?m)^\s*append\s+(.*\S)\s*$", block.group(1))
    if not append:
        raise ValueError(f"boot entry {entry!r} has no append line")
    return [word for word in append.group(1).split() if not word.startswith("initrd=")]


def parse_timing(text):
    """The probe's report as {name: milliseconds}, or None if it is absent or incomplete."""
    match = TIMING_LINE.search(text)
    if not match:
        return None
    values = dict(field.split("=") for field in match.group(1).split())
    if any(int(value) == 0 for value in values.values()):
        return None  # a timestamp systemd never recorded
    return {name: int(value) / 1000 for name, value in values.items()}


def median_difference_interval(on, off, resamples=RESAMPLES, seed=0):
    """95% bootstrap interval for median(on) - median(off)."""
    generator = random.Random(seed)  # noqa: S311 - resampling for statistics, not secrets
    differences = sorted(
        statistics.median(generator.choices(on, k=len(on)))
        - statistics.median(generator.choices(off, k=len(off)))
        for _ in range(resamples)
    )
    return differences[int(0.025 * resamples)], differences[int(0.975 * resamples) - 1]


def verdict(interval, budget, boots=MIN_BOOTS):
    if boots < MIN_BOOTS:
        return "unresolved: run more boots"
    low, high = interval
    if high <= budget:
        return "within budget"
    if low > budget:
        return "over budget"
    return "unresolved: run more boots"


def schedule(runs):
    """Alternate the variants, switching the leading one each round, so slow drift cancels out."""
    order = []
    for round_ in range(runs):
        pair = [SPLASH_ON, SPLASH_OFF]
        order.extend(pair if round_ % 2 == 0 else pair[::-1])
    return order


def tool(name):
    """The absolute path of a required program."""
    path = shutil.which(name)
    if not path:
        sys.exit(f"boot-budget: {name} not found in PATH")
    return path


def prepare(iso, workdir):
    """Extract the kernel and command line and make an ISO copy with the probe layer."""
    xorriso, mksquashfs = tool("xorriso"), tool("mksquashfs")
    workdir = Path(workdir)
    extracted = {name: workdir / name for name in ("vmlinuz", "initrd.img", "live.cfg")}
    subprocess.run(  # noqa: S603 - fixed argv, no shell
        [
            xorriso,
            "-osirrox",
            "on",
            "-indev",
            str(iso),
            "-extract",
            "/live/vmlinuz",
            str(extracted["vmlinuz"]),
            "-extract",
            "/live/initrd.img",
            str(extracted["initrd.img"]),
            "-extract",
            "/isolinux/live.cfg",
            str(extracted["live.cfg"]),
        ],
        check=True,
        capture_output=True,
    )
    layer_root = workdir / "layer"
    for name in PROBE_FILES:
        source, target = CHROOT / name, layer_root / name
        target.parent.mkdir(parents=True, exist_ok=True)
        if source.is_symlink():
            target.symlink_to(os.readlink(source))
        else:
            shutil.copy2(source, target)
    layer = workdir / "probe.squashfs"
    subprocess.run(  # noqa: S603 - fixed argv, no shell
        [mksquashfs, str(layer_root), str(layer), "-all-root", "-noappend", "-quiet"],
        check=True,
        capture_output=True,
    )
    patched = workdir / "measured.iso"
    subprocess.run(  # noqa: S603 - fixed argv, no shell
        [
            xorriso,
            "-indev",
            str(iso),
            "-outdev",
            str(patched),
            "-boot_image",
            "any",
            "replay",
            "-map",
            str(layer),
            PROBE_LAYER,
        ],
        check=True,
        capture_output=True,
    )
    append = default_append(extracted["live.cfg"].read_text())
    return patched, extracted["vmlinuz"], extracted["initrd.img"], append


def boot_once(iso, kernel, initrd, command_line, workdir):
    """Boot once and return the probe's report, or None if it never came."""
    serial = Path(workdir) / "serial.log"
    serial.unlink(missing_ok=True)
    process = subprocess.Popen(  # noqa: S603 - fixed argv, no shell
        [
            tool("qemu-system-x86_64"),
            "-m",
            "2048",
            "-smp",
            "2",
            "-enable-kvm",
            "-cpu",
            "host",
            "-display",
            "none",
            "-device",
            "virtio-vga",
            "-nic",
            "none",
            "-cdrom",
            str(iso),
            "-kernel",
            str(kernel),
            "-initrd",
            str(initrd),
            "-append",
            " ".join(command_line),
            "-serial",
            f"file:{serial}",
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        deadline = time.monotonic() + BOOT_TIMEOUT
        while time.monotonic() < deadline and process.poll() is None:
            report = parse_timing(serial.read_text(errors="replace")) if serial.exists() else None
            if report:
                return report
            time.sleep(0.2)
        return None
    finally:
        process.kill()
        process.wait()


def summarise(samples, budget):
    on = [run["session"] for run in samples[SPLASH_ON]]
    off = [run["session"] for run in samples[SPLASH_OFF]]
    interval = median_difference_interval(on, off)
    return {
        "budget_ms": budget,
        "boots_per_variant": len(on),
        "median_session_ms": {SPLASH_ON: statistics.median(on), SPLASH_OFF: statistics.median(off)},
        "spread_ms": {SPLASH_ON: max(on) - min(on), SPLASH_OFF: max(off) - min(off)},
        "added_ms": statistics.median(on) - statistics.median(off),
        "added_ms_95": list(interval),
        "verdict": verdict(interval, budget, len(on)),
        "samples": samples,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("iso", nargs="?", type=Path)
    parser.add_argument("--runs", type=int, default=10, help="boots per variant (default 10)")
    parser.add_argument("--budget-ms", type=float, default=150.0)
    parser.add_argument(
        "--reduced-motion",
        action="store_true",
        help="measure the still theme (xsphere.motion=reduced) instead of the animated one",
    )
    parser.add_argument("--json", type=Path, help="also write the results here")
    options = parser.parse_args()
    if not os.access("/dev/kvm", os.W_OK):
        sys.exit("boot-budget: needs a writable /dev/kvm; emulated timing means nothing")
    iso = options.iso or next(iter(sorted(ROOT.glob("*.iso"))), None)
    if not iso:
        sys.exit("boot-budget: no ISO found; build first")

    samples = {SPLASH_ON: [], SPLASH_OFF: []}
    with tempfile.TemporaryDirectory() as workdir:
        patched, kernel, initrd, append = prepare(iso, workdir)
        base = [*append, "xsphere.test.timing"]
        variants = dict(VARIANTS)
        if options.reduced_motion:
            variants[SPLASH_ON] = ["xsphere.motion=reduced"]
        # One discarded boot first, so the ISO is in the host's page cache for every measured boot.
        boot_once(patched, kernel, initrd, base, workdir)
        for index, variant in enumerate(schedule(options.runs), 1):
            report = boot_once(patched, kernel, initrd, base + variants[variant], workdir)
            if report is None:
                print(f"boot {index} ({variant}) did not report its timing", file=sys.stderr)
                sys.exit(3)
            samples[variant].append(report)
            print(f"boot {index:2d}  {variant:10s}  session at {report['session']:8.1f} ms", flush=True)

    result = summarise(samples, options.budget_ms)
    low, high = result["added_ms_95"]
    medians = result["median_session_ms"]
    print(
        f"median session start: {medians[SPLASH_ON]:.1f} ms with the splash, "
        f"{medians[SPLASH_OFF]:.1f} ms without"
    )
    print(f"added by the splash: {result['added_ms']:+.1f} ms (95% interval {low:+.1f} to {high:+.1f} ms)")
    print(f"budget {options.budget_ms:.0f} ms: {result['verdict']}")
    if options.json:
        options.json.write_text(json.dumps(result, indent=2) + "\n")
    sys.exit({"within budget": 0, "over budget": 1}.get(result["verdict"], 2))


if __name__ == "__main__":
    main()
