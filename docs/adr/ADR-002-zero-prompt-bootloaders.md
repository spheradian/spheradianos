# ADR-002: Zero-Prompt Direct Boot via `live-build` Bootloader Templates

**Date:** 2026-11-18  
**Status:** Accepted  
**Author:** Senior Software Architect  
**Approver:** Fábio Mendes (`mendsec`)  
**Confidence:** High  
**Impact:** Medium  
**Reversibility:** Easy  

## 1. Executive Summary

The default `live-build` bootloader templates (`grub-efi` and `syslinux/isolinux`) pause indefinitely at interactive boot menus, contradicting the XSphereOS goal of booting straight into the desktop (`docs/BOOT-EXPERIENCE.md` §2). Rather than building a custom bootloader, we will override the `live-build` templates under `config/bootloaders/` to boot immediately with hidden/zero-timeout defaults while preserving key-triggered recovery access.

## 2. Context and Problem

Observed in the generated M0 `binary/` output:
- `binary/boot/grub/config.cfg` sets `set default=0` without `set timeout` and emits an audio beep (`play 960 440 1 0 4 440 1`).
- `binary/isolinux/isolinux.cfg` sets `default vesamenu.c32`, `prompt 0`, and `timeout 0` (which in Syslinux disables the timeout and waits forever).

## 3. Scope

- **In scope:** Custom templates in `config/bootloaders/` (GRUB and ISOLINUX), static configuration assertions in `tests/`, and unattended QEMU boot verification (`scripts/boot-test.py`).
- **Out of scope:** Custom UEFI/BIOS bootloader development or migrating away from `live-build`.

## 4. Options Considered

- **Option A (Chosen):** Override `live-build` templates in `config/bootloaders/`.
- **Option B:** Migrate UEFI to `systemd-boot` / UKI (does not cover legacy BIOS or `live-build` hybrid ISO out-of-the-box).
- **Option C:** Build a custom bootloader (excessive complexity, hardware compatibility, and Secure Boot maintenance risk).

## 5. Decision

Adopt **Option A**:
- **GRUB:** Set `set default=0`, `set timeout_style=hidden`, `set timeout=0` (with modifier-key check to reveal the menu on demand), remove `play` beep and Debian splash, keep a dark background and `gfxpayload=keep`.
- **ISOLINUX:** Boot `live-amd64` directly (`prompt 0`, no blocking `vesamenu.c32`, or `timeout 1` for key-override).

## 6. Consequences and Trade-offs

- **Pros:** Resolves both UEFI and BIOS unattended boot with zero custom bootloader code; preserves Debian-signed `grub-efi` compatibility for future Secure Boot support.
- **Cons:** Short key-press window for fail-safe menu on fast hardware (mitigated by holding `Shift`/`Esc` during firmware POST).

## 7. Security and Compliance

No new attack surface. Preserves `Verify integrity of the boot medium` and fail-safe boot entries inside the hidden menu.

## 8. Related

- Note (2026-11-21): under UEFI in QEMU (OVMF), `Shift` does not reveal the GRUB menu, because `keystatus --shift` does not see it; tapping `Esc` does, and `scripts/boot-test.py --uefi` relies on it. Real UEFI firmware is untested; until it is, document `Esc` as the key to press.
- GitHub Issue `#14`: `[M0][Boot] Configure zero-prompt direct boot in config/bootloaders/ (GRUB & ISOLINUX)`
- `docs/BOOT-EXPERIENCE.md` §2
