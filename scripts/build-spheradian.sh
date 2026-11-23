#!/bin/sh
# Build mendsec/spheradian from a pinned commit SHA and stage it into the chroot
# overlay at config/includes.chroot/usr/bin/spheradian (M1, ADR-007).
set -eu
cd "$(dirname "$0")/.."

SPHERADIAN_REPO="${SPHERADIAN_REPO:-https://github.com/mendsec/spheradian.git}"
SPHERADIAN_SHA="${SPHERADIAN_SHA:-3214ba4737aafb554f9502aeeb9718cdba258d3d}"
OUT="config/includes.chroot/usr/bin/spheradian"

for tool in git cargo; do
	command -v "$tool" >/dev/null 2>&1 || {
		echo "error: '$tool' not found" >&2
		exit 1
	}
done

tmp_dir=$(mktemp -d)
trap 'rm -rf "$tmp_dir"' EXIT INT TERM

git clone --no-checkout "$SPHERADIAN_REPO" "$tmp_dir/src"
git -C "$tmp_dir/src" checkout --detach "$SPHERADIAN_SHA"
cargo build --manifest-path "$tmp_dir/src/Cargo.toml" --release --locked

mkdir -p "$(dirname "$OUT")"
install -m 0755 "$tmp_dir/src/target/release/spheradian" "$OUT"
echo "staged $OUT from $SPHERADIAN_SHA"
