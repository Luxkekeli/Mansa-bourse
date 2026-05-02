#!/usr/bin/env python3
"""Create final ZIP with all BRVM trading data."""
import zipfile
import os
import json
from datetime import datetime

BASE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(BASE, "brvm_data")
DESKTOP = os.path.join(os.path.expanduser("~"), "Desktop")
ZIP_NAME = "BRVM_Historical_Data_2010_2026.zip"
ZIP_PATH = os.path.join(DESKTOP, ZIP_NAME)

# Folders to include
INCLUDE_DIRS = ["csv_par_ticker", "json_par_ticker", "tradingview_format"]
# Key files to include at root
INCLUDE_FILES = [
    "BRVM_MASTER_OHLCV.csv",
    "BRVM_TRADING_FORMAT.csv",
    "brvm_api_data.json",
    "ticker_catalog.json",
    "ticker_list.json",
    "richbourse_ohlcv.csv",
]

README = """# BRVM Historical Stock Data (2010-2026)
# Donnees Historiques de la Bourse Regionale des Valeurs Mobilieres
# ================================================================
#
# CONTENU:
# --------
# 51 tickers (46 actions + 5 indices) | 107,311+ points de donnees
# Periode: 2010 -> Mars 2026
# Sources: Sikafinance.com + RichBourse.com (OHLCV pour les tickers cles)
# Devise: FCFA (Franc CFA BCEAO)
#
# FICHIERS:
# ---------
# BRVM_MASTER_OHLCV.csv     -> TOUTES les donnees en un seul fichier
#                               Colonnes: Symbol,Date,Open,High,Low,Close,Volume,Name,Sector
#
# BRVM_TRADING_FORMAT.csv   -> Format standard trading (anglais)
#                               Colonnes: Symbol,Date,Open,High,Low,Close,Volume,Name
#
# csv_par_ticker/            -> 1 fichier CSV par ticker
#                               Format: Date,Open,High,Low,Close,Volume
#                               Pret pour import dans Excel, Python, R
#
# json_par_ticker/           -> 1 fichier JSON par ticker
#                               Format TradingView lightweight-charts
#                               {time, open, high, low, close, volume}
#
# tradingview_format/        -> JSON enrichi par ticker
#                               {symbol, name, sector, currency, exchange, data:[...]}
#
# brvm_api_data.json         -> TOUTES les donnees en JSON (5.4 MB)
#                               {ticker: {name, sector, ohlcv: [[date,o,h,l,c,v],...]}}
#
# ticker_catalog.json        -> Catalogue avec metadata et statistiques
#                               first_date, last_date, perf_total, min/max/avg
#
# ticker_list.json           -> Liste simple des tickers avec noms et secteurs
#
# richbourse_ohlcv.csv       -> Donnees OHLCV brutes de RichBourse (chandeliers reels)
#
# UTILISATION DANS UNE PLATEFORME DE TRADING:
# -------------------------------------------
# 1. TradingView Lightweight Charts (JavaScript):
#    fetch('tradingview_format/SGBC_ci.json')
#      .then(r => r.json())
#      .then(d => chart.addCandlestickSeries().setData(d.data));
#
# 2. Chart.js / ApexCharts:
#    Utiliser json_par_ticker/SGBC_ci.json directement
#
# 3. Python (pandas):
#    import pandas as pd
#    df = pd.read_csv('csv_par_ticker/SGBC_ci.csv', parse_dates=['Date'])
#    df.set_index('Date').plot(y='Close')
#
# 4. Import global:
#    df = pd.read_csv('BRVM_MASTER_OHLCV.csv', parse_dates=['Date'])
#    ticker_data = df[df['Symbol'] == 'SGBC.ci']
#
# TICKERS DISPONIBLES:
# --------------------
# Actions (46): ABJC.ci, BICC.ci, BNBC.ci, BOAB.bj, BOABF.bf, BOAC.ci,
#   BOAM.ml, BOAN.ne, BOAS.sn, CABC.ci, CBIBF.bf, CFAC.ci, CIEC.ci,
#   ECOC.ci, ETIT.tg, FTSC.ci, LNBB.bj, NEIC.ci, NSBC.ci, NTLC.ci,
#   ONTBF.bf, ORAC.ci, ORGT.tg, PALC.ci, PRSC.ci, SAFC.ci, SCRC.ci,
#   SDCC.ci, SDSC.ci, SEMC.ci, SGBC.ci, SHEC.ci, SIBC.ci, SICC.ci,
#   SIVC.ci, SLBC.ci, SMBC.ci, SNTS.sn, SOGC.ci, SPHC.ci, STAC.ci,
#   STBC.ci, SVOC.ci, TTLC.ci, TTLS.sn, UNLC.ci, UNXC.ci
#
# Indices (5): BRVM30, BRVMC, BRVM-EN, BRVM-IN, BRVM-SP, CAPIBRVM
#
# SECTEURS: Agriculture, Distribution, Finance, Industrie,
#           Services, Services Publics, Transport
#
# NOTE: Les donnees avant 2010 ne sont pas disponibles gratuitement
# en ligne. La BRVM a ete creee en 1998 mais les archives historiques
# ne sont accessibles que via des fournisseurs de donnees payants.
#
# Genere le: """ + datetime.now().strftime("%Y-%m-%d %H:%M") + """
# Par: Bonjour Finance Data Pipeline
"""

def main():
    print(f"Creating {ZIP_PATH}...")
    
    count = 0
    with zipfile.ZipFile(ZIP_PATH, 'w', zipfile.ZIP_DEFLATED) as zf:
        # README
        zf.writestr("README.txt", README)
        count += 1
        
        # Root files
        for fname in INCLUDE_FILES:
            fpath = os.path.join(DATA, fname)
            if os.path.exists(fpath):
                zf.write(fpath, fname)
                size_mb = os.path.getsize(fpath) / 1024 / 1024
                print(f"  + {fname} ({size_mb:.1f} MB)")
                count += 1
        
        # Directories
        for dirname in INCLUDE_DIRS:
            dirpath = os.path.join(DATA, dirname)
            if os.path.isdir(dirpath):
                for fname in sorted(os.listdir(dirpath)):
                    fpath = os.path.join(dirpath, fname)
                    if os.path.isfile(fpath):
                        arcname = f"{dirname}/{fname}"
                        zf.write(fpath, arcname)
                        count += 1
                print(f"  + {dirname}/ ({len(os.listdir(dirpath))} files)")
    
    size_mb = os.path.getsize(ZIP_PATH) / 1024 / 1024
    print(f"\n{'='*60}")
    print(f"ZIP cree: {ZIP_PATH}")
    print(f"Taille: {size_mb:.1f} MB | Fichiers: {count}")
    print(f"{'='*60}")

if __name__ == "__main__":
    main()
