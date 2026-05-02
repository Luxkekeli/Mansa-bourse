import csv, json, os
DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "brvm_data")

# Check master CSV
tickers = {}
ohlc_real = 0
total = 0
with open(os.path.join(DATA, "BRVM_MASTER_OHLCV.csv"), 'r', encoding='utf-8') as f:
    for row in csv.DictReader(f):
        sym = row['Symbol']
        tickers[sym] = tickers.get(sym, 0) + 1
        total += 1
        o,h,l,c = float(row['Open']),float(row['High']),float(row['Low']),float(row['Close'])
        if o != h or h != l or l != c:
            ohlc_real += 1

# Load catalog for date ranges
cat = json.load(open(os.path.join(DATA, "ticker_catalog.json"), encoding='utf-8'))
ticker_info = {t['symbol']: t for t in cat['tickers']}

print("=" * 70)
print("  RAPPORT FINAL - DONNEES BRVM")
print("=" * 70)
print(f"\n  Total: {total:,} points de donnees")
print(f"  Tickers: {len(tickers)} ({cat['total_equities']} actions + {cat['total_indices']} indices)")
print(f"  OHLC reels (chandeliers): {ohlc_real:,} / {total:,} ({ohlc_real*100//total}%)")

print(f"\n  {'Ticker':<15} {'Points':>7} {'Debut':>12} {'Fin':>12} {'Dernier':>10}")
print(f"  {'-'*15} {'-'*7} {'-'*12} {'-'*12} {'-'*10}")
for sym in sorted(tickers.keys()):
    info = ticker_info.get(sym, {})
    print(f"  {sym:<15} {tickers[sym]:>7} {info.get('first_date','?'):>12} {info.get('last_date','?'):>12} {info.get('last_close',0):>10,.0f}")

# Check missing tickers vs BRVM official list
BRVM_OFFICIAL = [
    "ABJC.ci","BICB.bj","BICC.ci","BNBC.ci","BOAB.bj","BOABF.bf","BOAC.ci",
    "BOAM.ml","BOAN.ne","BOAS.sn","CABC.ci","CBIBF.bf","CFAC.ci","CIEC.ci",
    "ECOC.ci","ETIT.tg","FTSC.ci","LNBB.bj","NEIC.ci","NSBC.ci","NTLC.ci",
    "ONTBF.bf","ORAC.ci","ORGT.tg","PALC.ci","PRSC.ci","SAFC.ci","SCRC.ci",
    "SDCC.ci","SDSC.ci","SEMC.ci","SGBC.ci","SHEC.ci","SIBC.ci","SICC.ci",
    "SIVC.ci","SLBC.ci","SMBC.ci","SNTS.sn","SOGC.ci","SPHC.ci","STAC.ci",
    "STBC.ci","SVOC.ci","TTLC.ci","TTLS.sn","UNLC.ci","UNXC.ci"
]
present = set(tickers.keys())
missing = [t for t in BRVM_OFFICIAL if t not in present]
extra = [t for t in present if t not in BRVM_OFFICIAL]

print(f"\n  Actions BRVM officielles: {len(BRVM_OFFICIAL)}")
print(f"  Couvertes: {len(BRVM_OFFICIAL) - len(missing)}/{len(BRVM_OFFICIAL)}")
if missing:
    print(f"  Manquantes: {', '.join(missing)}")
if extra:
    print(f"  Extra (indices etc): {', '.join(extra)}")

# Files summary
files_csv = len(os.listdir(os.path.join(DATA, "csv_par_ticker")))
files_json = len(os.listdir(os.path.join(DATA, "json_par_ticker")))
files_tv = len(os.listdir(os.path.join(DATA, "tradingview_format")))
api_size = os.path.getsize(os.path.join(DATA, "brvm_api_data.json")) / 1024 / 1024

zip_path = os.path.join(os.path.expanduser("~"), "Desktop", "BRVM_Historical_Data_2010_2026.zip")
zip_size = os.path.getsize(zip_path) / 1024 / 1024 if os.path.exists(zip_path) else 0

print(f"\n  FICHIERS GENERES:")
print(f"  csv_par_ticker/:      {files_csv} fichiers")
print(f"  json_par_ticker/:     {files_json} fichiers")
print(f"  tradingview_format/:  {files_tv} fichiers")
print(f"  brvm_api_data.json:   {api_size:.1f} MB")
print(f"  ZIP Bureau:           {zip_size:.1f} MB")
print("=" * 70)
