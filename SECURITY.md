# Security Policy

## Supported Versions

XSphereOS has no released images yet. Only the current `main` branch is supported. Signed `testing` and `stable` releases arrive with Milestone `M4`. This table will list them once they exist.

| Version | Supported          |
| ------- | ------------------ |
| `main`  | :white_check_mark: |

## Scope

XSphereOS is in early development. Until Milestone **M5** is complete, trust-domain isolation in XSphereDE is **not** an enforced security boundary. See [Current Status](README.md#current-status) in the README. Reports are welcome for any defect in what this repository builds or runs, for example:

- **Image recipe and contents:** `auto/`, `config/package-lists/`, `config/hooks/`, and files shipped through `config/includes.chroot/` (APT sources, `systemd` units, `initramfs-tools`, Plymouth, `profile.d`).
- **Boot path:** GRUB and ISOLINUX templates in `config/bootloaders/`, and the autologin and boot-experience units (watchdog, failure reporting).
- **Build and test tooling:** `scripts/` (`build.sh`, `build-in-container.sh`, `run-qemu.sh`, `boot-test.py`, the asset generators).
- **CI and supply chain:** `.github/workflows/`, pinned actions, and how packages and artifacts are fetched.

Vulnerabilities in Debian packages that the image only ships unchanged should go to the [Debian Security Team](https://www.debian.org/security/). Tell us about them as well if the XSphereOS default configuration makes them worse. Issues in the desktop compositor go to [`spheradian/spheradian`](https://github.com/spheradian/spheradian/security/policy).

## Reporting a Vulnerability

Please **do not** report security vulnerabilities through public GitHub issues, discussions, or pull requests.

### Private Reporting Channels

1. **GitHub Private Vulnerability Reporting (Preferred):**
   Use the [Report a vulnerability](https://github.com/spheradian/spheradianos/security/advisories/new) button under the **Security** tab of this repository to open a confidential security advisory.
2. **Direct Email:**
   Send a detailed report to **fabiomendes@mailfence.com** with:
   - Description of the vulnerability and the affected component (see [Scope](#scope)).
   - Steps to reproduce or a proof of concept, including the image build (commit SHA) and whether it boots under BIOS or UEFI.
   - Potential impact and suggested mitigation, if any.

### Response Timeline and Governance

- **Acknowledgment:** within **48 hours** of receipt.
- **Triage and assessment:** within **7 days**.
- **Coordinated disclosure:** threat models, audit findings, and remediation tracking are kept in a dedicated **private security repository** until a fix is verified and released. Fixes land in this repository with neutral, functional commit messages. Advisories are published after the fix is available.
