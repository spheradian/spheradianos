#!/bin/sh
# Boot the built ISO in QEMU. Usage: scripts/run-qemu.sh [--uefi]
# UEFI needs OVMF (package 'ovmf'); default is BIOS boot.
set -eu
cd "$(dirname "$0")/.."
iso=""
for f in ./*.iso; do
	[ -e "$f" ] && {
		iso="$f"
		break
	}
done
[ -n "$iso" ] || {
	echo "no ISO found; build first" >&2
	exit 1
}

fw=""
if [ "${1:-}" = "--uefi" ]; then
	code=/usr/share/OVMF/OVMF_CODE_4M.fd
	[ -f "$code" ] || {
		echo "OVMF not found at $code" >&2
		exit 1
	}
	fw="-drive if=pflash,format=raw,readonly=on,file=$code"
fi

# shellcheck disable=SC2086
exec qemu-system-x86_64 -m 1024 -smp 2 -enable-kvm -cpu host \
	-device virtio-vga -nic user,model=virtio-net-pci \
	$fw -cdrom "$iso" -boot d
