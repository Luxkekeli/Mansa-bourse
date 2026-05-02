import zipfile, os

out = r'C:\Users\Kekeli.Donon\Desktop\brvm2\MANSA_v2.1_complete.zip'
base = r'D:\KLAUD\Claude_KI'
prefix = 'mansa_v2.1/'

# Directories and files to EXCLUDE
EXCLUDE_DIRS = {'.git', '__pycache__', '.agents', '.claude', 'node_modules', 'v8build', 'v8_platform'}
EXCLUDE_FILES = {
    'bonjour_finance_v4_community (1).zip',
    'bonjour_finance_v5_graphique (1).zip',
    'bonjour_finance_v5_graphique.zip',
    'bonjour_finance_v6_security.zip',
    'skills-lock.json',
    'app (1).html',  # duplicate
}
EXCLUDE_EXT = {'.pyc', '.pyo'}

# Ensure output directory exists
os.makedirs(os.path.dirname(out), exist_ok=True)

z = zipfile.ZipFile(out, 'w', zipfile.ZIP_DEFLATED)
count = 0
total_size = 0

for root, dirs, files in os.walk(base):
    # Skip excluded directories
    dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]

    for fname in sorted(files):
        # Skip excluded files
        if fname in EXCLUDE_FILES:
            continue
        ext = os.path.splitext(fname)[1].lower()
        if ext in EXCLUDE_EXT:
            continue

        fpath = os.path.join(root, fname)
        arcname = prefix + os.path.relpath(fpath, base).replace('\\', '/')

        z.write(fpath, arcname)
        fsize = os.path.getsize(fpath)
        total_size += fsize
        count += 1
        print(f'  + {arcname}  ({fsize:,} bytes)')

z.close()

zip_size = os.path.getsize(out)
print(f'\n{"="*50}')
print(f'  MANSA v2.1 — Complete Archive')
print(f'{"="*50}')
print(f'  Files:     {count}')
print(f'  Raw size:  {total_size:,} bytes ({total_size/1024/1024:.1f} MB)')
print(f'  ZIP size:  {zip_size:,} bytes ({zip_size/1024/1024:.1f} MB)')
print(f'  Ratio:     {zip_size/total_size*100:.1f}%')
print(f'  Location:  {out}')
print(f'{"="*50}')
