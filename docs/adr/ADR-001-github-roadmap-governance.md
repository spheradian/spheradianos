# ADR-001: GitHub Roadmap, Governance, and Continuity Structure

**Date:** 2026-11-18  
**Status:** Accepted  
**Author:** Senior Software Architect  
**Approver:** Fábio Mendes (`mendsec`)  
**Confidence:** High  
**Impact:** Medium  
**Reversibility:** Easy  

## 1. Executive Summary

`spheradian/spheradianos` had design documentation and local tests but no GitHub issue tracking, milestones, or project board. We decided to structure project continuity natively on GitHub using Milestones (`M0`–`M5`), granular Issues, area/type/priority Labels, and a linked GitHub Project (`SpheradianOS — Roadmap`).

## 2. Context and Problem

Without decomposed milestones and acceptance criteria, M1/M2 work risked starting before M0 quality gates (size/package budget, static CI checks, branch protection) were closed, and open design questions remained untracked.

## 3. Scope

- **In scope:** GitHub Milestones (`M0`–`M5`), Issues (`#1`–`#14`), Labels, and the `SpheradianOS — Roadmap` Project (organization Project `#2`, originally personal Project `#5`).
- **Out of scope:** Detailed threat models and hardening specifics, which remain in the private `spheradian/security` repository.

## 4. Options Considered

- **Option A (Chosen):** Native GitHub Milestones + Issues + Labels + GitHub Project v2.
- **Option B:** Markdown-only tracking inside `docs/`.
- **Option C:** External issue tracker (Linear/Jira).

## 5. Decision

Adopt **Option A**. All roadmap deliverables are tracked as Issues assigned to Milestones `M0` through `M5` and organized in `SpheradianOS — Roadmap`. Open architectural choices are tracked with the `type:adr` label (`#8`, `#11`) and resolved before adding new packages to `config/package-lists/`.

## 6. Consequences and Trade-offs

- **Pros:** Direct PR-to-issue linking (`Closes #N`), zero extra tooling cost, clear gate ordering.
- **Cons:** Requires discipline to keep project status updated on PR merges.

## 7. Security and Compliance

~~`spheradian/spheradianos` and the roadmap Project remain private.~~ Superseded by [ADR-010](ADR-010-spheradianos-public-visibility.md): `spheradian/spheradianos` becomes public after M0, and ADR-010 makes the roadmap Project (organization Project `#2`) public as well. No sensitive security findings from `spheradian/security` are mirrored in GitHub Issues.
