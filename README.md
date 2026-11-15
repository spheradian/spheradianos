# XSphereOS

Private repository for the XSphereOS distribution: a minimal Debian-based live image that boots straight into the XSphereDE spherical desktop.

Status: pre-implementation. See [docs/DISTRO-DESIGN.md](docs/DISTRO-DESIGN.md).

Security analysis and hardening notes live in the separate private `xspherede-security` repository, not here.

## Building the M0 image

Requirements (Debian or Ubuntu host, root access):

```sh
sudo apt install live-build debootstrap squashfs-tools xorriso qemu-system-x86 ovmf
```

```sh
sudo scripts/build.sh      # produces an ISO in the repository root
scripts/run-qemu.sh        # BIOS boot in QEMU
scripts/run-qemu.sh --uefi # UEFI boot (needs OVMF)
```

On a non-Debian host (for example Ubuntu, whose `live-build` is an old fork that rejects the options in `auto/config`), build inside a Debian container instead; only `podman` is needed on the host:

```sh
sudo scripts/build-in-container.sh
```

Layout:

- `auto/` live-build entry points; `auto/config` holds all image options (Debian `trixie`, `minbase`, no recommends).
- `config/package-lists/` the package manifest, one justification per package.
- `config/hooks/` and `config/includes.chroot/` image customization.
- `scripts/` build, QEMU, and size-report helpers.

## Boot splash

The `xsphere` Plymouth theme is wired into the recipe; see [docs/BOOT-EXPERIENCE.md](docs/BOOT-EXPERIENCE.md). A seed of light appears and its glow reveals a lattice of dots on a slowly turning sphere. Regions of the lattice wake, each in its colour, as systemd reports real boot milestones. Nothing is stored as frames: tiny images are placed by arithmetic from `scripts/boot_timeline.py`. Both theme variants total about 18 KiB. If a unit fails or the boot stalls for 20 s, the splash ends and the cause is printed in plain text.

```sh
python3 -m unittest discover -s tests -v   # static checks and timeline tests, no root needed
scripts/gen-boot-assets.py                 # regenerate the theme (images and scripts)
scripts/boot-test.py                       # boots the ISO headless in QEMU and checks the splash contract
scripts/boot-test.py --reduced-motion      # same, with the still-frame variant
scripts/boot-test.py --fault fail          # injects a failed unit: expects a plain-text report
scripts/boot-test.py --fault stall         # injects a stalled boot: expects the watchdog's text at 20 s
```

Kernel command line switches: `xsphere.motion=reduced` shows one still frame instead of the animation; removing `splash` or adding `plymouth.enable=0` boots in text. Press Esc during boot for text details.

M0 is done when the ISO boots in QEMU to an autologged-in shell and the package count and ISO size are recorded in the design document.
