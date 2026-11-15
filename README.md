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

## Boot splash (B1 prototype)

A static Plymouth theme (`xsphere`) is wired into the recipe; see [docs/BOOT-EXPERIENCE.md](docs/BOOT-EXPERIENCE.md). It has static checks only and has not been booted yet, because the image has never been built.

```sh
python3 -m unittest discover -s tests -v   # static checks, no root needed
scripts/gen-boot-assets.py                 # regenerate the splash image
```

To boot without the splash, remove `splash` from the kernel command line or add `plymouth.enable=0`. Press Esc during boot for text details.

M0 is done when the ISO boots in QEMU to an autologged-in shell and the package count and ISO size are recorded in the design document.
