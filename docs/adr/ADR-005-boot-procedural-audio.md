# ADR-005: Boot Procedural Audio (B5) Integration and KVM Boot-Time Measurement

**Date:** 2026-11-18  
**Status:** Accepted  
**Author:** Senior Software Architect  
**Approver:** Fábio Mendes (`mendsec`)  
**Confidence:** High  
**Impact:** Medium  
**Reversibility:** Easy  

## 1. Executive Summary

Current boot-time measurements (7.03 s KVM median in B2) exclude audio server startup and the procedural `audio-synth` (Milestone B5). We decided to track and implement `audio-synth` as a non-blocking, critical-path-isolated module, start `PipeWire`/`WirePlumber` in parallel before the B4 hand-off, and measure end-to-end boot time (including `audio-ready` timestamp) under **QEMU + KVM** with a virtual audio device.

## 2. Context and Problem

- `docs/BOOT-EXPERIENCE.md` (§6.4, §12 B5) specifies strict console-ROM budgets (≤ 64 KiB binary, ≤ 4 KiB score, ≤ 256 KiB RAM, ≤ 1% CPU, -12 dBFS peak cap, zero binary audio files), currently unbuilt.
- Measuring boot time without `PipeWire` and `audio-synth` hides audio initialization overhead and risks missing the arrival sound window at compositor Unfold (B4).

## 3. Scope

- **In scope:** `audio-synth` module, non-blocking `systemd`/`PipeWire` integration, and QEMU + KVM boot-time + `audio-ready` measurement in `scripts/boot-test.py`.
- **Out of scope:** Audio playback inside `initramfs` (Plymouth remains silent before root switch).

## 4. Options Considered

- **Option A:** Defer boot audio entirely to late M3 without including it in boot-time benchmarks.
- **Option B (Chosen):** Implement B5 (`audio-synth`), launch `PipeWire` in parallel before B4, and benchmark complete boot (including audio) using **QEMU + KVM** with virtual audio hardware (`intel-hda`), while keeping a zero-delay exit-0 skip when no audio device exists.

## 5. Decision

Adopt **Option B**:
1. Track B5 (`audio-synth`) in GitHub Issue `#16` under `M3: Usable Desktop` (with early integration testing alongside B4).
2. Run `audio-synth` as an isolated, unprivileged session unit with zero blocking on device negotiation (exits `0` immediately if no audio output is ready).
3. Use **QEMU + KVM** with a virtual audio device (`intel-hda` / `hda-duplex`) for full boot-time, CPU/RAM, and `audio-ready` measurements close to real hardware.

## 6. Consequences and Trade-offs

- **Pros:** Honest end-to-end console boot measurements; synchronized light-and-sound timeline on Unfold.
- **Cons:** Requires KVM-capable runner/host for full audio + GPU boot benchmarks (software-emulated headless runs still pass via graceful exit-0 skip).

## 7. Security and Compliance

`audio-synth` runs with unprivileged session permissions, isolated from the compositor critical path so an audio fault cannot crash the graphical session, and uses zero external binary audio blobs.

## 8. Related

- GitHub Issue `#16`: `[M3][Boot/Audio] Implement procedural boot audio synth (B5) and KVM audio-ready benchmark`
- `docs/BOOT-EXPERIENCE.md` (§6.4, §12 B5)
- `scripts/render-boot-preview.py`
