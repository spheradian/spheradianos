# XSphereOS: Technical References & Systems Research

This document records foundational operating-systems, graphics, and performance references used to guide **XSphereOS** and **XSphereDE** architecture decisions.

---

## 1. Operating Systems Internals & Linux Subsystems

### 1.1 Projetos de Sistemas Operacionais — DInf / UFPR
- **Source:** [https://web.inf.ufpr.br/bona/projetos-de-sistemas-operacionais/](https://web.inf.ufpr.br/bona/projetos-de-sistemas-operacionais/) (Prof. Luis Carlos Erpen de Bona, Departamento de Informática — UFPR)
- **Key topics covered:**
  - System calls (`syscalls`), concurrency, atomicity, and synchronization primitives.
  - Linux kernel memory management: physical zones, paging, Buddy System, SLAB allocators, demand paging, and Copy-on-Write (COW).
  - Storage & filesystems: Virtual File System (VFS), Linux block I/O subsystem, disk scheduling, page cache, encrypted filesystems, and **FUSE** (*Filesystem in Userspace*).
  - Performance analysis and SIMD parallelism.
- **How XSphereOS applies it:**
  - Establishes the architectural boundary between kernel responsibilities we inherit from Debian/Linux (VFS, memory management, `blkmq`, device drivers) and user-space engineering we own (`xspherede`, trust-domain isolation in M5, and performance profiling on modest hardware).
  - Provides a theoretical baseline for future per-domain filesystem/sandbox boundaries (M5, Issue `#13`).

### 1.2 The Linux Storage Stack Diagram (Thomas Krenn)
- **Source:** Thomas Krenn Wiki — *The Linux Storage Stack Diagram*
- **Relevance:** Maps the full path from user-space `read(2)`/`write(2)` and VFS/Page Cache through `dm-crypt`/LVM, the Block Layer (`blkmq` / I/O schedulers), and low-level drivers (`nvme`, `ahci`, `virtio_blk`). Reinforces why XSphereOS treats Debian's kernel and storage stack as a stable substrate rather than reimplementing block or filesystem drivers.

---

## 2. Console-Grade Fluidity & Wayland Compositor Design

### 2.1 Embedded Wayland Micro-Compositor Pattern (Gamescope / SteamOS)
- **Relevance:** Demonstrates how a modern Linux distribution achieves console-like responsiveness without rewriting the OS kernel:
  - **Embedded DRM/KMS execution:** The compositor runs directly on `seatd`/DRM/KMS without a nested desktop environment or X11/Xwayland overhead.
  - **Deterministic frame pacing & low input-to-photon latency:** Short swapchain path and zero-copy buffer sharing (`DMA-BUF`) prevent CPU memory-bandwidth saturation on modest GPUs.
  - **Resource isolation:** Keeping system UI overlays and compositor threads protected from background application spikes prevents micro-stutter.
- **How XSphereOS applies it:**
  - `xspherede` (Smithay + `wgpu`) targets direct DRM/KMS execution in M2 (Issue `#9`), zero X11/Xwayland (`DISTRO-DESIGN.md` §1), and `DMA-BUF` live window capture (`DISTRO-DESIGN.md` §5).
  - Motivates `cgroups v2` compositor QoS and `zram` protection (proposed in ADR-004).

### 2.2 Console-Grade Boot Resource Discipline (Original Xbox Boot Sound)
- **Source:** Brian Schmidt, *"Creating the Original Xbox Boot Sound"* (GameSoundCon, 2021) — already referenced in [BOOT-EXPERIENCE.md](BOOT-EXPERIENCE.md#L157-L170).
- **Relevance:** Procedural/code-driven generation instead of pre-rendered assets keeps the `xsphere` Plymouth theme at ~18 KiB with zero audio files.

### 2.3 Orbis OS / PlayStation 4 Open Source Components (`PS4OSSCode`)
- **Source:** [https://github.com/FreeBSDKernel9-0/PS4OSSCode](https://github.com/FreeBSDKernel9-0/PS4OSSCode)
- **Relevance:** Shows how a commercial console OS builds on a mature POSIX substrate (`freebsd-9.0`) paired with a small, curated set of open-source libraries (`WebKit`, `sqlite`, `zlib`, `sf_ffmpeg`, `lua-5.2.4`), while isolating games and web/UI processes from the system shell. Reinforces XSphereOS's Debian `minbase` substrate, `cgroups v2` compositor QoS (ADR-004), and M5 per-domain sandboxing (Issue `#13`).

### 2.4 Procedural WebGPU Scene with Adaptive Quality (`abyssal-garden`)
- **Source:** [https://github.com/Noniv/abyssal-garden](https://github.com/Noniv/abyssal-garden) (MIT). A browser demo, not an OS: WebGPU + WGSL shaders and Web Audio synthesis, with no image, model or sound files.
- **Relevance:**
  - Device-based quality levels (Low/Medium/High), and after a tab or GPU-driver crash the page restarts one level lower and remembers the settled level.
  - The scene renders blurred behind the start menu, so performance tuning finishes before the user enters.
  - WGSL is also the native shader language of `wgpu`, which `xspherede` uses.
- **How XSphereOS applies it:** ideas only, no code. Render levels with a persisted crash downgrade, and pipeline warm-up behind the Plymouth splash ([ADR-009](adr/ADR-009-gpu-render-levels-and-warmup.md)). It also confirms the procedural-asset approach of the boot theme and ADR-005.

---

## 3. Live Image Compression & Boot Latency

### 3.1 SquashFS Compression: `zstd` vs `xz`
- **Findings:**
  - `xz` (LZMA2) produces the smallest compressed image, but decompression is CPU-bound and memory-heavy, creating a bottleneck on older CPUs during live boot and runtime app launches.
  - `zstd` decompresses roughly **5x–8x faster** than `xz` with lower decompression memory overhead and native multi-threading, typically cutting live-image boot times by **20%–35%** at a modest ~1%–10% size trade-off (depending on compression level).
- **How XSphereOS applies it:**
  - Directly informs the M0/M1 evaluation of `--chroot-squashfs-compression-type` in `auto/config` (currently `xz`, proposed to evaluate/switch to `zstd` in ADR-004 for console-grade boot responsiveness).
