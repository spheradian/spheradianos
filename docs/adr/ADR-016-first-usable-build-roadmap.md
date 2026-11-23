# ADR-016: Roadmap Reordering: First Usable Build Before Boot Polish

**Date:** 2026-11-23  
**Status:** Proposed  
**Author:** Senior Software Architect  
**Approver:** Fábio Mendes (`mendsec`)  
**Confidence:** High  
**Impact:** High  
**Reversibility:** Easy  

## 1. Executive Summary

The innovation in Spheradian is proven only when people use it for real tasks ([PRODUCT-VISION.md](../PRODUCT-VISION.md) §8). Today nobody can: the desktop shows built-in demo windows and does not host applications. Meanwhile, most recent work in this repository has gone into the boot experience. The open pull requests #27, #28, and #29 are all boot polish.

We decide to put a **first usable build** in front of people before more polish:

- **M2 is redefined as "First Usable Build":**
  - the native Smithay compositor hosting real Wayland applications on the sphere;
  - controller and keyboard navigation;
  - a minimal Planisphere;
  - a live ISO;
  - a usability test protocol.
- **Moved out of M2:** the flicker-free boot hand-off (B4) moves to M3, together with the other polish.
- **New milestone M6 (`arm64`, Raspberry Pi 4/5):** it can start once M2 ships.
- **Not discarded:** the boot work already done stays. Open boot PRs are finished or parked, but they no longer set the pace.

## 2. Context and Problem

- **The critical path runs through the compositor.** Issues `spheradianos#9` and `spheradian#22` (native Smithay session) and `spheradian#23` (trusted input path) gate every usability question. Nothing about galaxies, warp, domains, or Planisphere can be tested with real work until a real application runs on the sphere.
- **M2 currently bundles B4.** M2 contains `spheradianos#7` (flicker-free Plymouth-to-compositor hand-off). B4 is high-effort polish (DRM master hand-off, deterministic first frame, timeline sharing) that adds nothing to a usability test.
- **The vision adds requirements that must exist from the first build:**
  - controller navigation (console feel), because retrofitting it changes every interaction;
  - the Presenter boundary for Planisphere (ADR-015), because retrofitting it changes the renderer architecture.
- **Usability evidence is needed early.** The historical risk for 3D desktops is daily usability, not technology. Finding out at M2 is cheaper than finding out at M4.

## 3. Scope

- **In scope:** the contents and order of milestones M2–M6; what is deferred; the usability test protocol; how the open PRs and issues are re-sorted.
- **Out of scope:** the design of each item, which lives in its own ADR or issue.

## 4. Options Considered

- **Option A: Keep the current order.** M2 ships with a perfect boot hand-off, but usability feedback arrives months later. The boot would be polished for an experience nobody has validated.
- **Option B: Ship the prototype as is for testing.** Fast, but tests of demo windows say nothing about real work.
- **Option C (Chosen): Redefine M2 around a usable build, move polish to M3, add M6 for `arm64`.**

## 5. Decision

### 5.1 Milestones

| Milestone | Scope | Done when |
|---|---|---|
| **M0** · Base image | Unchanged (done) | — |
| **M1** · Prototype session | Unchanged. Finish `#15` (fluidity baseline) | Kiosk prototype and fluidity baseline merged |
| **M2** · **First Usable Build** | Smithay compositor session hosting real Wayland clients on the sphere (`spheradianos#9`, `spheradian#22`, `spheradian#23`); `Presenter` boundary and a **minimal Planisphere** (ADR-015: projection, windows, galaxies, domain sectors; on Pixman at least); **controller and keyboard navigation** for every action in the usability script; default apps: terminal, file manager, one browser; live ISO; ADR-014 RAM and idle-CPU budgets measured | A live ISO on reference machines R1 and R2 completes the usability script (§5.3) in both presentations, and the first usability round is run and written up |
| **M3** · Usable desktop and polish | Previous M3 scope (browser and network decision `#8`, PipeWire and GPU probe `#10`, polar dock and launcher, low-power profile) **plus**: B4 flicker-free hand-off (`#7`), B5 procedural audio (`#16`), full Planisphere (live sphere↔chart switch, GLES 2 path), adjustments from usability round 1 | Usability round 2 shows improvement on round 1's findings; all ADR-014 budgets measured |
| **M4** · Installable and atomic | Installer, first boot (B7), the atomic system layer (ADR-013): image builder, signed images, update and rollback; signed package repository feeding image builds (`#11`, `#12`); SBOM; reproducible builds | Install, update, and roll back on R1 without a terminal |
| **M5** · Isolation | Per-domain sandboxing (`#13`, `spheradian#24`); optional microVM for `QUARANTINE` evaluated | Isolation tests pass; only then may trust domains be called a security boundary |
| **M6** · **`arm64` / Raspberry Pi** *(new)* | `aarch64` build in the desktop CI (start now, ADR-014 §5.1); Pi image and boot chain; R3–R5 budgets | SpheradianOS boots on Raspberry Pi 4 and 5 into the Sphere, and on a Pi 3 into Planisphere. Can run in parallel with M3–M5 once M2 ships |

The boot-experience track (B-milestones) keeps its numbering. Only its placement changes: B4 and B5 are in M3, B6 (real-hardware hardening) follows the reference machines, and B7 stays in M4.

### 5.2 Open work, re-sorted

| Item | Decision |
|---|---|
| PR #27 (no text cursor under BIOS), PR #28 (bootloader menu art), PR #29 (splash cost measurement) | Finish if they are close to done, since each is small. Otherwise park them. They do not block M2 |
| PR #30 (rename) | Merge first. Every other change rebases on it |
| PR #31 (build against trixie glibc) | Required for M2 (the compositor must run in the image) |
| PR #23 (ADR-010, visibility) | Independent; decide on its own schedule |
| `#7` (B4 hand-off) | Move from M2 to M3 |
| `spheradian#26` (`--fullscreen`), `spheradian#27` (low-power profile) | `#26` is superseded by the compositor session in M2; `#27` is folded into Planisphere and render levels |

### 5.3 Usability test protocol (first round, M2)

- **Participants:** 5–8 people, including at least two who are not developers. Fabrintek clients are a natural pool.
- **Tasks, run in Sphere, in Planisphere, and on a conventional desktop for comparison:**
  1. Open a browser and a terminal, and put them in different galaxies.
  2. Find a file and open it (using the file manager available at M2).
  3. Switch between three tasks quickly.
  4. Tell which window belongs to which trust domain.
  5. Do tasks 1–3 with a game controller only, then with a keyboard only.
- **Measures:** completion, time, errors, the System Usability Scale (SUS) questionnaire, and two direct questions: *"Did this feel new?"* and *"Would you use it every day?"*
- **Output:** a short report in `docs/usability/`, with the issues filed against M3.

## 6. Consequences and Trade-offs

- **Pros:**
  - Usability evidence comes several months earlier.
  - Planisphere and controller support are built into the architecture instead of retrofitted.
  - The first build already serves old hardware (R2) and gives Fabrintek something to show.
- **Cons:**
  - The first build will flicker between the splash and the desktop (B4 deferred), and will have no boot audio.
  - Four open boot PRs lose priority.
  - The M2 milestone on GitHub needs its issues and description updated (§7).

## 7. Follow-up Actions (manual, after acceptance)

1. Update the GitHub milestone descriptions for M2 and M3, and create M6.
2. Move `spheradianos#7` to M3. Create issues for Planisphere (minimal, M2), controller navigation (M2), the `Presenter` boundary (M2), the `aarch64` CI build (M6, can start now), and usability round 1 (M2).
3. Update the README roadmap table and `DISTRO-DESIGN.md` §9 to match §5.1. Both point to this ADR until then.

## 8. Related

- [PRODUCT-VISION.md](../PRODUCT-VISION.md)
- [ADR-009](ADR-009-gpu-render-levels-and-warmup.md), [ADR-014](ADR-014-hardware-targets-and-budgets.md), [ADR-015](ADR-015-planisphere-2d-presentation.md)
- ADR-013 (planned): atomic system layer, M4
- [BOOT-EXPERIENCE.md](../BOOT-EXPERIENCE.md) §12 (B-milestones)
