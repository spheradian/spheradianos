# ADR-017: A Command Layer for Spheradian Built on the `brush` Crates (Depend, Do Not Fork)

**Date:** 2026-11-28  
**Status:** Proposed  
**Author:** Senior Software Architect  
**Approver:** Fábio Mendes (`mendsec`)  
**Confidence:** Medium  
**Impact:** Medium  
**Reversibility:** Easy (before M3); Medium (after the builtins become a public interface)  

## 1. Executive Summary

The maintainer asked whether a fork of [`brush`](https://github.com/reubeno/brush), a Bash-compatible shell written in Rust, could serve SpheradianOS. The idea was especially for the 2D presentation, where it could act almost as a window manager for users who prefer a keyboard-driven, lightweight way of working.

A shell does not draw or manage windows. That stays the compositor's job (ADR-007, ADR-015). What a shell can do is **drive** the compositor. We decide:

- **Spheradian gets a command layer, `spheradian-shell`,** that exposes the single scene model of ADR-015 (windows, galaxies, depth, trust domains) as shell builtins. Keybindings, autostart, layouts, and automation become ordinary scripts. Power users can run the desktop from the keyboard or a controller-opened console instead of pointing.
- **It is built on the `brush` crates as pinned dependencies, not on a fork.** Everything we need is reachable through brush's public extension points: Rust builtins, `ShellExtensions`, and a replaceable `ProcessLauncher`. We fork only if upstream refuses a change we cannot do without, and we try to upstream it first.
- **It runs as its own process,** not inside the compositor. It talks to the compositor over an authenticated local IPC channel with explicit capabilities.
- **Every external command it launches goes through the per-domain sandbox launcher (M5)** via a custom `ProcessLauncher`. The shell can never be a way out of a trust domain.
- **Adoption is staged:** `brush-parser` alone for script auditing first, then the shell and the console overlay, then domain enforcement, then a text-mode presentation for tier 0.

## 2. Context and Problem

- **ADR-015 makes Planisphere first-class.** Some users will prefer it for speed, focus, or battery. For them, keyboard-first control of galaxies and windows is part of the appeal. Today there is no scripting or command interface to the compositor at all.
- **ADR-016 requires every action in the usability script to work by keyboard and controller.** A command layer gives every action a name and a scriptable form. That makes the bindings, tests, and accessibility tools share one vocabulary.
- **ADR-012 requires Rust on the target** and bans new non-`sh` interpreters in the image. A Bash-compatible shell in Rust fits that rule. Shipping GNU Bash as a component the project builds on does not.
- **The ADR-009/015 downgrade chain ends at `tier 0 text`.** Today that is a bare terminal, the kind of second-class fallback ADR-015 set out to remove.
- **Window managers such as Sway expose control through a separate IPC client (`swaymsg`)** driven from shell scripts. That works, but the language is a guest. An embedded shell makes scene objects native to the language.

### 2.1 What `brush` is (checked on 2026-11-28 against `main` at the 2026-11-27 commit)

| Property | Value |
|---|---|
| License | MIT (compatible with this project's Apache-2.0) |
| Language, MSRV | Rust, 1.88 |
| Maturity | `brush-core` 0.6 (pre-1.0, API not stable); about 2.4k stars, 111 open issues, 89 open PRs; packaged by Homebrew, Arch, Nix, Fedora (Terra) |
| Compatibility | Targets Bash 5.3+; over 1,700 compatibility tests against Bash itself. Missing: `select`, `wait -n`, `disown`; signal traps partial |
| Platforms | Linux `x86_64` and `aarch64` (glibc and musl) fully tested, which covers R1–R5 of ADR-014 |
| Crates | `brush-parser` (~12.8k lines, AST with optional `serde`), `brush-core` (~29.9k, runtime and `Shell` API), `brush-builtins` (~10.3k), `brush-interactive` (~9.7k, built on `reedline`: suggestions, highlighting, completion), `brush-shell` (binary) |
| Extension points | `Shell::builder()`, `run_string`, custom builtins in Rust, `ShellExtensions` with replaceable `ProcessLauncher`, `TaskSpawner`, and `ErrorFormatter`; experimental `precmd`/`preexec` hooks |
| `unsafe` | About 17 sites in `brush-core` (file descriptors, signals, `ioctl` for job control); none in `brush-parser`, `brush-builtins`, `brush-interactive` |
| Dependency tree | 637 packages in the workspace `Cargo.lock` (all crates, dev dependencies included). The tree for the crates we would use is not yet measured (§5.6) |

## 3. Scope

- **In scope:** whether and how the project uses `brush`; the shape of the command layer; its process and security boundaries; its staging across milestones; the criteria for ever forking.
- **Out of scope:** the exact builtin names and flags (designed in `spheradian/spheradian` with the M3 settings and launcher work); the IPC wire format; the visual design of the console overlay; the sandbox launcher itself (M5).

## 4. Options Considered

- **Option A: Fork `brush` and turn it into the Planisphere window manager.** Rejected. A shell cannot host Wayland clients, so the compositor is still required. A fork means maintaining about 70k lines of pre-1.0 code and its dependency tree as a second product. It would also drift from a fast-moving upstream.
- **Option B: No command layer; keyboard bindings hard-coded in the compositor.** Cheapest now. But automation, user layouts, and testing each grow their own ad-hoc interface, and tier 0 stays a bare terminal.
- **Option C: A Sway-style IPC protocol plus a small CLI client, used from any shell.** Proven. But it is only as useful as the shell on the target, which today is `dash` from `minbase`: ADR-012 §5.1 keeps shell on the target to short POSIX glue and forbids `bash` shebangs there, so scripting the desktop would rest on a minimal shell outside the project's control. It gives no control over how launched processes are confined.
- **Option D: Embed a different language (Lua, Rhai, Nushell).** Rhai and Lua are small and safe, but unfamiliar to people who already script in Bash. Nushell is large and has its own syntax. None of them give us Bash-compatible scripts that users already have.
- **Option E (Chosen): A separate `spheradian-shell` process built on the `brush` crates as pinned dependencies,** with scene builtins, a custom `ProcessLauncher`, and an IPC link to the compositor.

## 5. Decision

### 5.1 Architecture

```text
 ┌──────────────── spheradian (compositor) ────────────────┐
 │ shared core: scene model · focus · domain policy (ADR-015) │
 │ command endpoint: capability-checked IPC                 │
 │ console overlay: renders the shell's terminal, no logic  │
 └──────────────────────────▲───────────────────────────────┘
                            │ local socket, per-session token, capability set
 ┌──────────────────────────┴───────────────────────────────┐
 │ spheradian-shell (separate process, Rust)                │
 │ brush-core + brush-builtins + brush-interactive          │
 │ scene builtins: warp, galaxy, win, domain, presentation… │
 │ ProcessLauncher ──▶ per-domain sandbox launcher (M5)     │
 └──────────────────────────────────────────────────────────┘
```

- **Separate process.** A runaway script, a parser bug, or a crash in the shell must never take down the desktop. The compositor treats the shell as an untrusted client of its command endpoint.
- **The overlay is presentation only.** The "drop-down console" (a key or a controller chord opens it from the top edge) is a terminal surface the compositor draws above clients. The shell behind it is the same process that runs scripts.
- **Builtins, not text protocol, are the user interface.** Example shape, names to be designed in M3:

  ```bash
  warp work                                # space warp to a galaxy (ADR-015 §5.2)
  win move --galaxy study firefox          # move a window between galaxies
  domain run personal -- foot              # launch inside a trust domain
  presentation planisphere                 # live switch (ADR-015 §5.3)
  ```

  Each builtin maps to one command in the compositor's shared core, the same command a key or controller binding triggers. There is one command vocabulary.

### 5.2 Domain enforcement through `ProcessLauncher`

- `spheradian-shell` installs a custom `ProcessLauncher`. **Every** external program it starts, interactive or from a script, is started by the per-domain sandbox launcher in the domain the shell belongs to.
- A shell instance belongs to exactly one domain, shown by the compositor-drawn border of its console (ADR-015 §7). `domain run <other>` asks the compositor, which applies domain policy. The shell cannot spawn into another domain by itself.
- Until M5 delivers the sandbox launcher, the launcher is a pass-through and the shell is **not** a security boundary. The documentation says so in the same words as PRODUCT-VISION.md.

### 5.3 Compositor endpoint capabilities

- The endpoint accepts a per-session token passed to `spheradian-shell` at launch. Other local processes cannot drive the desktop.
- Capabilities are explicit: `scene.read`, `scene.arrange`, `domain.launch`, `presentation.switch`, `session.power`. Shells in high-risk domains get `scene.read` and `scene.arrange` limited to their own domain's windows.
- No capability allows drawing over or imitating compositor chrome, including domain borders.

### 5.4 Staging

| Stage | Milestone | What ships | Done when |
|---|---|---|---|
| S1 | M2 | `brush-parser` only, in host tooling and tests: parse shell scripts in `config/includes.chroot/` for the ADR-012 §5.5 static check | The check uses the AST instead of regular expressions, with tests |
| S2 | M3 | `spheradian-shell` with scene builtins, compositor endpoint with capabilities, console overlay; key and controller bindings expressed as builtin calls | Every action in the ADR-016 usability script can be done from the console and from a script, in both presentations |
| S3 | M5 | `ProcessLauncher` wired to the per-domain sandbox launcher; capability limits per domain | Anti-escape tests: no command typed or scripted in domain A starts a process outside A |
| S4 | After M5 | Tier 0 text presentation: a text-mode session (tmux-like panes) driven by the same builtins and the same scene model | Tier 0 passes the usability tasks that do not need a graphical app |

S1 counts as host tooling under ADR-012 §5.2, which allows Rust there only when it reuses a crate that ships on the target. S1 is therefore done only once S2 is committed. Until then, the existing Python check stays.

### 5.5 Fork policy

We fork `brush` only if **all** of these hold:

1. A capability we need is not reachable through the public API (builtins, `ShellExtensions`, `ProcessLauncher`, `TaskSpawner`).
2. We proposed the change upstream and it was declined or stalled for more than one milestone.
3. The fork is a small patch set rebased on upstream releases, not a divergent codebase. The patch set and its upstream status are listed in the crate's README.

### 5.6 Dependency gate (precondition for S2)

Before S2 starts, a PR records for `brush-core`, `brush-builtins`, and `brush-interactive` on `aarch64-unknown-linux-gnu` and `x86_64-unknown-linux-gnu`:

- the resolved dependency tree (`cargo tree -e normal`) and its size;
- `cargo deny` results against the desktop's policy (licences, advisories, bans, duplicates);
- each `unsafe` site in the used crates, with a one-line justification. `unsafe` stays forbidden in **our** code (`ENGINEERING-PLAN.md` §4.1); in dependencies it is justified per site, as ADR-012 §5.1 requires;
- the resident memory of an idle `spheradian-shell`, checked against the ADR-014 session budget (Planisphere ≤ 150 MiB for the whole session).

If the tree or the memory cost is unacceptable, S2 falls back to Option C (IPC plus a minimal client) and S1 stays.

## 6. Consequences and Trade-offs

- **Pros:**
  - A keyboard- and controller-first way to run the whole desktop, which gives Planisphere the "lightweight window manager" feel some users want, without a second window manager.
  - A console in the game-console sense, matching the console-feel commitment.
  - Bash-compatible scripting on the target without GNU Bash, consistent with ADR-012.
  - One command vocabulary for bindings, scripts, accessibility tools, and automated usability tests.
  - Domain confinement enforced at the one place every launch passes through.
  - A path for tier 0 to become a real presentation instead of a bare terminal.
  - No fork to maintain; upstream improvements arrive with version bumps.
- **Cons:**
  - Depends on a pre-1.0 upstream; API changes cost work at each bump. Pinning and the S2 gate contain this.
  - Builtin names become a user-facing interface that is hard to change once scripts depend on them. They need a stability policy before the first release that ships S2.
  - A second process in the session adds memory, measured in §5.6.
  - Bash compatibility gaps (`select`, `wait -n`, `disown`, partial signal traps) affect some user scripts.
- **Amends:**
  - ADR-015 §5.4: the downgrade chain's last step becomes "tier 0 text presentation (S4)" once S4 lands.
  - ADR-012 §5.5: the static shebang check may use `brush-parser` (S1).

## 7. Security and Compliance

- The shell is an untrusted client of the compositor. It has a token-authenticated endpoint, explicit capabilities, and no ability to draw compositor chrome.
- Until S3, the shell is not a security boundary, and the docs must say so plainly.
- `brush-core` contains `unsafe` for file descriptors, signals, and job control. It is reviewed per site under §5.6 and tracked in `spheradian/security`.
- Scripts loaded at login (`.bashrc`-style files) run inside the shell's domain, through the same `ProcessLauncher`. A malicious dotfile can do no more than the domain allows.
- `brush` is fuzzed upstream (`fuzz/`). We add our builtins' argument parsing to the desktop's own fuzzing targets.

## 8. Open Questions

1. Builtin namespace: plain names (`warp`) or a prefix (`sph warp`) to avoid clashing with user functions and existing commands?
2. Should the console overlay be available in the Sphere presentation too, or only in Planisphere?
3. Login shell: does `spheradian-shell` become the default interactive shell in terminals, or only the console's shell, with `foot` keeping the user's choice?
4. Stability policy for builtin names and flags before the first public release that ships S2.
5. How the per-session token reaches `spheradian-shell` and how it is bound to one domain. Passing it by argv or environment would let every child in that domain inherit it and drive the compositor with the shell's capabilities, and the per-domain limit in §5.3 depends on that binding (for example an inherited file descriptor that is closed before exec, or `SO_PEERCRED` checks on the socket).
6. Whether S1 is done when the static check uses the AST (§5.4 table, M2) or only once S2 is committed (§5.4 text, M3). Also: the scripts under `config/includes.chroot/` are POSIX `sh`, so a Bash parser may accept constructs that `sh` rejects. Should S1 also enforce POSIX?
7. A release gate between S2 (M3) and S3 (M5). During that window the console is a working shell whose launcher passes everything through. Should S2 ship only in images labelled as prototypes until the console banner shows the "not a security boundary" notice?
8. Default-deny capabilities: §5.3 limits shells "in high-risk domains" without defining them. Should every shell be limited to its own domain's windows by default, with `scene.arrange` beyond that and `session.power` granted explicitly?

## 9. Related

- [PRODUCT-VISION.md](../PRODUCT-VISION.md) §2 (console feel, security)
- [ADR-007](ADR-007-m1-kiosk-prototype-session.md): current terminal fallback
- [ADR-009](ADR-009-gpu-render-levels-and-warmup.md): downgrade chain
- [ADR-012](ADR-012-implementation-language-policy.md): Rust on the target, static checks
- [ADR-014](ADR-014-hardware-targets-and-budgets.md): session RAM budget, reference machines
- [ADR-015](ADR-015-planisphere-2d-presentation.md): Planisphere, shared core, tier 0
- [ADR-016](ADR-016-first-usable-build-roadmap.md): usability script, keyboard and controller navigation
- `brush`: <https://github.com/reubeno/brush>, compatibility reference at <https://brush.sh/reference/compatibility/>
