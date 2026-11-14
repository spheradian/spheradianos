#!/bin/sh
# Print the size budget numbers tracked per release (design doc 3.2).
set -eu
cd "$(dirname "$0")/.."
iso=$(ls -1 ./*.iso 2>/dev/null | head -n1 || true)
[ -n "$iso" ] || { echo "no ISO found; build first" >&2; exit 1; }
echo "ISO:      $iso"
echo "ISO size: $(du -h "$iso" | cut -f1)"
if [ -f live-image-amd64.packages ]; then
	echo "Packages: $(grep -c . live-image-amd64.packages)"
fi
