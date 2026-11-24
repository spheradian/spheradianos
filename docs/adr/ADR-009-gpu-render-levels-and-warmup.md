# ADR-009: GPU Render Levels with Persisted Crash Downgrade, and Pipeline Warm-Up Behind the Splash (M2 / B4)

**Date:** 2026-11-21  
**Status:** Accepted  
**Author:** Senior Software Architect  
**Approver:** Fábio Mendes (`mendsec`)  
**Confidence:** Medium  
**Impact:** High  
**Reversibility:** Easy  

## 1. Executive Summary

`BOOT-EXPERIENCE.md` §6.3 defines capability tiers (0 Text → 3 Full) that may only be downgraded during a boot, but it does not say what happens *inside* tier 3, nor what the next boot does after the GPU path crashed. It also assumes the compositor's first frames are smooth, while shader compilation and pipeline creation on first use are the most common cause of first-frame stutter. We decide that `spheradian` (M2) will:

1. Expose **render levels** (`low`, `medium`, `high`) inside tier 3, chosen from adapter probes and a measured warm-up.
2. **Persist a downgrade** after a GPU failure (device lost, driver reset, crash loop), so the next start begins one level lower, and fall through to tier 2 / the flat fallback session when `low` also fails.
3. **Warm up** the GPU device and render pipelines on a DRM render node while Plymouth still owns the display, so the Resolve/Unfold hand-off (B4) runs on already-compiled pipelines.

Both patterns are inspired by the public `abyssal-garden` WebGPU demo (see §8); no code is reused.

## 2. Context and Problem

- **Tier 3 is too coarse.** A working Vulkan/GL path on a 2012 integrated GPU and on a current discrete GPU both land in "Full". Without a finer level, the sphere either looks poor everywhere or stutters on modest hardware, contradicting ADR-004.
- **Downgrade is per boot only.** A driver that hangs the GPU at `high` will do so again on every boot. The user sees a crash, a fallback, and the same crash next time. The persisted tier setting is already an open question (`BOOT-EXPERIENCE.md` §13, question 6).
- **First-use compilation stutters.** `wgpu` creates Vulkan/GL pipelines on demand; the driver compiles shaders at that moment (tens to hundreds of milliseconds per pipeline on weak CPUs). If this happens during Unfold, the signature moment of the boot is the one that drops frames.
- **The compositor already starts early.** Option B in `BOOT-EXPERIENCE.md` §2 starts `spheradian` before Plymouth quits. That window is currently idle from the GPU's point of view.

## 3. Scope

- **In scope:** render-level model and selector, crash detection and persisted downgrade, warm-up and pipeline cache during the Plymouth phase, kernel command-line overrides, test strategy, and the systemd/file-system contract between `spheradianos` and `spheradian`.
- **Out of scope:** the content of each level (exact lattice density, effects), which is tuned in `spheradian/spheradian`; custom drivers or kernel changes (ADR-004 §3); tiers 0–2, which stay as specified in `BOOT-EXPERIENCE.md` §6.3.

## 4. Options Considered

- **Option A: Single quality, per-boot downgrade only.** Simplest. Repeats GPU crashes on every boot and cannot serve both weak and strong hardware.
- **Option B (Chosen): Render levels + persisted, monotonic downgrade + warm-up behind the splash.**
- **Option C: Dynamic resolution scaling only.** Adjust render scale every frame from frame time. Handles load spikes but not driver crashes or compile stutter, and constant visible re-scaling conflicts with the "motion settles to stillness" design. Kept as an optional refinement *within* a level, not a substitute.

## 5. Decision

Adopt **Option B**.

### 5.1 Render levels

| Level | Intended hardware | Levers (tuned in `spheradian`) |
|---|---|---|
| `high` | Discrete GPU or recent integrated GPU | Native render scale, full lattice density, bloom on Resolve |
| `medium` | Typical integrated GPU | Reduced render scale and lattice density, cheaper bloom |
| `low` | Old or software-like GPU paths | Lowest scale, no bloom, minimal pipelines |

Below `low` is **tier 2** (compositor fade without a GPU path) and then the **flat fallback session** (`DISTRO-DESIGN.md` §5). The full order is therefore `high → medium → low → tier 2 / fallback → tier 0 text`.

### 5.2 Level selection

The selector is a **pure function** (no I/O), so it can be unit- and property-tested:

```
select(probe, persisted, cmdline, warmup_result) -> Level | Tier2
```

1. `cmdline` wins: `spheradian.render=low|medium|high|off` (`off` forces tier 2). `spheradian.motion=reduced` still forces tier 1 as today.
2. Otherwise start from `min(probe_level, persisted_cap)`, where `probe_level` comes from adapter info (device type, driver, memory) and `persisted_cap` from §5.3.
3. The warm-up (§5.4) renders a short off-screen sample of the Unfold scene. If its frame time exceeds the 16.7 ms budget at the chosen level, step down one level, at most once per start.
4. The level **never rises within a boot** (same rule as tiers).

### 5.3 Crash detection and persisted downgrade

- **In process:** a `wgpu` device-lost or uncaptured fatal error drops one level, recreates the device and resumes. A second loss in the same session at `low` exits non-zero so `systemd` starts the fallback session (`OnFailure=`).
- **Across starts (crash-loop sentinel):** before GPU init, the compositor writes the level it is about to try. After the first desktop frame plus 30 s without device loss, it marks that level as *settled*. If on start the previous attempt is unsettled, the previous start crashed, so `persisted_cap` becomes one level below it.
- **State file:** `/var/lib/spheradian/render-state` (`StateDirectory=spheradian`, mode `0600`, owned by the compositor's service user). It records the settled level, the cap, and the **GPU identity** (PCI vendor/device ID, driver name and version, kernel release).
- **Reset rule:** a change of GPU identity discards the cap and starts from probes again, so a driver update can bring `high` back. The user can also reset from settings or from Recovery Mode (ADR-006).
- **Live image:** the live ISO is stateless; the cap lives for the session only, and `spheradian.render=` is the persistent override there. This answers question 6 of `BOOT-EXPERIENCE.md` §13 for the render level.

### 5.4 Warm-up behind the splash

1. `spheradian` starts during Gather/Wake, as Option B already plans, and opens the **DRM render node** (`/dev/dri/renderD*`). It does not need DRM master for this, so Plymouth keeps the display.
2. It creates the `wgpu` device, compiles **every pipeline needed for Resolve, Unfold and the idle desktop**, uploads the procedurally generated geometry, and runs the off-screen sample of §5.2 step 3.
3. Where the backend supports it, pipelines are loaded from and saved to a **pipeline cache** in `/var/lib/spheradian/pipeline-cache/`, keyed by GPU identity. Mesa's own shader disk cache is pointed to the same state directory, not to a home directory.
4. **The warm-up never delays the boot.** If it is not finished when the session is ready, the hand-off happens anyway at the level reached so far (or `low`), and the remaining pipelines compile after Unfold. This keeps `BOOT-EXPERIENCE.md` §6.2 ("the splash never extends the boot").
5. Warm-up runs in the `spheradian-session.slice` QoS of ADR-004, so it cannot starve the rest of the boot.

## 6. Consequences and Trade-offs

- **Pros:**
  - The same image looks right on weak and strong GPUs, which serves the Kurumin-style "boot anywhere" goal.
  - A GPU crash costs the user one bad start, not every start.
  - Unfold runs on compiled pipelines; from the second boot on, the pipeline cache makes warm-up mostly a load.
  - The selector and sentinel are small pure modules, which fits the TDD rules of `ENGINEERING-PLAN.md`.
- **Cons:**
  - The compositor holds a GPU device earlier in the boot, which uses VRAM and power while Plymouth still runs.
  - A transient crash (for example a one-off driver hang) lowers the level until the GPU identity changes or the user resets. This is intentional: being stable matters more than looking good.
  - Three levels triple the visual checks in the manual release checklist (`BOOT-EXPERIENCE.md` §9).
  - Pipeline caches depend on the backend; on paths without support, warm-up still compiles but every boot pays the full cost.

## 7. Security and Compliance

- **The state file and the cache are untrusted input on every start.** Parsing is strict, size-bounded and versioned. Any parse error, unknown version or GPU-identity mismatch means "discard and start from probes", never "use partially". Cache blobs are passed only to the driver path that produced them, and only after their header identity matches.
- **No privilege for warm-up.** A render node needs no DRM master and no root. The compositor keeps the privilege rules of ADR-004 §7 (`RTKit` or scoped `CAP_SYS_NICE` only).
- **No home-directory writes before login.** Caches live in the service's own `StateDirectory`, not in `~/.cache`, so a user cannot plant a cache that the pre-login compositor loads.
- **Recovery Mode (ADR-006)** gets a "reset graphics settings" action that deletes the state directory after explicit confirmation.
- `abyssal-garden` is MIT-licensed; this ADR adopts ideas only. If code is ever reused, its licence notice must travel with it and the SBOM (Issue `#12`) must list it.

## 8. Verification

| Layer | Check |
|---|---|
| Unit / property (`proptest`, in `spheradian`) | The selector never returns a level above `cmdline`, `persisted_cap` or `probe_level`; the level never rises within a boot; any sequence of device-lost events ends at a level, tier 2 or fallback, never a stuck state; a corrupt or foreign state file always yields "start from probes" |
| Software GPU in CI | Warm-up, pipeline cache save/load and the off-screen sample run against Mesa `lavapipe` (software Vulkan) in the `image-boot.yml` workflow |
| QEMU fault injection (`scripts/boot-test.py`) | New test-only parameter `spheradian.test.gpu=init-fail|lost|slow`. Assert: `lost` drops one level and the session continues; two starts with `init-fail` end in the fallback session; the second boot after a crash starts one level lower; `slow` (warm-up exceeds the session-ready point) does not delay the session |
| Manual (per release) | Hand-off flicker and Unfold smoothness at each level on real older and newer GPUs |

## 9. Related

- `BOOT-EXPERIENCE.md` §2 (Option B), §5 (hand-off), §6.2 (never extend the boot), §6.3 (capability tiers), §13 question 6
- `DISTRO-DESIGN.md` §5 (mandatory fallback session)
- [ADR-004](ADR-004-console-grade-fluidity.md) (`cgroups v2` QoS, `DMA-BUF`, privilege rules)
- [ADR-006](ADR-006-installed-performance-and-recovery.md) (Recovery Mode)
- GitHub Issue `#7`: Plymouth hand-off (B4)
- GitHub Issue `#9`: M2 native compositor
- `docs/REFERENCES.md` §2.4 (`abyssal-garden`)
