# ADR-006: Installed System Performance (`host-only` `initramfs`, Binary Tiers) and Console-Style Recovery Fallback

**Date:** 2026-11-19  
**Status:** Accepted  
**Author:** Senior Software Architect  
**Approver:** Fábio Mendes (`mendsec`)  
**Confidence:** High  
**Impact:** Alto  
**Reversibility:** Medium  

## 1. Executive Summary

The Live ISO (`M0–M3`) carries `live-boot`, `squashfs`, and a generic `initrd` (~46 MiB) for universal hardware compatibility, penalizing boot time relative to a console. We decided that the **installed system (`M4`)** will strip `live-boot`/`squashfs`, generate a `host-only` `initramfs` (`MODULES=dep`, `COMPRESS=zstd`, ~8–12 MiB) at install time, remain 100% binary-distributed (with optional CI-built CPU tier packages, never compiling on the user's machine), and ship a **console-style Recovery Mode** backed by a generic fallback `initrd` if hardware changes.

## 2. Context and Problem

- Evaluating console-grade boot solely on the Live ISO hides the performance achievable on an installed NVMe/SSD target.
- Compiling the OS on the user's machine during installation (source-based Gentoo style) is slow and fragile on modest hardware and breaks signed binary `apt` updates (`M4`).
- Using a `host-only` `initramfs` introduces the risk of failing to boot if the user moves the disk to different hardware (e.g., a new storage controller).

## 3. Scope

- **In scope:** Installed-system architecture in `M4` (Issue `#11`), post-install `initramfs` generation, console-style Recovery Mode fallback, and installed-disk KVM benchmarks (`M4`).
- **Out of scope:** On-device source compilation during installation.

## 4. Options Considered

- **Option A:** Source-based compilation on the target machine during installation.
- **Option B (Chosen):** Signed binary distribution + post-install `host-only` `initramfs` (`MODULES=dep`, `zstd`) + generic fallback `initrd` leading to a modern **Console-Style Recovery Mode**.
- **Option C:** Keep the generic Live `initrd` layout on installed disks.

## 5. Decision

Adopt **Option B**:
1. Separate performance targets: **Live ISO** (universal try-out) vs **Installed System (`M4`)** (primary console-grade boot target).
2. At install time (`M4`), remove `live-boot`/`live-config`/`squashfs` and generate a `host-only` `initramfs` (`MODULES=dep` + `COMPRESS=zstd`).
3. Keep all OS updates 100% binary and signed via APT (`spheradianos-base`); any future CPU microarchitecture optimization (e.g., `x86-64-v3`) is built in CI, never on the user's device.
4. Maintain a **generic fallback `initrd` + Console-Style Recovery Mode** (clean minimal Wayland recovery UI, analogous to PlayStation Safe Mode) to re-detect hardware, rebuild `host-only` `initramfs`, verify integrity, or repair boot if the disk is moved to different hardware.

## 6. Consequences and Trade-offs

- **Pros:** Shrinks installed `initrd` from ~46 MiB to ~8–12 MiB without local compilation; preserves signed binary updates and modest-hardware support; handles hardware swaps gracefully with a modern recovery UI.
- **Cons:** Requires maintaining two test targets in KVM from `M4` onward (Live ISO and installed disk image) plus the fallback recovery boot entry.

## 7. Security and Compliance

Binary-only CI-built packages preserve SBOM provenance and signatures (Issue `#12`) without shipping compilers (`gcc`/`rustc`) on end-user machines. Recovery mode actions that modify system configuration require explicit user confirmation.

## 8. Related

- [ADR-004](ADR-004-console-grade-fluidity.md) (`zstd`, `cgroups v2`, `zram`, `DMA-BUF`)
- GitHub Issue `#11`: `[M4][ADR] Decide installer strategy and non-free firmware policy`
- GitHub Issue `#12`: `[M4][DevSecOps] Set up signed APT repository, SBOM, artifact signing, and reproducible-build check`
