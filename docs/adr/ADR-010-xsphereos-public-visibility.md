# ADR-010: Make `mendsec/xsphereos` Public After M0, Announce at M2

**Date:** 2026-11-22  
**Status:** Proposed  
**Supersedes:** The `xsphereos` clauses of [ADR-003](ADR-003-xspherede-visibility.md) §4, [ADR-001](ADR-001-github-roadmap-governance.md) §7, and `ENGINEERING-PLAN.md` §5.3 (see §7)  
**Author:** Senior Software Architect  
**Approver:** Fábio Mendes (`mendsec`)  
**Confidence:** Medium  
**Impact:** Medium  
**Reversibility:** Hard (a published history cannot be withdrawn: clones, forks, and caches persist)  

## 1. Executive Summary

`mendsec/xsphereos` is private by decision of ADR-003, ADR-001, and `ENGINEERING-PLAN.md` §5.3. We propose to **make it public once Milestone `M0` is closed and the pre-publication checklist in §5 is complete**, without announcing it, and to **announce the project publicly when `M2` (real compositor, B4) is done**. `mendsec/xspherede-security` stays private, unchanged.

## 2. Context and Problem

When ADR-003 was written, `xsphereos` held little more than design documents, and keeping it private cost nothing. The situation has changed:

- **CI cost.** The repository now runs a QEMU boot gate (`image-boot.yml`, BIOS and UEFI) on top of static checks, `unittest`, and `gitleaks`. Image builds and boots are the most expensive jobs in either repository. Public repositories get standard GitHub-hosted Linux runners at no cost, with KVM available. This is the same argument that kept `xspherede` public in ADR-003.
- **Security material is already separated.** Threat models, audit findings, and hardening specifics live only in `xspherede-security` (`ENGINEERING-PLAN.md` §5, `BOOT-EXPERIENCE.md` §11). What `xsphereos` holds (the `live-build` recipe, package lists, boot theme generators, test harness, design docs, ADRs) is the kind of material a Debian derivative normally publishes.
- **Honest disclaimers are already in place.** The README and docs state that trust-domain isolation is not an enforced boundary until `M5`. Publishing does not change what is claimed.
- **Project identity.** XSphereOS is positioned "in the spirit of Kurumin Linux", a community distribution. An open history from early on supports outside review, issue reports, and contributions.
- **First impressions.** Before `M2` the image boots to a shell or a prototype session. A public *announcement* is better timed with the B4 hand-off, when a real terminal renders on the sphere.

Repository visibility and public announcement are separable decisions. This ADR treats them separately.

## 3. Options Considered

- **Option A:** Keep `xsphereos` private until `M4` (first signed release) or `M5` (enforced isolation).
- **Option B (Chosen):** Make it public after `M0` plus the §5 checklist; announce at `M2`.
- **Option C:** Make it public immediately.

| | A: private until M4/M5 | B: public after M0, announce at M2 | C: public now |
|---|---|---|---|
| CI cost of boot gates | Paid minutes for months | Free from M0 | Free now |
| Exposure of unfinished work | None | Visible, but not promoted | Visible, checklist not done |
| Licensing and history audited first | Yes | Yes (§5 is a gate) | No |
| Outside review before first release | None | From M0 | From now |
| Security risk | Lowest | Low: no threat material in this repo | Low, but unverified history |

Option A protects nothing that matters: the sensitive material already lives in another repository, and waiting until `M5` ties visibility to a milestone unrelated to what this repository contains. Option C skips the decisions that cannot be undone after publication (licence, name, history audit).

## 4. Decision

Adopt **Option B**:

1. Complete the checklist in §5. Each item is a GitHub Issue under Milestone `M0`.
2. Once `M0` is closed and every §5 item is done, the approver switches `mendsec/xsphereos` to public. This is a manual action by the approver, never by automation.
3. Do not announce the project before `M2` is complete. "Announce" means posts, forum threads, release notes, or promotion outside GitHub. Being discoverable on GitHub is fine.
4. `mendsec/xspherede-security` stays private. The rule that no threat models, audit findings, or vulnerability details are committed to `xsphereos` becomes stricter, because the repository will be readable by anyone.
5. **Licence: MIT** for the distribution recipe, tooling, tests, and documentation in `xsphereos`, matching `xspherede`. This resolves the licensing part of `DISTRO-DESIGN.md` §10, open question 6 (naming and branding remain open, see §5). It allows derivative distributions, including closed ones, and keeps both projects under one simple licence. Packages shipped in the image keep their own Debian licences, and the MIT licence covers only what this repository authors.

## 5. Pre-Publication Checklist (gate)

All items must be done before the visibility switch.

**Decisions that cannot be changed after publication**

- [x] **Licence.** MIT `LICENSE` committed at the repository root, as decided in §4 item 5.
- [ ] **Name and branding.** Check that "XSphereOS" and its boot theme do not conflict with an existing mark or project. Resolve the branding part of open question 6.
- [ ] **Third-party material.** Confirm every file in the repository is original or carries its licence notice. Confirm that `docs/REFERENCES.md` describes external projects without copying their content.

**History and metadata audit**

- [x] **Secret scan across all history.** Run `gitleaks` over every branch and every commit, not only the PR diff. Any finding means the secret is rotated, and the history is rewritten *before* publication.
  - 2026-11-22: `gitleaks git --log-opts=--all` scanned 67 commits on all remote branches. No leaks found. Run it again immediately before the switch to cover later commits.
- [ ] **Issues, PRs, comments, and Actions logs.** Review them all. They become public along with the code. Anything that belongs in `xspherede-security` is moved there, and the original is edited or deleted.
- [ ] **Project `#5`.** Decide whether `XSphereOS — Roadmap` becomes public along with the repository, or stays private.
- [ ] **Commit author identity.** Accept that commit author names and e-mail addresses become public, or rewrite them to a noreply address before publication.
- [ ] **Stale branches.** Delete remote branches that should not be published (for example `backup/*`, abandoned experiments).
  - 2026-11-22: `backup/*` exists only locally and was never pushed. Remote branches whose PRs are already merged: `ci/code-security-reviewers` (`#18`), `claude/adr-009-renumber-accepted` (`#21`), `claude/planning-progress-66bfed` (`#22`), `claude/project-progress-review-2c45ab` (`#20`). Delete them, and enable *Automatically delete head branches* in the repository settings.

**Repository hygiene**

- [x] **`SECURITY.md`.** Added, as `ENGINEERING-PLAN.md` §5.3 already assumes, with private reporting through GitHub and e-mail.
- [ ] **Private vulnerability reporting.** Enable it in the repository settings right after the visibility switch. GitHub does not offer it on this private repository, so the button that `SECURITY.md` links to does not work until then.
- [ ] **GitHub protections.** Enable secret scanning and push protection, and protect `main` as in `ENGINEERING-PLAN.md` §5.3 and rollout step 1.
- [ ] **Workflow review for public triggers.** Confirm no workflow runs untrusted fork code with secrets or write permissions (`pull_request_target`, self-hosted runners, `secrets.*` on fork PRs). Confirm third-party actions stay pinned by SHA. This includes the PR reviewers proposed in PR `#18`.
  - 2026-11-22 review of `ci.yml`, `claude-review.yml`, and `image-boot.yml` on `main`. No workflow uses `pull_request_target` or self-hosted runners. Default permissions are empty or read-only, every checkout sets `persist-credentials: false`, actions are pinned by SHA, and downloaded binaries (`actionlint`, `opengrep`) are checked by SHA-256. The Claude jobs run only for same-repository PRs or for `@claude` mentions from owners, members, and collaborators, with `allow_fork_prs: false`, and fork PRs do not receive secrets. `image-boot.yml` builds fork code with `sudo` only on ephemeral GitHub-hosted runners, with no secrets.
  - Remaining: drop `id-token: write` from both Claude jobs, since no OIDC provider is configured. After the switch, set *Require approval for all external contributors* for fork PR workflow runs, so that the 45-minute boot job does not run unreviewed.
- [ ] **Wording.** Update text that says the repository is private (`README.md`, `docs/ARCHITECTURE.md`, ADR-001, ADR-003, `ENGINEERING-PLAN.md` §5.3). Re-verify the claims about other distributions in `docs/BOOT-EXPERIENCE.md` §10, which that section itself flags for re-checking "before any public statement".
- [x] **`CONTRIBUTING.md`** (short): how to build, how to run the tests, the PR template, and the security-impact rule.

## 6. Consequences and Trade-offs

- **Pros:** No CI cost for the boot gates. Outside review and bug reports from `M0` onward. Consistent visibility with `xspherede`. Forces the licence and naming decisions while they are still cheap.
- **Cons:** Unfinished work is visible before `M2`. Publication cannot be undone. Small ongoing overhead: triaging outside issues and PRs, and reviewing workflows with fork PRs in mind.
- **Neutral:** Development practice does not change. The private-tracker rule for security-impact notes in PRs already assumes public PRs.

## 7. Documents to Update on Acceptance

- ADR-003 §4: limit the "remain strictly private" clause to `xspherede-security`, and note that it is superseded for `xsphereos` by this ADR.
- ADR-001 §7: replace with the Project `#5` decision from §5.
- `ENGINEERING-PLAN.md` §5.3: "`xspherede-security` stays private; `xsphereos` is public per ADR-010."
- `README.md` and `docs/ARCHITECTURE.md`: repository table and layer labels.

## 8. Security and Compliance

- Publishing `xsphereos` does not change the security model. Isolation is still not an enforced boundary until `M5`, and the docs and UI keep saying so.
- No threat models, audit findings, exploit details, or hardening specifics may be committed to `xsphereos`. They go to `xspherede-security`. Security fixes land with neutral, functional commit messages (`ENGINEERING-PLAN.md` §5.3).
- Vulnerability reports go through `SECURITY.md`, never public issues.

## 9. Open Questions

1. Whether Project `#5` becomes public.
2. Whether to rewrite commit author e-mails to a noreply address before publication.
