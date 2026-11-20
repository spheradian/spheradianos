"""Static assertions for XSphereOS live-build configuration and package manifests."""

from pathlib import Path
import unittest


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
            REPO_ROOT
            / "config"
            / "includes.chroot"
            / "etc"
            / "systemd"
            / "zram-generator.conf"
        ).read_text(encoding="utf-8")
        self.assertIn("compression-algorithm = zstd", zram_cfg)

        slice_cfg = (
            REPO_ROOT
            / "config"
            / "includes.chroot"
            / "etc"
            / "systemd"
            / "system"
            / "xsphere-session.slice"
        ).read_text(encoding="utf-8")
        self.assertIn("CPUWeight=500", slice_cfg)
        self.assertIn("MemoryLow=", slice_cfg)

    def test_package_lists_have_justifications_and_no_forbidden_packages(self) -> None:
        lists_dir = REPO_ROOT / "config" / "package-lists"
        list_files = sorted(
            p for p in lists_dir.glob("*.list.chroot") if p.name != "live.list.chroot"
        )
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
                    f"{path.name}:{lineno} package '{stripped}' must have a justification comment directly above it",
                )
                for prefix in FORBIDDEN_PREFIXES:
                    self.assertFalse(
                        stripped.startswith(prefix),
                        f"{path.name}:{lineno} forbidden package '{stripped}'",
                    )
                prev_line = stripped

    def test_bootloaders_enforce_zero_prompt_direct_boot(self) -> None:
        grub_cfg = (
            REPO_ROOT / "config" / "bootloaders" / "grub-pc" / "config.cfg"
        ).read_text(encoding="utf-8")
        self.assertIn("set default=0", grub_cfg)
        self.assertIn("set timeout=0", grub_cfg)
        self.assertIn("set timeout_style=hidden", grub_cfg)
        self.assertNotIn("play ", grub_cfg)

        isolinux_cfg = (
            REPO_ROOT / "config" / "bootloaders" / "isolinux" / "isolinux.cfg"
        ).read_text(encoding="utf-8")
        self.assertIn("default live-amd64", isolinux_cfg)
        self.assertNotIn("vesamenu.c32", isolinux_cfg)
        self.assertNotIn("timeout 0", isolinux_cfg)

        isolinux_live = (
            REPO_ROOT / "config" / "bootloaders" / "isolinux" / "live.cfg.in"
        ).read_text(encoding="utf-8")
        self.assertIn("linux /live/vmlinuz", isolinux_live)
        self.assertIn("initrd /live/initrd.img", isolinux_live)
        self.assertNotIn("@LINUX_LIVE@", isolinux_live)
        self.assertNotIn("@INITRD_LIVE@", isolinux_live)


if __name__ == "__main__":
    unittest.main()
