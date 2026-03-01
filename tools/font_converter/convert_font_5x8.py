#!/usr/bin/env python3
"""
Convert a set of glyph PNGs into a fixed-width 5x8 bitmap font header.

- Target glyph: 5x8 pixels (W x H)
- Optional input: 7x8 with 1px padding left+right ("5+2") -> we crop center 5 columns.
- Output: C header with 256 glyphs (ASCII/extended), each glyph is 5 bytes (columns),
          LSB = top pixel (row 0). Missing glyphs become blank.

Usage:
  python tools/font_converter/convert_font_5x8.py \
    --input assets/fonts_7seg_5x8/png \
    --manifest assets/fonts_7seg_5x8/manifest.json \
    --out wled00/src/font/font_olove_7seg_5x8.h
"""

from __future__ import annotations
import argparse
import json
from pathlib import Path

from PIL import Image  # pip install pillow


def load_glyph(path: Path, threshold: int = 128) -> list[int]:
    """Return 5 bytes (columns) for a single glyph."""
    img = Image.open(path).convert("L")  # grayscale
    w, h = img.size
    if h != 8:
        raise ValueError(f"{path.name}: expected height 8, got {h}")

    # Accept 5x8 or 7x8 (5+2 padding)
    if w == 7:
        # crop center 5 columns
        img = img.crop((1, 0, 6, 8))
        w = 5
    if w != 5:
        raise ValueError(f"{path.name}: expected width 5 or 7, got {w}")

    # Binarize
    pix = img.load()
    cols: list[int] = []
    for x in range(5):
        col = 0
        for y in range(8):
            on = pix[x, y] >= threshold
            if on:
                col |= (1 << y)  # LSB = row0 (top)
        cols.append(col)
    return cols


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True, type=Path, help="Folder with PNG glyphs")
    ap.add_argument("--manifest", required=True, type=Path, help="JSON map: codepoint(hex) -> filename")
    ap.add_argument("--out", required=True, type=Path, help="Output header path")
    ap.add_argument("--threshold", type=int, default=128, help="0..255 threshold")
    ap.add_argument("--font_name", default="olove_7seg_5x8", help="C identifier suffix")
    args = ap.parse_args()

    inp = args.input
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))

    # 256 glyphs, default blank
    table: list[list[int]] = [[0, 0, 0, 0, 0] for _ in range(256)]

    for cp_hex, filename in manifest.items():
        cp = int(cp_hex, 16)
        if not (0 <= cp <= 255):
            # Keep it simple for MVP; later we can generate multi-page tables
            raise ValueError(f"codepoint {cp_hex} out of 0..255 range")
        glyph_path = inp / filename
        if not glyph_path.exists():
            raise FileNotFoundError(glyph_path)
        table[cp] = load_glyph(glyph_path, threshold=args.threshold)

    out = args.out
    out.parent.mkdir(parents=True, exist_ok=True)

    cname = args.font_name
    lines: list[str] = []
    lines.append("// AUTO-GENERATED FILE - DO NOT EDIT BY HAND")
    lines.append("#pragma once")
    lines.append("#include <Arduino.h>")
    lines.append("")
    lines.append(f"static const uint8_t font_{cname}[256][5] PROGMEM = {{")
    for i, cols in enumerate(table):
        lines.append(f"  /* 0x{i:02X} */ {{{', '.join(f'0x{c:02X}' for c in cols)}}},")
    lines.append("};")
    lines.append("")
    lines.append("// Fixed advance: 5px glyph + 1px spacing")
    lines.append(f"static constexpr uint8_t font_{cname}_advance = 6;")
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"Wrote: {out} (glyphs: {sum(1 for g in table if any(g))}/256)")


if __name__ == "__main__":
    main()