#!/usr/bin/env python3
"""
Consolidation des données BRVM en formats structurés pour trading.
Fusionne sikafinance + richbourse (si disponible) en:
  - CSV OHLCV par ticker (Date,Open,High,Low,Close,Volume)
  - JSON par ticker (format TradingView lightweight-charts)
  - Master CSV combiné
  - Catalogue/metadata des tickers
"""

import csv
import json
import os
import sys
from datetime import datetime
from collections import defaultdict

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "brvm_data")

TICKER_NAMES = {
    "ABJC.ci": "Servair Abidjan CI",
    "BICB.bj": "BIIC Benin",
    "BICC.ci": "BICICI CI",
    "BNBC.ci": "Bernabe CI",
    "BOAB.bj": "BOA Benin",
    "BOABF.bf": "BOA Burkina Faso",
    "BOAC.ci": "BOA Cote d'Ivoire",
    "BOAM.ml": "BOA Mali",
    "BOAN.ne": "BOA Niger",
    "BOAS.sn": "BOA Senegal",
    "BRVM30": "Indice BRVM 30",
    "BRVMC": "Indice BRVM Composite",
    "BRVM_EN": "Indice BRVM Energie",
    "BRVM_IN": "Indice BRVM Industrie",
    "BRVM_SP": "Indice BRVM Services Publics",
    "CABC.ci": "Sicable CI",
    "CAPIBRVM": "Capitalisation BRVM",
    "CBIBF.bf": "Coris Bank International BF",
    "CFAC.ci": "CFAO Motors CI",
    "CIEC.ci": "CIE CI",
    "ECOC.ci": "Ecobank CI",
    "ETIT.tg": "Ecobank Transnational Inc. TG",
    "FTSC.ci": "Filtisac CI",
    "LNBB.bj": "Loterie Nationale Benin",
    "NEIC.ci": "NEI-CEDA CI",
    "NSBC.ci": "NSIA Banque CI",
    "NTLC.ci": "Nestle CI",
    "ONTBF.bf": "Onatel BF",
    "ORAC.ci": "Orange CI",
    "ORGT.tg": "Oragroup TG",
    "PALC.ci": "Palm CI",
    "PRSC.ci": "Tractafric Motors CI",
    "SAFC.ci": "SAFCA CI",
    "SCRC.ci": "Sucrivoire CI",
    "SDCC.ci": "SODE CI",
    "SDSC.ci": "Bollore Transport & Logistics CI",
    "SEMC.ci": "Crown SIEM CI",
    "SGBC.ci": "Societe Generale CI",
    "SHEC.ci": "Vivo Energy CI",
    "SIBC.ci": "SIB CI",
    "SICC.ci": "SICOR CI",
    "SIVC.ci": "Air Liquide CI",
    "SLBC.ci": "Solibra CI",
    "SMBC.ci": "SMB CI",
    "SNTS.sn": "Sonatel SN",
    "SOGC.ci": "SOGB CI",
    "SPHC.ci": "SAPH CI",
    "STAC.ci": "SETAO CI",
    "STBC.ci": "SITAB CI",
    "SVOC.ci": "Movis CI",
    "TTLC.ci": "TotalEnergies CI",
    "TTLS.sn": "TotalEnergies SN",
    "UNLC.ci": "Unilever CI",
    "UNXC.ci": "Uniwax CI",
}

# Sector classification
SECTORS = {
    "ABJC.ci": "Services", "BICB.bj": "Finance", "BICC.ci": "Finance",
    "BNBC.ci": "Distribution", "BOAB.bj": "Finance", "BOABF.bf": "Finance",
    "BOAC.ci": "Finance", "BOAM.ml": "Finance", "BOAN.ne": "Finance",
    "BOAS.sn": "Finance", "CABC.ci": "Industrie", "CBIBF.bf": "Finance",
    "CFAC.ci": "Distribution", "CIEC.ci": "Services Publics", "ECOC.ci": "Finance",
    "ETIT.tg": "Finance", "FTSC.ci": "Industrie", "LNBB.bj": "Services",
    "NEIC.ci": "Industrie", "NSBC.ci": "Finance", "NTLC.ci": "Industrie",
    "ONTBF.bf": "Services Publics", "ORAC.ci": "Services Publics",
    "ORGT.tg": "Finance", "PALC.ci": "Agriculture", "PRSC.ci": "Distribution",
    "SAFC.ci": "Finance", "SCRC.ci": "Agriculture", "SDCC.ci": "Services Publics",
    "SDSC.ci": "Transport", "SEMC.ci": "Industrie", "SGBC.ci": "Finance",
    "SHEC.ci": "Distribution", "SIBC.ci": "Finance", "SICC.ci": "Industrie",
    "SIVC.ci": "Industrie", "SLBC.ci": "Industrie", "SMBC.ci": "Industrie",
    "SNTS.sn": "Services Publics", "SOGC.ci": "Agriculture", "SPHC.ci": "Agriculture",
    "STAC.ci": "Industrie", "STBC.ci": "Industrie", "SVOC.ci": "Transport",
    "TTLC.ci": "Distribution", "TTLS.sn": "Distribution", "UNLC.ci": "Industrie",
    "UNXC.ci": "Industrie",
}


def parse_date_to_iso(date_str):
    """Convert DD/MM/YYYY to YYYY-MM-DD."""
    try:
        parts = date_str.strip().split('/')
        if len(parts) == 3:
            d, m, y = parts
            return f"{y}-{m.zfill(2)}-{d.zfill(2)}"
        return date_str
    except:
        return date_str


def load_master_csv():
    """Load BRVM_ALL_TICKERS_1998_2026.csv (semicolon-separated, French headers)."""
    master = os.path.join(DATA_DIR, "BRVM_ALL_TICKERS_1998_2026.csv")
    data = defaultdict(list)
    
    if not os.path.exists(master):
        print(f"ERREUR: {master} non trouve!")
        return data
    
    count = 0
    with open(master, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f, delimiter=';')
        for row in reader:
            sym = row.get('symbole', '').strip()
            date_raw = row.get('date', '').strip()
            if not sym or not date_raw:
                continue
            
            iso_date = parse_date_to_iso(date_raw)
            
            try:
                o = float(row.get('ouverture', 0) or 0)
                h = float(row.get('haut', 0) or 0)
                l = float(row.get('bas', 0) or 0)
                c = float(row.get('cloture', 0) or 0)
                v = int(float(row.get('volume', 0) or 0))
            except (ValueError, TypeError):
                continue
            
            data[sym].append({
                'date': iso_date,
                'open': o,
                'high': h,
                'low': l,
                'close': c,
                'volume': v,
            })
            count += 1
    
    print(f"Charge: {count} lignes, {len(data)} tickers depuis master CSV")
    return data


def load_richbourse_data():
    """Load richbourse OHLCV data if available."""
    # Prefer the complete file from Selenium scrape
    rb_complete = os.path.join(DATA_DIR, "richbourse_ohlcv_complete.csv")
    rb_partial = os.path.join(DATA_DIR, "richbourse_ohlcv.csv")
    rb_file = rb_complete if os.path.exists(rb_complete) else rb_partial
    data = defaultdict(list)
    
    if not os.path.exists(rb_file):
        print("Pas de donnees RichBourse supplementaires")
        return data
    
    count = 0
    with open(rb_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            sym = row.get('Symbol', '').strip()
            date = row.get('Date', '').strip()
            if not sym or not date:
                continue
            try:
                data[sym].append({
                    'date': date,
                    'open': float(row.get('Open', 0)),
                    'high': float(row.get('High', 0)),
                    'low': float(row.get('Low', 0)),
                    'close': float(row.get('Close', 0)),
                    'volume': int(float(row.get('Volume', 0))),
                })
                count += 1
            except:
                continue
    
    print(f"Charge: {count} lignes RichBourse, {len(data)} tickers")
    return data


def merge_data(sika_data, rb_data):
    """Merge sikafinance and richbourse data, preferring richbourse OHLC."""
    merged = defaultdict(dict)
    
    # Load sikafinance first
    for sym, rows in sika_data.items():
        for r in rows:
            merged[sym][r['date']] = r
    
    # Overlay richbourse (better OHLC)
    updated = 0
    added = 0
    for sym, rows in rb_data.items():
        # Map richbourse ticker to sikafinance ticker
        suffix_map = {
            "BOAB": "BOAB.bj", "BICB": "BICB.bj", "LNBB": "LNBB.bj",
            "BOABF": "BOABF.bf", "CBIBF": "CBIBF.bf", "ONTBF": "ONTBF.bf",
            "ETIT": "ETIT.tg", "ORGT": "ORGT.tg",
            "SNTS": "SNTS.sn", "BOAS": "BOAS.sn", "TTLS": "TTLS.sn",
            "BOAM": "BOAM.ml", "BOAN": "BOAN.ne",
        }
        full_sym = suffix_map.get(sym, f"{sym}.ci") if '.' not in sym else sym
        
        for r in rows:
            if r['date'] in merged.get(full_sym, {}):
                existing = merged[full_sym][r['date']]
                # Update if richbourse has real OHLC (not all equal)
                if r['open'] != r['close'] or r['high'] != r['low']:
                    existing.update(r)
                    updated += 1
            else:
                if full_sym not in merged:
                    merged[full_sym] = {}
                merged[full_sym][r['date']] = r
                added += 1
    
    if updated or added:
        print(f"Fusion: {updated} mis a jour, {added} ajoutes depuis RichBourse")
    
    return merged


def save_outputs(merged):
    """Save in all trading-friendly formats."""
    
    # Output directories
    csv_dir = os.path.join(DATA_DIR, "csv_par_ticker")
    json_dir = os.path.join(DATA_DIR, "json_par_ticker")
    tv_dir = os.path.join(DATA_DIR, "tradingview_format")
    
    for d in [csv_dir, json_dir, tv_dir]:
        os.makedirs(d, exist_ok=True)
    
    all_rows = []
    catalog = []
    stats = {'tickers': 0, 'rows': 0, 'actions': 0, 'indices': 0}
    
    for sym in sorted(merged.keys()):
        date_map = merged[sym]
        rows = sorted(date_map.values(), key=lambda x: x['date'])
        
        if not rows:
            continue
        
        stats['tickers'] += 1
        stats['rows'] += len(rows)
        is_index = sym.startswith('BRVM') or sym == 'CAPIBRVM'
        if is_index:
            stats['indices'] += 1
        else:
            stats['actions'] += 1
        
        safe_name = sym.replace('.', '_')
        name = TICKER_NAMES.get(sym, sym)
        sector = SECTORS.get(sym, 'Indice' if is_index else 'Autre')
        
        dates = [r['date'] for r in rows]
        closes = [r['close'] for r in rows if r['close'] > 0]
        
        # === CSV per ticker ===
        csv_path = os.path.join(csv_dir, f"{safe_name}.csv")
        with open(csv_path, 'w', newline='', encoding='utf-8') as f:
            w = csv.writer(f)
            w.writerow(['Date', 'Open', 'High', 'Low', 'Close', 'Volume'])
            for r in rows:
                w.writerow([r['date'], r['open'], r['high'], r['low'], r['close'], r['volume']])
        
        # === JSON per ticker (TradingView lightweight-charts format) ===
        tv_data = []
        for r in rows:
            entry = {
                'time': r['date'],
                'open': r['open'],
                'high': r['high'],
                'low': r['low'],
                'close': r['close'],
            }
            if r['volume']:
                entry['volume'] = r['volume']
            tv_data.append(entry)
        
        json_path = os.path.join(json_dir, f"{safe_name}.json")
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(tv_data, f)
        
        tv_path = os.path.join(tv_dir, f"{safe_name}.json")
        with open(tv_path, 'w', encoding='utf-8') as f:
            json.dump({
                'symbol': sym,
                'name': name,
                'sector': sector,
                'currency': 'FCFA',
                'exchange': 'BRVM',
                'data': tv_data
            }, f, ensure_ascii=False)
        
        # === Master rows ===
        for r in rows:
            all_rows.append([sym, r['date'], r['open'], r['high'], r['low'], r['close'], r['volume'], name, sector])
        
        # === Catalog entry ===
        cat_entry = {
            'symbol': sym,
            'name': name,
            'sector': sector,
            'type': 'index' if is_index else 'equity',
            'currency': 'FCFA',
            'exchange': 'BRVM',
            'total_datapoints': len(rows),
            'first_date': min(dates) if dates else '',
            'last_date': max(dates) if dates else '',
            'last_close': closes[-1] if closes else 0,
            'min_close': min(closes) if closes else 0,
            'max_close': max(closes) if closes else 0,
            'avg_volume': round(sum(r['volume'] for r in rows) / len(rows)) if rows else 0,
        }
        
        # Calculate performance
        if len(closes) >= 2:
            cat_entry['perf_total'] = round((closes[-1] / closes[0] - 1) * 100, 2)
        if len(closes) >= 252:
            cat_entry['perf_1y'] = round((closes[-1] / closes[-252] - 1) * 100, 2)
        
        catalog.append(cat_entry)
        
        print(f"  {safe_name:20s} {len(rows):6d} pts  [{dates[0]} -> {dates[-1]}]")
    
    # === Master CSV ===
    master_path = os.path.join(DATA_DIR, "BRVM_MASTER_OHLCV.csv")
    with open(master_path, 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        w.writerow(['Symbol', 'Date', 'Open', 'High', 'Low', 'Close', 'Volume', 'Name', 'Sector'])
        for row in sorted(all_rows, key=lambda x: (x[0], x[1])):
            w.writerow(row)
    
    # === Catalog JSON ===
    catalog_path = os.path.join(DATA_DIR, "ticker_catalog.json")
    with open(catalog_path, 'w', encoding='utf-8') as f:
        json.dump({
            'generated': datetime.now().isoformat(),
            'exchange': 'BRVM - Bourse Regionale des Valeurs Mobilieres',
            'currency': 'FCFA (Franc CFA BCEAO)',
            'timezone': 'Africa/Abidjan (GMT+0)',
            'total_tickers': stats['tickers'],
            'total_equities': stats['actions'],
            'total_indices': stats['indices'],
            'total_datapoints': stats['rows'],
            'tickers': sorted(catalog, key=lambda x: x['symbol'])
        }, f, indent=2, ensure_ascii=False)
    
    # === Summary JSON (for quick loading) ===
    summary = {sym: {'name': TICKER_NAMES.get(sym, sym), 'sector': SECTORS.get(sym, '')} 
               for sym in sorted(merged.keys()) if merged[sym]}
    with open(os.path.join(DATA_DIR, "ticker_list.json"), 'w', encoding='utf-8') as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)
    
    # === API-ready combined JSON ===
    api_data = {}
    for sym in sorted(merged.keys()):
        date_map = merged[sym]
        rows = sorted(date_map.values(), key=lambda x: x['date'])
        if rows:
            api_data[sym] = {
                'name': TICKER_NAMES.get(sym, sym),
                'sector': SECTORS.get(sym, ''),
                'ohlcv': [[r['date'], r['open'], r['high'], r['low'], r['close'], r['volume']] for r in rows]
            }
    
    api_path = os.path.join(DATA_DIR, "brvm_api_data.json")
    with open(api_path, 'w', encoding='utf-8') as f:
        json.dump(api_data, f, ensure_ascii=False)
    print(f"\n  API JSON: {os.path.getsize(api_path) / 1024 / 1024:.1f} MB")
    
    return stats


def main():
    print("=" * 70)
    print("   CONSOLIDATION DONNEES BRVM - Formats Trading")
    print("   Sources: Sikafinance + RichBourse")
    print("=" * 70)
    
    # Load data
    print("\n[1/3] Chargement des sources...")
    sika = load_master_csv()
    rb = load_richbourse_data()
    
    # Merge
    print("\n[2/3] Fusion des donnees...")
    merged = merge_data(sika, rb)
    
    # Save
    print("\n[3/3] Generation des fichiers structures...\n")
    stats = save_outputs(merged)
    
    print("\n" + "=" * 70)
    print(f"   CONSOLIDATION TERMINEE!")
    print(f"   {stats['tickers']} tickers ({stats['actions']} actions + {stats['indices']} indices)")
    print(f"   {stats['rows']:,} points de donnees")
    print(f"")
    print(f"   FICHIERS GENERES dans {DATA_DIR}:")
    print(f"   csv_par_ticker/     -> CSV individuels (Date,O,H,L,C,V)")
    print(f"   json_par_ticker/    -> JSON individuels (TradingView)")
    print(f"   tradingview_format/ -> JSON enrichis (symbol,name,sector,data)")
    print(f"   BRVM_MASTER_OHLCV.csv -> Master CSV combine")
    print(f"   brvm_api_data.json  -> JSON API-ready (toutes donnees)")
    print(f"   ticker_catalog.json -> Catalogue avec metadata et stats")
    print(f"   ticker_list.json    -> Liste simple des tickers")
    print("=" * 70)


if __name__ == "__main__":
    main()
