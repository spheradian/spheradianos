#!/bin/sh
# Print the size budget numbers tracked per release (design doc 3.2).
set -eu
cd "$(dirname "$0")/.."
iso=""
for f in ./*.iso; do
	[ -e "$f" ] && {
		iso="$f"
		break
	}
done
[ -n "$iso" ] || { echo "no ISO found; build first" >&2; exit 1; }
echo "ISO:      $iso"
echo "ISO size: $(du -h "$iso" | cut -f1)"
if [ -f live-image-amd64.packages ]; then
	echo "Packages: $(grep -c . live-image-amd64.packages)"
fi
