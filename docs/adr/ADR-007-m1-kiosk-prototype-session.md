# ADR-007: M1 Prototype Session via Wayland Kiosk (`cage` + `seatd`), Fallback Session, and Pinned `spheradian` Build

**Date:** 2026-11-20  
**Status:** Accepted  
**Author:** Senior Software Architect  
**Approver:** Fábio Mendes (`mendsec`)  
**Confidence:** High  
**Impact:** High  
**Reversibility:** Easy  

## 1. Executive Summary

`spheradian/spheradian` is currently a `winit` + `wgpu` application (the native Smithay compositor lands in M2) with no published `.deb` packages or GitHub releases. We decided to launch it in M1 inside `cage` (a minimal Wayland-only kiosk compositor) on top of `seatd` and `mesa-vulkan-drivers` within `spheradian-session.slice` (`ADR-004`), with an automatic fallback to a flat Wayland terminal (`foot`) if Vulkan/GL or `spheradian` fails, while building `spheradian` from a pinned commit SHA during image CI.

## 2. Context and Problem

- The M0 image only boots to a `tty1` console with no Wayland stack.
- `spheradian` needs a Wayland host compositor in M1 (no X11/Xwayland).
- Compiled binaries must not be committed to the `spheradianos` Git repository.
- Existing `boot-test.py` console assertions (`B1–B3`) expect a `tty1` shell unless an explicit console mode switch is preserved.

## 3. Scope

- **In scope:** Manifest additions (`seatd`, `cage`, `mesa-vulkan-drivers`, `libegl-mesa0`, `foot`), `spheradian-session.service` in `spheradian-session.slice`, `scripts/build-spheradian.sh`, and `spheradian.session=console` / `spheradian.fallback=1` kernel switches.
- **Out of scope:** Native Smithay compositor (`M2`, Issue `#9`) and flicker-free Plymouth hand-off (`M2`, Issue `#7`).

## 4. Options Considered

- **Option A (Chosen):** `cage` + `seatd` + `mesa-vulkan-drivers` + `foot` fallback, building `spheradian` from a pinned commit SHA.
- **Option B:** Full `weston` or `sway` environment (unnecessary footprint and complexity for a single kiosk app).
- **Option C:** Skip M1 and wait for native Smithay compositor in M2 (delays real-image graphics validation).

## 5. Decision

Adopt **Option A**:
1. Add `seatd`, `cage`, `mesa-vulkan-drivers`, `libegl-mesa0`, and `foot` to `config/package-lists/spheradianos-base.list.chroot` with one-line justifications.
2. Run `spheradian-session.service` inside `spheradian-session.slice` (`ADR-004`) as unprivileged user `spheradian`, launching `cage -s -- /usr/bin/spheradian` and falling back automatically to `cage -s -- /usr/bin/foot` if `spheradian` fails or `spheradian.fallback=1` is set.
3. Preserve `spheradian.session=console` via `ConditionKernelCommandLine=!spheradian.session=console` so `boot-test.py` console tests remain deterministic.
4. Build `spheradian/spheradian` from a pinned commit SHA (`scripts/build-spheradian.sh`) and keep the binary gitignored, inside a digest-pinned Debian trixie Rust container so it links against the image's glibc. A host build on the CI runner required `GLIBC_2.43` symbols that trixie (2.41) lacks, so `spheradian` exited at once and the kiosk always showed `foot`.

## 6. Consequences and Trade-offs

- **Pros:** First demonstrable graphical SpheradianOS image; exercises `spheradian-session.slice` and Mesa/Wayland early; easy to swap `cage` for native `spheradian` in M2.
- **Cons:** Adds Mesa/LLVM dependencies to the image (~380–430 MiB projected) and requires a Rust toolchain in CI until M4 APT packaging lands.

## 7. Security and Compliance

`spheradian-session.service` runs as unprivileged user `spheradian` via `seatd` (never `root`). `spheradian` is built from an immutable commit SHA with `--locked`, and zero X11/Xwayland packages are installed.

## 8. Related

- GitHub Issue `#5`: `[M1] Launch Spheradian prototype in live image under minimal Wayland kiosk session`
- [ADR-004](ADR-004-console-grade-fluidity.md) (`spheradian-session.slice`)
