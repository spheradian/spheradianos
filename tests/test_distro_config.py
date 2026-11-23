"""Static assertions for XSphereOS live-build configuration and package manifests."""

import contextlib
import importlib.util
import io
import os
import shlex
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def load_audit_packages():
    path = REPO_ROOT / "scripts" / "audit_packages.py"
    spec = importlib.util.spec_from_file_location("audit_packages", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


audit_packages = load_audit_packages()


class DistroConfigTests(unittest.TestCase):
    def test_auto_config_enforces_minimal_debian_trixie(self) -> None:
        auto_config = (REPO_ROOT / "auto" / "config").read_text(encoding="utf-8")
        self.assertIn("--distribution trixie", auto_config)
        self.assertIn("--architectures amd64", auto_config)
        self.assertIn("--variant=minbase", auto_config)
        self.assertIn("--apt-recommends false", auto_config)
        self.assertIn("--apt-indices false", auto_config)
        self.assertIn("--updates true", auto_config)
        self.assertIn("--security true", auto_config)
        self.assertIn("--debian-installer none", auto_config)
        self.assertIn("--firmware-binary false", auto_config)
        self.assertIn("--firmware-chroot false", auto_config)
        self.assertIn("--chroot-squashfs-compression-type zstd", auto_config)
        self.assertIn("username=xsphere", auto_config)
        self.assertNotIn("username=root", auto_config)

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

    def test_m1_kiosk_session_and_fallback_configured(self) -> None:
        manifest = (REPO_ROOT / "config" / "package-lists" / "xsphereos-base.list.chroot").read_text(
            encoding="utf-8"
        )
        for pkg in ("seatd", "cage", "mesa-vulkan-drivers", "libegl-mesa0", "foot"):
            self.assertIn(pkg, manifest)
        # Without pam_systemd the session gets no logind session and no
        # /run/user/<uid>, and the kiosk restarts in a loop (minbase installs
        # no Recommends, so it must be listed).
        self.assertIn("\nlibpam-systemd\n", manifest)

        service = (
            REPO_ROOT
            / "config"
            / "includes.chroot"
            / "etc"
            / "systemd"
            / "system"
            / "xsphere-session.service"
        ).read_text(encoding="utf-8")
        self.assertIn("Slice=xsphere-session.slice", service)
        self.assertIn("ConditionKernelCommandLine=!xsphere.session=console", service)
        self.assertIn("User=xsphere", service)
        # Conflicts= is applied when the boot transaction is built, before the
        # condition is checked, so it would stop the tty1 getty even when the
        # session is then skipped (xsphere.session=console): no shell at all.
        self.assertNotIn("Conflicts=getty@tty1.service", service)

        # The same kernel switch selects exactly one owner of tty1.
        getty_condition = (
            REPO_ROOT
            / "config"
            / "includes.chroot"
            / "etc"
            / "systemd"
            / "system"
            / "getty@tty1.service.d"
            / "xsphere-session.conf"
        ).read_text(encoding="utf-8")
        self.assertIn("[Unit]", getty_condition)
        self.assertIn("ConditionKernelCommandLine=xsphere.session=console", getty_condition)

        launcher = (
            REPO_ROOT / "config" / "includes.chroot" / "usr" / "lib" / "xsphereos" / "xsphere-session"
        ).read_text(encoding="utf-8")
        self.assertIn("cage -s -- /usr/bin/xspherede", launcher)
        self.assertIn("exec cage -s -- /usr/bin/foot", launcher)
        # scripts/boot-test.py cuts xspherede's output out of the journal between these.
        self.assertIn("xsphere-session: starting xspherede", launcher)
        self.assertIn("falling back to foot", launcher)

    def test_session_journal_reaches_the_boot_test_only_inside_its_qemu(self) -> None:
        systemd_dir = REPO_ROOT / "config" / "includes.chroot" / "etc" / "systemd" / "system"
        unit = (systemd_dir / "xsphereos-test-journal.service").read_text(encoding="utf-8")
        self.assertIn("ConditionVirtualization=vm", unit)
        self.assertIn("ExecStart=/usr/lib/xsphereos/test-journal", unit)
        wanted = systemd_dir / "multi-user.target.wants" / "xsphereos-test-journal.service"
        self.assertTrue(wanted.is_symlink())

        script = (
            REPO_ROOT / "config" / "includes.chroot" / "usr" / "lib" / "xsphereos" / "test-journal"
        ).read_text(encoding="utf-8")
        # Gated on a fw_cfg entry that only scripts/boot-test.py gives its QEMU guest.
        self.assertIn("/sys/firmware/qemu_fw_cfg/by_name/opt/xsphereos/test-journal/raw", script)
        self.assertIn('[ -e "$flag" ] || exit 0', script)
        self.assertIn("-u xsphere-session.service", script)
        self.assertIn(">/dev/ttyS0", script)
        self.assertIn("status --full xsphere-session.service", script)
        # The session's own output is logged under its user's logind scope.
        self.assertIn('_UID="$(id -u xsphere)"', script)

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
                self.assertFalse(
                    audit_packages.is_forbidden_package(stripped),
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
        self.assertIn("default live-amd64", isolinux_cfg)
        self.assertNotIn("vesamenu.c32", isolinux_cfg)
        self.assertNotIn("timeout 0", isolinux_cfg)

        isolinux_live = (REPO_ROOT / "config" / "bootloaders" / "isolinux" / "live.cfg.in").read_text(
            encoding="utf-8"
        )
        self.assertIn("linux /live/vmlinuz", isolinux_live)
        self.assertIn("initrd /live/initrd.img", isolinux_live)
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

    def test_privacy_security_and_old_hardware_baseline(self) -> None:
        chroot_etc = REPO_ROOT / "config" / "includes.chroot" / "etc"
        apt_cfg = (chroot_etc / "apt" / "apt.conf.d" / "90xsphereos").read_text(encoding="utf-8")
        self.assertIn('APT::Install-Recommends "false";', apt_cfg)
        self.assertIn('APT::Install-Suggests "false";', apt_cfg)

        base_list_path = REPO_ROOT / "config" / "package-lists" / "xsphereos-base.list.chroot"
        base_packages = {line.strip() for line in base_list_path.read_text(encoding="utf-8").splitlines()}
        self.assertIn("firmware-linux-free", base_packages)

        autologin_path = chroot_etc / "systemd" / "system" / "getty@tty1.service.d" / "autologin.conf"
        autologin_cfg = autologin_path.read_text(encoding="utf-8")
        self.assertIn("--autologin xsphere", autologin_cfg)
        self.assertNotIn("--autologin root", autologin_cfg)

        sudoers_dir = chroot_etc / "sudoers.d"
        if sudoers_dir.is_dir():
            for path in sorted(sudoers_dir.rglob("*")):
                if path.is_file():
                    self.assertNotIn(
                        "NOPASSWD",
                        path.read_text(encoding="utf-8"),
                        f"Passwordless sudo rule is forbidden: {path.name}",
                    )

        systemd_dir = chroot_etc / "systemd" / "system"
        remote_units = {"ssh.service", "sshd.service", "telnet.socket", "telnetd.service"}
        for path in sorted(systemd_dir.rglob("*")):
            self.assertNotIn(path.name, remote_units, f"Forbidden remote service unit: {path}")

    def test_audit_packages_flags_forbidden_and_accepts_clean_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            clean = tmp / "clean.packages"
            clean_lines = (
                "base-files\t13.8",
                "firmware-linux-free\t20241210-2",
                "libx11-6:amd64\t2:1.8.12-1",
                "plymouth\t24.004.60-5",
                "zstd\t1.5.7+dfsg-1",
            )
            clean.write_text("\n".join(clean_lines) + "\n", encoding="utf-8")
            self.assertEqual(audit_packages.audit_manifest_file(clean), (5, []))
            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                self.assertEqual(audit_packages.main([str(clean)]), 0)

            tainted = tmp / "tainted.packages"
            tainted_lines = (
                "indi-dsi\t0.4",
                "libindidriver1:amd64\t1.9.9",
                "xwayland\t2:24.1",
                "openssh-server\t1:9.9",
                "popularity-contest\t1.76",
                "proxychains4\t4.17",
                "kali-linux-core\t2025.1",
                "plasma-desktop\t4:6.3",
                "xfce4\t4.20",
                "lxqt-core\t33",
                "lxde\t13",
                "mate-desktop\t1.26",
                "cinnamon\t6.4",
                "budgie-desktop\t10.9",
                "enlightenment\t0.27",
                "gdm3\t48.0",
                "sddm\t0.21",
                "lightdm\t1.32",
                "lxdm\t0.5.3",
                "xdm\t1:1.1.11",
            )
            tainted.write_text("\n".join(tainted_lines) + "\n", encoding="utf-8")
            expected = [
                "budgie-desktop",
                "cinnamon",
                "enlightenment",
                "gdm3",
                "indi-dsi",
                "kali-linux-core",
                "libindidriver1",
                "lightdm",
                "lxde",
                "lxdm",
                "lxqt-core",
                "mate-desktop",
                "openssh-server",
                "plasma-desktop",
                "popularity-contest",
                "proxychains4",
                "sddm",
                "xdm",
                "xfce4",
                "xwayland",
            ]
            self.assertEqual(audit_packages.audit_manifest_file(tainted), (20, expected))
            stderr = io.StringIO()
            with contextlib.redirect_stderr(stderr):
                self.assertEqual(audit_packages.main([str(tainted)]), 1)
                self.assertEqual(audit_packages.main([str(tmp / "missing.packages")]), 2)


if __name__ == "__main__":
    unittest.main()
