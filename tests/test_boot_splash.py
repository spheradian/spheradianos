"""Static checks for the boot splash (BOOT-EXPERIENCE.md milestone B1).

Run from the repository root: python3 -m unittest discover -s tests -v
Standard library only, no GPU, no network, no root.
"""

import configparser
import importlib.util
import os
import re
import struct
import subprocess
import tempfile
import unittest
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CHROOT = ROOT / "config" / "includes.chroot"
THEME_NAME = "xsphere"
THEME_DIR_IN_IMAGE = f"/usr/share/plymouth/themes/{THEME_NAME}"
THEME_DIR = CHROOT / THEME_DIR_IN_IMAGE.lstrip("/")
# Console-grade budget (docs/BOOT-EXPERIENCE.md 6.4): the whole theme, not 1 MiB.
ASSET_BUDGET_BYTES = 64 * 1024
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


def decode_png_rgb(data):
    """Decode the restricted PNG subset the generator writes (8-bit indexed, filter 0)."""
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError("not a PNG")
    pos, idat, palette, width, height = 8, b"", b"", 0, 0
    while pos < len(data):
        length, kind = struct.unpack(">I4s", data[pos : pos + 8])
        body = data[pos + 8 : pos + 8 + length]
        if kind == b"IHDR":
            width, height, depth, colour = struct.unpack(">IIBB", body[:10])
            if (depth, colour) != (8, 3):
                raise ValueError("expected an 8-bit indexed image")
        elif kind == b"PLTE":
            palette = body
        elif kind == b"IDAT":
            idat += body
        pos += 12 + length
    raw = zlib.decompress(idat)
    stride = width + 1
    rows = [raw[i * stride : (i + 1) * stride] for i in range(height)]
    if any(row[0] != 0 for row in rows):
        raise ValueError("expected filter type 0 on every row")
    return width, height, b"".join(
        palette[index * 3 : index * 3 + 3] for row in rows for index in row[1:]
    )


def load_generator():
    path = ROOT / "scripts" / "gen-boot-assets.py"
    spec = importlib.util.spec_from_file_location("gen_boot_assets", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ThemeDefinition(unittest.TestCase):
    def setUp(self):
        self.theme = read_ini(THEME_DIR / f"{THEME_NAME}.plymouth")

    def test_theme_uses_the_script_plugin(self):
        self.assertEqual(self.theme["Plymouth Theme"]["ModuleName"], "script")

    def test_theme_has_name_and_description(self):
        for key in ("Name", "Description"):
            self.assertTrue(self.theme["Plymouth Theme"][key].strip())

    def test_theme_paths_point_inside_its_own_directory(self):
        script = self.theme["script"]
        self.assertEqual(script["ImageDir"], THEME_DIR_IN_IMAGE)
        self.assertEqual(
            script["ScriptFile"], f"{THEME_DIR_IN_IMAGE}/{THEME_NAME}.script"
        )
        self.assertTrue((THEME_DIR / f"{THEME_NAME}.script").is_file())

    def test_daemon_selects_the_theme_without_delay(self):
        daemon = read_ini(CHROOT / "etc" / "plymouth" / "plymouthd.conf")["Daemon"]
        self.assertEqual(daemon["Theme"], THEME_NAME)
        self.assertEqual(daemon["ShowDelay"], "0")


class ThemeScript(unittest.TestCase):
    def setUp(self):
        self.script = (THEME_DIR / f"{THEME_NAME}.script").read_text()

    def test_every_image_the_script_loads_exists(self):
        names = re.findall(r'Image\("([^"]+)"\)', self.script)
        self.assertTrue(names, "script loads no image")
        for name in names:
            self.assertTrue((THEME_DIR / name).is_file(), name)

    def test_b1_theme_is_static(self):
        # A still frame satisfies reduced motion and the flash limits by construction.
        self.assertNotIn("SetRefreshFunction", self.script)

    def test_background_is_true_black(self):
        for call in ("SetBackgroundTopColor", "SetBackgroundBottomColor"):
            self.assertRegex(self.script, rf"Window\.{call}\s*\(\s*0\s*,\s*0\s*,\s*0\s*\)")


class ThemeAssets(unittest.TestCase):
    def test_assets_fit_the_size_budget(self):
        total = sum(p.stat().st_size for p in THEME_DIR.rglob("*") if p.is_file())
        self.assertLessEqual(total, ASSET_BUDGET_BYTES)

    def test_theme_ships_no_binary_audio(self):
        audio = [p for p in THEME_DIR.rglob("*") if p.suffix.lower() in AUDIO_SUFFIXES]
        self.assertEqual(audio, [])

    def test_committed_sphere_matches_the_generator(self):
        generator = load_generator()
        width, height, pixels = decode_png_rgb((THEME_DIR / "sphere.png").read_bytes())
        self.assertEqual((width, height), (generator.SIZE, generator.SIZE))
        self.assertEqual(pixels, generator.render_sphere())

    def test_sphere_edges_are_black_so_it_blends_with_the_background(self):
        width, height, pixels = decode_png_rgb((THEME_DIR / "sphere.png").read_bytes())
        row = width * 3
        border = (
            pixels[:row]
            + pixels[-row:]
            + b"".join(pixels[y * row : y * row + 3] for y in range(height))
            + b"".join(pixels[(y + 1) * row - 3 : (y + 1) * row] for y in range(height))
        )
        self.assertEqual(set(border), {0})


class InitramfsFootprint(unittest.TestCase):
    HOOK = CHROOT / "etc" / "initramfs-tools" / "hooks" / "xsphereos-splash-trim"

    def test_trim_hook_is_executable_and_runs_after_plymouth(self):
        self.assertTrue(os.access(self.HOOK, os.X_OK))
        self.assertIn('PREREQ="plymouth"', self.HOOK.read_text())

    def test_trim_hook_refuses_to_run_without_a_destination(self):
        environment = {k: v for k, v in os.environ.items() if k != "DESTDIR"}
        result = subprocess.run([str(self.HOOK)], env=environment, capture_output=True)
        self.assertNotEqual(result.returncode, 0)

    def test_trim_hook_removes_fonts_and_keeps_the_theme(self):
        with tempfile.TemporaryDirectory() as root:
            font = Path(root, "usr/share/fonts/truetype/dejavu/DejaVuSans.ttf")
            theme = Path(root, "usr/share/plymouth/themes/xsphere/sphere.png")
            for path in (font, theme):
                path.parent.mkdir(parents=True)
                path.touch()
            subprocess.run([str(self.HOOK)], env={**os.environ, "DESTDIR": root}, check=True)
            self.assertFalse(font.exists())
            self.assertTrue(theme.exists())


class ImageRecipe(unittest.TestCase):
    def test_kernel_command_line_enables_a_quiet_splash(self):
        params = boot_parameters()
        self.assertIn("quiet", params)
        self.assertIn("splash", params)
        self.assertNotIn("splash=0", params)
        self.assertIn("vt.global_cursor_default=0", params)

    def test_plymouth_is_in_the_manifest(self):
        packages = self.manifest_packages()
        self.assertIn("plymouth", packages)

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
