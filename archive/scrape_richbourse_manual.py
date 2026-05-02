#!/usr/bin/env python3
"""
Scraper RichBourse avec navigateur reel (Selenium).
UTILISATION:
  1. pip install selenium
  2. python scrape_richbourse_manual.py
  3. Le navigateur s'ouvre - resoudre le captcha manuellement
  4. Appuyer sur ENTREE dans le terminal
  5. Le script scrape automatiquement les 48 tickers
"""

import csv
import json
import os
import re
import time
import sys
from datetime import datetime

try:
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
except ImportError:
    print("Installation de selenium...")
    os.system(f"{sys.executable} -m pip install selenium")
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "brvm_data")
OUT_FILE = os.path.join(DATA_DIR, "richbourse_ohlcv_complete.csv")

TICKERS = [
    "ABJC", "BICB", "BICC", "BNBC", "BOAB", "BOABF", "BOAC", "BOAM",
    "BOAN", "BOAS", "CABC", "CBIBF", "CFAC", "CIEC", "ECOC", "ETIT",
    "FTSC", "LNBB", "NEIC", "NSBC", "NTLC", "ONTBF", "ORAC", "ORGT",
    "PALC", "PRSC", "SAFC", "SCRC", "SDCC", "SDSC", "SEMC", "SGBC",
    "SHEC", "SIBC", "SICC", "SIVC", "SLBC", "SMBC", "SNTS", "SOGC",
    "SPHC", "STAC", "STBC", "SVOC", "TTLC", "TTLS", "UNLC", "UNXC"
]

SUFFIX_MAP = {
    "BOAB": ".bj", "BICB": ".bj", "LNBB": ".bj",
    "BOABF": ".bf", "CBIBF": ".bf", "ONTBF": ".bf",
    "ETIT": ".tg", "ORGT": ".tg",
    "SNTS": ".sn", "BOAS": ".sn", "TTLS": ".sn",
    "BOAM": ".ml", "BOAN": ".ne",
}


def extract_ohlcv(page_source, ticker):
    """Extract OHLCV from Highcharts JS embedded in page."""
    rows = []
    
    # OHLC: [timestamp, open, high, low, close]
    ohlc_pattern = r'\[(\d{13}),(\d+(?:\.\d+)?),(\d+(?:\.\d+)?),(\d+(?:\.\d+)?),(\d+(?:\.\d+)?)\]'
    ohlc_matches = re.findall(ohlc_pattern, page_source)
    
    # Volume: [timestamp, volume] after 'column' type chart
    vol_map = {}
    vol_section = page_source.split("type: 'column'")
    if len(vol_section) > 1:
        vol_matches = re.findall(r'\[(\d{13}),(\d+)\]', vol_section[-1][:100000])
        for vm in vol_matches:
            vol_map[int(vm[0])] = int(vm[1])
    
    seen = set()
    for m in ohlc_matches:
        ts = int(m[0])
        if ts in seen:
            continue
        seen.add(ts)
        dt = datetime.utcfromtimestamp(ts / 1000)
        suffix = SUFFIX_MAP.get(ticker, ".ci")
        rows.append({
            'Symbol': f"{ticker}{suffix}",
            'Date': dt.strftime('%Y-%m-%d'),
            'Open': float(m[1]),
            'High': float(m[2]),
            'Low': float(m[3]),
            'Close': float(m[4]),
            'Volume': vol_map.get(ts, 0)
        })
    
    return sorted(rows, key=lambda x: x['Date'])


def main():
    print("=" * 60)
    print("  SCRAPER RICHBOURSE - Mode Navigateur Reel")
    print("=" * 60)
    
    # Setup Chrome
    options = Options()
    options.add_argument("--start-maximized")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)
    
    print("\nOuverture du navigateur Chrome...")
    driver = webdriver.Chrome(options=options)
    
    # Navigate to richbourse to trigger captcha
    driver.get("https://www.richbourse.com/common/mouvements/index/SGBC")
    
    print("\n" + "!" * 60)
    print("  IMPORTANT: Resolvez le captcha dans le navigateur")
    print("  puis appuyez sur ENTREE ici quand la page est chargee")
    print("!" * 60)
    input("\n>>> Appuyez sur ENTREE apres avoir resolu le captcha... ")
    
    # Verify page loaded
    if "mouvements" not in driver.current_url:
        print("La page ne semble pas chargee. Reessayez.")
        input(">>> Appuyez sur ENTREE quand la page est prete... ")
    
    all_rows = []
    
    for i, ticker in enumerate(TICKERS):
        url = f"https://www.richbourse.com/common/mouvements/index/{ticker}"
        print(f"  ({i+1}/{len(TICKERS)}) {ticker}...", end=" ", flush=True)
        
        try:
            driver.get(url)
            time.sleep(2)  # Wait for page + JS to load
            
            # Check for captcha again
            if "sgcaptcha" in driver.current_url or "Robot" in driver.title:
                print("CAPTCHA! Resolvez-le...")
                input(">>> ENTREE quand pret... ")
            
            source = driver.page_source
            
            if "ne sont pas disponibles" in source:
                print("pas de donnees")
                continue
            
            rows = extract_ohlcv(source, ticker)
            if rows:
                all_rows.extend(rows)
                print(f"{len(rows)} lignes OHLCV")
            else:
                print("0 lignes")
        
        except Exception as e:
            print(f"ERREUR: {e}")
    
    driver.quit()
    
    # Save CSV
    if all_rows:
        with open(OUT_FILE, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=['Symbol', 'Date', 'Open', 'High', 'Low', 'Close', 'Volume'])
            writer.writeheader()
            writer.writerows(all_rows)
        
        print(f"\n{'=' * 60}")
        print(f"  TERMINE! {len(all_rows)} lignes sauvegardees")
        print(f"  Fichier: {OUT_FILE}")
        print(f"  Lancez ensuite: python consolidate_data.py")
        print(f"{'=' * 60}")
    else:
        print("\nAucune donnee recuperee.")


if __name__ == "__main__":
    main()
