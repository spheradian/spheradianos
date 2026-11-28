#!/bin/sh
# Build the SpheradianOS live ISO. Requires: live-build, debootstrap, squashfs-tools, xorriso, python3, root.
set -eu
cd "$(dirname "$0")/.."

for tool in lb debootstrap mksquashfs xorriso python3; do
	command -v "$tool" >/dev/null 2>&1 || {
		echo "error: '$tool' not found. On Debian/Ubuntu: sudo apt install live-build debootstrap squashfs-tools xorriso python3" >&2
		exit 1
	}
done
[ "$(id -u)" -eq 0 ] || {
	echo "error: run as root (sudo scripts/build.sh)" >&2
	exit 1
}

lb clean --purge >/dev/null 2>&1 || true
lb config
lb build
scripts/size-report.sh
