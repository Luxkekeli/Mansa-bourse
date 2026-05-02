import requests
from bs4 import BeautifulSoup

headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
session = requests.Session()
session.headers.update(headers)

# Step 1: GET the download page to get CSRF token
print("=== Step 1: GET download page for CSRF token ===")
r = session.get('https://www.sikafinance.com/marches/download/SNTS.sn')
soup = BeautifulSoup(r.text, 'html.parser')
token = soup.find('input', {'name': '__RequestVerificationToken'})
csrf = token['value'] if token else ''
print(f"CSRF token: {csrf[:40]}...")

# Step 2: POST to download CSV
print("\n=== Step 2: POST to download CSV (1 month) ===")
data = {
    'dtFrom': '2025-01-01',
    'dtTo': '2025-01-31',
    '__Invariant': ['dtFrom', 'dtTo'],
    '__RequestVerificationToken': csrf
}
r2 = session.post('https://www.sikafinance.com/marches/download/SNTS.sn', data=data)
print(f"Status: {r2.status_code}")
print(f"Content-Type: {r2.headers.get('Content-Type', 'N/A')}")
print(f"Content-Disposition: {r2.headers.get('Content-Disposition', 'N/A')}")
print(f"Content length: {len(r2.content)} bytes")
content = r2.text[:1500]
print(f"Content preview:\n{content}")

# Step 3: Test historiques with URL parameters
print("\n\n=== Step 3: Test historiques with query params ===")
for params in [
    {'periode': '0', 'dtFrom': '2024-01-01', 'dtTo': '2024-12-31'},
    {'Periode': '0', 'dtFrom': '2024-01-01', 'dtTo': '2024-12-31'},
    {'period': '0', 'from': '2024-01-01', 'to': '2024-12-31'},
]:
    r3 = session.get('https://www.sikafinance.com/marches/historiques/SNTS.sn', params=params)
    soup3 = BeautifulSoup(r3.text, 'html.parser')
    table = soup3.find('table')
    rows = table.find_all('tr') if table else []
    print(f"Params {params} => {len(rows)} rows")
    if rows and len(rows) > 1:
        cells = rows[1].find_all('td')
        if cells:
            print(f"  First data row: {[c.get_text(strip=True) for c in cells[:3]]}")
        cells_last = rows[-1].find_all('td')
        if cells_last:
            print(f"  Last data row: {[c.get_text(strip=True) for c in cells_last[:3]]}")
