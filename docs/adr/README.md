# Architecture Decision Records (ADRs)

This directory stores Architecture Decision Records for **SpheradianOS**, per `docs/ENGINEERING-PLAN.md` (§4.3).

## Index

| ID | Title | Status | Date |
|---|---|---|---|
| [ADR-001](ADR-001-github-roadmap-governance.md) | GitHub Roadmap, Governance, and Continuity Structure | Accepted | 2026-11-18 |
| [ADR-002](ADR-002-zero-prompt-bootloaders.md) | Zero-Prompt Direct Boot via `live-build` Bootloader Templates | Accepted | 2026-11-18 |
| [ADR-003](ADR-003-spheradian-visibility.md) | Repository Visibility Policy for `spheradian/spheradian` | Accepted (partly superseded by ADR-010) | 2026-11-18 |
| [ADR-004](ADR-004-console-grade-fluidity.md) | Console-Grade Fluidity Discipline (`zstd`, `cgroups v2` QoS, `zram`, `DMA-BUF`) | Accepted | 2026-11-18 |
| [ADR-005](ADR-005-boot-procedural-audio.md) | Boot Procedural Audio (B5) Integration and KVM Boot-Time Measurement | Accepted | 2026-11-18 |
| [ADR-006](ADR-006-installed-performance-and-recovery.md) | Installed System Performance (`host-only` `initramfs`) and Console-Style Recovery | Accepted | 2026-11-19 |
| [ADR-007](ADR-007-m1-kiosk-prototype-session.md) | M1 Prototype Session via Wayland Kiosk (`cage` + `seatd`) and Pinned `spheradian` Build | Accepted | 2026-11-20 |
| [ADR-009](ADR-009-gpu-render-levels-and-warmup.md) | GPU Render Levels with Persisted Crash Downgrade, and Pipeline Warm-Up Behind the Splash (M2 / B4) | Accepted | 2026-11-21 |
| [ADR-010](ADR-010-spheradianos-public-visibility.md) | Make `spheradian/spheradianos` Public After M0, Announce at M2 | Proposed | 2026-11-22 |
| [ADR-011](ADR-011-organization-and-product-structure.md) | Organization and Product Structure (Fabrintek, Spheradian, SpheradianOS) After the System76 and Silverblue Models | Proposed | 2026-11-23 |
| [ADR-012](ADR-012-implementation-language-policy.md) | Implementation Language Policy: Rust for What Ships, Scripts for What Builds | Proposed | 2026-11-23 |
| [ADR-014](ADR-014-hardware-targets-and-budgets.md) | Hardware Targets, Reference Machines, and Resource Budgets (`amd64` First, `arm64` Raspberry Pi Second) | Proposed | 2026-11-23 |
| [ADR-015](ADR-015-planisphere-2d-presentation.md) | Planisphere, the 2D Presentation of Spheradian as a First-Class Experience | Proposed | 2026-11-23 |
| [ADR-016](ADR-016-first-usable-build-roadmap.md) | Roadmap Reordering: First Usable Build Before Boot Polish | Proposed | 2026-11-23 |
| [ADR-017](ADR-017-command-layer-on-brush.md) | A Command Layer for Spheradian Built on the `brush` Crates (Depend, Do Not Fork) | Proposed | 2026-11-28 |

ADR-008 is reserved for the three-pillar positioning ADR (Privacy, Security, Old Computers), which is not yet committed. ADR-013 is reserved for the atomic system layer (ADR-011 §7).
