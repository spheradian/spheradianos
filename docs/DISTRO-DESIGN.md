# XSphereOS: Distribution Design

Status: **M0 complete** (2026-11-18). The minimal `trixie` `minbase` live ISO builds reproducibly via `live-build`, boots zero-prompt in QEMU (BIOS and UEFI) into an autologged-in shell with the `xsphere` Plymouth splash, and passes static and boot-splash contract tests. M1–M5 remain planned.

XSphereOS is the planned first (and initially only) target for XSphereDE: a small, easy-to-use Linux distribution built from a deliberately minimal Debian base, in the spirit of Kurumin Linux. It boots straight into the spherical desktop, works out of the box, and requires no configuration from a first-time user.

> Scope note: detailed threat models, hardening specifics, and audit findings are tracked in the private security repository, not here. This document only states design intent at a high level.

---

## 1. Goals

1. **It just works.** Boot the live image, land inside the sphere, with network, audio, and a browser available within seconds. No installer questions before the user can try it.
2. **Small and light.** Runs well on modest, older hardware. A minimal base, few resident services, and a low-power rendering mode.
3. **XSphereDE is the only shell.** No second desktop environment, no X11 session, no Xwayland.
4. **Debian as a parts bin, not a flavor.** Use Debian for its kernel, libc, drivers, firmware, and package archive. Everything user-facing is XSphereOS's own.
5. **Reproducible.** The image is built from a committed recipe, from a clean machine, with a documented procedure.

## 2. Non-goals (for now)

- Supporting other desktop environments or display servers.
- Supporting architectures other than `amd64` initially. *[ADR-014](adr/ADR-014-hardware-targets-and-budgets.md) proposes `arm64` (Raspberry Pi 4/5) as the second target after the first usable build.*
- Being a general-purpose server distribution.
- Claiming a security boundary before per-domain isolation is real. The trust-domain model remains unverified until clients are actually sandboxed.

## 3. Base system

### 3.1 Why Debian

- Broad hardware and firmware coverage, which matters for an "old machines" audience.
- `live-build` and `debootstrap` make image creation straightforward and scriptable.
- Stable release cadence and long security-update support for the parts we inherit.
- Familiar to the Kurumin lineage (Knoppix/Debian).

### 3.2 Minimal-first rule

The base is created with `debootstrap --variant=minbase` against Debian **stable**, and packages are added only when something requires them.

Rules:

- Do **not** start from a Debian desktop task or metapackage. No `task-*`, no `gnome-*`, no `kde-*`.
- `Recommends` are **not** installed by default (`APT::Install-Recommends "false"`). Needed recommended packages are named explicitly.
- Every package in the manifest has a one-line justification. A package without one is removed.
- A budget is tracked per release: installed package count and compressed ISO size.

### 3.3 Initial package manifest (sketch)

| Layer | Contents |
|---|---|
| Kernel and boot | `linux-image-amd64`, `systemd-boot` or `grub-efi`, `live-boot` |
| Init and system | `systemd` (kept, see 3.4), `dbus`, `udev` |
| Graphics | Mesa (Vulkan and GL drivers), `libdrm`, `libinput`, `libseat`/`seatd` |
| Network | `NetworkManager` (or `iwd` plus a small front end), `wpa_supplicant` |
| Audio and capture | `pipewire`, `wireplumber` |
| Firmware | `firmware-linux-free` plus selected non-free firmware where hardware demands |
| Apps (initial) | one browser, one terminal, one file manager, chosen for size and Wayland-native behavior |
| XSphereOS own | `xspherede` compositor, session files, first-boot helper, settings tool |

### 3.4 Init system

Keep `systemd` initially. Replacing it saves little and costs a great deal in compatibility; revisit only if boot time or footprint measurements justify it.

## 4. What XSphereOS owns

Debian supplies the substrate. XSphereOS progressively takes over these layers:

1. **The session.** A Wayland session (`xspherede.desktop`) launched directly by a minimal login path, with no heavyweight display manager.
2. **First-boot experience.** Network setup, language and keyboard, and an optional install prompt, all presented inside the sphere.
3. **Settings.** A small native tool for the handful of settings a user actually needs (display, network, audio, trust-domain defaults).
4. **Application launching.** A launcher and dock on the polar rings (see the roadmap), mapping applications to trust domains by default.
5. **Packaging and updates.** A custom APT repository and metapackage (`xsphereos-base`), so the system is defined by one package and upgrades are normal `apt` upgrades. *Under review: [ADR-011](adr/ADR-011-organization-and-product-structure.md) §6 moves the system layer to an immutable image with atomic updates, so packages feed image builds and installed systems receive whole images. ADR-013 will decide.*
6. **Branding and defaults.** Boot splash, wallpaper (the sphere itself), default configuration, and sane hardened defaults.

Over time, decisions move from "whatever Debian ships" to "what XSphereOS ships", with a documented list of deliberate divergences.

## 5. Desktop session architecture

```
firmware -> bootloader -> kernel -> systemd
                                      |
                              seatd / logind
                                      |
                       xspherede (Wayland compositor, Smithay + wgpu)
                          |                        |
                   Wayland clients          trusted shell UI
                 (per trust domain)        (Mini-Globe, docks, lockdown)
```

Dependencies on the XSphereDE roadmap (the distro cannot be useful until these land):

| Roadmap item | Why the distro needs it |
|---|---|
| Native Wayland compositor on Smithay | Without it there is no session and no real applications |
| Input routing through a trusted path | Required before running any real client |
| Live window capture / DMA-BUF textures | Real application windows on curved surfaces |
| Per-domain process isolation | Makes trust domains mean something |
| Polar docks and launchers | First-boot and daily-use usability |

A **fallback session** is mandatory: on hardware with no usable Vulkan or GL, or if the compositor fails to start, boot into a minimal flat Wayland session so the machine is never unusable. *[ADR-015](adr/ADR-015-planisphere-2d-presentation.md) proposes that this session be **Planisphere**, a full 2D presentation of the same desktop, not a minimal fallback.*

## 6. Performance mode for modest hardware

The default visual effects are GPU-heavy. XSphereOS ships a low-power profile, selected automatically or manually:

- Volumetric code rain off or reduced.
- Lower window mesh subdivision.
- Reduced frame rate cap and no continuous redraw when idle.
- Mini-Globe at reduced resolution.

The profile is chosen at first boot from a quick GPU capability probe and can be changed in settings.

## 7. Image build and release

- **Tooling:** `live-build` driven by a recipe in the repository; one command produces a hybrid ISO (UEFI first, BIOS optional).
- **Reproducibility:** pinned Debian snapshot date per release, pinned package versions for XSphereOS packages, committed lock data, deterministic timestamps.
- **Artifacts:** ISO, checksums, and a detached signature.
- **Channels:** `nightly` (developer-only), `testing`, `stable`.
- **CI:** build the image and boot-test it headlessly in QEMU, asserting that the session reaches a running compositor (or the fallback).

## 8. Repository and process layout

- `xspherede` (this repository): the compositor and desktop. Stays focused on the desktop.
- `xsphereos` (new, separate): the image recipe, package manifests, APT repository tooling, branding, first-boot helper, and release scripts.
- `xspherede-security` (private, existing): all security analysis, threat models, and hardening notes for both of the above.

Keeping the distro recipe separate prevents distribution concerns from leaking into the desktop codebase and lets the two have different visibility and release cadences.

## 9. Milestones

> [ADR-016](adr/ADR-016-first-usable-build-roadmap.md) proposes reordering M2–M5 around a first usable build and adding M6 (`arm64`).

| # | Milestone | Done when |
|---|---|---|
| M0 | Base image | `minbase` live ISO boots in QEMU to a shell; manifest and size budget recorded |
| M1 | Prototype session | The current XSphereDE prototype launches on that image as a windowed app under a stub compositor or kiosk session |
| M2 | Real compositor | Smithay session boots; one real client (terminal) renders on the sphere |
| M3 | Usable desktop | Browser, files, terminal, network, audio, launcher; low-power profile |
| M4 | Installable | Installer, signed APT repo, first-boot flow, update path |
| M5 | Isolation | Per-domain sandboxing makes trust domains enforceable |

M1 is the earliest point at which the distro is demonstrable, and it does not depend on the Wayland compositor work.

### 9.1 M0 Measured Baseline (2026-11-18)

| Metric | Measured value | Notes |
|---|---|---|
| Hybrid ISO size | 268 MiB (281,018,368 bytes) | `live-image-amd64.hybrid.iso` (`xz` squashfs) |
| SquashFS rootfs size | 196 MiB | `binary/live/filesystem.squashfs` |
| Installed package count | 190 packages | `live-image-amd64.packages` (`trixie`, `minbase`, no recommends) |
| Boot behavior | Zero-prompt (BIOS & UEFI) | `config/bootloaders/` (`ADR-002`); `scripts/boot-test.py` covers both, UEFI with `--uefi` (2026-11-21) |

UEFI notes (2026-11-21, QEMU with OVMF, KVM):

- From a disk, as a USB stick boots, the hidden GRUB menu reaches the autologged-in shell in about 6.5 s. From QEMU's emulated CD drive, OVMF reads so slowly that GRUB needs about 45 s to load the kernel and initramfs; the boot completes, but `--uefi` therefore attaches the ISO as a disk. A real optical drive has not been measured.
- Tapping `Esc` opens the hidden GRUB menu. Holding or tapping `Shift` does not: GRUB's `keystatus --shift` does not see it under OVMF. Whether `Shift` works on real UEFI firmware is untested (see ADR-002).
- Not yet covered: real hardware and Secure Boot.

## 10. Open questions

1. Browser choice under a size budget and a Wayland-native requirement.
2. Network stack: `NetworkManager` versus a lighter `iwd`-based option.
3. Installer: custom, or adapt an existing one (Calamares or the Debian installer).
4. Handling of non-free firmware in a default image.
5. Whether and when to replace any Debian-supplied component with an XSphereOS one, and how to track those divergences.
6. Name, branding, and licensing of the distribution as distinct from the desktop. *Names and structure proposed in [ADR-011](adr/ADR-011-organization-and-product-structure.md); licensing still open (ADR-011 §5.5).*
