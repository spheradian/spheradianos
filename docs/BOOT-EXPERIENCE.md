# XSphereOS: Boot Experience

Status: **draft for review, pre-implementation**. Nothing described here exists yet. This document builds on [DISTRO-DESIGN.md](DISTRO-DESIGN.md) and follows the rules in [ENGINEERING-PLAN.md](ENGINEERING-PLAN.md).

> Scope note: boot-security design (secure boot, measured boot, threat models) lives in the private `xspherede-security` repository. This document mentions it only at a high level, in section 11.

> Originality note: this is an original work inspired by a *feeling*: a short, cinematic, sound-and-light-driven moment at power-on that makes the machine feel alive, as in the startup intro of the original Xbox console. It uses **no** Microsoft or Xbox assets, logo, sounds, shapes, colours or trade dress, and it must not be made to resemble them. Every visual and audio element is generated from XSphereOS's own sphere motif and its own code.

> Reference note: the reference video was not available to the author of this draft, so nothing here claims to reproduce specific frames, shapes or sounds from it. Questions that need the video owner's input are collected in section 13.

---

## 1. Vision

XSphereDE is a sphere: windows live on its surface, trust domains are regions of it, and the Mini-Globe shows it from outside. The boot experience is the **first appearance of that same sphere**, and the desktop is where it ends up. The boot is not an intro video placed in front of the desktop; it is the desktop assembling itself.

The sequence, in one sentence: *a point of light appears in the dark, gathers into a sphere, its surface lights up as the system genuinely comes alive, and then the sphere unfolds around the viewer and becomes the desktop*.

Design principles:

1. **Continuity.** One visual identity from the first pixel after the kernel to the first interactive frame. The last frame of the splash and the first frame of the desktop are the same image.
2. **Honesty.** The animation reflects real boot progress. It never fakes work and never delays the system to finish a show.
3. **Light and sound as one timeline.** Visual and audio events come from one deterministic timeline, so they cannot drift apart.
4. **Failure is a first-class state.** A fault is shown in the same visual language *and* with readable text. The splash can never hide an error.
5. **Cheap.** The boot experience must not be a reason a machine boots slower. It degrades down to plain text on hardware that cannot afford it.

Target feel (not a spec of frames): calm, confident, about two to three seconds of *authored* motion that overlaps the real boot rather than extending it; a single, soft, low-register sound at the moment the sphere resolves into the desktop.

---

## 2. The boot chain and where each stage can hook in

| # | Stage | Who owns the screen | What we can do | Notes |
|---|---|---|---|---|
| 1 | UEFI firmware | Firmware (OEM logo via BGRT) | Nothing visual. Optionally keep the BGRT logo as the first frame and fade from it | We do not replace firmware branding; legacy BIOS shows nothing |
| 2 | Bootloader (`systemd-boot` or GRUB) | Bootloader (GOP framebuffer) | Menu hidden by default (timeout 0 with a key to show it), a plain dark background that matches the splash background, no text unless a key is held | Prevents a white or text flash between firmware and splash |
| 3 | Kernel early boot | `efifb` or `simpledrm` on the firmware framebuffer | `quiet loglevel=3`, `vt.global_cursor_default=0`, no console text on screen | Messages still go to the journal and serial console |
| 4 | Initramfs, early userspace | Plymouth (`plymouthd` in the initramfs) | First animated frame as soon as a KMS device exists; theme runs here | The only stage where we can draw *before* root is mounted |
| 5 | KMS driver load (`i915`, `amdgpu`, `nouveau`, virtio, ...) | Plymouth, switching from `simpledrm` | Plymouth re-opens the real DRM device when it appears (it handles this itself) | A mode change here can flash; mitigated by keeping the same resolution and a dark frame |
| 6 | Root mount, `systemd` start | Plymouth (`plymouth-start.service`) | Progress events (`plymouth update-root-fs`, status messages) feed the theme | Live image: root is a squashfs overlay (`live-boot`) |
| 7 | Services up (`seatd`/`logind`, PipeWire, network) | Plymouth until takeover | Real unit readiness drives the sphere's surface lighting | Section 4 |
| 8 | Compositor start (`xspherede`) | Hand-off from Plymouth to the compositor | DRM master hand-over without a visible modeset; compositor renders the matching first frame | Section 5 |
| 9 | Session running | Compositor | The "unfolding" transition into the desktop; the arrival sound | Input is live from the first desktop frame |

### 2.1 Mechanisms, with the realistic options for each hook

**Plymouth (stages 4 to 7).** Plymouth is the standard way to draw during early boot on Debian: it runs from the initramfs, supports KMS and a framebuffer fallback, a text fallback, password prompts, and a `script` plugin for custom 2D themes. It is the most pragmatic carrier for the early half of the sequence. Limits we must design around: no GPU 3D, no Mesa in the initramfs, a small scripting language, and a separate renderer from the desktop (the source of the classic splash-to-desktop discontinuity).

**simpledrm / KMS hand-off (stages 3 to 5).** On a modern kernel, firmware framebuffers are exposed through `simpledrm`, which gives Plymouth a DRM device before the native driver loads. When the native driver probes, the framebuffer is taken over. We keep the splash background a flat dark colour for the first frames so that a mode change or driver swap is not visible as a flash.

**Wayland-native splash (stage 8 and 9).** Three architectures are possible for the second half:

| Option | Description | Pros | Cons |
|---|---|---|---|
| A. Plymouth only | Plymouth draws everything and `plymouth quit` before the session | Simplest, already packaged | Visible discontinuity at hand-off; no GPU 3D; the end of the intro is not the desktop |
| B. **Plymouth then compositor intro (recommended)** | Plymouth carries stages 4 to 7 with a 2D approximation of the sphere. `xspherede` starts early and renders the final "gather and unfold" itself with the real renderer, starting from the frame Plymouth ended on | Real continuity; the intro ends *as* the desktop; reuses existing wgpu sphere code | Needs compositor work (depends on roadmap item "native Wayland compositor"); needs the hand-off protocol of section 5 |
| C. Custom KMS splash daemon | A small Rust program replaces Plymouth, drawing via dumb buffers or a tiny software rasteriser | Full control, one codebase, testable pure core | Re-implements password prompts, serial handling, multi-monitor; large maintenance cost. Revisit only if Plymouth proves limiting |

**Decision (proposed):** option B. Option A is the fallback and the M0 to M1 stopping point. Option C is deferred and tracked as an open question.

---

## 3. Experience timeline (draft)

Times are targets measured from the first frame drawn, on a mid-range 2020 laptop with an SSD. They describe *authored* motion; the real system dictates when the final stages start (section 6.2).

| Phase | Stage hook | Visual | Sound | Notes |
|---|---|---|---|---|
| Ignite | Plymouth, initramfs | Dark field; a single point of light fades in at the centre | none | Matches the bootloader background so there is no flash |
| Gather | Plymouth | The point expands into a faint sphere wireframe, rotating slowly | none | Loops indefinitely if the boot is slow; never speeds up artificially |
| Wake | Plymouth, `systemd` | Regions of the surface (trust-domain meridians) light up as real milestones complete: root mounted, devices settled, session services ready | none | Section 4 |
| Resolve | Hand-off | Sphere reaches full brightness; the compositor takes over on the same frame | Soft low tone begins (if enabled) | Section 5 |
| Unfold | Compositor | The camera moves from outside the sphere to the inside; the surface becomes the desktop; Mini-Globe fades in | Tone resolves into a short, original chord | About 0.8 to 1.2 s, and input is already live |

The sound is **synthesised procedurally** from a small, deterministic description (a few oscillators, an envelope, a filter sweep), not recorded or sampled. This keeps the repository free of binary audio, makes the output reproducible and licence-clean, and removes any chance of resembling an existing jingle. It also lets the same timeline description drive both light and sound.

---

## 4. Honest progress: the sphere as a live boot indicator

Most splash screens show an animation or an estimated progress bar. Here, progress is **data**:

- A small readiness model maps real boot milestones to sphere regions: root filesystem mounted, device manager settled, `seatd`/`logind` ready, audio server ready, network up, compositor ready. A region lights only when its milestone is reached.
- In the initramfs, milestones come from Plymouth's own messages. After the root switch, a tiny helper subscribes to `systemd` unit state changes and forwards them with `plymouth update` and later to the compositor.
- The model is a **pure function** from an event stream to a state (`Pending`, `Ready`, `Failed`, `TimedOut` per milestone). It has no GPU, clock or I/O dependency, so it is fully unit-testable (section 9).
- If a milestone fails or times out, its region shows a visible "fracture" in the theme's language **and** the text diagnostics of section 7 appear. The visual is decoration; the text is the contract.

Boot progress that moves backwards, or a splash that outlives the boot, is a bug, and is covered by property tests.

---

## 5. Hand-off: Plymouth to compositor without flicker

The classic flicker has three causes: a second modeset, a blank frame while DRM master changes owner, and a visual discontinuity (a different background or object). The plan addresses each.

1. **Ordering.** `xspherede.service` is ordered after `plymouth-start.service`. Before taking the DRM device it runs `plymouth deactivate`, which releases DRM master but leaves the last frame scanned out on the display. After its first frame is presented it runs `plymouth quit --retain-splash`, so Plymouth never clears the screen.
2. **No visible modeset.** The compositor reuses the resolution and refresh rate already active, and commits its first frame with an atomic commit that does not require a full modeset when the existing configuration already matches. If it does not match, it falls back to a normal modeset on a dark frame.
3. **Deterministic first frame.** Rather than reading the previous framebuffer back (which needs privileges and driver support), the compositor *recomputes* the frame Plymouth ended on. Both consume the same small timeline description (a data file generated at image build time), and the final Plymouth frame is a known function of the timeline position. The compositor starts its intro at exactly that position.
4. **Session start does not wait for the show.** The compositor accepts input and shows windows as soon as it is ready; the unfold animation runs *on top of* a live desktop and can be interrupted by any input (section 8).

Failure handling: if the compositor fails to start, `plymouth quit` runs through the normal `systemd` ordering, the fallback session of DISTRO-DESIGN section 5 starts, and the user sees text diagnostics (section 7). A hand-off that cannot be completed is never a reason to leave a frozen splash on screen.

---

## 6. Timing, performance and graceful degradation

### 6.1 Budgets (initial, to be validated by measurement)

| Item | Budget | How measured |
|---|---|---|
| Added wall-clock boot time versus splash disabled | at most 150 ms, target 0 | `systemd-analyze` and QEMU boot-time comparison, splash on versus `xsphere.splash=off` |
| Added initramfs size | at most 1.5 MB compressed | size check in image build |
| Theme assets in the image | at most 1 MB, no binary audio | size check |
| First splash frame | within 1 s of the kernel starting on KVM-accelerated QEMU | timestamped log marker versus kernel start |
| CPU use of splash during early boot | at most one core partially, no busy-wait; frame rate capped at 30 fps in Plymouth | profiling |
| Compositor intro | at most 1.2 s, interruptible, renders on the integrated GPU within the low-power profile limits | frame timing in the compositor |
| Idle after intro | zero continuous redraw (consistent with DISTRO-DESIGN section 6) | frame counter |

If a budget is exceeded, the build fails or the effect is cut, not the budget.

### 6.2 The splash never extends the boot

- No fixed minimum display time. If the system is ready sooner than the animation, the animation is shortened, not waited out.
- If the system is slower than the animation, the "Gather" phase loops. It does not speed up or fake progress.
- A hard watchdog: if no milestone advances for 20 s, text diagnostics are shown (section 7).

### 6.3 Capability tiers

| Tier | Selected when | Experience |
|---|---|---|
| 0. Text | `xsphere.splash=off`, `plymouth.enable=0`, no KMS or framebuffer, serial-only console, or any failure | Plain kernel and `systemd` status text. The mandatory baseline |
| 1. Static | Reduced-motion enabled, or very slow framebuffer only | One still frame of the sphere on the dark background, then a cross-fade into the desktop |
| 2. 2D animated | KMS or `simpledrm`, no usable 3D | Plymouth theme: the full sequence drawn in 2D up to the hand-off; the compositor performs a simple fade if it has no GPU path |
| 3. Full | Compositor starts with a working Vulkan or GL path | Tier 2 plus the compositor "Unfold", the real-renderer sphere and arrival sound |

Tier choice is automatic from probes (KMS present, compositor GPU init result) with manual overrides on the kernel command line. A tier can only ever be downgraded during a boot, never upgraded, so a late failure always lands on a lower, working tier.

---

## 7. Failures always drop to readable diagnostics

This is a hard rule, and has a test for every clause.

1. Any of the following immediately ends the splash and shows text: `emergency.target` or `rescue.target` reached, a unit in the boot-critical chain fails, the compositor fails to start, the 20 s watchdog fires, a kernel panic or oops (the kernel prints directly to the console, not through the splash), initramfs failing to mount the root.
2. The text view shows at minimum: what failed, the last relevant journal lines, and how to continue (key hints). It must be legible without the theme's fonts or images.
3. `Esc` (and the `xsphere.splash=off` command-line parameter) always switch to text details, in every phase and tier. `Esc` is native Plymouth behaviour and is preserved.
4. Splash exit is on the same `systemd` ordering Plymouth already provides for failure targets (`plymouth-quit` conflicts), not on a custom timer alone.
5. The theme may *add* a visual cue for failure. It must never replace or delay the text.
6. Serial consoles get text always; the splash is not drawn on them.
7. Password prompts (for example future disk-encryption unlock) must work through the theme with a readable text fallback. This is a requirement on the theme even though encryption is not in M0.

---

## 8. Accessibility

| Concern | Decision |
|---|---|
| Skippable | Any key or pointer press during the boot skips the remaining authored motion and, once the session is up, the "Unfold". `Esc` shows text details |
| Reduced motion | Honoured via `xsphere.motion=reduced` on the kernel command line, a persisted setting from the settings tool, and the desktop's reduced-motion preference. Result: tier 1 (still frame and cross-fade, no rotation or zoom) |
| Audio | **Off unless enabled** (proposed default for the live image, see section 13). When enabled: only played when the output is not muted and volume is above zero, capped at a low fixed level, never louder than the system volume, short (about 1.5 s), played only after the audio server is up. Never delays the session. A separate, distinct, quiet cue for failure is allowed |
| Photosensitivity | No full-screen flashing; no more than three flashes per second and no large high-contrast flicker (follow WCAG 2.3.1). A static test checks that the timeline never exceeds the luminance change rate limit |
| Contrast and legibility | Text diagnostics use high contrast and a plain font, independent of theme assets |
| Screen readers | The splash is purely visual; failure diagnostics are text on the console, which is readable by console screen readers. Spoken boot feedback is out of scope for now and listed as an open question |
| Colour independence | State is never conveyed by colour alone; failed regions also change shape or pattern, and text accompanies them |

---

## 9. Test strategy

This follows ENGINEERING-PLAN.md: pure logic is test-first, infrastructure gets a gate before features, and the GPU/Plymouth layer is kept thin.

### 9.1 Design for testability

- **Pure cores, written test-first:**
  - the *timeline*: position in time to a set of render parameters (sphere radius, rotation, region brightness), and the audio parameters for the same instant;
  - the *readiness model*: event stream to milestone states and tier decisions;
  - the *tier selector*: probe results and command-line flags to a tier.
- These live in a small Rust crate with no GPU, clock or I/O dependency; time is injected (the `Clock` trait of ENGINEERING-PLAN 3.3). The Plymouth script and the compositor are thin adapters that only *apply* the computed parameters.
- Property tests (`proptest`): progress never decreases; any event sequence ends in either `Session` or `Text`, never a stuck state; the tier never upgrades within a boot; every failure event produces a text-mode instruction; luminance change per second stays under the photosensitivity limit; the timeline function is continuous at the hand-off position (the last Plymouth frame equals the first compositor frame within a tolerance).

### 9.2 Static layer (every pull request)

- `shellcheck` and `shfmt` on scripts, `bats-core` for script behaviour.
- Theme file checks: required keys present, asset sizes within the budget, no binary audio, asset checksums match the generator output.
- Config assertions: kernel command line contains the documented flags; no splash dependency pulls in a forbidden package; initramfs hook adds only the expected files.

### 9.3 QEMU boot tests (image changes and nightly)

All run headless against the built ISO, using a serial console plus QMP (`screendump`) for pixels:

| Test | Asserts |
|---|---|
| Splash happy path | `plymouthd` starts; at least N non-blank, changing screendumps before hand-off; `plymouth --ping` fails after session start (splash gone); the session unit is active; no failed units |
| Clean exit | The splash exits within a bounded time after the session is ready; no leftover `plymouthd` process; the last screendump is not a splash frame |
| Text fallback | With `xsphere.splash=off` and with a serial-only console, no splash is drawn and the boot reaches the same session or console state |
| Fault injection | A test-only kernel parameter makes a named unit fail (and another makes the compositor fail to start). Assert: the splash ends within the watchdog bound, the failure text appears on the console, the fallback session starts when applicable |
| Watchdog | Stall a milestone; assert text diagnostics appear at about 20 s |
| Reduced motion | `xsphere.motion=reduced` yields a static theme state (consecutive screendumps equal) |
| Esc key | A scripted `Esc` via QMP switches to text details |
| Budget | Compare boot time with splash on versus off and record the delta, plus initramfs and asset sizes. Size gates are hard; timing is a trend reported per run, hard-gated only on KVM-capable runners, because emulated timing is noisy |
| Frame golden (tolerance) | A downscaled screendump at fixed timeline positions compared with a stored reference using a perceptual tolerance, to catch broken themes without pixel-exact brittleness |

### 9.4 Manual checks (explicit, documented)

Visual and audio quality, flicker at the real-hardware hand-off, behaviour on real old GPUs and on a plain framebuffer. These cannot be fully automated and are recorded in a checklist per release, as ENGINEERING-PLAN section 7 prescribes for GPU code.

### 9.5 Clean Code and DevSecOps for this feature

- Small modules with one reason to change: `timeline`, `readiness`, `tier`, `theme-adapter`, `audio-synth`. No function above about 40 lines.
- Assets (frames, if any, and the audio) are generated at build time by a documented, deterministic script, so the output is reproducible and reviewable; no opaque binary blobs.
- The initramfs payload is minimal and static, runs with no network, parses no untrusted input at boot, and is covered by the image's checksums and signature.
- Every new dependency (crate or package) needs a justification line, as in the package lists.

---

## 10. What is genuinely new

An honest survey of the field, with the caveat that claims about other distributions are from general knowledge and should be re-verified before any public statement.

**What exists:** Plymouth themes (spinner, logo-with-progress, fade-in, custom `script` animations) on essentially all mainstream distributions; firmware-logo continuity (BGRT) on some; a splash that is a separate renderer from the desktop that follows it, with a visible mode change or blank frame between them; estimated or decorative progress; startup sounds that are recorded files, usually played by the desktop session after login rather than as part of the boot.

**What this design adds, and why it is different:**

1. **The splash is the desktop's own first frames.** The same sphere object, the same renderer for the final phase, and a recomputed, matched hand-off frame. The boot dissolves into the live desktop instead of being replaced by it.
2. **Progress as real, spatial data.** The sphere's regions map to real boot milestones and, later, to trust domains, so the boot visualises the system's own structure instead of a generic bar.
3. **One timeline for light and sound, with procedurally generated audio.** No sampled assets, reproducible, licence-clean, tiny, and impossible to drift out of sync.
4. **Failure designed in, and tested.** A fault is part of the visual language, always paired with text, and covered by fault-injection tests in CI. Splash screens are rarely tested at all.
5. **Explicit capability tiers with a monotonic downgrade rule.** Text, static, 2D, full, chosen by probes, so old hardware gets a smaller experience rather than a broken one.
6. **Boot experience as an engineered, budgeted component.** Hard budgets, property-tested logic, and a CI boot test that asserts a clean splash exit and a running session.

It is *not* new to have a short cinematic boot. The novelty is continuity, honesty and testability.

---

## 11. Security (high level only)

- The splash stack runs early and as root, so it is kept minimal, static and offline, and treats nothing from the network or user media as input.
- The initramfs and theme assets are part of what a boot-integrity scheme must cover; they must be reproducible and signed with the rest of the image.
- The splash must never be a place that can mislead the user about system state (for example by hiding a failure or faking a password prompt).
- Secure boot, measured boot and the threat model are specified in the private `xspherede-security` repository.

---

## 12. Milestones

Mapped to the distro milestones of DISTRO-DESIGN section 9. Each is done only when its tests are green.

| # | Milestone | Done when | Depends on |
|---|---|---|---|
| B0 | This design approved | The open questions in section 13 that block B1 are answered | none |
| B1 | Static brand theme | A minimal Plymouth theme (dark field, still sphere) ships in the live-build recipe; `quiet` boot; text fallback and `Esc` work; QEMU test asserts clean exit and session start; budgets recorded | M0 image |
| B2 | Animated 2D sequence | Timeline crate with unit and property tests; Ignite, Gather and loop animation in Plymouth; reduced-motion tier; frame-golden tests | B1 |
| B3 | Honest progress and failure path | Readiness model driven by real events; failure fracture plus text; watchdog; fault-injection tests | B2 |
| B4 | Compositor hand-off | `xspherede` renders the Resolve and Unfold phases; no-flicker hand-off on QEMU and real hardware; tier 3 and downgrade tests | M2 real compositor |
| B5 | Procedural audio | Audio synth module, muted-aware playback, tests for the generator output and the gating logic | B4, PipeWire in the image |
| B6 | Hardening and measurement | Budget measurements on real older hardware; photosensitivity test; manual checklist; password-prompt support | B4 |
| B7 | First-boot integration | The sequence flows into the first-boot flow inside the sphere | M4 |

Deliverable 2 of this effort (after approval of this document) is B1, optionally the start of B2.

---

## 13. Open questions

For the user, about the vision:

1. **The reference video.** What specifically should carry over: the pacing, the use of a single bright colour on dark, a transformation of one shape into another, the sound character (deep, bright, metallic)? Which three adjectives describe it best?
2. **Duration.** Is a short sequence (about 2 to 3 s of authored motion that overlaps the boot) right, or should a longer, fixed-length intro be possible as an option, understanding that it would delay the session?
3. **Colour identity.** Which palette is the sphere's: the existing code-rain green, or something else?
4. **Audio default.** Proposed: off on the live image, with a first-boot choice to enable it. Acceptable, or should it be on by default when the system is not muted?

For engineering:

5. Plymouth then compositor (option B) versus a custom splash daemon (option C): confirm B for now.
6. Where does the persisted reduced-motion and tier setting live so the initramfs can read it, given the live image is stateless? (Proposal: command line on the live image, a file embedded in the initramfs by a hook on an installed system.)
7. How is the timeline description shared between the Plymouth script (limited language) and the compositor, and which crate owns it (the `xsphereos` repository or `xspherede`)?
8. Does the readiness helper after the root switch subscribe to `systemd` over D-Bus, or is a simpler unit-ordering-based signal enough?
9. Spoken or tonal diagnostics for blind users: in scope, or a later milestone?
10. Is the KVM-capable runner available for hard timing gates, or are timing measurements trend-only (ENGINEERING-PLAN open question 4)?
11. Whether the bootloader menu is visible by default on the live ISO (it matters for the "no text before the splash" goal, and for BIOS boot).
