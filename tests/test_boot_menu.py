"""Bootloader menu art and GRUB font subsetting (BOOT-EXPERIENCE.md 2 and 6.4).

Run from the repository root: python3 -m unittest discover -s tests -v
"""

import importlib.util
import os
import re
import shutil
import struct
import subprocess
import tempfile
import unittest
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BOOTLOADERS = ROOT / "config" / "bootloaders"
GRUB_THEME = BOOTLOADERS / "grub-pc" / "spheradian"
FONT_HOOK = ROOT / "config" / "hooks" / "live" / "9100-spheradianos-grub-font.hook.binary"
MENU_ART_BUDGET = 64 * 1024
GRUB_FONT_ALLOWANCE = 4 * 1024  # ascii.pf2 is built at image build time (about 3 KiB)


def load(name, filename):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def png_header(data):
    """(width, height, bit depth, colour type, interlace) of a PNG."""
    if data[:8] != b"\x89PNG\r\n\x1a\n" or data[12:16] != b"IHDR":
        raise ValueError("not a PNG")
    width, height, depth, colour, _, _, interlace = struct.unpack(">IIBBBBB", data[16:29])
    return width, height, depth, colour, interlace


def png_pixels(data):
    """Raw scanlines of a single-IDAT, filter-0 PNG, as written by the generator."""
    pos, idat = 8, b""
    while pos < len(data):
        length, kind = struct.unpack(">I4s", data[pos : pos + 8])
        if kind == b"IDAT":
            idat += data[pos + 8 : pos + 8 + length]
        pos += 12 + length
    return zlib.decompress(idat)


class MenuArt(unittest.TestCase):
    def test_committed_art_matches_the_generator(self):
        for relative, data in load("gen", "gen-boot-assets.py").bootloader_files().items():
            path = BOOTLOADERS / relative
            self.assertTrue(path.is_file(), relative)
            self.assertEqual(path.read_bytes(), data, f"{relative} is stale; run gen-boot-assets.py")

    def test_art_is_a_png_both_bootloaders_can_read(self):
        # GRUB's PNG reader and vesamenu both take 8-bit RGB without interlace.
        for path in (BOOTLOADERS / "isolinux" / "splash.png", GRUB_THEME / "background.png"):
            _, _, depth, colour, interlace = png_header(path.read_bytes())
            self.assertEqual((depth, colour, interlace), (8, 2, 0), path.name)

    def test_isolinux_background_is_black_because_it_shows_on_every_boot(self):
        data = (BOOTLOADERS / "isolinux" / "splash.png").read_bytes()
        self.assertEqual(png_header(data)[:2], (640, 480))
        raw = png_pixels(data)
        self.assertEqual(set(raw), {0})

    def test_grub_art_is_not_blank(self):
        raw = png_pixels((GRUB_THEME / "background.png").read_bytes())
        self.assertGreater(max(raw), 200)

    def test_menu_art_fits_its_budget(self):
        files = [BOOTLOADERS / "isolinux" / "splash.png", *GRUB_THEME.iterdir()]
        committed = sum(p.stat().st_size for p in files)
        self.assertLessEqual(committed + GRUB_FONT_ALLOWANCE, MENU_ART_BUDGET)


class Configuration(unittest.TestCase):
    def test_isolinux_uses_the_black_background(self):
        config = (BOOTLOADERS / "isolinux" / "isolinux.cfg").read_text()
        self.assertRegex(config, r"(?m)^menu background splash\.png$")

    def test_grub_loads_only_the_small_font_and_the_theme(self):
        config = (BOOTLOADERS / "grub-pc" / "config.cfg").read_text()
        code = "\n".join(line.split("#", 1)[0] for line in config.splitlines())
        self.assertIn("loadfont /boot/grub/spheradian/ascii.pf2", code)
        self.assertNotIn("unicode", code)
        self.assertIn("set theme=/boot/grub/spheradian/theme.txt", code)

    def test_theme_images_exist(self):
        theme = (GRUB_THEME / "theme.txt").read_text()
        for image in re.findall(r'desktop-image:\s*"([^"]+)"', theme):
            self.assertTrue((GRUB_THEME / image).is_file(), image)
        self.assertIn('title-text: ""', theme)

    def test_font_hook_is_executable_and_build_has_python(self):
        self.assertTrue(os.access(FONT_HOOK, os.X_OK))
        self.assertIn("scripts/subset-grub-font.py", FONT_HOOK.read_text())
        self.assertIn("python3", (ROOT / "scripts" / "build-in-container.sh").read_text())


def make_font(codes):
    """A minimal PF2 font: glyph for code c is 8x2 pixels of value c & 0xFF."""
    head = b"".join(
        struct.pack(">4sI", name, len(body)) + body
        for name, body in (
            (b"FILE", b"PFF2"),
            (b"NAME", b"Test Regular 16\x00"),
            (b"PTSZ", struct.pack(">H", 16)),
        )
    )
    glyphs = [struct.pack(">HHhhh", 8, 2, 0, -2, 8) + bytes([c & 0xFF, c & 0xFF]) for c in codes]
    offset = len(head) + 8 + 9 * len(codes) + 8
    index = b""
    for code, glyph in zip(codes, glyphs, strict=True):
        index += struct.pack(">IBI", code, 0, offset)
        offset += len(glyph)
    return (
        head
        + struct.pack(">4sI", b"CHIX", len(index))
        + index
        + struct.pack(">4sI", b"DATA", 0xFFFFFFFF)
        + b"".join(glyphs)
    )


class FontSubset(unittest.TestCase):
    def setUp(self):
        self.subset = load("subset", "subset-grub-font.py")

    def glyphs(self, data):
        sections = dict(self.subset.read_sections(data))
        chix = sections[b"CHIX"]
        return {
            code: self.subset.glyph_at(data, offset)
            for code, _, offset in (
                self.subset.CHIX_ENTRY.unpack_from(chix, i) for i in range(0, len(chix), 9)
            )
        }

    def test_keeps_exactly_the_printable_ascii_glyphs_unchanged(self):
        codes = [0x0A, 0x20, 0x41, 0x7E, 0x7F, 0xE9, 0x2191, 0x4E2D]
        source = make_font(codes)
        result = self.subset.subset(source)
        kept = self.glyphs(result)
        self.assertEqual(sorted(kept), [0x20, 0x41, 0x7E])
        original = self.glyphs(source)
        for code, glyph in kept.items():
            self.assertEqual(glyph, original[code])

    def test_index_is_sorted_even_when_the_source_is_not(self):
        # GRUB binary-searches CHIX, so an unsorted index loses glyphs silently.
        result = self.subset.subset(make_font([0x7E, 0x41, 0x20]))
        chix = dict(self.subset.read_sections(result))[b"CHIX"]
        codes = [self.subset.CHIX_ENTRY.unpack_from(chix, i)[0] for i in range(0, len(chix), 9)]
        self.assertEqual(codes, [0x20, 0x41, 0x7E])

    def test_keeps_the_font_header(self):
        result = dict(self.subset.read_sections(self.subset.subset(make_font([0x41]))))
        self.assertEqual(result[b"NAME"], b"Test Regular 16\x00")
        self.assertEqual(result[b"PTSZ"], struct.pack(">H", 16))

    def test_rejects_what_is_not_a_pf2_font(self):
        for data in (b"", b"\x89PNG\r\n\x1a\n", make_font([0x41])[:30]):
            with self.assertRaises(self.subset.FontError):
                self.subset.subset(data)

    def test_rejects_a_font_without_the_needed_characters(self):
        with self.assertRaises(self.subset.FontError):
            self.subset.subset(make_font([0x4E2D]))


class FontHook(unittest.TestCase):
    def test_skips_only_when_grub_directory_is_absent(self):
        with tempfile.TemporaryDirectory() as tmp:
            binary = Path(tmp) / "binary"
            binary.mkdir()
            result = subprocess.run(
                [str(FONT_HOOK)],
                cwd=binary,
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("skipping", result.stdout)

    def test_fails_when_grub_exists_without_unicode_font(self):
        with tempfile.TemporaryDirectory() as tmp:
            binary = Path(tmp) / "binary"
            (binary / "boot" / "grub").mkdir(parents=True)
            result = subprocess.run(
                [str(FONT_HOOK)],
                cwd=binary,
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("not found", result.stderr)

    def test_builds_ascii_subset_inside_fake_live_build_tree(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "scripts").mkdir()
            shutil.copy2(ROOT / "scripts" / "subset-grub-font.py", root / "scripts" / "subset-grub-font.py")
            binary = root / "binary"
            grub_dir = binary / "boot" / "grub"
            grub_dir.mkdir(parents=True)
            (grub_dir / "spheradian").mkdir()
            (grub_dir / "unicode.pf2").write_bytes(make_font([0x20, 0x41]))
            result = subprocess.run(
                [str(FONT_HOOK)],
                cwd=binary,
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue((grub_dir / "spheradian" / "ascii.pf2").is_file())


if __name__ == "__main__":
    unittest.main()
