#!/usr/bin/env python3
"""Launch-day data freshness — bump the latest available BRVM snapshot to "today".

Two modes:
  --live      : essaie de scraper BRVM.org via le pipeline (peut échouer si offline)
  --carry-fwd : prend la dernière clôture connue et la dupplique à la date d'aujourd'hui
                (mode BETA acceptable pour un launch — affiche un badge de
                fraîcheur honnête dans le footer)

Le script écrit aussi une entrée pipeline_logs avec la date courante et un
flag "carry_forward" pour que le footer du site puisse afficher la vérité :
  « Dernière mise à jour : 28 avril 2026 (mode BETA — données reportées) »

Usage :
    python scripts/refresh_market_data.py --carry-fwd   # rapide, hors-ligne OK
    python scripts/refresh_market_data.py --live        # essaie BRVM.org
"""

from __future__ import annotations

import argparse
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB = ROOT / "mansa.db"


def carry_forward(db_path: Path, target_date: str) -> int:
    """Pour chaque ticker, copie la dernière clôture connue à `target_date`.

    Idempotent : INSERT OR REPLACE sur (symbol, date).
    Retourne le nombre de lignes ajoutées/mises à jour.
    """
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    # Récupère la dernière clôture par ticker.
    rows = cur.execute("""
        WITH ranked AS (
            SELECT symbol, date, open, high, low, close, volume,
                   ROW_NUMBER() OVER (PARTITION BY symbol ORDER BY date DESC) AS rn
            FROM prices
        )
        SELECT symbol, open, high, low, close, volume FROM ranked WHERE rn = 1
    """).fetchall()
    n = 0
    for sym, op, hi, lo, cl, vol in rows:
        cur.execute(
            "INSERT OR REPLACE INTO prices (symbol, date, open, high, low, close, volume) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (sym, target_date, op, hi, lo, cl, vol),
        )
        n += 1
    # Trace dans pipeline_logs.
    cur.execute(
        "INSERT INTO pipeline_logs (source, status, tickers_updated, rows_inserted, "
        "duration_ms, message) VALUES (?, ?, ?, ?, ?, ?)",
        ("carry_forward", "warning", n, n, 0,
         f"Carry-forward {n} tickers to {target_date} (BETA — données reportées de la dernière séance connue)"),
    )
    conn.commit()
    conn.close()
    return n


def try_live(db_path: Path) -> bool:
    """Tente le pipeline live BRVM.org. Retourne True si réussi."""
    sys.path.insert(0, str(ROOT / "server"))
    try:
        import data_pipeline  # type: ignore
    except ImportError as e:
        print(f"[refresh] data_pipeline import failed: {e}")
        return False
    pipe = data_pipeline.DataPipeline()
    if not pipe.connect_db():
        return False
    try:
        rows = pipe.fetch_brvm_org() or pipe.fetch_richbourse() or pipe.fetch_local_cache()
        if not rows:
            return False
        rows = pipe.validate_data(rows)
        n = pipe.store_data(rows, "live")
        print(f"[refresh] live ok — {n} rows inserted")
        return n > 0
    finally:
        pipe.close_db()


def main():
    p = argparse.ArgumentParser(description="Refresh BRVM market data for launch.")
    p.add_argument("--db", default=str(DEFAULT_DB))
    p.add_argument("--live", action="store_true", help="Try live scrape first")
    p.add_argument("--carry-fwd", action="store_true", help="Carry-forward latest close to today")
    p.add_argument("--target-date", default=None, help="ISO date (default: today UTC)")
    args = p.parse_args()

    db = Path(args.db)
    if not db.exists():
        print(f"[refresh] DB not found: {db}", file=sys.stderr)
        return 1

    target = args.target_date or datetime.now(timezone.utc).strftime("%Y-%m-%d")

    if args.live:
        if try_live(db):
            print(f"[refresh] OK live data fetched for {target}")
            return 0
        print("[refresh] live failed, falling back to carry-forward")

    if args.live or args.carry_fwd:
        n = carry_forward(db, target)
        print(f"[refresh] OK carry-forward {n} tickers to {target}")
        # Show DB state.
        conn = sqlite3.connect(db)
        latest = conn.execute("SELECT MAX(date) FROM prices").fetchone()[0]
        log = conn.execute(
            "SELECT source, status, message FROM pipeline_logs ORDER BY id DESC LIMIT 1"
        ).fetchone()
        conn.close()
        print(f"[refresh] latest date in DB now: {latest}")
        print(f"[refresh] latest pipeline log: {log}")
        return 0

    print("[refresh] specify --live or --carry-fwd")
    return 1


if __name__ == "__main__":
    sys.exit(main())
