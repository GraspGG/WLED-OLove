#!/usr/bin/env python3
"""
Build WLED/MM font tables from per-glyph JSON files (editor-friendly source).

Input JSON per glyph (minimal):
{
  "encoding": "cp437",
  "byte_hex": "30",
  "char": "0",
  "width": 5,
  "spaceR": 1,
  "matrix": [[0/1 x5] x8]
}

Output (generated):
- wled00/src/font/font_olove_7seg_5x8.h
- wled00/src/font/font_olove_7seg_5x8.cpp

Arrays:
- font_olove_7seg_5x8[256][5]      (columns, bit0=top row)
- font_olove_7seg_5x8_width[256]   (0..5)
- font_olove_7seg_5x8_spaceR[256]  (0..3 typical)
"""

from __future__ import annotations
import argparse
import json
from pathlib import Path

W, H = 5, 8

def matrix_to_cols(matrix: list[list[int]]) -> list[int]:
    if len(matrix) != H or any(len(r) != W for r in matrix):
        raise ValueError("matrix must be 8x5")
    cols = []
    for x in range(W):
        b = 0
        for y in range(H):
            if int(matrix[y][x]) != 0:
                b |= (1 << y)  # bit0 = top row
        cols.append(b)
    return cols

def compute_width(matrix: list[list[int]]) -> int:
    w = 0
    for x in range(W):
        if any(int(matrix[y][x]) != 0 for y in range(H)):
            w = x + 1
    return w

def sanitize_matrix(matrix: list[list[int]], width: int) -> list[list[int]]:
    # enforce clipping: everything right of width becomes 0
    width = max(0, min(W, int(width)))
    out = [[0]*W for _ in range(H)]
    for y in range(H):
        for x in range(W):
            if x < width:
                out[y][x] = 1 if int(matrix[y][x]) != 0 else 0
            else:
                out[y][x] = 0
    return out

def printable_ascii(i: int) -> str:
    if 0x20 <= i <= 0x7E:
        c = chr(i)
        if c == "\\":
            c = "\\\\"
        return f" '{c}'"
    return ""

def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default="fonts/5x8/olove_7seg/classic/glyphs", type=Path)
    ap.add_argument("--out_h", default="wled00/src/font/font_olove_7seg_5x8.h", type=Path)
    ap.add_argument("--out_cpp", default="wled00/src/font/font_olove_7seg_5x8.cpp", type=Path)
    ap.add_argument("--name", default="font_olove_7seg_5x8")
    args = ap.parse_args()

    src: Path = args.src
    if not src.exists():
        raise SystemExit(f"Missing source folder: {src}")

    cols_table = [[0,0,0,0,0] for _ in range(256)]
    width_table = [0 for _ in range(256)]
    space_table = [1 for _ in range(256)]
    meta = {}

    seen = set()
    glyph_count = 0

    for jf in sorted(src.glob("*.json")):
        data = json.loads(jf.read_text(encoding="utf-8"))

        bhex = str(data.get("byte_hex","")).strip().lower().replace("0x","")
        if len(bhex) != 2:
            raise SystemExit(f"{jf}: byte_hex must be 2 hex digits (00..FF), got {bhex!r}")
        b = int(bhex, 16)
        if b in seen:
            raise SystemExit(f"Duplicate byte_hex {bhex} from {jf}")
        seen.add(b)

        matrix = data["matrix"]
        width = int(data.get("width", compute_width(matrix)))
        width = max(0, min(W, width))
        matrix = sanitize_matrix(matrix, width)

        spaceR = int(data.get("spaceR", 1))
        # sane defaults: allow 0..5 but typical 0..3
        spaceR = max(0, min(5, spaceR))

        # special-case: space char
        ch = data.get("char","")
        if b == 0x20 or ch == " ":
            width = 0
            # 2 is a good readable default for space on 5x8
            if "spaceR" not in data:
                spaceR = 2

        cols = matrix_to_cols(matrix)

        cols_table[b] = cols
        width_table[b] = width
        space_table[b] = spaceR
        meta[b] = ch
        glyph_count += 1

    # write header
    args.out_h.parent.mkdir(parents=True, exist_ok=True)
    h_lines = []
    h_lines.append("// AUTO-GENERATED FILE - DO NOT EDIT BY HAND")
    h_lines.append("#pragma once")
    h_lines.append("#include <Arduino.h>")
    h_lines.append("")
    h_lines.append(f"extern const uint8_t {args.name}[256][5] PROGMEM;")
    h_lines.append(f"extern const uint8_t {args.name}_width[256] PROGMEM;")
    h_lines.append(f"extern const uint8_t {args.name}_spaceR[256] PROGMEM;")
    h_lines.append("")
    h_lines.append("// Glyph grid is always 5x8 (columns x rows).")
    h_lines.append("// width: 0..5 visible columns; spaceR: additional right-side spacing columns (units, pre-scale).")
    args.out_h.write_text("\n".join(h_lines) + "\n", encoding="utf-8")

    # write cpp
    args.out_cpp.parent.mkdir(parents=True, exist_ok=True)
    c_lines = []
    c_lines.append("// AUTO-GENERATED FILE - DO NOT EDIT BY HAND")
    c_lines.append("#include <Arduino.h>")
    c_lines.append(f'#include "{args.out_h.name}"')
    c_lines.append("")
    c_lines.append(f"const uint8_t {args.name}[256][5] PROGMEM = {{")
    for i in range(256):
        cols = cols_table[i]
        tag = meta.get(i, "")
        extra = f" {tag}" if tag else ""
        c_lines.append(
            f"  /* 0x{i:02X}{printable_ascii(i)}{extra} */ "
            + "{"
            + ", ".join(f"0x{b:02X}" for b in cols)
            + "},"
        )
    c_lines.append("};")
    c_lines.append("")
    c_lines.append(f"const uint8_t {args.name}_width[256] PROGMEM = {{")
    c_lines.append("  " + ", ".join(str(w) for w in width_table))
    c_lines.append("};")
    c_lines.append("")
    c_lines.append(f"const uint8_t {args.name}_spaceR[256] PROGMEM = {{")
    c_lines.append("  " + ", ".join(str(s) for s in space_table))
    c_lines.append("};")
    c_lines.append("")
    c_lines.append(f"// Source glyphs: {glyph_count} from {src}")
    args.out_cpp.write_text("\n".join(c_lines) + "\n", encoding="utf-8")

    print(f"Wrote: {args.out_h}")
    print(f"Wrote: {args.out_cpp}")
    print(f"Glyphs imported: {glyph_count} (non-empty files in {src})")

if __name__ == "__main__":
    main()