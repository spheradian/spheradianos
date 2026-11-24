#!/usr/bin/env python3
"""Audit Debian package lists or built image manifests for forbidden packages.

Usage: scripts/audit_packages.py path/to/live-image-amd64.packages
"""

import argparse
import sys
from collections.abc import Iterable
from pathlib import Path

FORBIDDEN_PREFIXES: tuple[str, ...] = (
    "task-",
    "gnome-",
    "kde-",
    "plasma-",
    "xfce4",
    "lxqt",
    "lxde",
    "mate-",
    "cinnamon",
    "budgie-",
    "enlightenment",
    "xorg",
    "xwayland",
    "xserver-xorg",
    "kali-",
    "parrot-",
    "indi-",
    "libindi",
)

_FORBIDDEN_PACKAGE_NAMES = {
    "popularity-contest",
    "openssh-server",
    "telnet",
    "telnetd",
    "rsh-client",
    "rsh-server",
    "proxychains",
    "proxychains4",
    "gdm3",
    "sddm",
    "lightdm",
    "lxdm",
    "xdm",
}
FORBIDDEN_PACKAGES: frozenset[str] = frozenset(_FORBIDDEN_PACKAGE_NAMES)


def normalize_package_name(raw: str) -> str:
    """Return the bare Debian package name from a manifest or package-list line."""
    stripped = raw.strip()
    if not stripped or stripped.startswith("#"):
        return ""
    token = stripped.split(None, 1)[0]
    return token.split(":", 1)[0]


def is_forbidden_package(name: str) -> bool:
    """Return True if a normalized package name matches the forbidden policy."""
    if not name:
        return False
    return name in FORBIDDEN_PACKAGES or any(name.startswith(prefix) for prefix in FORBIDDEN_PREFIXES)


def find_forbidden_packages(entries: Iterable[str]) -> list[str]:
    """Return sorted unique forbidden package names found in raw manifest lines."""
    matches: set[str] = set()
    for entry in entries:
        name = normalize_package_name(entry)
        if is_forbidden_package(name):
            matches.add(name)
    return sorted(matches)


def audit_manifest_file(path: Path) -> tuple[int, list[str]]:
    """Read a built package manifest and return (package_count, forbidden_packages)."""
    lines = path.read_text(encoding="utf-8").splitlines()
    packages = [name for line in lines if (name := normalize_package_name(line))]
    return len(packages), find_forbidden_packages(packages)


def main(argv: list[str] | None = None) -> int:
    """CLI entry point returning 0 on clean manifests, 1 on violations, 2 on missing input."""
    parser = argparse.ArgumentParser(
        description="Audit an SpheradianOS package manifest against forbidden packages.",
    )
    parser.add_argument("manifest", type=Path, help="Path to live-image-amd64.packages")
    args = parser.parse_args(argv)

    manifest: Path = args.manifest
    if not manifest.is_file():
        print(f"error: manifest not found: {manifest}", file=sys.stderr)
        return 2

    count, forbidden = audit_manifest_file(manifest)
    if forbidden:
        joined = ", ".join(forbidden)
        print(f"error: forbidden package(s) in {manifest}: {joined}", file=sys.stderr)
        return 1

    print(f"OK: audited {count} packages in {manifest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
