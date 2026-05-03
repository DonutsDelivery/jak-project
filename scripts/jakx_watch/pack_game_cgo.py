#!/usr/bin/env python3
"""
Pack out/jakx/iso/GAME.CGO directly from existing .o/.go files in out/jakx/obj/,
bypassing goalc's compilation step.

DGO format (from DgoWriter.cpp):
  u32  entry_count
  60b  dgo_name (null-padded)
  for each entry:
    u32  file_size
    60b  name_in_dgo (null-padded, no extension)
    data (file_size bytes)
    padding to 16-byte alignment
"""

import struct
import os
import sys
import re

BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OBJ_DIR = os.path.join(BASE, "out", "jakx", "obj")
ISO_DIR = os.path.join(BASE, "out", "jakx", "iso")
GD_FILE = os.path.join(BASE, "goal_src", "jakx", "dgos", "game.gd")
OUT_CGO = os.path.join(ISO_DIR, "GAME.CGO")


def name_in_dgo(file_name: str) -> str:
    """Mirror the name_in_dgo logic from Tools.cpp."""
    if file_name.endswith(".o"):
        return file_name[:-2]
    if file_name.endswith("-ag.go"):
        return file_name[:-6]
    if file_name.endswith(".go"):
        return file_name[:-3]
    return file_name


def null_pad(s: str, length: int) -> bytes:
    b = s.encode("ascii")
    return b[:length] + b"\x00" * (length - len(b))


def parse_gd(path: str):
    """Parse the .gd file and return list of file names (strings in the inner list)."""
    with open(path) as f:
        content = f.read()
    # Strip line comments
    content = re.sub(r";;[^\n]*", "", content)
    # Extract all quoted strings
    names = re.findall(r'"([^"]+)"', content)
    # The first string is the DGO name (GAME.CGO), the rest are entries
    return names[0], names[1:]


def pack():
    dgo_name, entries = parse_gd(GD_FILE)
    print(f"DGO name: {dgo_name}, {len(entries)} entries")

    buf = bytearray()

    # Header placeholder — fill in count after we know how many files we actually pack
    packed = []

    for fname in entries:
        obj_path = os.path.join(OBJ_DIR, fname)
        if not os.path.exists(obj_path):
            print(f"  WARN: missing {fname}, skipping")
            continue
        data = open(obj_path, "rb").read()
        packed.append((fname, data))

    # DGO header: count + name
    buf += struct.pack("<I", len(packed))
    buf += null_pad(dgo_name, 60)

    for fname, data in packed:
        nid = name_in_dgo(fname)
        buf += struct.pack("<I", len(data))
        buf += null_pad(nid, 60)
        buf += data
        # Pad to 16-byte alignment
        while len(buf) & 0xF:
            buf += b"\x00"

    os.makedirs(ISO_DIR, exist_ok=True)
    with open(OUT_CGO, "wb") as f:
        f.write(buf)

    print(f"Wrote {OUT_CGO} ({len(buf):,} bytes, {len(packed)} objects)")
    missing = [e for e in entries if not os.path.exists(os.path.join(OBJ_DIR, e))]
    if missing:
        print(f"  Missing files: {missing}")


if __name__ == "__main__":
    pack()
