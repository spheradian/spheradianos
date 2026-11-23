"""Static checks for the boot splash (BOOT-EXPERIENCE.md, milestones B1 and B2).

Run from the repository root: python3 -m unittest discover -s tests -v
Standard library only, no GPU, no network, no root.
"""

import configparser
import importlib.util
import os
import re
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CHROOT = ROOT / "config" / "includes.chroot"
THEMES_IN_IMAGE = "/usr/share/plymouth/themes"
THEMES = CHROOT / THEMES_IN_IMAGE.lstrip("/")
INITRAMFS = CHROOT / "etc" / "initramfs-tools"
ANIMATED, STILL = "spheradian", "spheradian-still"
# Console-grade budget (docs/BOOT-EXPERIENCE.md 6.4): both themes together.
THEME_BUDGET_BYTES = 64 * 1024
AUDIO_SUFFIXES = {".wav", ".ogg", ".mp3", ".flac", ".opus"}


def read_ini(path):
    parser = configparser.ConfigParser()
    parser.optionxform = str
    parser.read_string(path.read_text())
    return parser


def boot_parameters():
    text = (ROOT / "auto" / "config").read_text()
    match = re.search(r'--bootappend-live "([^"]*)"', text)
    if not match:
        raise AssertionError("auto/config has no --bootappend-live option")
    return match.group(1).split()


def load_generator():
    path = ROOT / "scripts" / "gen-boot-assets.py"
    spec = importlib.util.spec_from_file_location("gen_boot_assets", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_timeline():
    path = ROOT / "scripts" / "boot_timeline.py"
    spec = importlib.util.spec_from_file_location("boot_timeline", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def theme_files():
    return [p for name in (ANIMATED, STILL) for p in (THEMES / name).rglob("*") if p.is_file()]


def script_of(name):
    return (THEMES / name / f"{name}.script").read_text()


class ThemeDefinition(unittest.TestCase):
    def test_both_themes_use_the_script_plugin_and_their_own_script(self):
        for name in (ANIMATED, STILL):
            theme = read_ini(THEMES / name / f"{name}.plymouth")
            self.assertEqual(theme["Plymouth Theme"]["ModuleName"], "script")
            self.assertTrue(theme["Plymouth Theme"]["Description"].strip())
            self.assertEqual(theme["script"]["ScriptFile"], f"{THEMES_IN_IMAGE}/{name}/{name}.script")

    def test_both_themes_share_one_image_directory(self):
        for name in (ANIMATED, STILL):
            theme = read_ini(THEMES / name / f"{name}.plymouth")
            self.assertEqual(theme["script"]["ImageDir"], f"{THEMES_IN_IMAGE}/{ANIMATED}")

    def test_daemon_selects_the_animated_theme_without_delay(self):
        daemon = read_ini(CHROOT / "etc" / "plymouth" / "plymouthd.conf")["Daemon"]
        self.assertEqual(daemon["Theme"], ANIMATED)
        self.assertEqual(daemon["ShowDelay"], "0")


class ThemeScript(unittest.TestCase):
    def test_every_image_the_scripts_load_exists(self):
        for name in (ANIMATED, STILL):
            images = re.findall(r'Image\("([^"]+)"\)', script_of(name))
            self.assertTrue(images, f"{name} loads no image")
            for image in images:
                self.assertTrue((THEMES / ANIMATED / image).is_file(), image)

    def test_only_the_animated_theme_animates(self):
        self.assertRegex(script_of(ANIMATED), r"(?m)^motion = 1;$")
        self.assertRegex(script_of(STILL), r"(?m)^motion = 0;$")

    def test_the_two_scripts_differ_only_in_the_motion_switch(self):
        animated = script_of(ANIMATED).replace("motion = 1;", "motion = 0;")
        self.assertEqual(animated, script_of(STILL))

    def test_background_is_true_black(self):
        for call in ("SetBackgroundTopColor", "SetBackgroundBottomColor"):
            self.assertRegex(script_of(ANIMATED), rf"Window\.{call}\s*\(\s*0\s*,\s*0\s*,\s*0\s*\)")

    def test_scripts_listen_for_every_real_boot_milestone(self):
        for name in (ANIMATED, STILL):
            script = script_of(name)
            self.assertIn("Plymouth.SetUpdateStatusFunction(status_update);", script)
            for index, (unit, _) in enumerate(load_timeline().MILESTONES):
                self.assertIn(f'milestone[{index}] = "{unit}";', script)

    def test_no_image_is_scaled_while_animating(self):
        # Scaling allocates; the per-frame functions may only move and fade sprites.
        script = script_of(ANIMATED)
        per_frame = script[script.index("fun place(") :]
        self.assertNotIn(".Scale(", per_frame)
        self.assertIsNone(re.search(r"(?<![A-Za-z])Image\(", per_frame))


class GeneratedFiles(unittest.TestCase):
    def test_committed_theme_matches_the_generator(self):
        expected = load_generator().theme_files()
        committed = {str(p.relative_to(THEMES)): p.read_bytes() for p in theme_files()}
        self.assertEqual(sorted(committed), sorted(expected))
        for name, data in expected.items():
            self.assertEqual(committed[name], data, f"{name} is stale; run gen-boot-assets.py")

    def test_themes_fit_the_size_budget(self):
        self.assertLessEqual(sum(p.stat().st_size for p in theme_files()), THEME_BUDGET_BYTES)

    def test_themes_ship_no_binary_audio_and_no_stored_frames(self):
        suffixes = [p.suffix.lower() for p in theme_files()]
        self.assertFalse(AUDIO_SUFFIXES & set(suffixes))
        # Motion is computed, not stored: a seed, a dot and one coloured dot per
        # region, never a frame sequence.
        self.assertEqual(suffixes.count(".png"), 2 + len(load_timeline().MILESTONES))
        for path in theme_files():
            if path.suffix == ".png":
                self.assertLess(path.stat().st_size, 4096, path.name)


class InitramfsIntegration(unittest.TestCase):
    TRIM = INITRAMFS / "hooks" / "spheradianos-splash-trim"
    THEMES_HOOK = INITRAMFS / "hooks" / "spheradianos-splash-themes"
    MOTION = INITRAMFS / "scripts" / "init-top" / "spheradianos-motion"

    def run_script(self, script, **variables):
        environment = {k: v for k, v in os.environ.items() if k != "DESTDIR"}
        environment.update(variables)
        return subprocess.run([str(script)], env=environment, capture_output=True, text=True)

    def test_scripts_are_executable(self):
        for script in (self.TRIM, self.THEMES_HOOK, self.MOTION):
            self.assertTrue(os.access(script, os.X_OK), script.name)

    def test_hooks_run_after_plymouth_and_refuse_to_run_without_a_destination(self):
        for hook in (self.TRIM, self.THEMES_HOOK):
            self.assertIn('PREREQ="plymouth"', hook.read_text())
            self.assertNotEqual(self.run_script(hook).returncode, 0)

    def test_trim_hook_removes_fonts_and_keeps_the_theme(self):
        with tempfile.TemporaryDirectory() as root:
            font = Path(root, "usr/share/fonts/truetype/dejavu/DejaVuSans.ttf")
            theme = Path(root, "usr/share/plymouth/themes/spheradian/seed.png")
            for path in (font, theme):
                path.parent.mkdir(parents=True)
                path.touch()
            self.assertEqual(self.run_script(self.TRIM, DESTDIR=root).returncode, 0)
            self.assertFalse(font.exists())
            self.assertTrue(theme.exists())

    def test_themes_hook_adds_the_reduced_motion_theme(self):
        with tempfile.TemporaryDirectory() as root:
            result = self.run_script(self.THEMES_HOOK, DESTDIR=root, SPHERADIAN_THEMES=str(THEMES))
            self.assertEqual(result.returncode, 0, result.stderr)
            copied = Path(root, "usr/share/plymouth/themes", STILL, f"{STILL}.script")
            self.assertTrue(copied.is_file())

    def select_theme(self, command_line):
        with tempfile.TemporaryDirectory() as root:
            cmdline, config = Path(root, "cmdline"), Path(root, "plymouthd.conf")
            cmdline.write_text(command_line + "\n")
            config.write_text("[Daemon]\nTheme=spheradian\nShowDelay=0\n")
            result = self.run_script(
                self.MOTION, SPHERADIAN_CMDLINE=str(cmdline), SPHERADIAN_PLYMOUTH_CONF=str(config)
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            return read_ini(config)["Daemon"]["Theme"]

    def test_reduced_motion_parameter_selects_the_still_theme(self):
        self.assertEqual(self.select_theme("boot=live quiet splash spheradian.motion=reduced"), STILL)

    def test_default_command_line_keeps_the_animated_theme(self):
        self.assertEqual(self.select_theme("boot=live quiet splash"), ANIMATED)
        self.assertEqual(self.select_theme("boot=live spheradian.motion=full splash"), ANIMATED)


class ImageRecipe(unittest.TestCase):
    def test_kernel_command_line_enables_a_quiet_splash(self):
        params = boot_parameters()
        self.assertIn("quiet", params)
        self.assertIn("splash", params)
        self.assertNotIn("splash=0", params)
        self.assertIn("vt.global_cursor_default=0", params)

    def test_plymouth_is_in_the_manifest(self):
        self.assertIn("plymouth", self.manifest_packages())

    def test_no_extra_plymouth_theme_packages(self):
        # plymouth-themes pulls fontconfig and fonts; the theme needs only the base package.
        extra = [p for p in self.manifest_packages() if p.startswith("plymouth-")]
        self.assertEqual(extra, [])

    def test_every_manifest_package_has_a_justification_on_the_line_above(self):
        for path in self.manifest_files():
            previous = ""
            for line in path.read_text().splitlines():
                if line.strip() and not line.startswith("#"):
                    self.assertRegex(previous, r"^#\s*\S", f"{path.name}: {line}")
                previous = line

    def test_manifest_has_no_inline_comments(self):
        # live-build hands the whole line to apt, so an inline comment breaks the build.
        for path in self.manifest_files():
            for line in path.read_text().splitlines():
                if not line.startswith("#"):
                    self.assertNotIn("#", line, f"{path.name}: {line}")

    @staticmethod
    def manifest_files():
        # live.list.chroot is generated by "lb config" and is not part of the manifest.
        lists = (ROOT / "config" / "package-lists").glob("*.list.chroot")
        return [p for p in lists if p.name != "live.list.chroot"]

    @staticmethod
    def manifest_packages():
        packages = []
        for path in ImageRecipe.manifest_files():
            for line in path.read_text().splitlines():
                name = line.split("#", 1)[0].strip()
                if name:
                    packages.append(name)
        return packages


if __name__ == "__main__":
    unittest.main()
