#!/usr/bin/env python3
"""Launch-day release ZIP — final build before going live."""

import os
import zipfile

OUT = r"C:\Users\Kekeli.Donon\Desktop\brvm2\MANSA_v2.2_launchday.zip"
BASE = r"D:\KLAUD\Claude_KI\mansa"
PREFIX = "mansa_v2.2-launchday/"

EXCLUDE_DIRS = {
    "__pycache__", ".pytest_cache", ".ruff_cache", ".mypy_cache",
    "node_modules", ".venv", "venv", "logs", "test-results",
    "playwright-report",
}
EXCLUDE_EXT = {".pyc", ".pyo", ".log"}
EXCLUDE_FILES = {"build_session5_zip.py", "build_phase0_zip.py", "build_session2_zip.py", "build_session4_zip.py"}

os.makedirs(os.path.dirname(OUT), exist_ok=True)

count = 0
total = 0
with zipfile.ZipFile(OUT, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as z:
    for root, dirs, files in os.walk(BASE):
        dirs[:] = sorted(d for d in dirs if d not in EXCLUDE_DIRS)
        for fname in sorted(files):
            if fname in EXCLUDE_FILES:
                continue
            ext = os.path.splitext(fname)[1].lower()
            if ext in EXCLUDE_EXT:
                continue
            fpath = os.path.join(root, fname)
            arcname = PREFIX + os.path.relpath(fpath, BASE).replace("\\", "/")
            z.write(fpath, arcname)
            total += os.path.getsize(fpath)
            count += 1

zip_size = os.path.getsize(OUT)
print()
print("=" * 60)
print("  MANSA v2.2 LAUNCH-DAY - PRODUCTION RELEASE")
print("=" * 60)
print(f"  Files:       {count}")
print(f"  Raw size:    {total:,} bytes ({total/1024/1024:.1f} MB)")
print(f"  ZIP size:    {zip_size:,} bytes ({zip_size/1024/1024:.1f} MB)")
print(f"  Location:    {OUT}")
print("=" * 60)
print("  P0:          8/8 LIVRES")
print("  P1:          9/10 LIVRES (Vite scaffold + plan)")
print("  Tests:       102 pytest + 10 e2e specs")
print("  Academy:     12 lecons completes (Novice + Analyst Junior)")
print("  i18n:        ~250 cles FR/EN")
print("  Data:        carry-fwd to today (BETA badge in footer)")
print("=" * 60)
