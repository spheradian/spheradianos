# XSphereOS

Private repository for **XSphereOS** (`mendsec/xsphereos`): a minimal, Debian-based (`trixie`, `minbase`, `amd64`) live and installable Linux distribution built to boot straight into the **XSphereDE** spherical Wayland desktop, in the spirit of Kurumin Linux.

> **Security scope:** Threat models, audit findings, and hardening specifics live in the private `mendsec/xspherede-security` repository, not here. Until Milestone **M5** is complete, trust-domain isolation in XSphereDE is **not** an enforced security boundary.

---

## Repository Ecosystem

| Repository | Visibility | Role |
|---|---|---|
| `mendsec/xsphereos` (this repo) | Private | `live-build` image recipe, package manifests, boot experience, QEMU/CI test harness, release tooling |
| `mendsec/xspherede` | Public (MIT, [ADR-003](docs/adr/ADR-003-xspherede-visibility.md)) | Smithay + `wgpu` spherical Wayland compositor and desktop shell |
| `mendsec/xspherede-security` | Private | Security analysis, threat models, and hardening notes for both projects |

---

## Current Status

XSphereOS is in active **M0 / Boot Experience (B1–B3)** development:

- **Implemented:**
  - `live-build` recipe (`auto/`, `config/`) producing a bootable hybrid ISO (`minbase`, no `Recommends`, `amd64`).
  - `xsphere` Plymouth boot theme (~18 KiB across both variants), generated arithmetically from [`scripts/boot_timeline.py`](scripts/boot_timeline.py) via [`scripts/gen-boot-assets.py`](scripts/gen-boot-assets.py).
  - **B1–B3 boot experience:** Ignite → Gather → Wake animation driven by real `systemd` milestones, `xsphere.motion=reduced` still-frame mode, 20 s stall watchdog, and plain-text failure reporting at login.
  - Headless QEMU boot verification ([`scripts/boot-test.py`](scripts/boot-test.py)) with normal, reduced-motion, failed-unit, and stalled-boot fault injection.
  - Concept audio/visual preview generator ([`scripts/render-boot-preview.py`](scripts/render-boot-preview.py), outputs in `preview/`).
  - GitHub Actions static & config CI ([`.github/workflows/ci.yml`](.github/workflows/ci.yml)): `shellcheck`, `shfmt -d`, and `unittest`.
- **In progress / planned:**
  - **M0:** Zero-prompt GRUB-EFI & ISOLINUX bootloaders ([ADR-002](docs/adr/ADR-002-zero-prompt-bootloaders.md)), recorded ISO/package budgets, and CI boot-test gate.
  - **M1–M5:** Prototype & fallback flat Wayland session, console-grade fluidity (`zstd` squashfs, `cgroups v2` QoS, `zram`, `DMA-BUF` per [ADR-004](docs/adr/ADR-004-console-grade-fluidity.md)), real Smithay compositor hand-off (**B4**), procedural boot audio (**B5**, [ADR-005](docs/adr/ADR-005-boot-procedural-audio.md)), signed APT repo & installer, and per-domain sandboxing (**M5**).

---

## Roadmap

### Distribution Milestones (`M0`–`M5`)

| Milestone | Scope | Done When |
|---|---|---|
| **M0** · Base image | Minimal Debian `minbase` live ISO | Boots unattended in QEMU to an autologged-in shell; package count and ISO size budgets recorded; static & boot CI green |
| **M1** · Prototype session | Early desktop & performance substrate | XSphereDE prototype runs in a stub/kiosk session; fallback flat Wayland session exists; `zstd` squashfs, `cgroups v2` QoS, and `zram` applied ([ADR-004](docs/adr/ADR-004-console-grade-fluidity.md)) |
| **M2** · Real compositor | Native Wayland session | `xspherede` (Smithay + `wgpu`) boots via DRM/KMS hand-off (**B4**); zero-copy `DMA-BUF` window capture renders a real terminal on the sphere |
| **M3** · Usable desktop | Daily-driver essentials | Wayland-native browser, file manager, terminal, network, PipeWire/WirePlumber audio, procedural boot audio (**B5**, [ADR-005](docs/adr/ADR-005-boot-procedural-audio.md)), polar launcher, and low-power profile |
| **M4** · Installable | Packaging & release pipeline | Installer, signed APT repo (`xsphereos-base`), first-boot flow (**B7**), reproducible builds, CycloneDX SBOM, and signed `testing` → `stable` releases |
| **M5** · Isolation | Enforced trust domains | Per-domain sandboxing (namespaces, seccomp, cgroups, clipboard vault) turns trust domains into a real security boundary |

### Boot Experience Milestones (`B0`–`B7`)

- **B0–B3 (Implemented):** Design approved; static brand theme; animated 2D sequence from a tested timeline; honest progress driven by `systemd` milestones, 20 s watchdog, and plain-text failure diagnostics.
- **B4–B7 (Planned):** Compositor Resolve/Unfold hand-off (`M2`), non-blocking procedural `audio-synth` (`M3` / [ADR-005](docs/adr/ADR-005-boot-procedural-audio.md)), real-hardware hardening & budget measurements, and first-boot integration (`M4`).

---

## Building & Running the Image

### Requirements (Debian host, root access)

```sh
sudo apt install live-build debootstrap squashfs-tools xorriso qemu-system-x86 ovmf
```

### Build and Boot in QEMU

```sh
sudo scripts/build.sh      # produces live-image-amd64.hybrid.iso in the repository root
scripts/run-qemu.sh        # BIOS boot in QEMU
scripts/run-qemu.sh --uefi # UEFI boot in QEMU (requires OVMF)
scripts/size-report.sh     # inspect ISO size and installed package footprint
```

On a non-Debian host (such as Ubuntu, whose `live-build` rejects options in `auto/config`), build inside a Debian container instead (requires `podman` on the host):

```sh
sudo scripts/build-in-container.sh
```

---

## Testing & Boot Splash Verification

### Static & Unit Checks (no root required)

```sh
python3 -m unittest discover -s tests -v   # config assertions, timeline math, and splash checks
shellcheck auto/config auto/build auto/clean scripts/*.sh
shfmt -d scripts/*.sh
```

### Boot Splash & Headless QEMU Tests

```sh
scripts/gen-boot-assets.py                 # regenerate the xsphere Plymouth theme (images and scripts)
scripts/boot-test.py                       # boot the ISO headless in QEMU and verify the splash contract
scripts/boot-test.py --reduced-motion      # verify the still-frame variant (xsphere.motion=reduced)
scripts/boot-test.py --fault fail          # inject a failed systemd unit: expects a plain-text report
scripts/boot-test.py --fault stall         # inject a stalled boot: expects the 20 s watchdog report
```

### Kernel Command-Line Switches

- `xsphere.motion=reduced`: renders a single still frame instead of the animated sphere.
- `plymouth.enable=0` (or removing `splash`): boots in plain text mode.
- `Esc` during boot: switches to detailed text output.

---

## Repository Layout

- [`auto/`](auto/) — `live-build` entry points; [`auto/config`](auto/config) defines all image options (Debian `trixie`, `minbase`, `--apt-recommends false`).
- [`config/`](config/) — package manifests (`config/package-lists/` with one-line justification per package), hooks (`config/hooks/`), bootloader templates (`config/bootloaders/`), and chroot overlays (`config/includes.chroot/`).
- [`scripts/`](scripts/) — image build, QEMU runner, size reporting, boot asset generation, preview rendering, and headless boot tests.
- [`tests/`](tests/) — unit, timeline, splash, and distribution configuration tests.
- [`preview/`](preview/) — generated concept boot audio/video previews and QEMU test captures.
- [`docs/`](docs/) — architecture, design, engineering plan, references, and ADRs.
- [`.github/workflows/`](.github/workflows/) — CI pipeline enforcing shell linting, formatting, and unit/config tests.

---

## Documentation & ADRs

- [docs/DISTRO-DESIGN.md](docs/DISTRO-DESIGN.md) — Goals, non-goals, Debian `minbase` rules, session architecture, and `M0`–`M5` milestones.
- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) — Layered system diagrams, boot hand-off sequence, DevSecOps pipeline, plus [Excalidraw canvas](docs/architecture/xsphereos.excalidraw) and [offline HTML inspector](docs/architecture/index.html).
- [docs/BOOT-EXPERIENCE.md](docs/BOOT-EXPERIENCE.md) — Boot chain hooks, Ignite/Gather/Wake/Resolve/Unfold timeline, capability tiers, procedural audio, and `B0`–`B7` milestones.
- [docs/ENGINEERING-PLAN.md](docs/ENGINEERING-PLAN.md) — TDD, Clean Code, DevSecOps gates, supply-chain pinning, SBOM, and release process.
- [docs/REFERENCES.md](docs/REFERENCES.md) — Systems research, storage/compression benchmarks, and frame-pacing references.
- [docs/adr/README.md](docs/adr/README.md) — Architecture Decision Records:
  - [ADR-001](docs/adr/ADR-001-github-roadmap-governance.md) — GitHub Roadmap, Governance, and Continuity Structure
  - [ADR-002](docs/adr/ADR-002-zero-prompt-bootloaders.md) — Zero-Prompt Direct Boot via `live-build` Bootloader Templates
  - [ADR-003](docs/adr/ADR-003-xspherede-visibility.md) — Repository Visibility Policy for `mendsec/xspherede`
  - [ADR-004](docs/adr/ADR-004-console-grade-fluidity.md) — Console-Grade Fluidity Discipline (`zstd`, `cgroups v2`, `zram`, `DMA-BUF`)
  - [ADR-005](docs/adr/ADR-005-boot-procedural-audio.md) — Boot Procedural Audio (B5) Integration and KVM Boot-Time Measurement
  - [ADR-006](docs/adr/ADR-006-installed-performance-and-recovery.md) — Installed System Performance (`host-only` `initramfs`) and Console-Style Recovery
  - [ADR-009](docs/adr/ADR-009-gpu-render-levels-and-warmup.md) — GPU Render Levels with Persisted Crash Downgrade, and Pipeline Warm-Up Behind the Splash (M2 / B4)
