# ADR-003: Repository Visibility Policy for `mendsec/spheradian`

**Date:** 2026-11-18  
**Status:** Accepted  
**Author:** Senior Software Architect  
**Approver:** Fábio Mendes (`mendsec`)  
**Confidence:** High  
**Impact:** Medium  
**Reversibility:** Easy  

## 1. Executive Summary

`mendsec/spheradian` is currently public under the MIT license, while `mendsec/spheradianos` and `mendsec/spheradian-security` are private. We decided to **keep `mendsec/spheradian` public**, preserving free unlimited CI/CD for the Rust compositor matrix and public auditability, while keeping distribution recipes and security threat models isolated in the two private repositories.

## 2. Context and Problem

`DISTRO-DESIGN.md` (§8) and `ENGINEERING-PLAN.md` (§5.3) separate the desktop compositor (`spheradian`) from the distribution (`spheradianos`) and security tracking (`spheradian-security`). Making `spheradian` private would unify repository privacy during early development, at the cost of private GitHub Actions minute quotas and extra token management for artifact consumption in `spheradianos`.

## 3. Options Considered

- **Option A (Chosen):** Keep `mendsec/spheradian` **public** (MIT license).
- **Option B:** Convert `mendsec/spheradian` to **private**.

## 4. Decision

Adopt **Option A**: `mendsec/spheradian` remains public under the MIT license; `mendsec/spheradianos` and `mendsec/spheradian-security` remain strictly private.

## 5. Consequences and Trade-offs

- **Pros:** Unlimited GitHub Actions minutes for Rust `stable`, MSRV 1.88, BSD cross-check, `cargo audit`, and coverage; simpler artifact consumption by `spheradianos`; public auditability of the desktop codebase.
- **Cons:** Pre-M2 desktop development remains publicly visible.

## 6. Security and Compliance

- No secrets, credentials, or detailed threat models from `spheradian-security` may be committed to `spheradian`.
- Documentation and UI must continue stating that trust-domain isolation is not an enforced security boundary until Milestone `M5` is complete.
