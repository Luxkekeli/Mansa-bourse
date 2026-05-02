"""
Bonjour-Finance v18 — MANSA Strategy: News, Parcours Academy, Défis, Parrainage, Daily Streak
"""
import zipfile, os, sys

SRC = r'D:\KLAUD\Claude_KI\v8build\bonjour_secure'
DST = os.path.join(os.path.expanduser('~'), 'Desktop', 'bonjour_finance_v18_mansa.zip')
EXCLUDE_DIRS = {'.ratelimit', '__pycache__', '.git', 'node_modules'}
EXCLUDE_EXT = {'.pyc', '.pyo'}

count = 0
total_size = 0

with zipfile.ZipFile(DST, 'w', zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
    for root, dirs, files in os.walk(SRC):
        # Filter excluded dirs in-place
        dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]
        for fname in files:
            if any(fname.endswith(ext) for ext in EXCLUDE_EXT):
                continue
            full = os.path.join(root, fname)
            arc = 'bonjour_secure/' + os.path.relpath(full, SRC).replace('\\', '/')
            fsize = os.path.getsize(full)
            zf.write(full, arc)
            count += 1
            total_size += fsize

zip_size = os.path.getsize(DST)
print(f"=== Bonjour-Finance v18 MANSA — ZIP created ===")
print(f"Files: {count}")
print(f"Uncompressed: {total_size/1024/1024:.1f} MB")
print(f"Compressed:   {zip_size/1024/1024:.1f} MB")
print(f"Output: {DST}")
print("Done!")
