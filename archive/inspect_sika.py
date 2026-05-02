import requests
from bs4 import BeautifulSoup

headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}

# Check download page structure
print("=== DOWNLOAD PAGE ===")
r = requests.get('https://www.sikafinance.com/marches/download/SNTS.sn', headers=headers)
print(f"Status: {r.status_code}, URL: {r.url}")
soup = BeautifulSoup(r.text, 'html.parser')
forms = soup.find_all('form')
print(f"Forms found: {len(forms)}")
for i, f in enumerate(forms):
    print(f"Form {i}: action={f.get('action')}, method={f.get('method')}")
    for inp in f.find_all(['input', 'select', 'button']):
        print(f"  {inp.name}: name={inp.get('name')}, type={inp.get('type')}, id={inp.get('id')}, value={inp.get('value', '')[:50]}")

# Look for any script tags with API URLs
scripts = soup.find_all('script')
for s in scripts:
    txt = s.string or ''
    if 'ajax' in txt.lower() or 'fetch' in txt.lower() or '/api/' in txt.lower() or 'download' in txt.lower() or 'historique' in txt.lower():
        print(f"\n=== SCRIPT WITH API/DOWNLOAD ===\n{txt[:2000]}")

print("\n\n=== HISTORIQUES PAGE ===")
r2 = requests.get('https://www.sikafinance.com/marches/historiques/SNTS.sn', headers=headers)
print(f"Status: {r2.status_code}, URL: {r2.url}")
soup2 = BeautifulSoup(r2.text, 'html.parser')
forms2 = soup2.find_all('form')
print(f"Forms found: {len(forms2)}")
for i, f in enumerate(forms2):
    print(f"Form {i}: action={f.get('action')}, method={f.get('method')}")
    for inp in f.find_all(['input', 'select', 'button', 'option']):
        print(f"  {inp.name}: name={inp.get('name')}, type={inp.get('type')}, id={inp.get('id')}, value={inp.get('value', '')[:80]}")

# Check table data
table = soup2.find('table')
if table:
    rows = table.find_all('tr')
    print(f"\nTable rows: {len(rows)}")
    for row in rows[:3]:
        cells = row.find_all(['th', 'td'])
        print([c.get_text(strip=True) for c in cells])

# Look for scripts with data/AJAX
for s in soup2.find_all('script'):
    txt = s.string or ''
    if 'ajax' in txt.lower() or 'fetch' in txt.lower() or '/api/' in txt.lower() or 'getJSON' in txt.lower() or 'historique' in txt.lower() or 'periode' in txt.lower():
        print(f"\n=== SCRIPT ===\n{txt[:3000]}")
