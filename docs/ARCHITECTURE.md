# XSphereOS: System Architecture

High-level architecture and system design for **XSphereOS** (`mendsec/xsphereos`), **XSphereDE** (`mendsec/xspherede`), and their DevSecOps pipeline.

> **Other views in this repository:**
> - **Miro-like editable canvas:** [docs/architecture/xsphereos.excalidraw](architecture/xsphereos.excalidraw) (open in [excalidraw.com](https://excalidraw.com) or the IDE Excalidraw extension).
> - **Offline interactive inspector:** [docs/architecture/index.html](architecture/index.html) (open locally in any browser).

---

## 1. Layered System Architecture

```mermaid
flowchart TB
    subgraph L4["Layer 4 · Wayland Clients & Trust Domains (M2–M5)"]
        direction LR
        UI["Trusted Shell UI<br/>(Mini-Globe, Polar Docks, Launcher, Settings)"]
        APPS["Wayland Clients<br/>(Terminal, Wayland Browser, File Manager)"]
        SANDBOX["Per-Domain Sandbox (M5)<br/>(namespaces, seccomp, cgroups, clipboard vault)"]
    end

    subgraph L3["Layer 3 · Compositor & Session (mendsec/xspherede · Public MIT)"]
        direction LR
        SMITHAY["xspherede Compositor<br/>(Smithay + wgpu · no X11/Xwayland)"]
        CORE["Pure Core & Policy<br/>(input, state, commands, WindowSurfaceProvider)"]
        FALLBACK["Fallback Flat Wayland Session<br/>(No Vulkan/GL hardware path)"]
    end

    subgraph L2["Layer 2 · Debian minbase Substrate (mendsec/xsphereos · Private)"]
        direction LR
        SYS["Core OS<br/>(systemd, dbus, udev, seatd/logind)"]
        MEDIA["Graphics, Audio & Net<br/>(Mesa, PipeWire/WirePlumber, NM vs iwd)"]
        PKG["Packaging & Install (M4)<br/>(Signed APT, xsphereos-base, Installer)"]
    end

    subgraph L1["Layer 1 · Boot Chain (M0 / M2)"]
        direction LR
        BOOT["GRUB-EFI & ISOLINUX<br/>(ADR-002 Zero-Prompt · timeout=0)"]
        KERN["Linux Kernel + simpledrm<br/>(quiet loglevel=3 · KMS hand-off)"]
        PLY["Plymouth xsphere (~18 KiB)<br/>(boot_timeline.py · 20s watchdog · B4)"]
    end

    BOOT --> KERN --> PLY
    PLY -->|"DRM/KMS master hand-off (M2)"| SMITHAY
    SYS --> SMITHAY
    MEDIA --> SMITHAY
    SMITHAY --- CORE
    SMITHAY -.->|"GPU unavailable"| FALLBACK
    SMITHAY -->|"Wayland + DMA-BUF"| UI
    SMITHAY -->|"Wayland + DMA-BUF"| APPS
    SANDBOX -.->|"Enforced boundary (M5)"| APPS

    click BOOT "https://github.com/mendsec/xsphereos/issues/14" "Issue #14: Zero-prompt bootloaders"
    click PLY "https://github.com/mendsec/xsphereos/issues/7" "Issue #7: Plymouth hand-off (B4)"
    click SMITHAY "https://github.com/mendsec/xsphereos/issues/9" "Issue #9: Smithay compositor session"
    click FALLBACK "https://github.com/mendsec/xsphereos/issues/5" "Issue #5: M1 prototype & fallback"
    click MEDIA "https://github.com/mendsec/xsphereos/issues/8" "Issue #8: Browser & network ADR"
    click PKG "https://github.com/mendsec/xsphereos/issues/12" "Issue #12: Signed APT & release"
    click SANDBOX "https://github.com/mendsec/xsphereos/issues/13" "Issue #13: Per-domain sandboxing"
```

---

## 2. Zero-Prompt Boot & Hand-Off Sequence (ADR-002 & B4)

```mermaid
sequenceDiagram
    autonumber
    participant FW as UEFI / BIOS Firmware
    participant BL as GRUB-EFI / ISOLINUX
    participant K as Linux Kernel (simpledrm)
    participant P as Plymouth (xsphere)
    participant C as xspherede (Smithay + wgpu)

    FW->>BL: Power on
    alt Shift / Esc held
        BL-->>BL: Show hidden menu (fail-safe / checksums)
    else Default (Zero-Prompt)
        BL->>K: Load vmlinuz + initrd (timeout=0, black screen, no beep)
    end
    K->>P: Mount initramfs & start plymouthd on DRM
    Note over P: Ignite -> Gather -> Wake (systemd milestones)
    alt Unit fails or 20s stall
        P-->>P: Drop to plain-text diagnostics
    else Normal boot
        P->>C: Resolve & DRM master hand-off (B4, M2)
        C-->>C: Unfold into live spherical desktop (or fallback flat session)
    end
```

---

## 3. DevSecOps & Supply Chain Pipeline

```mermaid
flowchart LR
    PR["Pull Request"] --> S1["Static Gates (#2)<br/>shellcheck, shfmt, unittest,<br/>manifest & auto/config checks"]
    PR --> S2["Security Gates (#2, #3)<br/>gitleaks, zizmor,<br/>cargo audit & deny (xspherede)"]
    S1 --> Q["QEMU Headless Boot (#6)<br/>normal, reduced-motion,<br/>fault fail/stall, size budget"]
    S2 --> Q
    Q --> R["Release Pipeline (#12, M4)<br/>Pinned Debian snapshot,<br/>CycloneDX SBOM, signing, reproducible diff"]
```

---

## 4. Architecture Decision Records

See [docs/adr/README.md](adr/README.md) for accepted and proposed ADRs:
- [ADR-001](adr/ADR-001-github-roadmap-governance.md) — GitHub Roadmap, Governance, and Continuity Structure
- [ADR-002](adr/ADR-002-zero-prompt-bootloaders.md) — Zero-Prompt Direct Boot via `live-build` Bootloader Templates
- [ADR-003](adr/ADR-003-xspherede-visibility.md) — Repository Visibility Policy for `mendsec/xspherede`
- [ADR-004](adr/ADR-004-console-grade-fluidity.md) — Console-Grade Fluidity Discipline (`zstd`, `cgroups v2`, `zram`, `DMA-BUF`)
- [ADR-005](adr/ADR-005-boot-procedural-audio.md) — Boot Procedural Audio (B5) Integration and KVM Boot-Time Measurement
- [ADR-006](adr/ADR-006-installed-performance-and-recovery.md) — Installed System Performance (`host-only` `initramfs`) and Console-Style Recovery
- [ADR-007](adr/ADR-007-m1-kiosk-prototype-session.md) — M1 Prototype Session via Wayland Kiosk (`cage` + `seatd`) and Pinned `xspherede` Build
- ADR-008 (reserved, not yet committed) — Three-Pillar Positioning (Privacy, Security, Old Computers) and Vulnerability-Driven Anti-Pattern Prevention
- [ADR-011](adr/ADR-011-organization-and-product-structure.md) — Organization and Product Structure (Fabrintek, Spheradian, SpheradianOS) After the System76 and Silverblue Models
- [ADR-012](adr/ADR-012-implementation-language-policy.md) — Implementation Language Policy: Rust for What Ships, Scripts for What Builds
- [ADR-014](adr/ADR-014-hardware-targets-and-budgets.md) — Hardware Targets, Reference Machines, and Resource Budgets
- [ADR-015](adr/ADR-015-planisphere-2d-presentation.md) — Planisphere, the 2D Presentation of Spheradian
- [ADR-016](adr/ADR-016-first-usable-build-roadmap.md) — Roadmap Reordering: First Usable Build Before Boot Polish

---

## 5. Technical References & Research

See [docs/REFERENCES.md](REFERENCES.md) for systems research (UFPR Operating Systems Projects, Linux Storage Stack, embedded Wayland micro-compositor frame pacing, SquashFS `zstd` vs `xz` benchmarks, and comparative Privacy, Security, and Old Computers distribution research).
