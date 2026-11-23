# ADR-015: Planisphere, the 2D Presentation of Spheradian as a First-Class Experience

**Date:** 2026-11-23  
**Status:** Proposed  
**Author:** Senior Software Architect  
**Approver:** Fábio Mendes (`mendsec`)  
**Confidence:** Medium  
**Impact:** High  
**Reversibility:** Medium  

## 1. Executive Summary

Machines that cannot run the 3D sphere currently fall back to a terminal (`foot` in `cage`, ADR-007). ADR-009 ends its downgrade chain at a "flat fallback session". Both treat 2D as a failure state. The vision ([PRODUCT-VISION.md](../PRODUCT-VISION.md)) requires the opposite: someone on an old laptop or a Raspberry Pi 3 should still feel they are using something new.

We decide that the 2D mode is **Planisphere**, a full presentation of the same desktop:

- **The same model, projected.** A planisphere is a star chart: the celestial sphere drawn flat, with the observer at the center. Planisphere draws Spheradian's sphere the same way. Every window keeps its (θ, φ, r) coordinates, its galaxy, and its trust domain. Only the projection changes.
- **One compositor, two presenters.** The scene, input, policy, and layout live in one shared core. The Sphere presenter renders through `wgpu`. The Planisphere presenter renders through Smithay's renderer abstraction, on GLES 2 or on the Pixman CPU renderer. That covers every machine with KMS.
- **A choice, not only a fallback.** Planisphere is selected automatically below render level `low`. Users can also choose it at any time, for focus, accessibility, battery, or taste, and switch back live.
- **Held to the same quality bar.** Planisphere is not done until it passes the same usability tasks as the Sphere and meets ADR-014 budgets on the low-end reference machines.

## 2. Context and Problem

- **A fallback designed as a failure produces a second-class product.** On the hardware the vision cares most about (old computers, small boards), the terminal fallback would be the whole experience.
- **The 2D sphere already exists in the boot.** The Plymouth theme draws the sphere's lattice in 2D (dots placed by a tested timeline, ~18 KiB, no 3D) during Ignite → Gather → Wake. The visual identity already survives without a GPU. The desktop can do the same.
- **The innovation is in the model, not in the rendering.** What is new in Spheradian is spatial organization (galaxies, depth, a universe you move through), visible trust domains, and console-style navigation. None of that requires a 3D renderer. A 3D renderer is one way to show it.
- **Smithay supports GLES 2 and CPU rendering.** It has a `GlesRenderer` (`renderer_gl`) and a software Pixman renderer (`renderer_pixman`) behind the same rendering traits. The 2D path needs neither `wgpu` nor GLES 3.
- **CI cannot test the real fallback today.** QEMU without a 3D GPU hits the terminal fallback. With Planisphere on Pixman, CI exercises a real desktop on every change.

## 3. Scope

- **In scope:** what Planisphere is, the projection, which elements carry over and how, switching between presentations, architecture (shared core and presenters), selection rules, the quality bar, and the documents this ADR amends.
- **Out of scope:** pixel-level visual design (tuned in `spheradian/spheradian`); the Sphere's own render levels (ADR-009); budgets (ADR-014).

## 4. Options Considered

- **Option A: Keep a conventional fallback** (a terminal, or a plain tiling or floating desktop). Cheapest. The low-end experience becomes a different, ordinary product, which contradicts the vision.
- **Option B: Simplified 3D on software rendering** (`llvmpipe`). Keeps the sphere, but at a few frames per second on the CPUs that need it, with high power draw. Rejected by ADR-014 §5.2.
- **Option C: A separate 2D desktop with its own code.** Can be good, but doubles design and maintenance, and the two would drift apart.
- **Option D (Chosen): Planisphere, a second projection of the same model in the same compositor,** with its own renderer path and the same quality bar.

## 5. Decision

### 5.1 The projection

- **Default: azimuthal equidistant projection, centered on the current galaxy.** This is the projection of a real planisphere. You are at the center of the chart, as you are at the center of the sphere. The distance from the center is the angular distance from your view direction, and the direction on the chart is the direction you would turn. Turning in the Sphere becomes rotating the chart in Planisphere.
- **Depth (r):** shown as scale and layer order (nearer is larger and on top), with a small parallax when the chart moves.
- **The edge of the chart:** the opposite side of the sphere (180° away) is the chart's outer ring, compressed. Windows there are reachable, but visually signal "behind you".
- **Alternative projection: equirectangular "map" view** for an overview of the whole universe at once. It plays the role the Mini-Globe plays in the Sphere.

### 5.2 What carries over, element by element

| Element | Sphere | Planisphere |
|---|---|---|
| Windows | Curved surfaces at (θ, φ, r) | Flat surfaces at the projected position, scaled by r, never distorted. Text stays crisp, which is an advantage on small screens |
| Galaxies | Clusters with their own center and halo | Clusters on the chart with a halo ring; the chart re-centers on the selected galaxy |
| Space warp | Turn toward a galaxy and warp | Animated pan and zoom along the chart to the target galaxy, with the same easing and "settle to stillness" rules |
| Trust domains | Regions of the sphere; compositor-drawn borders | **Sectors of the chart** with a domain color field; the same compositor-drawn borders that client content cannot draw over or fake |
| Mini-Globe | Small globe from outside | A small **wireframe globe drawn in 2D** (the lattice projected on the CPU, as the boot splash does), plus the equirectangular map on demand |
| Boot continuity | Compositor continues the splash (B4) | Easier: the splash is already 2D, so the first Planisphere frame can match the last splash frame exactly |
| Controls | Controller, keyboard, mouse (ADR-016) | **The same bindings**: stick or arrows rotate the chart, triggers zoom (depth), shoulder buttons cycle galaxies |
| Palette, type, motion language | Shared design tokens | The same tokens |

### 5.3 Switching between presentations

- **Live switch, when the hardware can run both:** an animated transition in which the sphere unrolls into the chart (and back). The transition is the clearest demonstration that both are the same space.
- **A setting and a kernel switch:** `spheradian.presentation=sphere|planisphere|auto` (default `auto`), alongside the existing `spheradian.render` and `spheradian.motion` switches. These are the names after PR #30.
- **Reduced motion:** the switch becomes a cross-fade, and chart movement becomes instant re-centering. This follows the boot's `motion=reduced` rule.
- Window positions, galaxies, and domains are **never** stored separately per presentation. There is one model.

### 5.4 Architecture (in `spheradian/spheradian`)

```text
             ┌──────────────── shared core (pure, tested, no GPU) ────────────────┐
 input ───▶  │ scene model (θ, φ, r, galaxies) · focus · commands · domain policy │
             │ layout · navigation · motion timeline · projection math            │
             └──────────────┬───────────────────────────────┬───────────────────────┘
                            │ Presenter trait               │
              ┌─────────────▼─────────────┐   ┌──────────────▼───────────────────────┐
              │ Sphere presenter (wgpu)   │   │ Planisphere presenter                │
              │ Vulkan / GL(ES) 3.x       │   │ Smithay renderer traits:             │
              │ render levels (ADR-009)   │   │ GlesRenderer (GLES 2) or Pixman (CPU)│
              └───────────────────────────┘   └──────────────────────────────────────┘
```

- The projection math (azimuthal equidistant, equirectangular, inverse mapping for pointer hits) is pure and covered by property tests, as `ENGINEERING-PLAN.md` §3.3 already requires for the spherical math. For example: a project-then-unproject round trip returns the same point, and every window lands inside the chart.
- Planisphere relies on damage tracking (redraw only what changed) so the Pixman path stays inside ADR-014's idle-CPU and frame-time budgets.
- The ADR-009 downgrade chain becomes `high → medium → low → Planisphere (GLES 2) → Planisphere (Pixman) → tier 0 text`.

### 5.5 Selection

| Situation | Presentation |
|---|---|
| ADR-009 probe and warm-up succeed at `low` or above | Sphere (unless the user chose Planisphere) |
| No Vulkan or GL(ES) 3.x, GLES 2 available | Planisphere on GLES 2 |
| No GPU acceleration | Planisphere on Pixman |
| GPU crash loop persisted at `low` (ADR-009) | Planisphere, recorded the same way as a level downgrade |
| User setting or `spheradian.presentation=planisphere` | Planisphere, on the best renderer available |

### 5.6 Quality bar (Definition of Done)

Planisphere ships only when all of these hold:

1. Every task in the usability script (ADR-016) can be completed in Planisphere with the same inputs as in the Sphere.
2. In the usability sessions, Planisphere is judged by participants as a distinct, new experience, not as "a normal desktop". The question is part of the session protocol.
3. It meets the ADR-014 budgets on R2 (old `amd64`, GLES 2) and in CI (Pixman). R5 (Raspberry Pi 3) is added once `arm64` work starts.
4. The compositor-drawn trust-domain borders pass the same anti-spoofing tests in both presenters.
5. A live switch preserves focus, window positions, galaxy, and domain state exactly (an automated test in the shared core).

## 6. Consequences and Trade-offs

- **Pros:**
  - Every supported machine gets the real product.
  - The innovation is shown to be in the model, which also answers the "3D desktops are a gimmick" objection.
  - CI can test a real desktop without a GPU.
  - Planisphere doubles as an accessibility, focus, and battery mode on capable hardware.
  - Boot continuity is simpler in 2D.
- **Cons:**
  - Two presenters to keep at the same quality.
  - The `Presenter` boundary has to be designed before the M2 compositor grows. Retrofitting it later would be expensive.
  - Azimuthal projection distorts the far side. Usability testing must check that "behind you" stays understandable.
- **Amends:**
  - ADR-007: the `foot` terminal fallback stays only until Planisphere lands. After that, the terminal is an app, not the fallback.
  - ADR-009: the downgrade chain (§5.4).
  - `DISTRO-DESIGN.md` §5–6: "fallback flat session" and the low-power profile become Planisphere.
  - `BOOT-EXPERIENCE.md` §6.3: tier 2 becomes Planisphere.

## 7. Security and Compliance

- Domain borders and the domain color field are drawn by the compositor in both presenters. Client buffers are composited beneath them and can never overlap or imitate them. This is a hard rule, tested in both presenters.
- The Pixman path processes client buffers on the CPU. Buffer size and format validation (the existing `SurfaceDims`-style checks in `ENGINEERING-PLAN.md` §4.1) applies before any import, in both presenters.

## 8. Related

- [PRODUCT-VISION.md](../PRODUCT-VISION.md) §5
- [ADR-007](ADR-007-m1-kiosk-prototype-session.md), [ADR-009](ADR-009-gpu-render-levels-and-warmup.md) (amended)
- [ADR-014](ADR-014-hardware-targets-and-budgets.md) (budgets, reference machines)
- [ADR-016](ADR-016-first-usable-build-roadmap.md) (minimal Planisphere in the first usable build)
- [BOOT-EXPERIENCE.md](../BOOT-EXPERIENCE.md) §6.3; [DISTRO-DESIGN.md](../DISTRO-DESIGN.md) §5–6
- Smithay renderer module documentation (`renderer_gl`, `renderer_pixman`), docs.rs, Smithay 0.7
