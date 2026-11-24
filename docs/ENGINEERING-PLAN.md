# XSphereOS and XSphereDE: Engineering Plan (TDD, Clean Code, DevSecOps)

Status: **draft for review**. This plan covers both the desktop (`spheradian/spheradian`) and the distribution (`spheradian/spheradianos`). It builds on [DISTRO-DESIGN.md](DISTRO-DESIGN.md).

> Scope note: this file states practices and gates. Threat models, audit findings, and hardening specifics live only in the private `xspherede-security` repository.

---

## 1. Where we start (measured, not assumed)

| Area | Current state | Gap |
|---|---|---|
| Rust tests | 7 `#[test]` across ~3,400 lines (6 in `security.rs`, 1 in `camera.rs`) | `main.rs` (1,471 lines), `window3d.rs`, `sphere_env.rs`, `minimap.rs` have none |
| Structure | `main.rs` mixes windowing, rendering, input, and app state | Hard to test; hard to review |
| CI (xspherede) | fmt, clippy `-D warnings`, test on stable and MSRV 1.88, `cargo audit`, BSD cross-check, weekly schedule, actions pinned by SHA, least-privilege token | Good base. No coverage, no deny/licence policy, no SBOM, no release signing |
| Distro | M0 live-build recipe, syntax-checked only; never built | No automated checks at all yet |

The plan below closes these gaps in order of risk reduction per unit of effort.

---

## 2. Principles

1. **Tests come first for logic, gates come first for everything else.** Pure logic is written test-first. Infrastructure (image builds, CI) gets an automated check before it gets features.
2. **Small, reviewable changes.** One concern per pull request, ideally under 400 changed lines.
3. **Nothing merges red.** Required status checks on `main`; no bypass for the maintainer.
4. **Describe what exists.** Docs and logs state current behavior, never intent (already a project rule).
5. **Security is a pipeline stage, not a phase.** Every gate in section 5 runs on every change.

---

## 3. TDD

### 3.1 The loop

Red, green, refactor, on every behavior change:

1. Write a failing test that names the behavior.
2. Write the minimum code to pass it.
3. Refactor with the test suite as a safety net.
4. Commit the test and the code together; keep commits small enough to bisect.

Bug fixes begin with a failing regression test that reproduces the bug.

### 3.2 Test pyramid for this project

| Level | XSphereDE (Rust) | XSphereOS (image) | Speed target |
|---|---|---|---|
| Unit | Pure functions and state machines: spherical math, raycasting, trust-domain policy, clipboard vault, surface validation | Manifest and config parsers, script helpers | seconds, no GPU, no network |
| Integration | Layout and input routing against a fake `WindowSurfaceProvider`; headless wgpu adapter where available | Config-tree checks: every package justified, no forbidden package, `auto/config` options as expected | under a minute |
| System | Compositor session in a headless backend | Boot the ISO in QEMU, assert the console reaches the expected state | minutes, nightly and on image changes |

Rule: logic must be testable **without** a GPU or a window. GPU-dependent code is kept thin so the bulk of behavior is unit-testable.

### 3.3 Designing for testability (Rust)

- Extract pure cores from `main.rs`: input mapping, focus and drag state, window placement, command handling. Each becomes a module that takes values and returns values.
- Introduce traits at the boundaries that need faking: `WindowSurfaceProvider` (already on the roadmap), a `Clock`, and a `HostInfo` source for the audit module (reads of `/proc` become injectable).
- Property tests (`proptest`) for the math and policy code: raycast hits always land on the sphere; clamping always stays in range; the clipboard vault never releases data across a disallowed domain pair; surface validation rejects every out-of-bounds dimension.
- Keep the existing integrity test that pins the shader digest. It fails by design when the shader changes without the digest being updated.

### 3.4 Testing the distro

- **Static layer (fast, every PR):** `shellcheck` on all scripts, `shfmt --diff`, a test that parses `config/package-lists/*` and fails on any line without a justification comment, and a test that rejects forbidden packages (desktop metapackages, `xwayland`, setuid helpers we do not want).
- **Config assertions:** parse `auto/config` and assert `minbase`, `--apt-recommends false`, pinned distribution, and no installer.
- **Boot test (QEMU, on image changes and nightly):** boot the ISO headless with a serial console, expect a login or shell prompt within a timeout, run assertions over serial (kernel command line, no unexpected listening ports, package count within budget).
- **Size budget test:** fail the build if ISO size or package count exceeds the recorded budget by more than an agreed margin.
- **Shell test framework:** `bats-core` for script behavior.

### 3.5 Coverage policy

Coverage is a signal, not a goal. Use `cargo llvm-cov` in CI and report it; require that **new and changed lines in logic modules** are covered, and set a floor for `security.rs` that only ratchets upward. No coverage target applies to GPU glue code.

---

## 4. Clean Code

### 4.1 Rust conventions

- **Small modules with one reason to change.** Target: no file above ~500 lines, no function above ~40 lines. First refactor: split `main.rs` into `app`, `input`, `render`, `state`, and `commands` modules without changing behavior, protected by the tests from section 3.
- **Names express intent.** Types and functions are named for the domain (trust domain, surface, vault), not the mechanism.
- **Make invalid states unrepresentable.** Prefer enums and newtypes to booleans and raw integers (for example a validated `SurfaceDims` newtype instead of passing width and height separately).
- **Errors are values.** Return `Result` with typed errors in library code; no `unwrap`/`expect` outside tests and startup assertions with a stated reason. With `panic = "abort"` in release, a stray panic is a crash of the whole session.
- **Keep the existing hard rules:** `unsafe` forbidden, few dependencies, English only.
- **Lints as policy.** Beyond `clippy -D warnings`, enable a curated set (`clippy::pedantic` subset, `unwrap_used`, `expect_used`, `indexing_slicing` in security-sensitive modules) and document each exception in code.
- **Comments explain why, not what.** If a comment narrates the code, rename or extract instead.

### 4.2 Shell and image-recipe conventions

- POSIX `sh` with `set -eu`, `shellcheck`-clean, `shfmt`-formatted.
- Scripts do one thing, take arguments explicitly, and print actionable errors.
- No logic in hooks that can live in a tested script.
- Configuration over code: image options live in `auto/config` and the package lists, not scattered in scripts.

### 4.3 Review and change hygiene

- Pull request template requires: what changed, why, how it was tested, and a security-impact note (none, or "see private tracker" without details).
- Conventional-style commit messages, English, imperative.
- Refactors and behavior changes never share a commit.
- Architecture decisions that are hard to reverse get a short ADR in `docs/adr/`.

---

## 5. DevSecOps

### 5.1 Pipeline stages and gates

Every pull request runs the same stages; all required to pass.

| Stage | Tooling | Applies to |
|---|---|---|
| Format and lint | `cargo fmt`, `clippy -D warnings`, `shellcheck`, `shfmt` | both |
| Test | `cargo test --locked` on stable and MSRV; `bats`; config tests | both |
| Coverage report | `cargo llvm-cov` | desktop |
| Dependency advisories | `cargo audit` (existing) and `cargo deny` (advisories, licences, bans, duplicate versions) | desktop |
| Secret scanning | `gitleaks` in CI; GitHub secret scanning and push protection enabled | both |
| Static security analysis | CodeQL where supported, plus clippy security-relevant lints | desktop |
| Workflow security | `zizmor` or equivalent over `.github/workflows` | both |
| Image build and boot test | live-build, QEMU boot test | distro |
| Artifact integrity | checksums, detached signature, SBOM | distro and desktop releases |

### 5.2 Supply chain

- **Pin everything.** GitHub Actions by commit SHA (already done), `Cargo.lock` committed and `--locked` everywhere, Debian snapshot date per image release, XSphereOS package versions pinned.
- **Few dependencies, justified.** Each new crate or package needs a rationale in the PR; `cargo deny` bans unwanted licences and duplicate trees.
- **Update flow.** Dependabot (exists) for crates and actions; for the distro, a scheduled job bumps the Debian snapshot and opens a PR that must pass the full pipeline.
- **SBOM.** Generate an SBOM per release (CycloneDX for the Rust build, package list for the image) and publish it with the artifacts.
- **Provenance.** Build releases in CI, not on a developer machine; sign artifacts (Sigstore or a dedicated release key) and publish checksums. Aim for reproducible image builds: pinned snapshot, deterministic timestamps, comparison of two independent builds in CI.

### 5.3 Repository and access controls

- Branch protection on `main`: required reviews or a required self-review checklist for a solo maintainer, required status checks, linear history, no force pushes, signed commits.
- Least-privilege tokens in workflows (`permissions: contents: read` default, already used); `persist-credentials: false` on checkout (already used).
- Two-factor authentication on the maintainer account; hardware key for the release signing role.
- Repository visibility: `xspherede-security` stays private, with its access list reviewed on a schedule. `xsphereos` is public per ADR-010, like `xspherede`.
- Security reporting stays private per `SECURITY.md`; fixes land with neutral, functional commit messages.

### 5.4 Runtime and host hardening (high level)

Specifics belong in the private repository. At the plan level:

- Secure defaults in the shipped image, expressed as tested configuration, not documentation.
- A boot-time self-audit (extending the existing host audit) whose results are asserted in the QEMU boot test.
- Per-domain isolation is the milestone (M5) that turns the trust model into an enforced boundary. Until then, docs and UI continue to say it is not one.

### 5.5 Release process

1. Tag from `main` after a green pipeline.
2. CI builds artifacts, generates SBOM, checksums, and signatures.
3. Publish to the `testing` channel first; promote to `stable` after a soak period and a manual smoke check.
4. Changelog entry in `CHANGELOG.md`, written in functional terms.
5. A documented rollback path for each channel.

---

## 6. Rollout plan

Ordered so each step makes the next safer.

| Step | Deliverable | Repo |
|---|---|---|
| 1 | Branch protection, required checks, secret scanning and push protection enabled | both |
| 2 | `shellcheck`, `shfmt`, and config-assertion tests for the recipe; CI workflow for the distro repo | xsphereos |
| 3 | First real image build and QEMU boot test; record size and package budget (completes M0) | xsphereos |
| 4 | `cargo deny` and `gitleaks` added to the desktop CI; `cargo llvm-cov` report | xspherede |
| 5 | Characterization tests around `main.rs` behavior, then split `main.rs` into modules (behavior unchanged) | xspherede |
| 6 | Property tests for math and the policy engine; `WindowSurfaceProvider` trait with a fake | xspherede |
| 7 | SBOM generation and signed, CI-built release artifacts | both |
| 8 | Reproducible-build comparison job for the image | xsphereos |
| 9 | ADR directory and PR template updates (security-impact note, test evidence) | both |

Definition of done for any change: tests written first where logic is involved, all gates green, docs updated, no new unjustified dependency, security-impact note filled in.

---

## 7. Risks and trade-offs

- **Overhead for a solo maintainer.** Mitigation: automate gates; keep human steps to a short checklist.
- **GPU code is hard to test in CI.** Mitigation: thin GPU layer, headless or software adapter where available, and treat manual visual checks as an explicit, documented step.
- **Reproducible image builds are fiddly.** Mitigation: treat them as a goal with a measured gap, not a blocker for the first releases.
- **Refactoring `main.rs` risks regressions.** Mitigation: characterization tests first, behavior-preserving commits only.

## 8. Open questions

1. Required review policy while there is a single maintainer.
2. Signing approach: Sigstore keyless versus a dedicated release key.
3. Whether the headless wgpu adapter is reliable enough on GitHub-hosted runners for integration tests.
4. Where the boot test runs: GitHub-hosted runners with software emulation, or a self-hosted runner with KVM.
