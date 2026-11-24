# Contributing to XSphereOS

Thanks for your interest in XSphereOS. This repository holds the Debian `live-build` recipe, the boot experience, and the test and release tooling for the distribution. The desktop compositor lives in [`spheradian/spheradian`](https://github.com/spheradian/spheradian), and contributions to the compositor go there.

XSphereOS is in early development and has a single maintainer. Small, focused changes are the easiest to review. Everyone taking part is expected to follow the [Code of Conduct](CODE_OF_CONDUCT.md).

## Before You Start

- **Security issues:** do not open a public issue. Follow [SECURITY.md](SECURITY.md).
- **Bugs:** open an issue with the *Bug report* template. Include the commit SHA, the boot mode (BIOS or UEFI), and what the boot test or console showed.
- **Larger changes:** open an issue first so the approach can be agreed before you write code. This includes a new package, a new boot behavior, or a change to `auto/config`. Decisions that are hard to reverse need an ADR: use the *ADR Proposal* template and see [docs/adr/](docs/adr/README.md).
- **Where to start:** issues labeled `good first issue` are small and self-contained. Comment on one before you begin, so two people do not do the same work.
- **Roadmap:** the milestones (`M0`–`M5`, `B0`–`B7`) are in the [README](README.md#roadmap). Work that jumps ahead of an open milestone gate may be asked to wait.

## Building and Testing

You need a Debian host with root access. On other hosts, build in a container: see [Building & Running the Image](README.md#building--running-the-image).

```sh
sudo apt install live-build debootstrap squashfs-tools xorriso qemu-system-x86 ovmf shellcheck shfmt pre-commit
```

You do not need root, a Debian host, or an ISO build to contribute to Python, shell, docs, or CI changes: the static checks below are enough for those. Only changes that affect the image or the boot path need the build and boot tests.

Static checks need no root access. `pre-commit` runs the same set as the CI: `unittest`, `ruff`, `shellcheck`, and `shfmt`. The full list of commands is in the [README](README.md#static--security-checks-no-root-required).

```sh
pre-commit run --all-files
```

If your change affects the image or the boot path, build the ISO and run the boot tests:

```sh
sudo scripts/build.sh
scripts/boot-test.py
scripts/boot-test.py --reduced-motion
scripts/boot-test.py --uefi
```

If you touch the splash, the watchdog, or failure reporting, also run `--fault fail` and `--fault stall`. If you change `scripts/boot_timeline.py`, regenerate the theme with `scripts/gen-boot-assets.py`.

## Conventions

The full rules are in [docs/ENGINEERING-PLAN.md](docs/ENGINEERING-PLAN.md) (§3 TDD, §4 Clean Code). The ones that matter most for this repository:

- **Tests first** for any logic: timeline math, config assertions, boot-test expectations.
- **Shell:** POSIX `sh` with `set -eu`. Code must be clean under `shellcheck` and formatted with `shfmt`. Each script does one thing, takes arguments explicitly, and prints actionable errors. Logic that can live in a tested script does not go in a hook.
- **Configuration over code:** image options belong in `auto/config` and `config/package-lists/`.
- **Minimal image:** the base is Debian `minbase` with no `Recommends`. Every new package needs a one-line justification in its package list, and its size and package-count impact must be stated in the PR (`scripts/size-report.sh`).
- **Language:** code, comments, docs, and commit messages are in English.

## Commits and Pull Requests

- Use conventional-style commit messages in the imperative, for example `fix(scripts): …`, `feat(m1): …`, `docs(adr): …`, or `test: …`.
- Refactors and behavior changes go in separate commits.
- Open the PR against `main` and fill in the [pull request template](.github/PULL_REQUEST_TEMPLATE.md): what changed and why, how it was tested, and the **security-impact** note. Write "None", or "See private tracker" with no details.
- All CI checks must pass. This includes the static checks, `ruff`, `actionlint` and `zizmor`, `opengrep`, `gitleaks`, and the QEMU boot gate.
- Update the docs in the same PR when behavior changes.
- **Review time:** there is a single maintainer, so expect a first response within about one week. If a PR has had no reply after two weeks, a polite ping on the PR is welcome.
- The QEMU boot job is slow (about 45 minutes) and, for first-time contributors, starts only after a maintainer approves the workflow run.

## License

XSphereOS is released under the [Apache License 2.0](LICENSE). By submitting a contribution, you agree that it is licensed under the same terms (Apache License 2.0, section 5).
