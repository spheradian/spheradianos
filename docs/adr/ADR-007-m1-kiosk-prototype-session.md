# ADR-007: M1 Prototype Session via Wayland Kiosk (`cage` + `seatd`), Fallback Session, and Pinned `xspherede` Build

**Date:** 2026-11-20  
**Status:** Accepted  
**Author:** Senior Software Architect  
**Approver:** Fábio Mendes (`mendsec`)  
**Confidence:** High  
**Impact:** High  
**Reversibility:** Easy  

## 1. Executive Summary

`spheradian/spheradian` is currently a `winit` + `wgpu` application (the native Smithay compositor lands in M2) with no published `.deb` packages or GitHub releases. We decided to launch it in M1 inside `cage` (a minimal Wayland-only kiosk compositor) on top of `seatd` and `mesa-vulkan-drivers` within `xsphere-session.slice` (`ADR-004`), with an automatic fallback to a flat Wayland terminal (`foot`) if Vulkan/GL or `xspherede` fails, while building `xspherede` from a pinned commit SHA during image CI.

## 2. Context and Problem

- The M0 image only boots to a `tty1` console with no Wayland stack.
- `xspherede` needs a Wayland host compositor in M1 (no X11/Xwayland).
- Compiled binaries must not be committed to the `xsphereos` Git repository.
- Existing `boot-test.py` console assertions (`B1–B3`) expect a `tty1` shell unless an explicit console mode switch is preserved.

## 3. Scope

- **In scope:** Manifest additions (`seatd`, `cage`, `mesa-vulkan-drivers`, `libegl-mesa0`, `foot`), `xsphere-session.service` in `xsphere-session.slice`, `scripts/build-xspherede.sh`, and `xsphere.session=console` / `xsphere.fallback=1` kernel switches.
- **Out of scope:** Native Smithay compositor (`M2`, Issue `#9`) and flicker-free Plymouth hand-off (`M2`, Issue `#7`).

## 4. Options Considered

- **Option A (Chosen):** `cage` + `seatd` + `mesa-vulkan-drivers` + `foot` fallback, building `xspherede` from a pinned commit SHA.
- **Option B:** Full `weston` or `sway` environment (unnecessary footprint and complexity for a single kiosk app).
- **Option C:** Skip M1 and wait for native Smithay compositor in M2 (delays real-image graphics validation).

## 5. Decision

Adopt **Option A**:
1. Add `seatd`, `cage`, `mesa-vulkan-drivers`, `libegl-mesa0`, and `foot` to `config/package-lists/xsphereos-base.list.chroot` with one-line justifications.
2. Run `xsphere-session.service` inside `xsphere-session.slice` (`ADR-004`) as unprivileged user `xsphere`, launching `cage -s -- /usr/bin/xspherede` and falling back automatically to `cage -s -- /usr/bin/foot` if `xspherede` fails or `xsphere.fallback=1` is set.
3. Preserve `xsphere.session=console` via `ConditionKernelCommandLine=!xsphere.session=console` so `boot-test.py` console tests remain deterministic.
4. Build `spheradian/spheradian` from a pinned commit SHA (`scripts/build-xspherede.sh`) and keep the binary gitignored.

## 6. Consequences and Trade-offs

- **Pros:** First demonstrable graphical XSphereOS image; exercises `xsphere-session.slice` and Mesa/Wayland early; easy to swap `cage` for native `xspherede` in M2.
- **Cons:** Adds Mesa/LLVM dependencies to the image (~380–430 MiB projected) and requires a Rust toolchain in CI until M4 APT packaging lands.

## 7. Security and Compliance

`xsphere-session.service` runs as unprivileged user `xsphere` via `seatd` (never `root`). `xspherede` is built from an immutable commit SHA with `--locked`, and zero X11/Xwayland packages are installed.

## 8. Related

- GitHub Issue `#5`: `[M1] Launch XSphereDE prototype in live image under minimal Wayland kiosk session`
- [ADR-004](ADR-004-console-grade-fluidity.md) (`xsphere-session.slice`)
