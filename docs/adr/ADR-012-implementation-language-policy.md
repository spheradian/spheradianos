# ADR-012: Implementation Language Policy (Rust for What Ships, Scripts for What Builds)

**Date:** 2026-11-23  
**Status:** Proposed  
**Author:** Senior Software Architect  
**Approver:** Fábio Mendes (`mendsec`)  
**Confidence:** High  
**Impact:** Medium  
**Reversibility:** Easy  

## 1. Executive Summary

Python is the most common language in this repository, which raised a question: should the project move to Rust, as System76 did? We measured what this repository actually contains (§2). We decided on a rule that depends on **where code runs, not which repository it lives in**:

- **Code that ships in the image and runs on the user's machine is written in Rust.** Exceptions are formats that a host program defines: systemd units, initramfs hooks, Plymouth scripts, and configuration files.
- **Code that runs on the developer's machine or in CI** (image builds, asset generators, QEMU boot tests, audits) stays in POSIX shell and stdlib-only Python. It is **not** rewritten in Rust.
- **Logic shared between the two moves into a Rust crate** when a shipped component first needs it. The boot timeline is the first case (B4).

This matches System76: COSMIC and the system tools are in Rust, while `pop-os/iso` uses Make and shell.

## 2. Context and Problem

Measured on `main` at `a4c3aa0`:

| Code | Lines | Language | Runs where | Ships in the image? |
|---|---|---|---|---|
| `scripts/*.py` (boot test, asset generator, preview renderer, timeline, package audit) | ~1,830 | Python | Developer machine, CI | No |
| `tests/*.py` | ~1,120 | Python | Developer machine, CI | No |
| `scripts/*.sh`, `auto/*` | ~140 | POSIX shell | Developer machine, CI | No |
| `usr/lib/spheradianos/spheradian-session`, `boot-watch`, `test-journal` | small | POSIX shell | **Target system** | Yes |
| initramfs hooks, `profile.d` script | small | POSIX shell | **Target system** (initramfs, login) | Yes |
| Plymouth theme script | small | Plymouth script | **Target system** | Yes |
| `spheradian` compositor (other repository) | ~3,400 | **Rust** | **Target system** | Yes (built from a pinned SHA, ADR-007) |

The only compiled program in the image is already Rust. **No Python ships in the image.** The Python here is tooling, the same role Make and shell play in `pop-os/iso`. Rewriting it would cost several weeks, and the tests that protect the boot contract would have to be rewritten too. The product would not improve.

The real gap is different: several shipped components are planned (session manager, installer, first boot, settings, `audio-synth`, sandbox), and **no document says which language they use**. Shell scripts on the target system are growing too. `boot-watch` already implements a watchdog and diagnostics.

`BOOT-EXPERIENCE.md` already expects this split. The timeline is "a tested Python module rather than a Rust crate, because its only consumer today is the theme generator … it moves to Rust when the compositor needs it (B4, open question 7)."

## 3. Scope

- **In scope:** every program, script, and library in `spheradian/spheradianos` and the components it ships (ADR-011); test and tooling code.
- **Out of scope:** the content of configuration files; upstream Debian packages; the private `security` repository; website and demo code (`spheradian-files` browser demo, Pages).

## 4. Options Considered

- **Option A: Rewrite everything in Rust**, including build and test tooling. One language, but the most expensive option. `live-build` and QEMU are driven through shell anyway, and the Rust boot test would still mostly spawn processes. Rejected.
- **Option B: Leave it implicit.** No cost now. Planned components might be started in shell or Python and need a rewrite later, and the "is this a remaster" question stays open. Rejected.
- **Option C (Chosen): Choose the language by where the code runs.** Rust on the target. Shell and Python on the host. Shared logic moves to Rust when a shipped component needs it.

## 5. Decision

### 5.1 Code on the target system: Rust

Any new program that is installed in the image and runs on the user's machine is written in Rust and follows the desktop's rules: `unsafe` forbidden, `--locked` builds, `cargo audit` and `cargo deny`, typed errors, no `unwrap` outside tests (`ENGINEERING-PLAN.md` §4.1). New C, C++, Python, Go, or JavaScript on the target is not allowed. Tracing the dependencies that crates pull in is part of the per-dependency justification rule.

**Allowed exceptions**, each limited to the format the host program requires:

| Exception | Why | Limit |
|---|---|---|
| systemd units, slices, drop-ins, `zram-generator.conf`, APT and Plymouth config | Declarative formats read by the host program | No embedded scripts beyond one `ExecStart` line |
| initramfs hooks and `init-top` scripts | `initramfs-tools` runs them under BusyBox `sh` before any Rust binary is available | POSIX `sh`, `shellcheck`-clean, no logic beyond copying files and parsing the kernel command line |
| Plymouth theme script | The only language Plymouth's script plugin runs | Only applies parameters that the generator computed (`BOOT-EXPERIENCE.md`, "thin adapters") |
| Short shell glue | Launching a binary with a fallback, under about 30 lines with no loops over input | Anything larger, or anything that parses data, becomes Rust |
| Test-only units and scripts (`*-test-*`) | Enabled only by kernel switches in the QEMU test | Must never be activated in a release image (checked by `tests/`) |

### 5.2 Code on the host and in CI: shell and Python

- Image build entry points stay in POSIX `sh` (`scripts/*.sh`, `auto/*`).
- Generators, boot tests, and audits stay in Python 3 using only the standard library, linted by `ruff` (including Bandit `S` rules), and covered by `unittest`.
- Rust may be used for host tooling only when it reuses a crate that ships on the target (§5.3).

### 5.3 Shared logic: a Rust crate, introduced when needed

When a shipped component needs logic that currently lives in Python host tooling, that logic moves to a Rust crate. The Python version is then removed or reduced to a thin wrapper that calls the crate's CLI. There must never be two implementations of the same logic.

First case: **the boot timeline.** At B4 the compositor must continue the Ignite → Gather → Wake timeline into Resolve and Unfold. The timeline math in `scripts/boot_timeline.py` then moves to a `spheradian-boot-timeline` crate. **Answer to `BOOT-EXPERIENCE.md` open question 7:** the crate lives in the desktop organization next to the compositor, because the compositor is its main consumer. This repository's asset generator calls the crate's CLI and pins it by version.

### 5.4 Migration of existing target code

| Component | Today | Target | When |
|---|---|---|---|
| `spheradian-session` (session launcher with fallback) | `sh` | `spheradian-session` (Rust): starts the compositor, supervises it, falls back, persists the render-level downgrade (ADR-009) | M2, when `cage` is replaced by the native compositor |
| `boot-watch` (end the splash, watchdog, failure report) | `sh` | Logic moves into `spheradian-session` or a small Rust binary; the systemd unit stays | B6 / M4, when the boot report is shown in the session |
| `test-journal` | `sh` | Unchanged (test only) | — |
| initramfs hooks, `profile.d` script, Plymouth script | `sh`, Plymouth script | Unchanged (exceptions in §5.1) | — |
| `audio-synth` (B5) | not started | Rust | M3 |
| Installer and first boot (M4, B7) | not started | Rust: installer engine as a library with a thin UI on Spheradian, following `distinst` | M4 |
| Settings, launcher | not started | Rust, inside or next to the compositor | M3 |
| Per-domain sandbox launcher (M5) | not started | Rust | M5 |
| System-layer tools: image update and rollback client, filesystem layout and memory policy services (ADR-011, ADR-013) | not started | Rust. Use upstream tools (for example OSTree, `bootc`, `systemd-sysupdate`) where they fit, and write Rust only for the parts the project owns | M4 |
| `boot_timeline.py` | Python, host | `spheradian-boot-timeline` crate (§5.3) | B4 |
| Other `scripts/*.py`, `tests/*.py` | Python, host | Unchanged | — |

### 5.5 Enforcement (added when this ADR is accepted)

- A static test in `tests/test_distro_config.py` fails if `config/includes.chroot/` contains a file whose shebang names an interpreter other than `sh` (no `python`, `bash`, `perl`, `node`). It also fails if a shell script there that is not an initramfs hook exceeds the glue limit, unless the file is listed in an explicit allowlist that links the migration row above.
- PR review checks that any new component on the target is a Rust crate.

## 6. Consequences and Trade-offs

- **Pros:**
  - A clear, checkable rule.
  - No rewrite cost for tooling that already works and is tested.
  - Everything that runs on the user's machine gets memory safety and the desktop's lint and audit gates.
  - Answers `BOOT-EXPERIENCE.md` open question 7.
  - Matches the model in ADR-011.
- **Cons:**
  - Two languages remain in this repository.
  - Building SpheradianOS requires a Rust toolchain until M4 packaging replaces source builds (already true since ADR-007).
  - Moving the boot timeline to Rust adds a dependency between repositories that must be pinned by version.

## 7. Security and Compliance

- Rust on the target removes whole classes of memory-safety bugs from the code the project writes. It does not cover upstream C code inherited from Debian. Hardening of that code is tracked in `spheradian/security`.
- Host tooling never runs on the target and parses only files from this repository. Its risk is supply-chain risk, which is why it stays stdlib-only Python.

## 8. Related

- [ADR-011](ADR-011-organization-and-product-structure.md): organization and product structure
- [ADR-005](ADR-005-boot-procedural-audio.md): `audio-synth` (B5)
- [ADR-007](ADR-007-m1-kiosk-prototype-session.md): pinned desktop build
- [ADR-009](ADR-009-gpu-render-levels-and-warmup.md): persisted render-level downgrade, owned by the session manager
- [docs/ENGINEERING-PLAN.md](../ENGINEERING-PLAN.md) §4: Rust and shell conventions
- [docs/BOOT-EXPERIENCE.md](../BOOT-EXPERIENCE.md) §13, open question 7
