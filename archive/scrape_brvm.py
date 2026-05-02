#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
BRVM Historical Data Scraper v3.0 - Multi-threaded
Recupere les donnees historiques de TOUS les titres BRVM (1998-2026)
Source: Sikafinance.com | 5 workers paralleles | Reprise automatique
"""

import os, sys, io, csv, time, json, logging, threading
from datetime import datetime
from io import StringIO
from pathlib import Path
from calendar import monthrange
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests
from bs4 import BeautifulSoup
import pandas as pd

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# --- Config ---
DOWNLOAD_URL = "https://www.sikafinance.com/marches/download"
OUTPUT_DIR = Path(r"D:\KLAUD\Claude_KI\brvm_data")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

LOG_FILE = OUTPUT_DIR / "scrape.log"
PROGRESS_FILE = OUTPUT_DIR / "progress.json"
END_DATE = datetime(2026, 3, 17)
WORKERS = 5
DELAY = 0.8

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept-Language': 'fr-FR,fr;q=0.9',
}

BRVM_TICKERS = {
    "SDSC.ci":"AFRICA GLOBAL LOGISTICS CI","BNBC.ci":"BERNABE CI","BICC.ci":"BICICI",
    "CFAC.ci":"CFAO CI","CIEC.ci":"CIE CI","SEMC.ci":"CROWN SIEM CI",
    "ECOC.ci":"ECOBANK CI","SIVC.ci":"ERIUM CI","FTSC.ci":"FILTISAC CI",
    "SVOC.ci":"MOVIS CI","NEIC.ci":"NEI CEDA CI","NTLC.ci":"NESTLE CI",
    "NSBC.ci":"NSIA BANQUE CI","ORAC.ci":"ORANGE CI","PALC.ci":"PALMCI",
    "SAFC.ci":"SAFCA CI","SPHC.ci":"SAPH CI","ABJC.ci":"SERVAIR ABIDJAN CI",
    "STAC.ci":"SETAO CI","SGBC.ci":"SGBCI","CABC.ci":"SICABLE CI",
    "SICC.ci":"SICOR CI","STBC.ci":"SITAB CI","SMBC.ci":"SMB CI",
    "SIBC.ci":"SIB CI","SDCC.ci":"SODECI","SOGC.ci":"SOGB CI",
    "SLBC.ci":"SOLIBRA CI","SCRC.ci":"SUCRIVOIRE CI","TTLC.ci":"TOTALENERGIES CI",
    "PRSC.ci":"TRACTAFRIC MOTORS CI","UNLC.ci":"UNILEVER CI","UNXC.ci":"UNIWAX CI",
    "SHEC.ci":"VIVO ENERGY CI","SNTS.sn":"SONATEL SN","TTLS.sn":"TOTALENERGIES SN",
    "BOAS.sn":"BANK OF AFRICA SN","BOAB.bj":"BANK OF AFRICA BJ",
    "BICB.bj":"BICB BJ","LNBB.bj":"LOTERIE NATIONALE BJ",
    "BOABF.bf":"BANK OF AFRICA BF","CBIBF.bf":"CORIS BANK BF","ONTBF.bf":"ONATEL BF",
    "BOAM.ml":"BANK OF AFRICA ML","BOAN.ne":"BANK OF AFRICA NE",
    "ETIT.tg":"ETI TG","ORGT.tg":"ORAGROUP TG",
    "BRVMC":"BRVM COMPOSITE","BRVM30":"BRVM 30",
    "BRVM-FI":"BRVM FINANCE","BRVM-AG":"BRVM AGRICULTURE",
    "BRVM-DI":"BRVM DISTRIBUTION","BRVM-IN":"BRVM INDUSTRIE",
    "BRVM-SP":"BRVM SERVICES PUBLICS","BRVM-TR":"BRVM TRANSPORT",
    "BRVM-EN":"BRVM ENERGIE","BRVM-OT":"BRVM AUTRES SECTEURS",
    "CAPIBRVM":"CAPITALISATION BRVM",
}

# --- Logging ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(message)s',
    datefmt='%H:%M:%S',
    handlers=[
        logging.FileHandler(LOG_FILE, encoding='utf-8', mode='w'),
        logging.StreamHandler(sys.stdout)
    ]
)
log = logging.getLogger(__name__)

# --- Thread-safe progress ---
_lock = threading.Lock()

def load_progress():
    if PROGRESS_FILE.exists():
        try:
            with open(PROGRESS_FILE, 'r') as f:
                return json.load(f)
        except:
            pass
    return {}

def save_progress(progress):
    with _lock:
        with open(PROGRESS_FILE, 'w') as f:
            json.dump(progress, f)

def mark_done(progress, key, rows):
    with _lock:
        progress[key] = rows


# --- Single-ticker scraper (runs in its own thread) ---
def scrape_one_ticker(ticker, name, progress):
    """Scrape all data for one ticker. Returns (ticker, total_rows)."""
    safe = ticker.replace('.','_').replace('-','_')
    out_file = OUTPUT_DIR / f"{safe}.csv"

    # Already done?
    done_key = f"DONE_{ticker}"
    if done_key in progress:
        return (ticker, progress[done_key])

    session = requests.Session()
    session.headers.update(HEADERS)

    def get_csrf():
        try:
            r = session.get(f"{DOWNLOAD_URL}/{ticker}", timeout=15)
            soup = BeautifulSoup(r.text, 'html.parser')
            t = soup.find('input', {'name': '__RequestVerificationToken'})
            return t['value'] if t else None
        except:
            return None

    def download_month(dt_from, dt_to, csrf):
        time.sleep(DELAY)
        try:
            r = session.post(f"{DOWNLOAD_URL}/{ticker}", data={
                'dtFrom': dt_from, 'dtTo': dt_to,
                '__Invariant': ['dtFrom', 'dtTo'],
                '__RequestVerificationToken': csrf
            }, timeout=20)
            if 'text/csv' in r.headers.get('Content-Type',''):
                return list(csv.DictReader(StringIO(r.text), delimiter=';'))
        except:
            pass
        return []

    # Phase 1: Probe to find data range (test Jan of key years)
    csrf = get_csrf()
    if not csrf:
        log.info(f"  {ticker}: no CSRF, skip")
        mark_done(progress, done_key, 0)
        return (ticker, 0)

    first_year = None
    for y in [2025, 2020, 2015, 2010, 2005, 2000, 1999, 1998]:
        if y > END_DATE.year:
            continue
        m = 9 if y == 1998 else 1
        _, ld = monthrange(y, m)
        rows = download_month(f"{y}-{m:02d}-01", f"{y}-{m:02d}-{ld:02d}", csrf)
        if rows:
            first_year = y
        elif first_year is not None:
            break  # found the boundary
        # Refresh CSRF periodically
        if not rows:
            new_csrf = get_csrf()
            if new_csrf:
                csrf = new_csrf

    if first_year is None:
        log.info(f"  {ticker}: no data found")
        mark_done(progress, done_key, 0)
        return (ticker, 0)

    log.info(f"  {ticker}: data from ~{first_year}")

    # Phase 2: Download month by month
    all_rows = []
    empty_streak = 0

    for year in range(first_year, END_DATE.year + 1):
        sm = 9 if year == 1998 else 1
        em = END_DATE.month if year == END_DATE.year else 12

        for month in range(sm, em + 1):
            mkey = f"{ticker}_{year}_{month:02d}"
            if mkey in progress:
                if progress[mkey] > 0:
                    empty_streak = 0
                continue

            _, ld = monthrange(year, month)
            last = min(datetime(year, month, ld), END_DATE)
            dt_from = f"{year}-{month:02d}-01"
            dt_to = last.strftime('%Y-%m-%d')

            rows = download_month(dt_from, dt_to, csrf)
            n = len(rows)

            if n > 0:
                all_rows.extend(rows)
                empty_streak = 0
            else:
                empty_streak += 1

            mark_done(progress, mkey, n)

            # Refresh CSRF every ~20 requests
            if (month % 6 == 0):
                new_csrf = get_csrf()
                if new_csrf:
                    csrf = new_csrf

            # Skip ahead if 18+ empty months (delisted period)
            if empty_streak >= 18 and year < 2022:
                log.info(f"  {ticker}: gap at {year}-{month:02d}, skipping to 2022")
                for sy in range(year, 2022):
                    for sm2 in range(1, 13):
                        mark_done(progress, f"{ticker}_{sy}_{sm2:02d}", 0)
                empty_streak = 0
                break

        # Save progress per year
        save_progress(progress)

        if empty_streak >= 18 and year < 2022:
            continue

    # Phase 3: Save CSV
    total = 0
    if all_rows:
        new_df = pd.DataFrame(all_rows)
        if out_file.exists():
            try:
                old_df = pd.read_csv(out_file, sep=';', dtype=str)
                new_df = pd.concat([old_df, new_df], ignore_index=True)
                new_df.drop_duplicates(subset=['date'], keep='last', inplace=True)
            except:
                pass
        try:
            new_df['_s'] = pd.to_datetime(new_df['date'], format='%d/%m/%Y', errors='coerce')
            new_df.sort_values('_s', inplace=True)
            new_df.drop(columns=['_s'], inplace=True)
        except:
            pass
        new_df.to_csv(out_file, sep=';', index=False)
        total = len(new_df)
    elif out_file.exists():
        total = len(pd.read_csv(out_file, sep=';'))

    mark_done(progress, done_key, total)
    save_progress(progress)
    log.info(f"  {ticker}: {total} rows saved")
    return (ticker, total)


# --- Consolidation ---
def consolidate():
    log.info("Consolidating all data...")
    frames = []
    for ticker, name in BRVM_TICKERS.items():
        safe = ticker.replace('.','_').replace('-','_')
        f = OUTPUT_DIR / f"{safe}.csv"
        if f.exists():
            try:
                df = pd.read_csv(f, sep=';', dtype=str)
                if len(df) > 0:
                    if 'symbole' not in df.columns:
                        df.insert(0, 'symbole', ticker)
                    df['nom'] = name
                    frames.append(df)
            except:
                pass

    if not frames:
        log.warning("No data to consolidate!")
        return

    big = pd.concat(frames, ignore_index=True)

    # Semicolon CSV (French format)
    big.to_csv(OUTPUT_DIR / "BRVM_ALL_TICKERS_1998_2026.csv", sep=';', index=False)

    # Comma CSV (trading platform format) with English headers
    trade = big.rename(columns={
        'symbole':'Symbol','date':'Date','ouverture':'Open',
        'haut':'High','bas':'Low','cloture':'Close','volume':'Volume','nom':'Name'
    })
    trade.to_csv(OUTPUT_DIR / "BRVM_TRADING_FORMAT.csv", index=False)

    # Per-ticker JSON for chart.js integration
    jdir = OUTPUT_DIR / "json"
    jdir.mkdir(exist_ok=True)
    for sym, grp in big.groupby('symbole'):
        records = []
        for _, row in grp.iterrows():
            try:
                d = str(row.get('date','')).split('/')
                iso = f"{d[2]}-{d[1]}-{d[0]}" if len(d)==3 else str(row.get('date',''))
                records.append({
                    "date": iso,
                    "open": float(row.get('ouverture',0) or 0),
                    "high": float(row.get('haut',0) or 0),
                    "low": float(row.get('bas',0) or 0),
                    "close": float(row.get('cloture',0) or 0),
                    "volume": int(float(row.get('volume',0) or 0)),
                })
            except:
                pass
        safe = sym.replace('.','_').replace('-','_')
        with open(jdir / f"{safe}.json", 'w') as f:
            json.dump({"symbol":sym,"name":BRVM_TICKERS.get(sym,''),"data":records}, f)

    log.info(f"Done: {len(big)} rows, {len(frames)} tickers")
    log.info(f"  CSV: BRVM_ALL_TICKERS_1998_2026.csv")
    log.info(f"  Trading: BRVM_TRADING_FORMAT.csv")
    log.info(f"  JSON: {jdir}")

    # Summary
    summary = {"date": datetime.now().isoformat(), "total_rows": len(big), "tickers": {}}
    for sym, grp in big.groupby('symbole'):
        summary["tickers"][sym] = {"name": BRVM_TICKERS.get(sym,''), "rows": len(grp)}
    with open(OUTPUT_DIR / "summary.json", 'w', encoding='utf-8') as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)


# --- Main ---
if __name__ == "__main__":
    print("=" * 60)
    print("  BRVM Scraper v3.0 | 58 tickers | 5 threads")
    print("  Source: Sikafinance.com | 1998-2026")
    print("  Ctrl+C = pause (reprend au prochain lancement)")
    print("=" * 60)

    progress = load_progress()
    tickers = list(BRVM_TICKERS.items())
    stats = {}

    try:
        with ThreadPoolExecutor(max_workers=WORKERS) as pool:
            futures = {
                pool.submit(scrape_one_ticker, t, n, progress): t
                for t, n in tickers
            }
            done_count = 0
            for future in as_completed(futures):
                ticker = futures[future]
                try:
                    t, count = future.result()
                    stats[t] = count
                    done_count += 1
                    log.info(f"[{done_count}/{len(tickers)}] {t}: {count} rows")
                except Exception as e:
                    log.error(f"FAIL {ticker}: {e}")
                    stats[ticker] = -1
                    done_count += 1
    except KeyboardInterrupt:
        log.info("\nInterrupted! Saving progress...")
        save_progress(progress)

    save_progress(progress)
    consolidate()

    # Final summary
    print("\n" + "=" * 60)
    total = sum(v for v in stats.values() if v > 0)
    ok = sum(1 for v in stats.values() if v > 0)
    print(f"  TOTAL: {total} rows | {ok}/{len(tickers)} tickers")
    print(f"  Output: {OUTPUT_DIR}")
    print("=" * 60)
