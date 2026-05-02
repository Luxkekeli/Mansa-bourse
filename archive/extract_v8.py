import zipfile, os

src = r'C:\Users\Kekeli.Donon\Desktop\brvm2\bonjour_finance_v8_responsive_dashboard.zip'
dst = r'D:\KLAUD\Claude_KI\v8build'

os.makedirs(dst, exist_ok=True)
with zipfile.ZipFile(src, 'r') as z:
    z.extractall(dst)
    print(f"Extracted {len(z.namelist())} files")

for root, dirs, files in os.walk(dst):
    level = root.replace(dst, '').count(os.sep)
    indent = ' ' * 2 * level
    print(f'{indent}{os.path.basename(root)}/')
    subindent = ' ' * 2 * (level + 1)
    for file in files:
        fpath = os.path.join(root, file)
        size = os.path.getsize(fpath)
        print(f'{subindent}{file} ({size:,} bytes)')
