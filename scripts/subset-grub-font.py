#!/usr/bin/env python3
"""Copy a GRUB PF2 font, keeping only the characters the boot menu needs.

Usage: scripts/subset-grub-font.py SOURCE.pf2 TARGET.pf2

GRUB reads its whole font file before it can draw a themed menu. Debian's
unicode.pf2 is about 2.3 MB, and loading it on every boot delays the splash by
about 0.8 s under OVMF (docs/BOOT-EXPERIENCE.md 6.4). The menu shows only
printable ASCII, so a subset of about 4 KB does the same job.

Standard library only. The PF2 layout: a sequence of sections, each a 4-byte
name and a 4-byte big-endian length, then the data. CHIX lists each character
(code point, flags, absolute offset of its glyph); DATA holds the glyphs and
runs to the end of the file. Each glyph is five big-endian 16-bit fields
(width, height, x offset, y offset, advance) and a packed 1-bit bitmap.
"""

import struct
import sys
from pathlib import Path

KEEP = range(0x20, 0x7F)  # printable ASCII
GLYPH_HEADER = struct.Struct(">HHhhh")
CHIX_ENTRY = struct.Struct(">IBI")


class FontError(ValueError):
    pass


def read_sections(data):
    """Return [(name, body)] in file order. DATA's body runs to the end of the file."""
    sections, pos = [], 0
    while pos < len(data):
        if pos + 8 > len(data):
            raise FontError("truncated section header")
        name, length = struct.unpack(">4sI", data[pos : pos + 8])
        if name == b"DATA":
            sections.append((name, data[pos + 8 :]))
            break
        body = data[pos + 8 : pos + 8 + length]
        if len(body) != length:
            raise FontError(f"truncated {name!r} section")
        sections.append((name, body))
        pos += 8 + length
    if not sections or sections[0] != (b"FILE", b"PFF2"):
        raise FontError("not a PF2 font")
    names = [name for name, _ in sections]
    if b"CHIX" not in names or b"DATA" not in names:
        raise FontError("PF2 font without CHIX or DATA")
    return sections


def glyph_at(data, offset):
    """The raw bytes of the glyph stored at an absolute file offset."""
    if offset + GLYPH_HEADER.size > len(data):
        raise FontError("glyph offset out of range")
    width, height, *_ = GLYPH_HEADER.unpack_from(data, offset)
    size = GLYPH_HEADER.size + (width * height + 7) // 8
    if offset + size > len(data):
        raise FontError("truncated glyph")
    return data[offset : offset + size]


def subset(data, keep=KEEP):
    """Return a PF2 font holding only the code points in `keep`."""
    sections = read_sections(data)
    chix = dict(sections)[b"CHIX"]
    if len(chix) % CHIX_ENTRY.size:
        raise FontError("malformed CHIX section")
    entries = [CHIX_ENTRY.unpack_from(chix, i) for i in range(0, len(chix), CHIX_ENTRY.size)]
    kept = [(code, flags, glyph_at(data, offset)) for code, flags, offset in entries if code in keep]
    if not kept:
        raise FontError("none of the requested characters are in the font")

    # Everything before CHIX keeps its size, so the glyph offsets are known up front.
    head = b"".join(
        struct.pack(">4sI", name, len(body)) + body
        for name, body in sections
        if name not in (b"CHIX", b"DATA")
    )
    chix_size = 8 + CHIX_ENTRY.size * len(kept)
    offset = len(head) + chix_size + 8
    index, glyphs = [], []
    for code, flags, glyph in kept:  # PF2 requires CHIX sorted by code point; it already is
        index.append(CHIX_ENTRY.pack(code, flags, offset))
        glyphs.append(glyph)
        offset += len(glyph)
    return (
        head
        + struct.pack(">4sI", b"CHIX", CHIX_ENTRY.size * len(kept))
        + b"".join(index)
        + struct.pack(">4sI", b"DATA", 0xFFFFFFFF)
        + b"".join(glyphs)
    )


def main():
    if len(sys.argv) != 3:
        sys.exit(__doc__.strip().splitlines()[2])
    source, target = Path(sys.argv[1]), Path(sys.argv[2])
    try:
        result = subset(source.read_bytes())
    except (OSError, FontError) as error:
        sys.exit(f"subset-grub-font: {error}")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(result)
    print(f"subset-grub-font: {source} -> {target} ({len(result)} bytes)")


if __name__ == "__main__":
    main()
