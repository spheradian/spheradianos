# ADR-014: Hardware Targets, Reference Machines, and Resource Budgets (`amd64` First, `arm64` Raspberry Pi Second)

**Date:** 2026-11-23  
**Status:** Proposed  
**Author:** Senior Software Architect  
**Approver:** Fábio Mendes (`mendsec`)  
**Confidence:** Medium  
**Impact:** High  
**Reversibility:** Medium  

## 1. Executive Summary

"Runs on old computers" and "runs on a Raspberry Pi" are part of the product vision ([PRODUCT-VISION.md](../PRODUCT-VISION.md)). Today they are not backed by any defined floor or measured budget. The only enforced budget is the ISO size. We decide:

1. **Targets:** `amd64` is the first target. `arm64` is the second target, with Raspberry Pi 4 and 5 as reference boards. Work on `arm64` starts after the first usable build (ADR-016).
2. **Presentation by GPU capability:** the sphere needs what `wgpu` needs (Vulkan, or GL/GLES 3.x). Every machine below that line gets Planisphere (ADR-015). No supported machine ends at a bare terminal.
3. **Reference machines:** a small, fixed set of real machines on which budgets are measured for every release.
4. **Budgets:** session RAM, idle CPU, frame time, boot time, and image size. The starting values in §5.3 are **proposals**. Each one is frozen after its first measurement and can only be raised by an explicit change to this ADR.

## 2. Context and Problem

- **The architecture rule conflicts with the vision.** `DISTRO-DESIGN.md` §2 lists "architectures other than `amd64`" as a non-goal "initially". The three-pillar ADR (reserved as ADR-008, not yet committed) excludes non-`amd64` systems. The vision now includes Raspberry Pi.
- **There is no hardware floor.** The documents say "modest, older hardware" without numbers. ADR-009 defines render levels but no machines to calibrate them on.
- **The fallback is not a product.** Below the GPU line, the session falls back to a terminal (`foot` in `cage`, ADR-007).
- **Only disk size is measured.** M0 measured a 268 MiB ISO, a 196 MiB SquashFS, and 190 packages. ADR-007 projects 380–430 MiB once Mesa and LLVM are added. Nobody has measured RAM, idle CPU, or frame time.
- **Raspberry Pi facts (checked November 2026):**
  - The Pi 4 (V3D 4.2) and Pi 5 (V3D 7.1) are supported by Mesa `v3d`/`v3dv`, which exposes Vulkan 1.3. Debian trixie ships Mesa 25.0.
  - Pi 5 support was merged into Linux 6.8.
  - The Pi 3 (VC4) has only GLES 2.0, below what `wgpu` needs.
  - Pi boards boot through their own firmware (`config.txt`), not UEFI or BIOS.
  - It is not yet verified whether Debian's own kernel, as opposed to Raspberry Pi OS's kernel, supports every Pi 5 peripheral.

## 3. Scope

- **In scope:** supported architectures, GPU capability lines, reference machines, budget definitions and starting values, how budgets are measured and enforced.
- **Out of scope:** how the `arm64` image is built and booted (decided with ADR-013, since the image builder changes anyway); the content of render levels (ADR-009); Planisphere's design (ADR-015).

## 4. Options Considered

- **Option A: Stay `amd64`-only, keep the terminal fallback.** Cheapest. Contradicts the vision on two points: Raspberry Pi support, and innovation on modest hardware.
- **Option B: Add `arm64` now, in parallel with the compositor.** Doubles the boot-chain and CI work before there is anything usable to put on a Pi. The rest of the boot experience is tuned for UEFI and BIOS, and would have to be redone for the Pi firmware too early.
- **Option C (Chosen): `amd64` first, `arm64` after the first usable build. Planisphere replaces the terminal fallback. Measured budgets on fixed reference machines.** The compositor is written in portable Rust from the start, so `arm64` costs little in the application code. The cost is in the boot chain and the image, and it is paid once there is something worth running.

## 5. Decision

### 5.1 Architectures

| Architecture | Status | Image format | Notes |
|---|---|---|---|
| `amd64` (x86-64 baseline as in Debian) | **First target** | Hybrid ISO (live), installer and atomic image (M4) | UEFI and BIOS, as today |
| `arm64` | **Second target**, after ADR-016's first usable build | SD-card or USB disk image | Raspberry Pi 4 and 5 are the reference boards. Other boards with mainline kernel and Mesa support are welcome, but not tested until a maintainer owns one |
| 32-bit (`i386`, `armhf`) | **Not supported** | — | Unchanged from the three-pillar ADR: keeps 64-bit mitigations and current security support |

The code must stay portable from now on: no `amd64`-only assumptions in the compositor or session (for example, no hard-coded `x86_64` paths or CPU features). This repository already cross-checks BSD builds in the desktop's CI. An `aarch64` build check is added there now, before any image work.

### 5.2 Presentation by GPU capability

| GPU capability (what the driver exposes) | Presentation | Examples (approximate, to be confirmed on reference machines) |
|---|---|---|
| Vulkan, or GL 3.3 / GLES 3.0 and newer | **Sphere**, at the render level ADR-009 selects (`high`, `medium`, `low`) | Intel HD 2000/3000 (2011) and newer; AMD Radeon HD 5000 and newer; Raspberry Pi 4 and 5 |
| GLES 2.0 only | **Planisphere**, on Smithay's GLES 2 renderer | Intel GMA X4500-class; Raspberry Pi 3 |
| No usable GPU acceleration (KMS only, or a virtual GPU without 3D) | **Planisphere**, on Smithay's Pixman CPU renderer | Very old graphics; VMs without 3D |
| No KMS | Text console (tier 0), as today | Should not happen on supported hardware |

Software 3D (Mesa `llvmpipe`/`lavapipe`) is **never** used to run the sphere for a user. It is too slow on the CPUs that would need it. It is used only for CI tests.

### 5.3 Budgets (starting proposals)

| Budget | Measured how | Starting proposal | Today |
|---|---|---|---|
| Live ISO size (`amd64`) | File size | ≤ 450 MiB | 268 MiB (M0, no Mesa) |
| Session RAM, Planisphere, no apps open | PSS of the compositor and session services, 60 s after the first frame | ≤ 150 MiB | Not measured |
| Session RAM, Sphere, no apps open | Same | ≤ 300 MiB | Not measured |
| Total RAM in use after boot, live, Planisphere | `MemTotal − MemAvailable` | ≤ 450 MiB | Not measured |
| Idle CPU, no input, no animation | Compositor CPU time over 60 s | < 1% of one core; zero frames presented | Not measured |
| Frame time at the selected level | p95 over the standard scene (ADR-009 warm-up scene) on each reference machine | ≤ 16.7 ms | Not measured |
| Boot to first interactive frame | Firmware hand-off to first input-ready frame | Set at first measurement | ~6.5–7 s to a console in QEMU with KVM |
| Minimum RAM to run the default apps (terminal, file manager, one browser tab) | Usability run on the reference machines | 2 GiB minimum, 4 GiB comfortable; Raspberry Pi 3 (1 GiB) supported without the browser | Not measured |

The browser, not the desktop, sets the real RAM floor. The budgets above keep the desktop's own share small enough that the browser fits.

### 5.4 Reference machines

| ID | Machine class | Why | Presentation expected |
|---|---|---|---|
| R1 | `amd64` laptop, about 2011–2013, Intel HD 3000/4000, 4 GiB RAM, SATA disk | The typical "old computer" the vision targets | Sphere `low` |
| R2 | `amd64` desktop or laptop, about 2008–2010, GLES 2-only graphics, 2 GiB RAM | The bottom of `amd64` support | Planisphere (GLES 2) |
| R3 | Raspberry Pi 4, 2–4 GiB | Portable `arm64` reference | Sphere `low` / `medium` |
| R4 | Raspberry Pi 5 | Current `arm64` reference | Sphere `medium` |
| R5 | Raspberry Pi 3 | Bottom of `arm64` support | Planisphere |
| CI | QEMU with KVM (`amd64`) and QEMU `virt` (`arm64`), software GPU | Every change | Planisphere (Pixman) and Sphere on `lavapipe` for functional tests only |

The maintainer does not have to own every machine on day one. R1 and R2 are needed for the first usable build. R3 through R5 are needed when `arm64` work starts.

### 5.5 Enforcement

- **In CI, on every image change:** ISO size; RAM figures and idle CPU measured over the serial console in `scripts/boot-test.py`; zero frames presented at idle.
- **Per release, on the reference machines:** frame time, boot time, and the usability run. The results are recorded in `DISTRO-DESIGN.md` §9, as the M0 baseline is today.
- A budget that fails blocks the release unless this ADR is changed in the same pull request with a stated reason.

## 6. Consequences and Trade-offs

- **Pros:**
  - "Old computers" and "Raspberry Pi" become checkable claims.
  - No supported machine is left with a bare terminal.
  - Planisphere also covers virtual machines without 3D, so CI exercises the real fallback path.
  - Portable code from the start keeps the cost of `arm64` low.
- **Cons:**
  - Two renderer paths to maintain (shared core, ADR-015).
  - Reference hardware has to be bought and kept working.
  - `arm64` brings a second boot chain (Pi firmware) and a second image format.
  - The Raspberry Pi 3 is supported only in a limited way (no browser in the default set).

## 7. Security and Compliance

- `arm64` images must meet the same rules as `amd64` images: signed, reproducible, the same package justification rule, no 32-bit userland.
- Pi firmware blobs are non-free. Each one is listed and justified in the package lists, like `amd64` firmware (three-pillar ADR, invariant 1).
- Secure Boot on `amd64` and verified boot on `arm64` remain open. They belong with the atomic image design (ADR-013).

## 8. Related

- [PRODUCT-VISION.md](../PRODUCT-VISION.md)
- [ADR-007](ADR-007-m1-kiosk-prototype-session.md): terminal fallback, replaced by Planisphere when ADR-015 lands
- [ADR-009](ADR-009-gpu-render-levels-and-warmup.md): render levels, now ending in Planisphere
- ADR-013 (planned): atomic system layer and image builder, including the `arm64` image
- [ADR-015](ADR-015-planisphere-2d-presentation.md): Planisphere
- [ADR-016](ADR-016-first-usable-build-roadmap.md): roadmap
- [DISTRO-DESIGN.md](../DISTRO-DESIGN.md) §2 (non-goals), §6 (performance mode), §9.1 (baseline)
- Sources: Phoronix, "Raspberry Pi Driver Updated With Vulkan 1.3 Support"; FOSDEM 2024, "Graphics stack updates for Raspberry Pi devices"; FOSDEM, "From Bookworm to Trixie: upgrading the Raspberry Pi graphics stack"
