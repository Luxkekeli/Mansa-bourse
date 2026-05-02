#!/usr/bin/env python3
"""
Scraper RichBourse.com - Données OHLCV BRVM (1 an de chandelier par ticker)
+ Fusion avec données Sikafinance existantes
"""

import requests
import re
import csv
import json
import os
import time
import sys
from datetime import datetime, timedelta

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'fr-FR,fr;q=0.9,en;q=0.8',
    'Referer': 'https://www.richbourse.com/',
}

BASE_URL = "https://www.richbourse.com/common/mouvements/index/"
OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "brvm_data")
os.makedirs(OUT_DIR, exist_ok=True)

# All BRVM tickers from richbourse
TICKERS = [
    "ABJC", "BICB", "BICC", "BNBC", "BOAB", "BOABF", "BOAC", "BOAM",
    "BOAN", "BOAS", "CABC", "CBIBF", "CFAC", "CIEC", "ECOC", "ETIT",
    "FTSC", "LNBB", "NEIC", "NSBC", "NTLC", "ONTBF", "ORAC", "ORGT",
    "PALC", "PRSC", "SAFC", "SCRC", "SDCC", "SDSC", "SEMC", "SGBC",
    "SHEC", "SIBC", "SICC", "SIVC", "SLBC", "SMBC", "SNTS", "SOGC",
    "SPHC", "STAC", "STBC", "SVOC", "TTLC", "TTLS", "UNLC", "UNXC"
]

TICKER_NAMES = {
    "ABJC": "Servair Abidjan", "BICB": "BIIC Benin", "BICC": "BICICI",
    "BNBC": "Bernabe CI", "BOAB": "BOA Benin", "BOABF": "BOA Burkina Faso",
    "BOAC": "BOA Cote d'Ivoire", "BOAM": "BOA Mali", "BOAN": "BOA Niger",
    "BOAS": "BOA Senegal", "CABC": "Sicable CI", "CBIBF": "Coris Bank International",
    "CFAC": "CFAO Motors CI", "CIEC": "CIE CI", "ECOC": "Ecobank CI",
    "ETIT": "Ecobank Transnational", "FTSC": "Filtisac CI", "LNBB": "LNB Benin",
    "NEIC": "NEI-CEDA CI", "NSBC": "NSIA Banque CI", "NTLC": "Nestle CI",
    "ONTBF": "Onatel BF", "ORAC": "Orange CI", "ORGT": "Oragroup Togo",
    "PALC": "Palm CI", "PRSC": "Tractafric Motors CI", "SAFC": "SAFCA CI",
    "SCRC": "Sucrivoire CI", "SDCC": "SODE CI", "SDSC": "Bollore-AGL CI",
    "SEMC": "Crown SIEM CI", "SGBC": "SGB CI", "SHEC": "Vivo Energy CI",
    "SIBC": "SIB CI", "SICC": "SICOR CI", "SIVC": "Air Liquide CI",
    "SLBC": "Solibra CI", "SMBC": "SMB CI", "SNTS": "Sonatel SN",
    "SOGC": "SOGB CI", "SPHC": "SAPH CI", "STAC": "SETAO CI",
    "STBC": "SITAB CI", "SVOC": "Movis CI", "TTLC": "TotalEnergies CI",
    "TTLS": "TotalEnergies SN", "UNLC": "Unilever CI", "UNXC": "Uniwax CI"
}

session = requests.Session()
session.headers.update(HEADERS)


def extract_ohlcv_from_html(html, ticker):
    """Extract OHLCV data arrays from Highcharts JavaScript in page source."""
    rows = []
    
    # Pattern 1: OHLC arrays like [timestamp, open, high, low, close]
    ohlc_pattern = r'\[(\d{13}),(\d+(?:\.\d+)?),(\d+(?:\.\d+)?),(\d+(?:\.\d+)?),(\d+(?:\.\d+)?)\]'
    ohlc_matches = re.findall(ohlc_pattern, html)
    
    # Pattern 2: Simple price arrays like [timestamp, price]
    simple_pattern = r'\[(\d{13}),(\d+(?:\.\d+)?)\]'
    simple_matches = re.findall(simple_pattern, html)
    
    # Pattern 3: Volume data - look for volume arrays
    # They appear as separate arrays, typically after the price data
    vol_pattern = r'\[(\d{13}),(\d+)\]'
    
    if ohlc_matches:
        # Group by unique timestamps to avoid duplicates
        seen_ts = set()
        ohlc_data = []
        for m in ohlc_matches:
            ts = int(m[0])
            if ts not in seen_ts:
                seen_ts.add(ts)
                ohlc_data.append({
                    'timestamp': ts,
                    'open': float(m[1]),
                    'high': float(m[2]),
                    'low': float(m[3]),
                    'close': float(m[4])
                })
        
        # Try to extract volume data
        # Volume arrays appear as [timestamp, volume] pairs after OHLC data
        # Split HTML to find volume section
        vol_map = {}
        # Look for volume data block - usually after 'column' chart type
        vol_section = html.split('type: \'column\'')
        if len(vol_section) > 1:
            vol_matches = re.findall(vol_pattern, vol_section[-1][:50000])
            for vm in vol_matches:
                vol_map[int(vm[0])] = int(vm[1])
        
        # If no volume from column section, try another approach
        if not vol_map:
            # Find all [ts, number] pairs that aren't in OHLC
            all_pairs = re.findall(r'\[(\d{13}),(\d+)\]', html)
            # Group pairs by occurrence order
            pair_groups = {}
            for p in all_pairs:
                ts = int(p[0])
                val = int(p[1])
                if ts not in pair_groups:
                    pair_groups[ts] = []
                pair_groups[ts].append(val)
            # Volume is typically the last value group that isn't a price
            for ts, vals in pair_groups.items():
                if len(vals) > 1:
                    # Last occurrence is likely volume
                    vol_map[ts] = vals[-1]
        
        for d in sorted(ohlc_data, key=lambda x: x['timestamp']):
            dt = datetime.utcfromtimestamp(d['timestamp'] / 1000)
            vol = vol_map.get(d['timestamp'], 0)
            rows.append({
                'symbol': ticker,
                'date': dt.strftime('%Y-%m-%d'),
                'open': d['open'],
                'high': d['high'],
                'low': d['low'],
                'close': d['close'],
                'volume': vol,
                'source': 'richbourse'
            })
    
    elif simple_matches:
        seen_ts = set()
        for m in simple_matches:
            ts = int(m[0])
            if ts not in seen_ts:
                seen_ts.add(ts)
                dt = datetime.utcfromtimestamp(ts / 1000)
                price = float(m[1])
                rows.append({
                    'symbol': ticker,
                    'date': dt.strftime('%Y-%m-%d'),
                    'open': price,
                    'high': price,
                    'low': price,
                    'close': price,
                    'volume': 0,
                    'source': 'richbourse'
                })
    
    return rows


def scrape_ticker(ticker):
    """Scrape one ticker from richbourse."""
    url = f"{BASE_URL}{ticker}"
    try:
        resp = session.get(url, timeout=30)
        if resp.status_code != 200:
            print(f"  [{ticker}] HTTP {resp.status_code}")
            return []
        
        html = resp.text
        if "ne sont pas disponibles" in html:
            print(f"  [{ticker}] Pas de donnees disponibles")
            return []
        
        rows = extract_ohlcv_from_html(html, ticker)
        return rows
    
    except Exception as e:
        print(f"  [{ticker}] Erreur: {e}")
        return []


def load_existing_sikafinance():
    """Load existing sikafinance data from brvm_data."""
    all_data = {}
    master_file = os.path.join(OUT_DIR, "BRVM_ALL_TICKERS_1998_2026.csv")
    
    if os.path.exists(master_file):
        with open(master_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f, delimiter=';')
            for row in reader:
                sym = row.get('symbole', '')
                date_str = row.get('date', '')
                if sym and date_str:
                    # Convert DD/MM/YYYY to YYYY-MM-DD
                    try:
                        parts = date_str.split('/')
                        if len(parts) == 3:
                            iso_date = f"{parts[2]}-{parts[1]}-{parts[0]}"
                        else:
                            iso_date = date_str
                    except:
                        iso_date = date_str
                    
                    key = f"{sym}|{iso_date}"
                    all_data[key] = {
                        'symbol': sym,
                        'date': iso_date,
                        'open': row.get('ouverture', '0'),
                        'high': row.get('haut', '0'),
                        'low': row.get('bas', '0'),
                        'close': row.get('cloture', '0'),
                        'volume': row.get('volume', '0'),
                        'name': row.get('nom', ''),
                        'source': 'sikafinance'
                    }
    
    print(f"Loaded {len(all_data)} existing records from sikafinance")
    return all_data


def merge_and_save(existing_data, richbourse_data):
    """Merge richbourse data with existing, preferring richbourse OHLC when available."""
    merged = dict(existing_data)
    new_count = 0
    updated_count = 0
    
    for row in richbourse_data:
        key = f"{row['symbol']}.ci|{row['date']}" if '.' not in row['symbol'] else f"{row['symbol']}|{row['date']}"
        
        # Try different key formats
        possible_keys = [
            f"{row['symbol']}|{row['date']}",
            f"{row['symbol']}.ci|{row['date']}",
            f"{row['symbol']}.sn|{row['date']}",
            f"{row['symbol']}.bj|{row['date']}",
            f"{row['symbol']}.bf|{row['date']}",
            f"{row['symbol']}.tg|{row['date']}",
            f"{row['symbol']}.ml|{row['date']}",
            f"{row['symbol']}.ne|{row['date']}",
        ]
        
        found_key = None
        for pk in possible_keys:
            if pk in merged:
                found_key = pk
                break
        
        if found_key:
            # Update if richbourse has better OHLC data (not all same value)
            existing = merged[found_key]
            if (row['open'] != row['high'] or row['high'] != row['low'] or 
                row['low'] != row['close']):
                # Richbourse has real OHLC data, update
                existing['open'] = row['open']
                existing['high'] = row['high']
                existing['low'] = row['low']
                existing['close'] = row['close']
                if row['volume'] > 0:
                    existing['volume'] = row['volume']
                existing['source'] = 'richbourse+sikafinance'
                updated_count += 1
        else:
            # New record
            ticker_suffix_map = {
                "BOAB": ".bj", "BICB": ".bj", "LNBB": ".bj",
                "BOABF": ".bf", "CBIBF": ".bf", "ONTBF": ".bf",
                "ETIT": ".tg", "ORGT": ".tg",
                "SNTS": ".sn", "BOAS": ".sn", "TTLS": ".sn",
                "BOAM": ".ml", "BOAN": ".ne",
            }
            suffix = ticker_suffix_map.get(row['symbol'], ".ci")
            full_sym = f"{row['symbol']}{suffix}"
            new_key = f"{full_sym}|{row['date']}"
            
            merged[new_key] = {
                'symbol': full_sym,
                'date': row['date'],
                'open': row['open'],
                'high': row['high'],
                'low': row['low'],
                'close': row['close'],
                'volume': row['volume'],
                'name': TICKER_NAMES.get(row['symbol'], row['symbol']),
                'source': 'richbourse'
            }
            new_count += 1
    
    print(f"Merge: {updated_count} updated with OHLC, {new_count} new records added")
    return merged


def save_all_outputs(merged_data):
    """Save merged data in multiple formats for trading platform integration."""
    
    # Sort all records
    records = sorted(merged_data.values(), key=lambda x: (x['symbol'], x['date']))
    
    # 1. Master CSV - All tickers combined (standard CSV format)
    master_file = os.path.join(OUT_DIR, "BRVM_MASTER_OHLCV.csv")
    with open(master_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['Symbol', 'Date', 'Open', 'High', 'Low', 'Close', 'Volume', 'Name', 'Source'])
        for r in records:
            writer.writerow([
                r['symbol'], r['date'], r['open'], r['high'], r['low'],
                r['close'], r['volume'], r.get('name', ''), r.get('source', '')
            ])
    print(f"Saved master: {master_file} ({len(records)} rows)")
    
    # 2. Individual ticker CSVs (trading-ready: Date,Open,High,Low,Close,Volume)
    by_ticker = {}
    for r in records:
        sym = r['symbol']
        if sym not in by_ticker:
            by_ticker[sym] = []
        by_ticker[sym].append(r)
    
    individual_dir = os.path.join(OUT_DIR, "tickers_ohlcv")
    os.makedirs(individual_dir, exist_ok=True)
    
    for sym, rows in sorted(by_ticker.items()):
        safe_name = sym.replace('.', '_')
        fpath = os.path.join(individual_dir, f"{safe_name}.csv")
        with open(fpath, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['Date', 'Open', 'High', 'Low', 'Close', 'Volume'])
            for r in sorted(rows, key=lambda x: x['date']):
                writer.writerow([r['date'], r['open'], r['high'], r['low'], r['close'], r['volume']])
        print(f"  {safe_name}.csv: {len(rows)} rows")
    
    # 3. JSON format for web charts (grouped by ticker)
    json_dir = os.path.join(OUT_DIR, "json")
    os.makedirs(json_dir, exist_ok=True)
    
    all_json = {}
    for sym, rows in sorted(by_ticker.items()):
        ticker_data = []
        for r in sorted(rows, key=lambda x: x['date']):
            ticker_data.append({
                't': r['date'],
                'o': float(r['open']) if r['open'] else 0,
                'h': float(r['high']) if r['high'] else 0,
                'l': float(r['low']) if r['low'] else 0,
                'c': float(r['close']) if r['close'] else 0,
                'v': int(float(r['volume'])) if r['volume'] else 0
            })
        all_json[sym] = ticker_data
        
        # Individual JSON
        safe_name = sym.replace('.', '_')
        with open(os.path.join(json_dir, f"{safe_name}.json"), 'w', encoding='utf-8') as f:
            json.dump(ticker_data, f, ensure_ascii=False)
    
    # Master JSON
    with open(os.path.join(json_dir, "brvm_all_tickers.json"), 'w', encoding='utf-8') as f:
        json.dump(all_json, f, ensure_ascii=False)
    print(f"Saved JSON: {len(all_json)} tickers")
    
    # 4. TradingView format (lightweight-charts compatible)
    tv_dir = os.path.join(OUT_DIR, "tradingview")
    os.makedirs(tv_dir, exist_ok=True)
    
    for sym, rows in sorted(by_ticker.items()):
        safe_name = sym.replace('.', '_')
        tv_data = []
        for r in sorted(rows, key=lambda x: x['date']):
            tv_data.append({
                'time': r['date'],
                'open': float(r['open']) if r['open'] else 0,
                'high': float(r['high']) if r['high'] else 0,
                'low': float(r['low']) if r['low'] else 0,
                'close': float(r['close']) if r['close'] else 0,
                'volume': int(float(r['volume'])) if r['volume'] else 0
            })
        with open(os.path.join(tv_dir, f"{safe_name}.json"), 'w', encoding='utf-8') as f:
            json.dump(tv_data, f, ensure_ascii=False)
    print(f"Saved TradingView format: {len(by_ticker)} tickers")
    
    # 5. Ticker metadata/catalog
    catalog = []
    for sym, rows in sorted(by_ticker.items()):
        dates = [r['date'] for r in rows if r['date']]
        if dates:
            catalog.append({
                'symbol': sym,
                'name': TICKER_NAMES.get(sym.split('.')[0], sym),
                'total_rows': len(rows),
                'first_date': min(dates),
                'last_date': max(dates),
                'has_ohlc': any(r['open'] != r['close'] or r['high'] != r['low'] for r in rows)
            })
    
    with open(os.path.join(OUT_DIR, "ticker_catalog.json"), 'w', encoding='utf-8') as f:
        json.dump(catalog, f, indent=2, ensure_ascii=False)
    print(f"Saved catalog: {len(catalog)} tickers")
    
    return len(records), len(by_ticker)


def main():
    print("=" * 60)
    print("SCRAPER RICHBOURSE.COM - Donnees OHLCV BRVM")
    print("=" * 60)
    
    # Step 1: Load existing sikafinance data
    print("\n[1/4] Chargement des donnees Sikafinance existantes...")
    existing_data = load_existing_sikafinance()
    
    # Step 2: Scrape richbourse for OHLCV data
    print(f"\n[2/4] Scraping RichBourse.com ({len(TICKERS)} tickers)...")
    all_richbourse = []
    
    for i, ticker in enumerate(TICKERS):
        print(f"  ({i+1}/{len(TICKERS)}) {ticker}...", end=" ", flush=True)
        rows = scrape_ticker(ticker)
        if rows:
            all_richbourse.extend(rows)
            print(f"{len(rows)} rows (OHLCV)")
        else:
            print("skip")
        time.sleep(1.5)  # Respectful rate limiting
    
    print(f"\nTotal RichBourse: {len(all_richbourse)} rows")
    
    # Save richbourse raw data
    rb_file = os.path.join(OUT_DIR, "richbourse_raw.csv")
    with open(rb_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['Symbol', 'Date', 'Open', 'High', 'Low', 'Close', 'Volume', 'Source'])
        for r in all_richbourse:
            writer.writerow([r['symbol'], r['date'], r['open'], r['high'], r['low'], r['close'], r['volume'], r['source']])
    
    # Step 3: Merge data
    print(f"\n[3/4] Fusion des donnees...")
    merged = merge_and_save(existing_data, all_richbourse)
    
    # Step 4: Save all output formats
    print(f"\n[4/4] Sauvegarde des fichiers structures...")
    total_rows, total_tickers = save_all_outputs(merged)
    
    print("\n" + "=" * 60)
    print(f"TERMINE!")
    print(f"  Total: {total_rows} lignes, {total_tickers} tickers")
    print(f"  Dossier: {OUT_DIR}")
    print(f"  Formats: CSV, JSON, TradingView")
    print("=" * 60)


if __name__ == "__main__":
    main()
