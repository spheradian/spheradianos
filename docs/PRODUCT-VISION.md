# Spheradian: Product Vision

This document says what Spheradian and SpheradianOS are meant to feel like and who they serve. It is the reference that the ADRs implement. Decisions live in the ADRs linked below. This file collects them into one picture and changes only when the vision changes.

> Status: vision stated by the maintainer on 2026-11-23. Most of it is **not implemented yet**. Today the desktop is a prototype that shows demo windows (v0.0.1), and trust domains are **not** a security boundary until M5.

---

## 1. One sentence

**An operating system that feels like a game console, protects you like something between secureblue and Qubes OS, shows your work and its trust domains as a sphere you move through, and runs on anything from a current laptop to a Raspberry Pi.**

## 2. Four commitments

| Commitment | What it means | Where it is decided |
|---|---|---|
| **Console feel** | Boots straight into the interface; updates happen in the background and cannot break the system; suspend and resume are the normal way to stop; everything works with a game controller and a keyboard as well as a mouse; nothing to configure before you can use it | §3; ADR-002 (zero-prompt boot); ADR-013 (atomic updates, planned); ADR-016 (controller navigation in the first usable build) |
| **Security between secureblue and Qubes OS** | A hardened, immutable, signed base, as in secureblue. Applications isolated per trust domain, as in Qubes, but with kernel isolation (namespaces, seccomp, cgroups) instead of one virtual machine per domain. An optional lightweight VM only for the highest-risk domain, on hardware that can afford it | §4; ADR-008 (three pillars, reserved); M5 |
| **Innovation in both modes** | The spherical desktop is the main presentation. The 2D mode, **Planisphere**, is the same design projected flat, not a plain fallback. Someone on a Raspberry Pi 3 should still feel they are using something new | §5; ADR-015 |
| **Runs on modest and portable hardware** | `amd64` first. Then `arm64`, with Raspberry Pi 4 and 5 as reference boards. Measured budgets for RAM, disk, and frame time, enforced in CI | §6; ADR-014 |

## 3. Console feel

What "feels like a console" means in practice. These are the rules the UI and the system layer are checked against:

1. **No waiting on the system.** From power-on to an interactive frame without a prompt; the boot experience overlaps real work and never extends it (`BOOT-EXPERIENCE.md` §6.2).
2. **Nothing to break.** The base is an image. An update either applies whole or not at all, and the previous image is always one boot away (ADR-013).
3. **Suspend is the off switch.** Resume to the exact sphere, galaxy, and windows you left.
4. **One input is enough.** Every action is reachable with a game controller alone, with a keyboard alone, and with a mouse alone. Pointer gestures are shortcuts, never the only way.
5. **Fullscreen by default.** No window chrome to manage. Windows are places in the sphere (or regions of the Planisphere), not boxes to drag.
6. **Calm when idle.** No continuous redraw when nothing changes. This also matters for battery and for old hardware.

## 4. Security between secureblue and Qubes OS

| | secureblue | **Spheradian** | Qubes OS |
|---|---|---|---|
| Base system | Hardened, immutable Fedora Atomic image | Hardened, immutable Debian-based image (ADR-013) | Xen hypervisor with template VMs |
| Isolation unit | Application sandboxing (Flatpak, hardening) | **Trust domain**: a set of applications isolated by the kernel (namespaces, seccomp, cgroups v2), M5 | One virtual machine per domain |
| Highest-risk work | Same as other apps | Optional microVM (KVM) for `QUARANTINE`, on capable hardware only | Disposable VMs |
| Hardware needed | Modest | Modest, down to Raspberry Pi | IOMMU, a lot of RAM, x86 only |
| How isolation is shown | Not visible in the UI | **The sphere is organized by domain**; compositor-drawn borders that applications cannot fake | Colored window borders |

The microVM option is a proposal to evaluate in M5, not a decision. Until M5, no material may call trust domains a security boundary.

## 5. Two presentations, one design

| | Sphere | Planisphere (ADR-015) |
|---|---|---|
| Renderer | `wgpu` (Vulkan or GL/GLES 3.x) | Smithay's GLES 2 renderer, or the Pixman CPU renderer |
| Typical hardware | GPUs from about 2012 on; Raspberry Pi 4/5 | Anything with KMS: old laptops, Raspberry Pi 3, virtual machines without 3D |
| Same model | Windows at (θ, φ, r), galaxies, trust-domain regions, Mini-Globe | The **same** coordinates projected onto a plane, the way a planisphere projects the sky |
| Chosen by | Render levels `high` → `medium` → `low` (ADR-009) | Automatically below `low`, or by the user at any time |

## 6. Hardware targets

See ADR-014 for the measured budgets and the reference machines. In short:

- **`amd64`:** the first target. The sphere runs from about 2012-era integrated GPUs; anything older gets Planisphere.
- **`arm64`:** the second target, after the first usable build. Raspberry Pi 4 and 5 run the sphere (Mesa `v3d`/`v3dv`, Vulkan 1.3 and GLES 3.1). Raspberry Pi 3 runs Planisphere. Images are SD-card images, not ISOs.
- **RAM:** the minimum and the comfortable amount are set by measurement (ADR-014), not by guesses in this document.

## 7. Who it is for

- People on modest or older machines who still want a modern, safe system.
- People who want strong compartmentalization without Qubes' hardware requirements.
- Clients of Fabrintek who need machines that are hard to break and easy to support (ADR-011).
- People who want a desktop that is new to use, not only new to look at.

## 8. How we will know

The vision is proven only by use. ADR-016 puts a usable build in front of people first. Each commitment above has an observable test:

| Commitment | Test |
|---|---|
| Console feel | Task completion with a controller only; resume time; update applied while in use, then rolled back |
| Security | M5 isolation tests (escape attempts between domains); the compositor-drawn border cannot be spoofed |
| Innovation in both modes | Usability sessions in which the same tasks are run in Sphere, in Planisphere, and on a conventional flat desktop, and then compared |
| Modest hardware | Budgets in ADR-014 pass on the reference machines in CI |
