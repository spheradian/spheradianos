# XSphereOS Code & Security Review Guidelines

Review every pull request against the rules in `docs/ENGINEERING-PLAN.md` and accepted ADRs under `docs/adr/`.

## 1. Security & Privilege Boundaries
- **Chroot & initramfs scripts (`config/hooks/`, `config/includes.chroot/`):**
  - Initramfs hooks must declare `PREREQ="plymouth"` (where applicable) and fail immediately if `${DESTDIR:-}` is unset or empty, preventing host/root filesystem mutation.
  - Require strict POSIX `sh` quoting, `set -eu`, and zero unvalidated path interpolation or `eval` / `curl | sh` / world-writable permissions (`chmod 777`, `a+rwx`, `o+w`).
- **`systemd` units (`config/includes.chroot/etc/systemd/system/`):**
  - Check ordering, least privilege, absolute `ExecStart=` paths, and ensure fault-injection units remain strictly gated by `ConditionKernelCommandLine=`.
- **GitHub Actions (`.github/workflows/`):**
  - Pin every third-party action by full 40-character commit SHA.
  - Enforce minimal per-job `permissions:` (`contents: read` by default), `persist-credentials: false` on checkout, and zero template injection (`${{ ... }}` directly inside `run:`).
- **Secrets & repository isolation (`ADR-003`):**
  - Reject any credentials, tokens, or private keys.
  - Never commit threat models, exploit details, or audit specifics belonging to `mendsec/xspherede-security`; PR security notes must stay neutral (`None` or `See private tracker`).

## 2. Distribution & ADR Invariants
- **Minimal Debian `trixie` (`auto/config`, `config/package-lists/`):**
  - Preserve `--distribution trixie`, `--variant=minbase`, `--apt-recommends false`, `--debian-installer none`, `--chroot-squashfs-compression-type zstd` (`ADR-004`), and `--firmware-binary false` / `--firmware-chroot false` (`ADR-007`).
  - Every package line in `config/package-lists/*.list.chroot` must have a one-line `#` justification comment directly above it and zero inline `#` comments; forbid `task-`, `gnome-`, `kde-`, `plasma-`, `xfce4`, `lxqt`, `lxde`, `mate-`, `cinnamon`, `budgie-`, `enlightenment`, `xorg`, `xwayland`, `xserver-xorg`, `kali-`, `parrot-`, `indi-`, `libindi`, heavyweight display managers (`gdm3`, `sddm`, `lightdm`, `lxdm`, `xdm`), and telemetry, cleartext, remote-daemon, or opaque-proxy packages enforced by `scripts/audit_packages.py` and `tests/test_distro_config.py`.
- **Boot experience (`ADR-002`, `docs/BOOT-EXPERIENCE.md`):**
  - Preserve zero-prompt bootloader defaults (`timeout=0`, hidden menu, no audio beep) and honest Plymouth failure reporting (`boot-watch`, `xsphere.motion=reduced`, no hidden errors).

## 3. Code Quality & Verification
- Keep scripts single-purpose, POSIX `sh` (`shellcheck` and `shfmt` clean), and standard-library Python where shipped/tested.
- Verify that behavior changes include unit or regression tests under `tests/`, and documentation describes existing implemented behavior only (`docs/ENGINEERING-PLAN.md` §2.4).

## 4. Review Output Format
- Start with a concise overall summary and merge readiness verdict.
- Group findings by severity (`Critical`, `High`, `Medium`, `Low`), citing file/line, concrete impact (including CWE identifier for security issues), and a minimal fix.
- Skip formatting or lint nitpicks already enforced by Ruff, ShellCheck, shfmt, actionlint, zizmor, Opengrep, and Gitleaks.
