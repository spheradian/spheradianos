#!/bin/sh
# Build mendsec/xspherede from a pinned commit SHA and stage it into the chroot
# overlay at config/includes.chroot/usr/bin/xspherede (M1, ADR-007).
#
# The build runs in a Debian trixie Rust container, so the binary links against
# the same glibc as the image. Built on the CI host instead, it required
# GLIBC_2.43 symbols that trixie (2.41) lacks, could not start, and the kiosk
# always fell back to foot.
set -eu
cd "$(dirname "$0")/.."

XSPHEREDE_REPO="${XSPHEREDE_REPO:-https://github.com/mendsec/xspherede.git}"
XSPHEREDE_SHA="${XSPHEREDE_SHA:-3214ba4737aafb554f9502aeeb9718cdba258d3d}"
# Rust toolchain on the image's Debian release, pinned by digest.
BUILD_IMAGE="${XSPHEREDE_BUILD_IMAGE:-docker.io/library/rust:1.100.0-trixie@sha256:ebc54bef33ec8f9a5cd05799366010f35efbb73b354fb4f2cb086ec6b9460ef5}"
OUT="config/includes.chroot/usr/bin/xspherede"

for tool in git podman; do
	command -v "$tool" >/dev/null 2>&1 || {
		echo "error: '$tool' not found" >&2
		exit 1
	}
done

tmp_dir=$(mktemp -d)
trap 'rm -rf "$tmp_dir"' EXIT INT TERM

git clone --no-checkout "$XSPHEREDE_REPO" "$tmp_dir/src"
git -C "$tmp_dir/src" checkout --detach "$XSPHEREDE_SHA"
podman run --rm -v "$tmp_dir/src:/src:Z" -w /src "$BUILD_IMAGE" \
	cargo build --release --locked

mkdir -p "$(dirname "$OUT")"
install -m 0755 "$tmp_dir/src/target/release/xspherede" "$OUT"
echo "staged $OUT from $XSPHEREDE_SHA (built in $BUILD_IMAGE)"
