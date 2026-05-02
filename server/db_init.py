#!/usr/bin/env python3
"""
MANSA — SQLite Database Initialization & Data Import
Imports existing CSV/JSON data into a structured SQLite database.
Usage: python db_init.py
"""

import csv
import json
import os
import sqlite3
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'mansa.db')
DATA_DIR = os.path.join(os.path.dirname(__file__), '..', 'brvm_data')

SCHEMA = """
-- ═══ MANSA Database Schema ═══

-- Tickers: all BRVM equities and indices
CREATE TABLE IF NOT EXISTS tickers (
    symbol      TEXT PRIMARY KEY,
    name        TEXT NOT NULL,
    sector      TEXT,
    type        TEXT DEFAULT 'equity',  -- equity | index
    country     TEXT,
    isin        TEXT,
    created_at  TEXT DEFAULT (datetime('now')),
    updated_at  TEXT DEFAULT (datetime('now'))
);

-- Daily OHLCV price data (time-series)
CREATE TABLE IF NOT EXISTS prices (
    symbol      TEXT NOT NULL,
    date        TEXT NOT NULL,
    open        REAL,
    high        REAL,
    low         REAL,
    close       REAL NOT NULL,
    volume      INTEGER DEFAULT 0,
    adj_close   REAL,
    PRIMARY KEY (symbol, date),
    FOREIGN KEY (symbol) REFERENCES tickers(symbol)
);

-- Fundamentals: annual financial data per ticker
CREATE TABLE IF NOT EXISTS fundamentals (
    symbol      TEXT NOT NULL,
    year        INTEGER NOT NULL,
    revenue     REAL,           -- Chiffre d'affaires
    ebitda      REAL,
    net_income  REAL,           -- Resultat net
    eps         REAL,           -- BNA (Benefice Net par Action)
    equity      REAL,           -- Capitaux propres
    total_debt  REAL,           -- Dette totale
    total_assets REAL,
    shares_outstanding INTEGER,
    per         REAL,           -- Price/Earnings
    pbr         REAL,           -- Price/Book
    roe         REAL,           -- Return on Equity
    roa         REAL,           -- Return on Assets
    margin_net  REAL,           -- Marge nette
    debt_equity REAL,           -- Dette/Fonds propres
    PRIMARY KEY (symbol, year),
    FOREIGN KEY (symbol) REFERENCES tickers(symbol)
);

-- Dividends history
CREATE TABLE IF NOT EXISTS dividends (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol      TEXT NOT NULL,
    year        INTEGER NOT NULL,
    amount      REAL NOT NULL,      -- Dividende brut par action
    ex_date     TEXT,               -- Date ex-dividende
    pay_date    TEXT,               -- Date de paiement
    yield_pct   REAL,               -- Rendement au moment du detachement
    payout_ratio REAL,
    FOREIGN KEY (symbol) REFERENCES tickers(symbol)
);

-- Market snapshots: daily aggregated market data
CREATE TABLE IF NOT EXISTS market_snapshots (
    date            TEXT PRIMARY KEY,
    brvm_composite  REAL,
    brvm_30         REAL,
    brvm_prestige   REAL,
    total_volume    INTEGER,
    total_value     REAL,           -- Valeur totale echangee
    nb_transactions INTEGER,
    nb_tickers_up   INTEGER,
    nb_tickers_down INTEGER,
    nb_tickers_flat INTEGER,
    market_cap      REAL            -- Capitalisation totale
);

-- User subscriptions (for payment integration)
CREATE TABLE IF NOT EXISTS subscriptions (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    user_email      TEXT NOT NULL,
    plan            TEXT NOT NULL DEFAULT 'free',  -- free | pro | sgi
    status          TEXT DEFAULT 'active',          -- active | expired | cancelled
    payment_method  TEXT,                           -- orange_money | wave | mtn_momo | card
    payment_ref     TEXT,
    amount          INTEGER DEFAULT 0,              -- FCFA
    start_date      TEXT DEFAULT (datetime('now')),
    end_date        TEXT,
    auto_renew      INTEGER DEFAULT 0,
    created_at      TEXT DEFAULT (datetime('now'))
);

-- Pipeline health monitoring
CREATE TABLE IF NOT EXISTS pipeline_logs (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp   TEXT DEFAULT (datetime('now')),
    source      TEXT NOT NULL,          -- brvm_org | sikafinance | richbourse
    status      TEXT NOT NULL,          -- success | error | warning
    tickers_updated INTEGER DEFAULT 0,
    rows_inserted   INTEGER DEFAULT 0,
    duration_ms     INTEGER,
    message     TEXT,
    error_detail TEXT
);

-- Analytics: page views and user behavior
CREATE TABLE IF NOT EXISTS analytics (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp   TEXT DEFAULT (datetime('now')),
    session_id  TEXT,
    event_type  TEXT NOT NULL,       -- page_view | click | search | trade_sim
    tab         TEXT,
    ticker      TEXT,
    metadata    TEXT,                 -- JSON blob for extra data
    user_agent  TEXT,
    ip_hash     TEXT                  -- SHA256 hash for privacy
);

-- ── P0-2: Real users table (replaces localStorage 'bfin_users') ──
-- password_hash is the full argon2 string (algo+salt+hash, self-describing).
-- email_verified flips to 1 once the user clicks the link in the verification email.
CREATE TABLE IF NOT EXISTS users (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    email              TEXT NOT NULL UNIQUE COLLATE NOCASE,
    password_hash      TEXT NOT NULL,
    prenom             TEXT NOT NULL,
    nom                TEXT,
    pays               TEXT,
    profil             TEXT,                          -- debutant | intermediaire | avance
    plan               TEXT DEFAULT 'free',           -- free | pro | sgi
    email_verified     INTEGER DEFAULT 0,
    verification_token TEXT,
    created_at         TEXT DEFAULT (datetime('now')),
    last_login_at      TEXT
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_users_email ON users(email);
CREATE INDEX IF NOT EXISTS idx_users_verification_token ON users(verification_token);

-- ── P0-2: Password reset tokens (one-shot, time-limited) ──
CREATE TABLE IF NOT EXISTS password_resets (
    token        TEXT PRIMARY KEY,
    user_id      INTEGER NOT NULL,
    expires_at   TEXT NOT NULL,
    consumed_at  TEXT,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_password_resets_user ON password_resets(user_id);

-- ── P0-1: Community posts (chat rooms / threads / replies) ──
-- IMPORTANT: `content` holds the RAW user input (audit only).
--            `sanitized_content` is bleach-cleaned HTML, the ONLY field served to clients.
CREATE TABLE IF NOT EXISTS community_posts (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    room              TEXT NOT NULL,                 -- e.g. 'general', 'these-SGBC', 'sgi-chat'
    user_email        TEXT NOT NULL,
    user_prenom       TEXT,
    parent_id         INTEGER,                       -- NULL for top-level, else replies
    content           TEXT NOT NULL,                 -- raw input, NEVER served to clients
    sanitized_content TEXT NOT NULL,                 -- bleach-sanitized, served to clients
    created_at        TEXT DEFAULT (datetime('now')),
    deleted_at        TEXT,
    FOREIGN KEY (parent_id) REFERENCES community_posts(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_community_posts_room ON community_posts(room, created_at);
CREATE INDEX IF NOT EXISTS idx_community_posts_parent ON community_posts(parent_id);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_prices_symbol ON prices(symbol);
CREATE INDEX IF NOT EXISTS idx_prices_date ON prices(date);
CREATE INDEX IF NOT EXISTS idx_prices_symbol_date ON prices(symbol, date DESC);
CREATE INDEX IF NOT EXISTS idx_dividends_symbol ON dividends(symbol);
CREATE INDEX IF NOT EXISTS idx_analytics_tab ON analytics(tab);
CREATE INDEX IF NOT EXISTS idx_analytics_timestamp ON analytics(timestamp);
CREATE INDEX IF NOT EXISTS idx_pipeline_logs_timestamp ON pipeline_logs(timestamp);
CREATE INDEX IF NOT EXISTS idx_subscriptions_email ON subscriptions(user_email);
"""

# Sector code mapping (from app.html)
SECTOR_MAP = {
    'Finance': 'FIN', 'Finances': 'FIN',
    'Distribution': 'DIS',
    'Services': 'SRV', 'Services publics': 'SRV',
    'Transport': 'TRP',
    'Industrie': 'IND',
    'Agriculture': 'AGR',
    'Autres': 'AUT',
}

# Country mapping from ticker suffix
COUNTRY_MAP = {
    '.ci': 'CI', '.sn': 'SN', '.bj': 'BJ', '.bf': 'BF',
    '.tg': 'TG', '.ml': 'ML', '.ne': 'NE', '.gw': 'GW',
}


def get_country(symbol):
    for suffix, code in COUNTRY_MAP.items():
        if symbol.lower().endswith(suffix):
            return code
    return 'CI'  # Default


def init_db():
    """Create database and tables."""
    conn = sqlite3.connect(DB_PATH)
    conn.executescript(SCHEMA)
    conn.commit()
    print(f"[DB] Database initialized: {DB_PATH}")
    return conn


def import_ticker_catalog(conn):
    """Import ticker metadata from ticker_catalog.json."""
    catalog_path = os.path.join(DATA_DIR, 'ticker_catalog.json')
    if not os.path.exists(catalog_path):
        print("[DB] ticker_catalog.json not found, trying ticker_list.json")
        catalog_path = os.path.join(DATA_DIR, 'ticker_list.json')

    if not os.path.exists(catalog_path):
        print("[DB] No ticker catalog found. Skipping metadata import.")
        return 0

    with open(catalog_path, encoding='utf-8') as f:
        catalog = json.load(f)

    count = 0
    cursor = conn.cursor()

    # Handle multiple formats: {tickers: [...]}, {symbol: {...}}, [...]
    if isinstance(catalog, dict) and 'tickers' in catalog:
        tickers = catalog['tickers']
    elif isinstance(catalog, dict):
        tickers = list(catalog.values()) if all(isinstance(v, dict) for v in catalog.values()) else []
    elif isinstance(catalog, list):
        tickers = catalog
    else:
        tickers = []

    # If tickers is a dict (symbol->info), convert to list
    if isinstance(tickers, dict):
        tickers = [{'symbol': k, **v} if isinstance(v, dict) else {'symbol': k, 'name': str(v)} for k, v in tickers.items()]

    for info in tickers:
        if isinstance(info, dict):
            symbol = info.get('symbol', '')
            name = info.get('name', symbol)
            sector = info.get('sector', 'Autres')
            ticker_type = info.get('type', 'equity')
        else:
            continue

        if not symbol:
            continue

        country = get_country(symbol)
        cursor.execute("""
            INSERT OR REPLACE INTO tickers (symbol, name, sector, type, country)
            VALUES (?, ?, ?, ?, ?)
        """, (symbol, name, sector, ticker_type, country))
        count += 1

    conn.commit()
    print(f"[DB] Imported {count} tickers from catalog")
    return count


def import_master_ohlcv(conn):
    """Import price data from BRVM_MASTER_OHLCV.csv."""
    master_path = os.path.join(DATA_DIR, 'BRVM_MASTER_OHLCV.csv')
    if not os.path.exists(master_path):
        print("[DB] BRVM_MASTER_OHLCV.csv not found. Trying individual CSVs.")
        return import_individual_csvs(conn)

    count = 0
    cursor = conn.cursor()
    batch = []

    with open(master_path, encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                symbol = row.get('Symbol', row.get('symbol', '')).strip()
                date = row.get('Date', row.get('date', '')).strip()
                if not symbol or not date:
                    continue

                # Normalize date format to YYYY-MM-DD
                if '/' in date:
                    parts = date.split('/')
                    if len(parts[0]) == 4:
                        date = date  # Already YYYY/MM/DD
                    else:
                        date = f"{parts[2]}-{parts[1].zfill(2)}-{parts[0].zfill(2)}"
                date = date.replace('/', '-')

                batch.append((
                    symbol, date,
                    float(row.get('Open', row.get('open', 0)) or 0),
                    float(row.get('High', row.get('high', 0)) or 0),
                    float(row.get('Low', row.get('low', 0)) or 0),
                    float(row.get('Close', row.get('close', 0)) or 0),
                    int(float(row.get('Volume', row.get('volume', 0)) or 0)),
                ))
                count += 1

                if len(batch) >= 5000:
                    cursor.executemany("""
                        INSERT OR REPLACE INTO prices (symbol, date, open, high, low, close, volume)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    """, batch)
                    batch = []
                    print(f"  ... {count} rows imported", end='\r')

            except (ValueError, KeyError):
                continue

    if batch:
        cursor.executemany("""
            INSERT OR REPLACE INTO prices (symbol, date, open, high, low, close, volume)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, batch)

    conn.commit()
    print(f"[DB] Imported {count} price rows from BRVM_MASTER_OHLCV.csv")
    return count


def import_individual_csvs(conn):
    """Fallback: import from individual ticker CSV files."""
    csv_dir = os.path.join(DATA_DIR, 'csv_par_ticker')
    if not os.path.exists(csv_dir):
        csv_dir = DATA_DIR

    count = 0
    cursor = conn.cursor()

    for fname in os.listdir(csv_dir):
        if not fname.endswith('.csv'):
            continue
        fpath = os.path.join(csv_dir, fname)
        try:
            with open(fpath, encoding='utf-8') as f:
                # Detect delimiter
                first_line = f.readline()
                f.seek(0)
                delimiter = ';' if ';' in first_line else ','
                reader = csv.DictReader(f, delimiter=delimiter)

                for row in reader:
                    symbol = row.get('symbole', row.get('Symbol', row.get('symbol', fname.replace('.csv', ''))))
                    date_str = row.get('date', row.get('Date', ''))
                    close_val = row.get('cloture', row.get('Close', row.get('close', 0)))

                    if not date_str or not close_val:
                        continue

                    # Normalize date
                    if '/' in date_str:
                        parts = date_str.split('/')
                        if len(parts[0]) <= 2:
                            date_str = f"{parts[2]}-{parts[1].zfill(2)}-{parts[0].zfill(2)}"
                    date_str = date_str.replace('/', '-')

                    cursor.execute("""
                        INSERT OR REPLACE INTO prices (symbol, date, open, high, low, close, volume)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    """, (
                        symbol.strip(), date_str.strip(),
                        float(row.get('ouverture', row.get('Open', row.get('open', 0))) or 0),
                        float(row.get('haut', row.get('High', row.get('high', 0))) or 0),
                        float(row.get('bas', row.get('Low', row.get('low', 0))) or 0),
                        float(close_val or 0),
                        int(float(row.get('volume', row.get('Volume', 0)) or 0)),
                    ))
                    count += 1
        except Exception as e:
            print(f"  [WARN] Error importing {fname}: {e}")

    conn.commit()
    print(f"[DB] Imported {count} price rows from individual CSVs")
    return count


def import_api_data(conn):
    """Import enriched data from brvm_api_data.json."""
    api_path = os.path.join(DATA_DIR, 'brvm_api_data.json')
    if not os.path.exists(api_path):
        return 0

    with open(api_path, encoding='utf-8') as f:
        data = json.load(f)

    count = 0
    cursor = conn.cursor()

    for symbol, info in data.items():
        if not isinstance(info, dict):
            continue

        name = info.get('name', symbol)
        sector = info.get('sector', 'Autres')

        # Upsert ticker
        cursor.execute("""
            INSERT OR REPLACE INTO tickers (symbol, name, sector, type, country)
            VALUES (?, ?, ?, 'equity', ?)
        """, (symbol, name, sector, get_country(symbol)))

        # Import OHLCV if present
        ohlcv = info.get('ohlcv', [])
        batch = []
        for row in ohlcv:
            if len(row) >= 5:
                batch.append((symbol, row[0], row[1], row[2], row[3], row[4],
                              int(row[5]) if len(row) > 5 else 0))
                count += 1

        if batch:
            cursor.executemany("""
                INSERT OR REPLACE INTO prices (symbol, date, open, high, low, close, volume)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, batch)

    conn.commit()
    print(f"[DB] Imported {count} rows from brvm_api_data.json")
    return count


def verify_db(conn):
    """Print database statistics."""
    cursor = conn.cursor()

    stats = {}
    cursor.execute("SELECT COUNT(*) FROM tickers")
    stats['tickers'] = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM prices")
    stats['price_rows'] = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(DISTINCT symbol) FROM prices")
    stats['symbols_with_data'] = cursor.fetchone()[0]

    cursor.execute("SELECT MIN(date), MAX(date) FROM prices")
    row = cursor.fetchone()
    stats['date_range'] = f"{row[0]} to {row[1]}"

    cursor.execute("SELECT symbol, COUNT(*) as cnt FROM prices GROUP BY symbol ORDER BY cnt DESC LIMIT 5")
    stats['top_5'] = cursor.fetchall()

    print("\n" + "=" * 50)
    print("  MANSA Database Statistics")
    print("=" * 50)
    print(f"  Tickers:          {stats['tickers']}")
    print(f"  Price rows:       {stats['price_rows']:,}")
    print(f"  Symbols w/ data:  {stats['symbols_with_data']}")
    print(f"  Date range:       {stats['date_range']}")
    print("  Top 5 by rows:")
    for sym, cnt in stats['top_5']:
        print(f"    {sym}: {cnt:,} rows")
    print("=" * 50)

    db_size = os.path.getsize(DB_PATH)
    print(f"  Database size:    {db_size / 1024 / 1024:.1f} MB")
    print(f"  Location:         {DB_PATH}")
    print()

    return stats


def main():
    print("=" * 50)
    print("  MANSA — Database Initialization")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 50)

    conn = init_db()

    # Import in order of priority
    import_ticker_catalog(conn)
    rows = import_master_ohlcv(conn)
    if rows < 1000:
        import_api_data(conn)

    verify_db(conn)
    conn.close()
    print("[DB] Done. Database ready for API server.")


if __name__ == '__main__':
    main()
