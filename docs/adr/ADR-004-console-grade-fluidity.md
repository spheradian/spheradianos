# ADR-004: Console-Grade Fluidity Discipline (`zstd` Boot Compression, `cgroups v2` QoS, `zram`, and Zero-Copy `DMA-BUF`)

**Date:** 2026-11-18  
**Status:** Accepted  
**Author:** Senior Software Architect  
**Approver:** Fábio Mendes (`mendsec`)  
**Confidence:** High  
**Impact:** High  
**Reversibility:** Easy  

## 1. Executive Summary

To deliver console-like responsiveness without rewriting kernel subsystems, XSphereOS must eliminate two latency bottlenecks: CPU-bound `xz` squashfs decompression during live boot/app launch and CPU/memory contention between heavy clients and the `xspherede` compositor. We decided to adopt `zstd` squashfs compression, `systemd` `cgroups v2` QoS + `zram` protection for `xspherede`, and enforce zero-copy `DMA-BUF` window capture.

## 2. Context and Problem

- `auto/config` currently sets `--chroot-squashfs-compression-type xz`, optimizing for minimum ISO size (268 MiB in M0) at the expense of slow CPU decompression on modest hardware.
- Standard desktop scheduling lets background workloads (e.g., browser tabs, I/O spikes) cause compositor micro-stutter.
- Copying 1080p@60fps window buffers via CPU (`wl_shm`) consumes ~498 MB/s of memory bandwidth per window.

## 3. Scope

- **In scope:** `auto/config` compression setting, `systemd` slice / `zram` configuration in `config/includes.chroot/`, and `DMA-BUF` zero-copy acceptance gate in M2.
- **Out of scope:** Custom Linux kernel, custom scheduler, or custom GPU drivers.

## 4. Options Considered

- **Option A:** Keep `xz` and default `systemd` scheduling without QoS.
- **Option B (Chosen):** `zstd` squashfs + `cgroups v2` QoS for `xspherede` + `zram` + mandatory `DMA-BUF` zero-copy.
- **Option C:** Build custom OS/kernel subsystems from scratch (excessive complexity and maintenance cost).

## 5. Decision

Adopt **Option B**:
1. Evaluate and switch `--chroot-squashfs-compression-type` from `xz` to `zstd`, recording boot-time and ISO-size deltas in `docs/DISTRO-DESIGN.md` (Issue `#1`).
2. Configure a dedicated `systemd` `cgroups v2` slice (`CPUWeight`, `IOWeight`, `MemoryLow`) for `xspherede` and enable `zram` to avoid swap thrashing on modest hardware.
3. Enforce zero-copy `DMA-BUF` window capture as a mandatory M2 acceptance criterion for normal GPU profiles.

## 6. Consequences and Trade-offs

- **Pros:** ~5x–8x faster squashfs decompression, snappier live boot and app launches, and stutter-free compositor frame pacing.
- **Cons:** Estimated ~10–15% ISO size increase compared to `xz` (acceptable on USB/QEMU targets; reversible if strict media limits arise).

## 7. Security and Compliance

`cgroups v2` resource isolation mitigates local DoS against the compositor and establishes the resource-control foundation for M5 per-domain sandboxing (Issue `#13`). Elevated compositor priority must not grant unnecessary root privileges (`RTKit` or scoped `CAP_SYS_NICE` only).

## 8. Related

- GitHub Issue `#15`: `[M1][Perf] Implement console-grade fluidity (zstd squashfs, cgroups v2 QoS, zram, DMA-BUF gate)`
- `docs/REFERENCES.md`
- `auto/config`
