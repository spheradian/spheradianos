# ADR-011: Organization and Product Structure (Fabrintek, Spheradian, SpheradianOS) After the System76 and Silverblue Models

**Date:** 2026-11-23  
**Status:** Proposed  
**Author:** Senior Software Architect  
**Approver:** Fábio Mendes (`mendsec`)  
**Confidence:** Medium  
**Impact:** High  
**Reversibility:** Medium  

## 1. Executive Summary

The project has outgrown its original framing ("XSphereOS, a Debian-based distribution for the XSphereDE desktop"). The GitHub organization `spheradian` already exists, the repositories have moved into it, and the desktop and the distribution have new names. What is still missing is a written decision on **who owns what, what is original, and how the pieces relate**.

We compared five ways that established projects organize a company, a desktop, and a distribution (§4). No single model fits, so we combine two:

- **The System76 model for the organization and the desktop.** One change: Fabrintek is a services company, not a hardware vendor.
- **The Fedora Silverblue model for the system layer.** SpheradianOS does more than package a desktop. It owns how the system is laid out, updated, and kept responsive: filesystem layout, atomic image-based updates, and memory management. This is the same kind of work Silverblue, Vanilla OS, and Endless OS do.

| Role | Reference | This project |
|---|---|---|
| Company that funds the work and can earn from it | System76 (hardware) | **Fabrintek** (IT services) |
| Open-source GitHub organization | `pop-os` | **`spheradian`** |
| Desktop environment, portable across distributions | COSMIC | **Spheradian** |
| Reference distribution, the "flagship" | Pop!_OS | **SpheradianOS** |
| Atomic, image-based system layer | Fedora Silverblue; on a Debian base, Vanilla OS (ABRoot) and Endless OS (OSTree) | **SpheradianOS system layer**: filesystem layout, atomic updates, memory management (design in a future ADR-013) |
| Distribution build recipe | `pop-os/iso` (Make and shell) | **`spheradian/spheradianos`** (`live-build`, shell, Python tooling) |
| Integration repository that pins component versions | `pop-os/cosmic-epoch` | Deferred until there are 3 or more shipped components (§5.4) |

The decision also states plainly what is original and what is inherited (§5.2). It sets naming rules (§5.3) and the order of the remaining migration steps (§7).

## 2. Context and Problem

- **Is the project a remaster?** The question was raised directly: Python is the most-used language in this repository, so the work can look like "an ISO assembler". In this repository that is true. The original work is in Rust, in a different repository: the desktop. No document says this, so the project looks smaller than it is.
- **The rename is underway, but no decision records it.** The `spheradian` organization was created on 2026-11-23. `mendsec/xspherede`, `mendsec/xsphereos`, and `mendsec/xspherede-security` now redirect to `spheradian/spheradian`, `spheradian/spheradianos`, and `spheradian/security`. The crate is now `spheradian`. PR #30 renamed identifiers in this repository. The naming discussion lives in an issue (`spheradian/spheradian#17`), not in an ADR.
- **`DISTRO-DESIGN.md` §10 leaves open question 6 open:** "Name, branding, and licensing of the distribution as distinct from the desktop."
- **The company layer is undocumented.** Fabrintek (`github.com/fabrintek`) already exists as the maintainer's IT services company. Its relationship to the open-source project has not been decided.
- **The licences disagree.** `spheradian/spheradian` ships `LICENSE` as Apache-2.0 (also in `Cargo.toml`). The organization profile, ADR-003, and this repository's README say MIT. PR #23 first proposed an MIT `LICENSE` for this repository. §5.5 resolves this in favour of Apache-2.0.

## 3. Scope

- **In scope:** the roles of Fabrintek, the `spheradian` organization, the desktop, and the distribution; the boundary between original and inherited work; naming conventions for repositories, crates, packages, binaries, and identifiers; repository layout; the order of the remaining rename steps; the licensing questions that must be settled.
- **Out of scope:** the mechanical rename of files and identifiers in this repository (PR #30); repository visibility (ADR-003, ADR-010 in PR #23); implementation language (ADR-012); legal and trademark filings, which this ADR only recommends.

## 4. Options Considered

Each model below was checked against public sources in November 2026 (§9).

### Option A (Chosen): System76 / Pop!_OS / COSMIC

- **Structure:** A company (System76) funds an open-source organization (`pop-os`). That organization ships a reference distribution (Pop!_OS, based on Ubuntu) and a desktop (COSMIC) that is deliberately portable. Fedora, Arch, openSUSE, NixOS, and Gentoo package COSMIC today.
- **Repositories:** One repository per component (`cosmic-comp`, `cosmic-panel`, `cosmic-files`, `libcosmic`, and others), each with its own `debian/` packaging. `cosmic-epoch` pins every component through git submodules and tags releases (`epoch-X.Y.Z`). The meta repository `pop-os/pop` lists all sources. The ISO is built by `pop-os/iso`, which uses Make and shell. Binaries come from an APT repository the company runs.
- **Languages:** Rust for the desktop and the system tools (installer `distinst`, `pop-launcher`, `system76-power`, firmware manager). Make and shell for the image.
- **Fit:** Close. One maintainer company, one desktop that is the reason the distribution exists, and a distribution that puts that desktop on real machines. Spheradian already targets Linux and BSD, so it is portable like COSMIC.
- **Difference:** System76 sells hardware, and Pop!_OS makes that hardware work well. Fabrintek sells IT services, so SpheradianOS is what Fabrintek can deploy and support for its clients (§5.1).

### Option B: elementary, Inc. / elementary OS / Pantheon

- **Structure:** One company and one organization. The desktop (Pantheon) is built mainly for the company's own distribution. The ISO is built from `elementary/os` with Debian `live-build`, the same tool this repository uses. Applications are written in Vala.
- **Why not:** The desktop is tied closely to one distribution. Spheradian already aims at several systems, including BSD. The `live-build` layout of `elementary/os` is still a useful reference for this repository.

### Option C: KDE e.V. / Plasma / KDE neon

- **Structure:** A non-profit foundation and a large community. The distribution (KDE neon) exists only to show the latest desktop.
- **Why not:** It needs a community and a foundation that do not exist yet. The idea of a distribution as a showcase for a desktop still applies to SpheradianOS.

### Option D (Adopted for the system layer): Fedora Silverblue, Vanilla OS, Endless OS

- **Structure:**
  - The operating system is an immutable image. Updates replace the whole image atomically and can be rolled back. User data and applications live apart from the system.
  - Fedora Silverblue uses `rpm-ostree` and, more and more, `bootc` with OCI images.
  - Vanilla OS uses Debian with ABRoot (A/B root partitions), the `vib` image builder, and Apx for containerized tools, all written in Go.
  - Endless OS is Debian-based and uses OSTree.
- **Why it applies:** SpheradianOS will do its own work in the system layer, mainly the filesystem and memory handling, not only in the desktop. The planned behaviour of Spheradian connects UX/UI, how data is organized, the filesystem, and security. It needs a system whose layout is predictable and cannot drift. An immutable base makes that layout something the project defines and tests, rather than something each machine accumulates.
- **Why not the whole model:** Vanilla OS and Silverblue ship an existing desktop (GNOME). Spheradian's desktop is original, so the System76 model still governs the organization and the desktop.
- **Two Debian-based examples exist:** Vanilla OS and Endless OS both run an atomic system on Debian. This keeps the "Stay on Debian" decision compatible with an immutable design.

### Option E: Valve / SteamOS / gamescope

- **Structure:** A product company ships a distribution as part of a device. Components such as `gamescope` are open source, but product needs drive the roadmap.
- **Why not:** It needs a product (the device) to anchor it. It is a possible future for Fabrintek (preinstalled machines for clients), not a starting point.

## 5. Decision

Adopt **Option A** for the organization, the desktop, and the relationship between them. Adopt **Option D** as the direction for the SpheradianOS system layer. The concrete design (image format, update mechanism, filesystem layout, memory management) needs its own ADR-013 before M4, because it changes how the image is built and upgraded (§6).

### 5.1 Roles

| Entity | What it is | What it owns |
|---|---|---|
| **Fabrintek** | The maintainer's company | Funding, legal identity (trademark holder, release-key custodian once M4 defines signing), and paid services: deployment, support, and custom images of SpheradianOS for clients. Fabrintek's internal repositories stay in `github.com/fabrintek` and never mix with the open-source organization. |
| **`spheradian` (GitHub org)** | The open-source project | Every public and private repository of the desktop and the distribution, the website, community health files, and the roadmap board. |
| **Spheradian** | The desktop environment | The spherical Wayland compositor and shell (`spheradian/spheradian`) and the components around it (`files`, later `settings`, `launcher`, and others). It stays portable: Linux and BSD, and no dependency on SpheradianOS. |
| **SpheradianOS** | The reference distribution and its system layer | This repository: the image recipe, boot experience, session integration, and the **system layer** (filesystem layout, atomic image updates and rollback, memory management). Also packaging (M4), installer and first boot (M4/B7), and enforced trust-domain isolation in the image (M5). |
| **`spheradian/security`** | Private security repository | Threat models, audits, and hardening specifics for both products (ADR-001, ADR-003). |

**How Fabrintek appears in public:** a single line in the organization profile and the website footer ("Spheradian is sponsored by Fabrintek"). Fabrintek's name does not appear in product names, package names, or the UI. COSMIC follows the same rule: the brand stays separate from System76, so other distributions can ship it without promoting another company.

### 5.2 What is original and what is inherited

Answer to "is this a remaster?":

| Layer | Source | Status |
|---|---|---|
| Kernel, libc, drivers, firmware, Mesa, systemd, PipeWire, the APT archive | Debian `trixie` (inherited, unmodified) | Inherited by design (`DISTRO-DESIGN.md` §1 goal 4, "Debian as a parts bin") |
| Image recipe, package curation and budgets, zero-prompt boot (ADR-002), fluidity profile (ADR-004, ADR-006) | `spheradian/spheradianos` | **Original integration work**: configuration and policy, not new programs |
| Boot experience: Ignite → Gather → Wake driven by real systemd milestones, watchdog, plain-text failure reports, procedural audio (B5) | `spheradian/spheradianos` | **Original design.** The implementation runs inside Plymouth today and moves into the compositor at B4 |
| Spherical compositor and shell, Mini-Globe, curved windows, trust-domain policy engine | `spheradian/spheradian` (Rust) | **Original software**, the core of the project |
| Spatial file manager | `spheradian/files` | **Original software** (concept stage) |
| System layer: immutable image, atomic updates and rollback, filesystem layout, memory management beyond the ADR-004 baseline | `spheradian/spheradianos`, tools in Rust (ADR-012) | **Original design and software, planned** (ADR-013) |
| Session manager, installer, first boot, settings, `audio-synth`, per-domain sandbox (M2–M5) | Planned, Rust (ADR-012) | **Original software, planned** |

What the project should say about itself: **"SpheradianOS is an atomic, Debian-based operating system built around Spheradian, an original spherical desktop in which the interface, the organization of data, the filesystem, and security work as one design."** It is not a new kernel and does not replace Debian's packages, and it should not claim to. The original work is the desktop and the system layer that it runs on. Pop!_OS makes the same kind of claim for the desktop, and Silverblue for the system layer.

### 5.3 Naming conventions

| Thing | Rule | Examples |
|---|---|---|
| Display names | `Spheradian` for the desktop; `SpheradianOS` for the distribution (one word, capital S and OS). No "DE" suffix, following issue #17. | "Spheradian 0.1", "SpheradianOS 1.0" |
| Repositories for shipped components | The same as the package and crate name, with the `spheradian-` prefix, as COSMIC does with `cosmic-*`. Crates and Debian packages share global namespaces, so the prefix belongs in the name, not only in the organization. | `spheradian-files`, `spheradian-session`, `spheradian-settings`, `spheradian-installer` |
| The main desktop repository | `spheradian` (already) | `spheradian/spheradian` |
| Repositories that ship nothing | Short names are fine | `security`, `.github`, `spheradianos` (the recipe) |
| Distribution identifiers | `spheradianos-` for distribution-level files; `spheradian-` for desktop-level files; `spheradian.` for kernel parameters | `spheradianos-base` (metapackage), `spheradianos-boot-watch.service`, `spheradian-session.slice`, `spheradian.motion=reduced` (applied by PR #30) |

This means `spheradian/files` should be renamed to `spheradian/spheradian-files` before it ships a package. GitHub redirects the old name. The redirect does not cover GitHub Pages, so the demo URL changes.

### 5.4 Repository layout

- **Now:** One repository per component, one recipe repository (this one), one security repository, and `.github`. This repository pins `spheradian` to a commit SHA (ADR-007, `scripts/build-spheradian.sh`, named `build-xspherede.sh` before PR #30).
- **When 3 or more components ship in the image:** Add an integration repository (`spheradian/spheradian-epoch`) that pins every component, so a desktop release is one tag. This works like `cosmic-epoch`. The recipe then pins one epoch tag instead of several SHAs.
- **At M4:** Each shipped component gets a `debian/` directory in its own repository, as in the `pop-os` repositories. The signed APT repository publishes binaries, and the image installs packages instead of staging binaries into `includes.chroot`. With an atomic system layer, packages are used when the image is **built**. Installed systems do not run `apt` against the base: they receive whole signed images (ADR-013).

### 5.5 Licensing

**Decided by the approver on 2026-11-23: Apache-2.0 for all project code.**

1. **Desktop components:** Apache-2.0, as `spheradian/spheradian` already ships (`LICENSE`, `Cargo.toml`). Every new component repository starts with the same licence. Apache-2.0 is permissive like MIT, and it adds an explicit patent grant and a `NOTICE` mechanism, which matters for a project that a company sponsors and that others may build products on.
2. **Distribution recipe:** Apache-2.0 as well, one licence across the organization. This repository gets an Apache-2.0 `LICENSE`. PR #23, which first proposed an MIT `LICENSE` here, switched to Apache-2.0 and merged with it.
3. **Where MIT was stated, it is corrected:**
   - ADR-003 and the architecture diagrams, in this change;
   - PR #23's `LICENSE` and ADR-010;
   - `spheradian/files`, relicensed from MIT in `spheradian/files#4` (single copyright holder; earlier versions stay available under MIT);
   - the organization profile, in `spheradian/.github#1`.
4. **Brand:** Code licences do not cover names and logos. A short trademark policy (in `.github`) should say who may use "Spheradian" and "SpheradianOS". Most distributions, Pop!_OS included, allow rebuilds but require a new name for modified images.

## 6. Consequences and Trade-offs

- **Pros:**
  - The original work and the inherited base are stated explicitly, which answers the "remaster" question.
  - Clear ownership of each piece.
  - The desktop stays usable on other distributions and on BSD, so more people can use it and test it.
  - Fabrintek has a sustainable role (services around SpheradianOS) without the brand depending on it.
  - The naming rules can be checked mechanically.
- **The atomic system layer contradicts parts of the current design.** ADR-013 must resolve each of these:
  - `DISTRO-DESIGN.md` §4 item 5 says "upgrades are normal `apt` upgrades". With an immutable base, the base is updated as a whole image, not package by package.
  - ADR-006 (`host-only` initramfs on the installed system) assumes the initramfs is generated on each machine. An image-based system usually ships a generic, signed initramfs, or builds it into the image.
  - `live-build` produces live ISOs. It does not produce updatable system images. The installer and update path will need an image builder (for example `mkosi`, `bootc`, OSTree tooling, or an ABRoot-style A/B layout), while `live-build` may remain for the live ISO only.
  - Applications (browser, terminal, file manager) need a home outside the immutable base, for example Flatpak or per-trust-domain containers. That choice interacts with M5 sandboxing.
- **Cons:**
  - More repositories to maintain. The integration repository is deferred until it pays for itself.
  - One more rename (`files` → `spheradian-files`) and a Pages URL change.
  - Separate brands for the company and the product mean Fabrintek gets less visibility from the project.

## 7. Migration Plan

| Step | Change | Where | Depends on |
|---|---|---|---|
| 1 | Merge the identifier rename (PR #30), coordinated with the open PRs it conflicts with (#23, #27, #28, #29, #31). Done: merged after #23, #27, #29, and #31 | `spheradianos` | — |
| 2 | Accept this ADR and ADR-012; close open question 6 in `DISTRO-DESIGN.md` §10 | `spheradianos` | — (licence decided: Apache-2.0, §5.5) |
| 3 | Align on Apache-2.0: `LICENSE` in this repository (done with this ADR), the organization profile in `.github`, and PR #23's `LICENSE` (done: merged as Apache-2.0) | `.github`, `spheradianos` | — |
| 4 | Close `spheradian/spheradian#17` with a link to this ADR | `spheradian` | Step 2 |
| 5 | Rename `files` → `spheradian-files`; update the Pages links | `spheradian-files` | Step 2 |
| 6 | Add the "sponsored by Fabrintek" line and a trademark policy to `.github` | `.github` | Step 3 |
| 7 | Register the domain (for example `spheradian.org`) and evaluate a trademark filing for "Spheradian" | Fabrintek | — |
| 8 | Commit the three-pillar positioning ADR (currently uncommitted, referenced as ADR-007 in `ARCHITECTURE.md`) under the free number ADR-008 | `spheradianos` | — |
| 9 | Write ADR-013, the atomic system layer: image format and builder, update and rollback mechanism, filesystem layout, memory management. Resolve the conflicts in §6 | `spheradianos` | Maintainer's design notes; before M4 |
| 10 | Add `spheradian-epoch` when the third component ships | new repository | M2–M3 |
| 11 | Per-repository `debian/` packaging and the signed APT repository (feeding image builds) | all shipped components | M4, ADR-013 |

## 8. Security and Compliance

- Fabrintek's internal repositories (client data, operations) must never be linked from, mirrored into, or share CI secrets with the `spheradian` organization.
- `spheradian/security` stays private regardless of the visibility of the other repositories (ADR-003, ADR-010).
- Until M5 is complete, no material from the company or the project may describe trust domains as an enforced security boundary.

## 9. Related

- [ADR-001](ADR-001-github-roadmap-governance.md): GitHub roadmap and governance
- [ADR-003](ADR-003-spheradian-visibility.md): desktop repository visibility (licence amended to Apache-2.0 by §5.5)
- [ADR-007](ADR-007-m1-kiosk-prototype-session.md): pinned desktop build in the image
- [ADR-012](ADR-012-implementation-language-policy.md): implementation language policy
- [docs/ORGANIZATION.md](../ORGANIZATION.md): the living map of the organization, repositories, and names
- PR #30 (identifier rename), PR #23 (ADR-010, public visibility), `spheradian/spheradian#17` (naming)
- Sources reviewed: `github.com/pop-os`, `pop-os/pop`, `pop-os/cosmic-epoch`, `pop-os/iso`, `elementary/os` (wiki: Building ISO Images), `github.com/Vanilla-OS`, Wikipedia: Pop!_OS, elementary OS
