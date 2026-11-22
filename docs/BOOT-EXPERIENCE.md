# XSphereOS: Boot Experience

Status: **draft for review, pre-implementation**. Nothing described here exists yet. This document builds on [DISTRO-DESIGN.md](DISTRO-DESIGN.md) and follows the rules in [ENGINEERING-PLAN.md](ENGINEERING-PLAN.md).

> Scope note: boot-security design (secure boot, measured boot, threat models) lives in the private `xspherede-security` repository. This document mentions it only at a high level, in section 11.

> Originality note: this is an original work inspired by a *feeling*: a short, cinematic, sound-and-light-driven moment at power-on that makes the machine feel alive, as in the startup intro of the original Xbox console. It uses **no** Microsoft or Xbox assets, logo, sounds, shapes, colours or trade dress, and it must not be made to resemble them. Every visual and audio element is generated from XSphereOS's own sphere motif and its own code.

> Reference note: the reference video was analysed visually, frame by frame, and the findings are in Appendix A. Its audio was not analysed. A second reference video was later analysed for sound by **spectral measurement** (level and frequency content over time, not by listening); the findings are in Appendix B. Both appendices extract *principles*; neither is a shot list or a score to reproduce.

---

## 1. Vision

XSphereDE is a sphere: windows live on its surface, trust domains are regions of it, and the Mini-Globe shows it from outside. The boot experience is the **first appearance of that same sphere**, and the desktop is where it ends up. The boot is not an intro video placed in front of the desktop; it is the desktop assembling itself.

The sequence, in one sentence: *a seed of light appears in the dark, restless and alive; its own glow reveals the lattice of the sphere around it, region by region, as the system genuinely comes up; when the system is ready the seed releases, its shell sweeps past the viewer, and the viewer is standing inside the lit sphere, which is the desktop*.

Design principles:

1. **Continuity.** One visual identity from the first pixel after the kernel to the first interactive frame. The last frame of the splash and the first frame of the desktop are the same image.
2. **Honesty.** The animation reflects real boot progress. It never fakes work and never delays the system to finish a show.
3. **Light and sound as one timeline.** Visual and audio events come from one deterministic timeline, so they cannot drift apart.
4. **Failure is a first-class state.** A fault is shown in the same visual language *and* with readable text. The splash can never hide an error.
5. **Cheap.** The boot experience must not be a reason a machine boots slower. It degrades down to plain text on hardware that cannot afford it.
6. **The light is the subject.** The seed is the only light source in the scene. Everything else is visible only because the seed illuminates it. Nothing is lit "from nowhere" (Appendix A, principle 1).
7. **What the light reveals is real.** The structure that emerges from the dark is not a set built for the intro: it is the actual geometry of the desktop sphere (its lattice, its trust-domain regions) seen from where the user will stand. Nothing shown during boot is thrown away afterwards.
8. **The climax is earned.** Tension rises with real boot activity and the release fires on the real "session ready" event, never on a fixed clock.
9. **Stillness after release.** The sequence ends in calm: a quiet, fully lit desktop, with no further motion demanded of the viewer.

Target feel (not a spec of frames): calm, confident, about two to three seconds of *authored* motion that overlaps the real boot rather than extending it; a bright, organic sound that rises with the seed and ends on a pleasant, settled note as the sphere becomes the desktop.

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
| Ignite | Plymouth, initramfs | True black. A barely visible speck appears at the centre and slowly gains strength | A single high, quiet glint as the speck appears, over a barely audible pad (if enabled) | Matches the bootloader background so there is no flash |
| Gather | Plymouth | The speck grows into a small, soft, *living* seed of light: its outline is never still, it breathes and ripples. Nothing else is visible yet | A faint, slow breath of air and two soft low notes as the seed gains body | Loops indefinitely if the boot is slow; never speeds up artificially |
| Wake | Plymouth, `systemd` | The seed's glow starts to reach its surroundings: arcs of the sphere's lattice emerge from the dark, lit only by the seed. Each region becomes visible when its real milestone completes (root mounted, devices settled, session services ready). The seed grows more agitated as more of the system is in motion | One soft bell per region that wakes, climbing the scale; the pad swells | Section 4. Agitation is driven by real activity, bounded by the photosensitivity limits of section 8 |
| Resolve | Hand-off | Session ready: the seed draws in, brightens toward a hot core (the one moment the palette leaves its base hue), and the compositor takes over on that frame | A short, quickening run of soft bell notes climbs as the seed draws in (if enabled) | Section 5. A bounded bloom, not a full-screen white flash |
| Unfold | Compositor | The seed releases: a shell of light expands outward and passes *through the viewer*. Where it passes, the lattice stays lit and becomes the desktop surface. The viewer is now inside the sphere. Motion settles to stillness; the Mini-Globe fades in; a small wordmark may appear near a pole and fade | The run lands on an original, consonant chord with a slow attack that decays gently into silence | About 0.8 to 1.2 s; input is already live; no hold on a logo |

Three properties make each boot its own while staying testable:

- **Driven, not canned.** The seed's turbulence is a function of real boot activity (milestone events, unit start rate), so a busy boot looks different from a quiet one.
- **A per-boot signature.** A non-secret random value (for example the kernel's per-boot identifier) seeds small variations in the seed's motion, so no two boots are identical. In tests the seed is fixed, so frames are reproducible.
- **Colour as information.** The seed starts near-neutral; each region of the lattice takes its trust-domain colour as it wakes, so the palette is assembled by the boot rather than applied to it. (Final palette is an open question, section 13.)

The sound is **synthesised procedurally** from a small, deterministic description (a few oscillators, an envelope, a filter sweep), not recorded or sampled. This keeps the repository free of binary audio, makes the output reproducible and licence-clean, and removes any chance of resembling an existing jingle. It also lets the same timeline description drive both light and sound.

Sound direction (from the user's description of the feeling wanted, in words only; the reference audio was not analysed and is not to be imitated): **bright, organic, rising, with a pleasant ending**. Translated into synthesis terms:

- *Bright*: clear, glassy bell tones in the middle and upper register, not a bass-heavy drone.
- *Organic*: slightly irregular note timing and a quiet, slowly breathing pad underneath; never a perfectly steady machine tone.
- *Rising*: one note per region that wakes, climbing a pentatonic scale, so the ascent is the boot's own progress made audible; density increases into Resolve.
- *Pleasant ending*: resolution to a consonant chord with a soft attack and a gentle decay; no hard stop, no dissonance, no sudden loudness.

Approved by ear (concept video, `scripts/render-boot-preview.py`): sine-based bells over a pad, a light reverb, and a release chord. Later additions, also approved by ear: sound from the first speck of light (after one second of deliberate silence on black) instead of starting at Wake, and three impact layers from Appendix B (a breath-like riser under the Resolve run, a round low bloom on the release doubled an octave up, a brief shimmer of air). A first attempt, a stack of harmonics gliding upward in pitch, was rejected as unpleasant; **avoid buzzy harmonic stacks and continuous pitch glides**. On a real boot, notes can only sound once the audio server is up, so the per-region notes of early milestones may be silent; how to handle that is an open point for milestone B5.

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
| Theme assets in the image | at most 64 KiB, no binary audio (section 6.4) | static test |
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

### 6.4 Console-grade resource discipline

A PC has memory and storage to spare, and that is exactly why software for it tends to be careless. The boot experience is held to the standard of a console boot ROM instead. The model is the original Xbox boot sound as documented by its author, Brian Schmidt ("Creating the Original Xbox Boot Sound", GameSoundCon, 2021): the whole boot ROM was 256 KiB, about 25 KiB of it was left for audio (barely half a second of 8-bit mono), and the result is an eight-second sequence.

How that was done, and what each technique means here:

| Their constraint or technique | What XSphereOS takes from it |
|---|---|
| No room for a recording, so the sound is *generated*: a text note list drives a synthesizer | The boot sound is a score plus a tiny synth, never an audio file. A 12.5 s stereo recording would be about 2.2 MiB; the score is a few hundred bytes |
| Waveforms made by code (sine, sawtooth, noise) cost almost no storage and are full fidelity | All timbres come from code. No samples at all |
| A filter that opens puts more energy into the sound without more data | Motion comes from parameters (filter, envelope, pitch), not from more material |
| Three tiny 6 kHz, 8-bit samples, only the *attacks*; sustained sines at the same pitch extend them | Spend bytes only where the ear needs them. Our bells are already attack-plus-sine and need no sample |
| One sample reversed in memory becomes a fourth sound | Derive variants by transformation instead of storing them |
| Full-fidelity noise layered over a poor sample hides its flaws | Layering is a way to *save* resources, not only to add richness |
| Nine tracks in total | A fixed, small voice budget |
| The animation exists to hide boot time, and plays while the system boots | Already principle 2 and section 6.2: never delay the boot |
| Timing taken frame by frame from the finished visuals | Stricter here: light and sound share one timeline |
| Peak level deliberately modest (about -18 dBFS intended, about -12 dBFS shipped), because the boot sound works as a volume reference | Peak capped at -12 dBFS |
| Stereo only: negotiating surround would have muted the first seconds | Never wait for an audio device to negotiate. If the default output is not ready, the sound is skipped |
| A bug in the boot sound code crashed about one boot in a thousand until it was fixed | The sound must not be able to break the boot: isolated from the critical path, and soak-tested over many boots |

**Budgets.** These are hard limits enforced by tests, not targets.

| Item | Budget | Now (measured 2026-11-15) |
|---|---|---|
| Everything this feature adds to the image (theme, score, synth) | 256 KiB, the size of that console's entire boot ROM | 12 KiB (both themes; no sound code yet) |
| Theme files | 64 KiB | 12 KiB for the animated theme and its still variant. The B1 still image was 106 KiB, then 51 KiB with a palette; B2 replaced it with two glow images (3.4 KiB and 0.3 KiB) placed by arithmetic |
| Bootloader menu art (ISOLINUX background, GRUB theme and its ASCII font) | 64 KiB, static test | 60 KiB: GRUB background 55 KiB, ISOLINUX black background 1 KiB, theme 1 KiB, font 3 KiB (made at build time from Debian's `unicode.pf2`). Measured cost of the themed menu on a normal UEFI boot in QEMU: within noise (median 2.72 s to the first splash frame against 2.66 s without it) |
| Boot sound score (note list and parameters) | 4 KiB, no samples | not built; the concept score is estimated at under 1 KiB |
| Boot sound synth, compiled | 64 KiB | not built |
| Synth memory while playing | 256 KiB | not built |
| Synth CPU | 1% of one core on the slowest supported machine, generated in real time | not built |
| Simultaneous voices | 32 | concept: not yet counted |
| Splash-related files in the initramfs, uncompressed | 1.5 MiB | 2.58 MiB in the last build, of which 1.10 MiB was two fonts the theme never uses. A trim hook now removes them: 1.46 MiB in the following build, with the boot test still passing |

Rules that follow:

1. **Generate, do not store.** If code can produce it, it is not shipped as data.
2. **Measure before and after.** Every budget row has a number from a real build, and a change that raises one must say why.
3. **Nothing unused ships.** Anything a packaged hook pulls in that the theme does not use is removed.
4. **A budget is exceeded by cutting the effect, never by raising the budget** (already the rule of section 6.1).

Findings outside this feature, recorded for the distribution as a whole: the initramfs is 72.7 MiB uncompressed (47 MiB compressed with gzip, since `zstd` is not in the image), of which 37 MiB is kernel modules. That is where the large savings are, and it is a distribution-level decision, not a boot-experience one.

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

7. **The set is the product.** In the reference, the environment revealed by the light exists only for the intro and is discarded by a cut to a logo. Here the revealed structure is the desktop itself, and there is no cut: the user ends up standing inside what they watched being lit.
8. **A boot that is alive rather than replayed.** Motion driven by real system activity plus a per-boot signature means the sequence is never the same video twice, while a fixed seed keeps it deterministic under test.
9. **No logo hold.** The reference spends about a third of its length on a static brand lock-up. Here that time is given back to the user: the "hold" is a usable desktop.

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

Status of B3 (2026-11-15): implemented and booted. `scripts/boot-test.py` passes in QEMU in four modes: normal, reduced motion, an injected failed unit (`--fault fail`) and an injected stall (`--fault stall`).

- *Honest progress.* systemd tells Plymouth the name of each service that finishes starting; six of them are milestones, and each wakes one 60 degree slice of the lattice in its own colour (`MILESTONES` in `scripts/boot_timeline.py`). Seen in captures: regions wake during a normal boot, and all six are awake in the stalled boot. The reduced-motion frame changes colour without animating.
- *Failure path.* `/usr/lib/xsphereos/boot-watch` runs only while the splash is up and checks once a second. A failed unit, or 20 s without a change in systemd's job queue, ends the splash and prints the cause on the console; the same text is kept in `/run/xsphereos/boot-report` and repeated at each login. In the stall test the console showed the jobs still being waited for. In the failure test the unit failed in the splash's last moment, so the report appeared on the console about a second after the login prompt.
- *Found by looking at captures, not by the test.* The first version missed a unit that failed between two checks just as the splash left; the boot test passed anyway because it only checked that a console appeared. The watch now checks once more after the splash is gone, and the test asserts that the report file exists after an injected failure and is absent after a healthy boot.
- *Deviations.* No "fracture" visual: the text takes over the screen, so there is no time for it; only the text contract is implemented. Failures are detected by polling once a second rather than by subscription, so the report can lag by up to a second. The watchdog covers the systemd phase only; a stall in the initramfs is handled by initramfs-tools' own timeout and panic path, which has not been tested here.

Status of B2 (2026-11-15): implemented and booted. `scripts/boot-test.py` passes in QEMU in both modes: the splash animates by default and is a still frame with `xsphere.motion=reduced`; in both it exits to a readable console and the session starts. Time from the boot menu to the console, median of five KVM runs each: 7.03 s animated, 7.35 s still, 7.03 s with the splash disabled. The spread between runs (about 0.4 s) is larger than any difference, so the animation's cost is below what this method can resolve; the 150 ms budget is not yet proven and needs a finer measurement. A text-mode cursor that showed while the kernel loaded under BIOS was fixed on 2026-11-22 (ADR-002 amendment); the firmware's text and the ISOLINUX banner still flash for a fraction of a second at power-on. The theme is now animated (Ignite, Gather, endless loop) with a reduced-motion variant selected by `xsphere.motion=reduced`. Deviations from the row above: the timeline is a tested Python module (`scripts/boot_timeline.py`) rather than a Rust crate, because its only consumer today is the theme generator and this repository has no Rust toolchain; it moves to Rust when the compositor needs it (B4, open question 7). The lattice is drawn as dots, not lines, because Plymouth's script plugin can only place images; this keeps the whole theme at about 12 KiB with no stored frames. Frame-golden tests are replaced by a motion check in `scripts/boot-test.py` (frames differ when animated, are identical when reduced), since QEMU timing is not deterministic enough for golden frames.

Status of B1 (2026-11-15): implemented. The `xsphere` Plymouth theme ships in the recipe and `scripts/boot-test.py` passes against a built ISO in QEMU (BIOS boot, KVM): splash shown, clean exit to a readable console, session starts. Not yet done from the B1 row: recording the timing and initramfs budgets, an automated `Esc` check, and a text-fallback boot test. The bootloader menu still shows live-build's default artwork.

---

## 13. Open questions

For the user, about the vision:

1. **The reference video.** The visual analysis is in Appendix A. Sound character is answered (bright, organic, rising, pleasant ending; see section 3). Still needed from the user: is the reading of the visual principles right?
2. **Duration.** Is a short sequence (about 2 to 3 s of authored motion that overlaps the boot) right, or should a longer, fixed-length intro be possible as an option, understanding that it would delay the session?
3. **Colour identity.** Which palette is the sphere's? Recommendation: *not* a single glowing green on black, because that is the reference's signature look and XSphereDE's code-rain green would land very close to it. Proposed instead: a near-neutral seed with the trust-domain colours emerging region by region.
4. **Audio default.** Proposed: off on the live image, with a first-boot choice to enable it. Acceptable, or should it be on by default when the system is not muted?

For engineering:

5. Plymouth then compositor (option B) versus a custom splash daemon (option C): confirm B for now.
6. Where does the persisted reduced-motion and tier setting live so the initramfs can read it, given the live image is stateless? (Proposal: command line on the live image, a file embedded in the initramfs by a hook on an installed system.)
7. How is the timeline description shared between the Plymouth script (limited language) and the compositor, and which crate owns it (the `xsphereos` repository or `xspherede`)?
8. Does the readiness helper after the root switch subscribe to `systemd` over D-Bus, or is a simpler unit-ordering-based signal enough?
9. Spoken or tonal diagnostics for blind users: in scope, or a later milestone?
10. Is the KVM-capable runner available for hard timing gates, or are timing measurements trend-only (ENGINEERING-PLAN open question 4)?
11. Whether the bootloader menu is visible by default on the live ISO (it matters for the "no text before the splash" goal, and for BIOS boot).

---

## Appendix A. Reference analysis

Source: the user's reference video, a 10.5 s capture of the original Xbox console's startup sequence. It was examined visually at about twenty sampled positions. **The audio was not heard**, so this appendix says nothing about sound. The description below exists only to extract design principles; none of its shapes, colours, marks or composition may be reproduced.

### A.1 What happens on screen

| Time (approx.) | Observation |
|---|---|
| 0.0 to 1.0 s | Black. Nothing |
| 1.3 s | A tiny, dim speck of coloured light at the centre of a black frame |
| 1.5 to 2.1 s | The speck grows into a small, soft glowing mass. Still nothing else visible |
| 2.6 to 3.0 s | The mass is bright and roughly round, with an unsteady outline. A faint hint of surrounding structure appears, lit by it |
| 3.4 to 4.2 s | The mass deforms continuously into irregular lobes, like something fluid or alive. A mechanical enclosure around it (rings, ribbed conduits, circular fixtures above and below) is now legible, entirely in the same hue and entirely lit by the mass |
| 4.6 to 5.5 s | The camera moves in and tilts; the enclosure brightens; the mass gets hotter (toward white) and more agitated |
| 6.0 s | The core turns white-hot with a warm tint, the only departure from the single hue in the whole sequence, and contracts |
| 6.5 s | A burst of light overexposes the whole frame; the brand emblem's silhouette is visible inside the burst |
| 7.0 s | Black background again, the emblem now crisp and solid; the wordmark is still arriving from below at large scale |
| 7.6 to 10.5 s | Static brand lock-up on black, held for about three seconds; a small company line fades in near the end |

Structure: about 1 s of darkness, about 5.5 s of action, about 3 s of hold.

### A.2 Principles extracted

1. **The light source is the protagonist, and the lighting is diegetic.** The environment is never lit independently. We learn where we are only because the thing we are watching glows. This is the single strongest reason the sequence feels like one coherent event rather than an animation over a background.
2. **Organic inside mechanical.** The energy is fluid, irregular and never repeats a pose; its surroundings are rigid and symmetrical. The contrast reads as "something alive is being woken inside a machine".
3. **One hue, one exception.** A strict monochrome palette throughout, broken exactly once, at the climax, by a hot white core. The restraint is what gives the climax its weight.
4. **A single rising curve, then release.** Size, brightness, agitation and camera motion all increase together, with no plateau, until one burst; then complete stillness. Tension and release, in under six seconds.
5. **The mark is a consequence, not an overlay.** The emblem appears *out of* the burst, as if the energy became it. The brand is the result of the event.
6. **It starts from nothing.** A full second of true black and a nearly invisible first speck. The quiet opening makes the ending feel large.
7. **Depth and a moving camera.** It reads as a place, not a flat graphic, because the camera travels through it.
8. **A long, calm hold.** Roughly a third of the running time is a static frame, letting the moment land.
9. **Fixed length, canned content.** The sequence appears to be the same every time and does not reflect what the machine is doing.

### A.3 How XSphereOS uses each principle, and where it goes further

| Principle | Kept | Changed or surpassed |
|---|---|---|
| 1. Diegetic light | Yes, as vision principle 6 | What the light reveals is the real desktop geometry, not a set (vision principle 7) |
| 2. Organic inside structure | Yes: a living seed inside the sphere's regular lattice | The seed's restlessness is driven by real boot activity and a per-boot signature, so it is alive in fact, not by animation |
| 3. One hue, one exception | The discipline is kept: a restrained base and a single hot moment at Resolve | A different palette entirely; colour arrives per region as information (trust domains) |
| 4. Rising curve and release | Yes | The curve is elastic and the release is triggered by the real "session ready" event (vision principle 8). On a slow boot the tension holds; it never fakes a climax |
| 5. Mark as consequence | Yes, in spirit | The consequence of the release is not a logo but the desktop itself. An optional small wordmark is secondary and transient |
| 6. Start from nothing | Yes: true black matched to the bootloader background, then a faint speck | Also solves a technical problem: dark first frames hide driver and mode hand-offs |
| 7. Depth and camera | Yes | The reference's camera pushes *toward* the energy and then cuts away. Ours lets the released shell pass through the viewer, ending *inside* the lit sphere with no cut |
| 8. Calm hold | The stillness is kept | The hold is a live, usable desktop instead of three seconds of logo |
| 9. Fixed, canned | Rejected | Elastic timing, honest progress, skippable, and tiered for weak hardware |

Constraints the reference did not have and this design does: it must never delay or hide the system (sections 6 and 7); it replaces the full-frame white burst with a bounded bloom for photosensitivity and offers a reduced-motion variant (section 8); and every stage is covered by automated tests (section 9).

### A.4 What must not be carried over

A glowing green mass on black, an X-shaped emblem or any mark emerging from a burst in that arrangement, the mechanical chamber imagery, the wordmark style, and any element of the sound. The palette recommendation in section 13 exists to keep clear distance from the reference's look.

---

## Appendix B. Reference sound analysis

Source: a second reference video from the user, a capture of the original Xbox console booting and its menu being navigated. Method: the audio was routed through a spectrum analyser while the video played (4096-point FFT at 48 kHz, one reading every 50 ms), recording level, spectral centroid, energy in five bands and the strongest peaks. **This is measurement, not listening**: it describes loudness and frequency content accurately, but says nothing certain about how the sound *feels*. Only the first 71 s were analysed (boot, menu ambience, first navigation sounds); the rest of the video, including a section of menu music, was not. None of these sounds, pitches or timbres may be reproduced; the appendix exists to extract principles.

### B.1 The boot sound (about 8 s)

| Time in video | Measured | Reading |
|---|---|---|
| before 4.15 s | Digital silence (below -65 dBFS) | Nothing before the hit |
| 4.25 s | From silence to about -9 dBFS RMS in under 100 ms; almost all energy below 80 Hz (strongest peak near 59 Hz); centroid 54 Hz | A sudden, deep sub-bass impact |
| 4.4 to 5.0 s | Centroid climbs 60 to 700 Hz; strongest peaks step upward from about 100 Hz to above 1 kHz | A fast upward sweep growing out of the impact |
| 5.05 s | Level back to -11 dBFS; the 4 to 12 kHz band jumps by almost 30 dB | A second, broadband layer enters (air or noise) |
| 5.5 to 9.0 s | Level almost flat at -11 to -12 dBFS; centroid 100 to 250 Hz; many low peaks (35 to 300 Hz) that keep shifting and are not harmonically related | A dense, restless low texture, held at constant loudness |
| 9.0 to 10.3 s | Centroid rises 240 to nearly 1000 Hz; high band up about 15 dB; level unchanged | The climax is a rise in *brightness*, not in volume |
| 10.4 to 11.6 s | Level falls to about -20 dBFS; centroid falls back under 200 Hz | Release and fall |
| 11.65 to 12.05 s | Two low hits (near 150 Hz, then near 105 Hz, the second back at -13 dBFS) with a faint tone near 1.8 kHz | A closing punctuation |
| 12.15 s | Silence within about 150 ms | A clean, abrupt end |

### B.2 The menu ambience and navigation sounds

- **A continuous very low drone** (strongest peak near 35 Hz in every reading) sits under everything at about -15 to -17 dBFS.
- **Recurring textured events** roughly every 1.0 to 1.25 s, not on a strict grid, with mid-range content and brief high-frequency bursts.
- **Navigation sounds are almost pure mid-range tones**: about half a second long, at two pitches roughly a third apart, with essentially no energy above 1 kHz, and clearly louder than the bed.
- **Transitions use noise sweeps**: short broadband bursts whose centroid rises quickly from a few hundred Hz to several kHz.

### B.3 Principles for impact

1. **Silence first, then an instant onset.** The hit lands from nothing in under a tenth of a second. Contrast, not loudness, creates impact.
2. **Weight comes from the bottom.** The foundation is sub-bass. (Small speakers cannot reproduce it, so a design relying on it needs a layer an octave or two higher that carries the same gesture.)
3. **Layer distinct roles.** A low hit, a rising sweep, a noisy "air" layer and a tonal ending, each entering at its own moment.
4. **Move the spectrum, hold the level.** Loudness stays almost constant; the drama is the brightness opening up and closing again.
5. **Keep it restless.** Shifting, non-harmonic low partials read as something alive rather than a steady machine tone.
6. **Peak with the picture.** The brightest moment is placed on the visual climax.
7. **End with punctuation and a clean stop.** A short low figure, then silence, gives finality.
8. **One sonic world.** The boot sound and the menu ambience share the same low register, so the boot flows into the environment.
9. **Interface tones stay soft.** Pure, mid-range, short, a consonant interval apart: informative without fatigue.

### B.4 Using this in XSphereOS

The approved sound (section 3) is deliberately gentle: bells, a pad and a chord. These principles can add impact *around* it without changing its character:

| Principle | Proposal for XSphereOS |
|---|---|
| 1, 6 | Keep the silence before the first note; place the strongest moment exactly on the Unfold release |
| 2 | A soft, round low "bloom" under the release chord, with a doubling an octave up so it survives small speakers; never a harsh thump |
| 3 | During Resolve, add a short breath-like rising sweep under the bell run; at release, a brief shimmer of air |
| 4 | Let brightness, not volume, carry the build; respect the loudness cap of section 8 |
| 5 | Already present: irregular bell timing and the breathing pad |
| 7 | Keep our own ending: a gentle decay into silence, not an abrupt cut. This is a deliberate difference from the reference |
| 8 | The pad's register can continue as a very quiet desktop ambience, if ambience is ever wanted (open question) |
| 9 | Reuse the bell timbre and the pentatonic scale for future interface sounds, so boot and desktop sound like one system |

Constraints the reference did not have still apply: sound is off unless enabled, capped in level, skipped when muted, and never delays the session (section 8). A sudden loud low hit at power-on is exactly what those rules exist to prevent, so "impact" here means clarity and timing, not loudness.
