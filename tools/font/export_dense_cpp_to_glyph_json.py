#!/usr/bin/env python3
import json, re
from pathlib import Path

# expects dense lines like: /* 0x30 ... */ {0x3E, 0x41, 0x41, 0x41, 0x3E},
RE = re.compile(r"/\*\s*0x([0-9A-Fa-f]{2}).*?\*/\s*\{\s*(0x[0-9A-Fa-f]{1,2}\s*,\s*){4}0x[0-9A-Fa-f]{1,2}\s*\}")

RE_BYTES = re.compile(r"0x([0-9A-Fa-f]{1,2})")

def cols_to_matrix(cols):
    # cols: 5 bytes, bit0 = top row
    m = [[0]*5 for _ in range(8)]
    for x in range(5):
        b = cols[x]
        for y in range(8):
            m[y][x] = 1 if (b & (1<<y)) else 0
    return m

def compute_width(matrix):
    # rightmost column that has any 1, +1; width=0 for empty
    w = 0
    for x in range(5):
        if any(matrix[y][x] for y in range(8)):
            w = x+1
    return w

def cp437_char(byte_val):
    try:
        return bytes([byte_val]).decode("cp437")
    except Exception:
        return ""

def main():
    inp = Path("wled00/src/font/font_olove_7seg_5x8.cpp")
    outdir = Path("fonts/5x8/olove_7seg/classic/glyphs")
    outdir.mkdir(parents=True, exist_ok=True)

    lines = inp.read_text(encoding="utf-8", errors="replace").splitlines()

    exported = 0
    for line in lines:
        m = RE.search(line)
        if not m:
            continue
        idx = int(m.group(1), 16)
        bytes_hex = RE_BYTES.findall(line)
        cols = [int(h,16) for h in bytes_hex[:5]]

        # skip empty glyphs
        if all(c == 0 for c in cols):
            continue

        matrix = cols_to_matrix(cols)
        width = compute_width(matrix)

        ch = cp437_char(idx)
        # default spacing rule (kannst du später verfeinern)
        spaceR = 1
        if idx == 0x20:  # space
            width = 0
            spaceR = 2
        if ch == '.':
            spaceR = 2

        data = {
            "encoding": "cp437",
            "byte_hex": f"{idx:02X}",
            "char": ch,
            "variant": "classic",
            "width": width,
            "spaceR": spaceR,
            "matrix": matrix
        }

        fn_char = ch if ch and ch.isalnum() else f"b{idx:02X}"
        (outdir / f"{idx:02X}_{fn_char}.json").write_text(json.dumps(data, indent=2), encoding="utf-8")
        exported += 1

    print(f"Exported {exported} glyph JSON files to {outdir}")

if __name__ == "__main__":
    main()