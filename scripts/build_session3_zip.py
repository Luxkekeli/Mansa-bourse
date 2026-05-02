#!/usr/bin/env python3
"""Build the v2.2-session3 release ZIP."""

import os
import zipfile

OUT = r"C:\Users\Kekeli.Donon\Desktop\brvm2\MANSA_v2.2_session3.zip"
BASE = r"D:\KLAUD\Claude_KI\mansa"
DB_SRC = r"D:\KLAUD\Claude_KI\mansa.db"
PREFIX = "mansa_v2.2-session3/"

EXCLUDE_DIRS = {
    "__pycache__", ".pytest_cache", ".ruff_cache", ".mypy_cache",
    "node_modules", ".venv", "venv", "logs",
}
EXCLUDE_EXT = {".pyc", ".pyo", ".log"}

os.makedirs(os.path.dirname(OUT), exist_ok=True)

count = 0
total = 0
with zipfile.ZipFile(OUT, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as z:
    for root, dirs, files in os.walk(BASE):
        dirs[:] = sorted(d for d in dirs if d not in EXCLUDE_DIRS)
        for fname in sorted(files):
            ext = os.path.splitext(fname)[1].lower()
            if ext in EXCLUDE_EXT:
                continue
            fpath = os.path.join(root, fname)
            arcname = PREFIX + os.path.relpath(fpath, BASE).replace("\\", "/")
            z.write(fpath, arcname)
            total += os.path.getsize(fpath)
            count += 1

    if os.path.exists(DB_SRC):
        z.write(DB_SRC, PREFIX + "mansa.db")
        total += os.path.getsize(DB_SRC)
        count += 1

zip_size = os.path.getsize(OUT)
print()
print("=" * 56)
print("  MANSA v2.2-session3 - Release Archive")
print("=" * 56)
print(f"  Files:     {count}")
print(f"  Raw size:  {total:,} bytes ({total/1024/1024:.1f} MB)")
print(f"  ZIP size:  {zip_size:,} bytes ({zip_size/1024/1024:.1f} MB)")
print(f"  Ratio:     {zip_size/total*100:.1f}%")
print(f"  Location:  {OUT}")
print("=" * 56)
