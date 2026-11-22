#!/bin/sh
# Build the XSphereOS live ISO inside a Debian container, so the host needs
# only podman. Use this on non-Debian hosts: Ubuntu ships an old live-build
# fork that does not understand the options in auto/config.
# Usage: sudo scripts/build-in-container.sh
set -eu
cd "$(dirname "$0")/.."

image=docker.io/library/debian:trixie

command -v podman >/dev/null 2>&1 || {
	echo "error: 'podman' not found. On Debian/Ubuntu: sudo apt install podman" >&2
	exit 1
}
[ "$(id -u)" -eq 0 ] || {
	echo "error: run as root (sudo scripts/build-in-container.sh); the build needs chroot and loop mounts" >&2
	exit 1
}

# Host networking: the default container network can fail to resolve DNS on
# hosts that use a local stub resolver, and the build needs the Debian mirrors.
podman run --rm --privileged --network host \
	--volume "$PWD:/work" --workdir /work \
	"$image" sh -euc '
		export DEBIAN_FRONTEND=noninteractive
		apt-get update
		apt-get install -y --no-install-recommends \
			live-build debootstrap squashfs-tools xorriso ca-certificates python3
		scripts/build.sh
	'

# Hand the artifacts back to the user who invoked sudo.
if [ -n "${SUDO_UID:-}" ]; then
	for artifact in ./*.iso build.log; do
		[ -e "$artifact" ] && chown "$SUDO_UID:${SUDO_GID:-$SUDO_UID}" "$artifact"
	done
fi
