"""Static assertions for XSphereOS live-build configuration and package manifests."""

import os
import shlex
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
FORBIDDEN_PREFIXES = ("task-", "gnome-", "kde-", "xorg", "xwayland")


class DistroConfigTests(unittest.TestCase):
    def test_auto_config_enforces_minimal_debian_trixie(self) -> None:
        auto_config = (REPO_ROOT / "auto" / "config").read_text(encoding="utf-8")
        self.assertIn("--distribution trixie", auto_config)
        self.assertIn("--variant=minbase", auto_config)
        self.assertIn("--apt-recommends false", auto_config)
        self.assertIn("--debian-installer none", auto_config)
        self.assertIn("--chroot-squashfs-compression-type zstd", auto_config)

    def test_console_grade_fluidity_config_exists(self) -> None:
        zram_cfg = (
            REPO_ROOT / "config" / "includes.chroot" / "etc" / "systemd" / "zram-generator.conf"
        ).read_text(encoding="utf-8")
        self.assertIn("compression-algorithm = zstd", zram_cfg)

        slice_cfg = (
            REPO_ROOT / "config" / "includes.chroot" / "etc" / "systemd" / "system" / "xsphere-session.slice"
        ).read_text(encoding="utf-8")
        self.assertIn("CPUWeight=500", slice_cfg)
        self.assertIn("MemoryLow=", slice_cfg)

    def test_package_lists_have_justifications_and_no_forbidden_packages(self) -> None:
        lists_dir = REPO_ROOT / "config" / "package-lists"
        list_files = sorted(p for p in lists_dir.glob("*.list.chroot") if p.name != "live.list.chroot")
        self.assertTrue(list_files, "Expected at least one .list.chroot file")

        for path in list_files:
            lines = path.read_text(encoding="utf-8").splitlines()
            prev_line = ""
            for lineno, raw in enumerate(lines, start=1):
                stripped = raw.strip()
                if not stripped or stripped.startswith("#"):
                    prev_line = stripped
                    continue
                self.assertNotIn(
                    "#",
                    stripped,
                    f"{path.name}:{lineno} has an inline comment (not allowed by live-build)",
                )
                self.assertTrue(
                    prev_line.startswith("#") and len(prev_line) > 2,
                    f"{path.name}:{lineno} package '{stripped}' must have a "
                    "justification comment directly above it",
                )
                for prefix in FORBIDDEN_PREFIXES:
                    self.assertFalse(
                        stripped.startswith(prefix),
                        f"{path.name}:{lineno} forbidden package '{stripped}'",
                    )
                prev_line = stripped

    def test_bootloaders_enforce_zero_prompt_direct_boot(self) -> None:
        grub_cfg = (REPO_ROOT / "config" / "bootloaders" / "grub-pc" / "config.cfg").read_text(
            encoding="utf-8"
        )
        self.assertIn("set default=0", grub_cfg)
        self.assertIn("set timeout=0", grub_cfg)
        self.assertIn("set timeout_style=hidden", grub_cfg)
        self.assertNotIn("play ", grub_cfg)

        isolinux_cfg = (REPO_ROOT / "config" / "bootloaders" / "isolinux" / "isolinux.cfg").read_text(
            encoding="utf-8"
        )
        directives = [
            line.split("#", 1)[0].strip()
            for line in isolinux_cfg.splitlines()
            if line.split("#", 1)[0].strip()
        ]
        self.assertIn("default live-amd64", directives)
        self.assertNotIn("timeout 0", directives)
        self.assertNotIn("prompt 1", directives)
        # ADR-002 amendment: vesamenu only as a hidden, timed screen, never blocking.
        self.assertIn("ui vesamenu.c32", directives)
        self.assertIn("menu hidden", directives)
        self.assertIn("timeout 5", directives)

        isolinux_live = (REPO_ROOT / "config" / "bootloaders" / "isolinux" / "live.cfg.in").read_text(
            encoding="utf-8"
        )
        self.assertIn("linux /live/vmlinuz", isolinux_live)
        self.assertIn("initrd /live/initrd.img", isolinux_live)
        # The default entry keeps the bootloader's graphics mode, so no text-mode
        # cursor shows while the kernel loads (BOOT-EXPERIENCE.md 2).
        default_entry = isolinux_live.split("label live-amd64-failsafe")[0]
        self.assertIn("append @APPEND_LIVE@ vga=current", default_entry)
        self.assertNotIn("@LINUX_LIVE@", isolinux_live)
        self.assertNotIn("@INITRD_LIVE@", isolinux_live)

    @staticmethod
    def _parse_unit_sections(path: Path) -> dict[str, list[tuple[str, str]]]:
        sections: dict[str, list[tuple[str, str]]] = {}
        current: str | None = None
        for raw in path.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith(("#", ";")):
                continue
            if line.startswith("[") and line.endswith("]"):
                current = line[1:-1].strip()
                sections.setdefault(current, [])
                continue
            if current is not None and "=" in line:
                key, value = line.split("=", 1)
                sections[current].append((key.strip(), value.strip()))
        return sections

    def test_systemd_units_are_valid_and_safe(self) -> None:
        chroot_root = REPO_ROOT / "config" / "includes.chroot"
        systemd_dir = chroot_root / "etc" / "systemd" / "system"

        services = sorted(p for p in systemd_dir.glob("*.service") if not p.is_symlink())
        slices = sorted(p for p in systemd_dir.glob("*.slice") if not p.is_symlink())
        self.assertTrue(services, "Expected at least one .service unit")
        self.assertTrue(slices, "Expected at least one .slice unit")

        for unit_path in services:
            sections = self._parse_unit_sections(unit_path)
            self.assertIn("Unit", sections, f"{unit_path.name} missing [Unit]")
            self.assertIn("Service", sections, f"{unit_path.name} missing [Service]")
            unit_entries = dict(sections["Unit"])
            self.assertTrue(unit_entries.get("Description"), f"{unit_path.name} missing Description=")

            exec_starts = [val for key, val in sections["Service"] if key == "ExecStart" and val]
            self.assertTrue(exec_starts, f"{unit_path.name} missing ExecStart=")
            for raw_cmd in exec_starts:
                cmd = raw_cmd.lstrip("@-:!+")
                argv = shlex.split(cmd)
                self.assertTrue(argv, f"{unit_path.name} has empty ExecStart=")
                exe = argv[0]
                self.assertTrue(
                    exe.startswith("/"),
                    f"{unit_path.name} ExecStart must use an absolute path: {raw_cmd}",
                )
                self.assertFalse(
                    Path(exe).name in {"sh", "bash", "dash"} and "-c" in argv[1:],
                    f"{unit_path.name} ExecStart must not invoke an inline shell: {raw_cmd}",
                )
                if exe.startswith(("/usr/lib/xsphereos/", "/usr/local/")):
                    target = chroot_root / exe.lstrip("/")
                    self.assertTrue(target.is_file(), f"{unit_path.name} missing ExecStart target {exe}")
                    self.assertTrue(
                        os.access(target, os.X_OK),
                        f"{unit_path.name} ExecStart target {exe} is not executable",
                    )

        for slice_path in slices:
            sections = self._parse_unit_sections(slice_path)
            self.assertIn("Unit", sections, f"{slice_path.name} missing [Unit]")
            self.assertIn("Slice", sections, f"{slice_path.name} missing [Slice]")
            unit_entries = dict(sections["Unit"])
            self.assertTrue(unit_entries.get("Description"), f"{slice_path.name} missing Description=")

        systemd_resolved = systemd_dir.resolve()
        for wants_dir in sorted(systemd_dir.glob("*.wants")):
            for link in sorted(wants_dir.iterdir()):
                self.assertTrue(link.is_symlink(), f"{link} should be a symlink")
                target = link.resolve()
                self.assertTrue(target.is_file(), f"Dangling systemd symlink: {link}")
                self.assertTrue(
                    target.is_relative_to(systemd_resolved),
                    f"Systemd symlink points outside systemd unit tree: {link} -> {target}",
                )


if __name__ == "__main__":
    unittest.main()
