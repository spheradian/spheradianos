#!/usr/bin/env python3
"""Generate the boot splash assets deterministically (standard library only).

Usage: scripts/gen-boot-assets.py
Writes sphere.png into the Plymouth theme directory. The image is original work:
a neutral seed of light at the centre of a sphere lattice that it illuminates.
tests/test_boot_splash.py checks that the committed PNG matches this generator.
"""

import math
import struct
import zlib
from pathlib import Path

SIZE = 480
SPHERE_RADIUS = 0.80  # fraction of the half-size; leaves a black margin
LATTICE_STEP = math.radians(30)
LINE_WIDTH = 0.014  # radians
TILT = math.radians(24)
SPIN = math.radians(18)
FRONT_LIGHT = 0.55
BACK_LIGHT = 0.20
SEED_COLOUR = (225, 235, 255)

OUTPUT = (
    Path(__file__).resolve().parent.parent
    / "config/includes.chroot/usr/share/plymouth/themes/xsphere/sphere.png"
)


def seed_glow(r2):
    core = math.exp(-r2 / (2 * 0.07**2))
    halo = 0.25 * math.exp(-r2 / (2 * 0.22**2))
    return core + halo


def distance_to_grid(angle):
    return abs((angle / LATTICE_STEP + 0.5) % 1.0 - 0.5) * LATTICE_STEP


def lattice_line(x, y, z):
    """Brightness of the latitude/longitude lattice at a point on the unit sphere."""
    y, z = (
        y * math.cos(TILT) - z * math.sin(TILT),
        y * math.sin(TILT) + z * math.cos(TILT),
    )
    x, z = (
        x * math.cos(SPIN) + z * math.sin(SPIN),
        -x * math.sin(SPIN) + z * math.cos(SPIN),
    )
    lat = math.asin(max(-1.0, min(1.0, y)))
    lon = math.atan2(x, z)
    d_lat = distance_to_grid(lat)
    d_lon = distance_to_grid(lon) * math.cos(lat)
    return math.exp(-((min(d_lat, d_lon) / LINE_WIDTH) ** 2))


def intensity(u, v):
    r2 = u * u + v * v
    value = seed_glow(r2)
    if r2 < 1.0:
        z = math.sqrt(1.0 - r2)
        limb_fade = 1.0 - r2**4
        value += FRONT_LIGHT * limb_fade * lattice_line(u, v, z)
        value += BACK_LIGHT * limb_fade * lattice_line(u, v, -z)
    return min(1.0, value)


PALETTE = [
    tuple(int(channel * level / 255 + 0.5) for channel in SEED_COLOUR)
    for level in range(256)
]


def render_levels():
    """Return SIZE x SIZE brightness levels (0-255), one byte per pixel, row by row."""
    half = SIZE / 2
    levels = bytearray()
    for py in range(SIZE):
        v = (py + 0.5 - half) / (half * SPHERE_RADIUS)
        for px in range(SIZE):
            u = (px + 0.5 - half) / (half * SPHERE_RADIUS)
            levels.append(int(255 * intensity(u, v) + 0.5))
    return bytes(levels)


def render_sphere():
    """Return SIZE x SIZE 8-bit RGB pixels, row by row (levels seen through the palette)."""
    return b"".join(bytes(PALETTE[level]) for level in render_levels())


def png_chunk(kind, body):
    checksum = zlib.crc32(kind + body) & 0xFFFFFFFF
    return struct.pack(">I", len(body)) + kind + body + struct.pack(">I", checksum)


def encode_png_indexed(width, height, levels):
    """One byte per pixel plus a 256-entry palette: about half the size of RGB."""
    raw = b"".join(
        b"\x00" + levels[row * width : (row + 1) * width] for row in range(height)
    )
    header = struct.pack(">IIBBBBB", width, height, 8, 3, 0, 0, 0)
    return (
        b"\x89PNG\r\n\x1a\n"
        + png_chunk(b"IHDR", header)
        + png_chunk(b"PLTE", b"".join(bytes(colour) for colour in PALETTE))
        + png_chunk(b"IDAT", zlib.compress(raw, 9))
        + png_chunk(b"IEND", b"")
    )


def main():
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_bytes(encode_png_indexed(SIZE, SIZE, render_levels()))
    print(f"wrote {OUTPUT} ({OUTPUT.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
