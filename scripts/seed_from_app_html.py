#!/usr/bin/env python3
"""P0-8 — Seed `tickers`, `dividends`, `fundamentals` from the inline `S=[...]` array in app.html.

Why this exists
---------------
The frontend currently ships a hard-coded `const S=[...]` array that holds 48
tickers with all their metadata, ratios, dividend amount, perf, history. This
data should live in the database so:
- The pipeline can refresh it.
- Multiple frontends (mobile, partners) can consume it via /api/*.
- The frontend bundle shrinks and Vite can split it (P1-1).

Migration mode (D5 default = "progressive")
-------------------------------------------
We populate the DB from the array and EXPOSE it via the API. The frontend
overlays API data onto `S` but keeps `S` as fallback for one release. This
script is **idempotent** — running it twice produces the same DB state.

Usage
-----
    python scripts/seed_from_app_html.py                       # default paths
    python scripts/seed_from_app_html.py --html ../app.html    # custom paths
    python scripts/seed_from_app_html.py --dry-run             # parse only
"""

from __future__ import annotations

import argparse
import re
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_HTML = ROOT / "frontend" / "app.html"
DEFAULT_DB = ROOT.parent / "mansa.db"  # repo root

# Sector code → human-readable name (matches db_init.py SECTOR_MAP intent).
SECTOR_NAMES = {
    "FIN": "Banques & Finance",
    "DIS": "Distribution",
    "SRV": "Services",
    "TRP": "Transport",
    "IND": "Industrie",
    "AGR": "Agriculture",
    "TEL": "Télécommunications",
    "ENE": "Énergie",
    "AUT": "Autres",
}

# Country suffix → code, mirrors data_pipeline.py / db_init.py.
COUNTRY_BY_SUFFIX = {
    ".ci": "CI", ".sn": "SN", ".bj": "BJ", ".bf": "BF",
    ".tg": "TG", ".ml": "ML", ".ne": "NE", ".gw": "GW",
}

# A few short→full-symbol overrides where the suffix isn't obvious.
SYMBOL_SUFFIX_HINT = {
    "BICB": ".bj", "BOAB": ".bj", "BOABF": ".bf", "BOAC": ".ci",
    "BOAM": ".ml", "BOAN": ".ne", "BOAS": ".sn", "ETIT": ".tg",
    "ORGT": ".tg", "ONTBF": ".bf", "CBIBF": ".bf", "LNBB": ".bj",
    "TTLS": ".sn", "SNTS": ".sn",
}


# ── Tolerant JS-object-literal parser ────────────────────────────────────
#
# The inline S array uses JS shorthand:
#   {t:'SDSC',n:'Africa Global Logistics',s:'TRP',c:1920,...}
# We don't need a full JS parser — we extract the top-level objects with
# regex, then parse each object's k:v pairs with another regex.

_OBJECT_RE = re.compile(r"\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}", re.DOTALL)
_KV_RE = re.compile(
    r"""
    (?P<key>\w+)         # property name (no quotes in JS shorthand)
    \s*:\s*
    (?P<value>
        '(?:[^'\\]|\\.)*'             # 'string'
      | "(?:[^"\\]|\\.)*"             # "string"
      | -?\d+(?:\.\d+)?               # number
      | \[[^\[\]]*(?:\[[^\[\]]*\][^\[\]]*)*\]  # nested array
      | \{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}        # nested object
      | true | false | null
    )
    """,
    re.VERBOSE | re.DOTALL,
)


def _coerce(raw: str):
    """Convert a JS literal to a Python value."""
    s = raw.strip()
    if not s:
        return None
    if s == "true":
        return True
    if s == "false":
        return False
    if s == "null":
        return None
    if s.startswith("'") or s.startswith('"'):
        return s[1:-1]
    if s.startswith("["):
        # Array of objects (e.g. hist:[{d:'...',v:1234},...]).
        return [_parse_obj(m.group(0)) for m in _OBJECT_RE.finditer(s)]
    if s.startswith("{"):
        return _parse_obj(s)
    try:
        if "." in s:
            return float(s)
        return int(s)
    except ValueError:
        return s


def _parse_obj(text: str) -> dict:
    """Parse a single JS object literal into a dict."""
    out = {}
    for m in _KV_RE.finditer(text):
        out[m.group("key")] = _coerce(m.group("value"))
    return out


def parse_s_array(html_path: Path) -> list[dict]:
    """Locate `const S=[...]` in app.html and return the list of ticker dicts."""
    text = html_path.read_text(encoding="utf-8")
    # Find the start of the array.
    start = text.find("const S=[")
    if start == -1:
        raise SystemExit(f"Could not locate `const S=[` in {html_path}")
    # Find the matching closing bracket. We track depth manually because the
    # array contains nested objects.
    i = start + len("const S=")
    if text[i] != "[":
        raise SystemExit("Unexpected layout near `const S=`")
    depth = 0
    end = -1
    for j in range(i, len(text)):
        ch = text[j]
        if ch == "[":
            depth += 1
        elif ch == "]":
            depth -= 1
            if depth == 0:
                end = j + 1
                break
    if end == -1:
        raise SystemExit("Unbalanced brackets in S array")
    body = text[i + 1:end - 1]  # strip outer [ ]
    return [_parse_obj(m.group(0)) for m in _OBJECT_RE.finditer(body) if "t:" in m.group(0)]


# ── Symbol resolution ────────────────────────────────────────────────────

def resolve_full_symbol(short: str) -> str:
    """Return the canonical full symbol (e.g. 'SDSC' → 'SDSC.ci')."""
    if "." in short:
        return short
    suffix = SYMBOL_SUFFIX_HINT.get(short, ".ci")  # default to CI
    return short + suffix


def country_from_symbol(sym: str) -> str:
    for suf, code in COUNTRY_BY_SUFFIX.items():
        if sym.lower().endswith(suf):
            return code
    return "CI"


# ── DB writers (idempotent) ──────────────────────────────────────────────

def upsert_ticker(conn: sqlite3.Connection, t: dict) -> str:
    """Upsert into `tickers`. Returns the canonical full symbol."""
    short = t["t"]
    full = resolve_full_symbol(short)
    sector = SECTOR_NAMES.get(t.get("s", "AUT"), t.get("s", "Autres"))
    country = country_from_symbol(full)
    conn.execute(
        """
        INSERT INTO tickers (symbol, name, sector, type, country)
        VALUES (?, ?, ?, 'equity', ?)
        ON CONFLICT(symbol) DO UPDATE SET
            name=excluded.name,
            sector=excluded.sector,
            country=excluded.country,
            updated_at=datetime('now')
        """,
        [full, t.get("n", short), sector, country],
    )
    return full


def upsert_fundamentals(conn: sqlite3.Connection, full: str, t: dict, year: int) -> None:
    """Insert this year's snapshot of fundamentals from S."""
    conn.execute(
        """
        INSERT OR REPLACE INTO fundamentals (
            symbol, year, per, pbr, roe, roa, margin_net, debt_equity
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            full, year,
            t.get("per"), t.get("pbr"), t.get("roe"),
            t.get("roa"), t.get("marge"), t.get("detteFP"),
        ],
    )


def upsert_dividend(conn: sqlite3.Connection, full: str, t: dict, year: int) -> None:
    """Insert the latest dividend amount + yield from S.

    `dividends` has its own AUTOINCREMENT id, so we use INSERT OR IGNORE on
    (symbol, year) by manually deleting the row first.
    """
    if t.get("div") is None or t.get("div") == 0:
        return
    conn.execute("DELETE FROM dividends WHERE symbol = ? AND year = ?", [full, year])
    conn.execute(
        """
        INSERT INTO dividends (symbol, year, amount, yield_pct)
        VALUES (?, ?, ?, ?)
        """,
        [full, year, t.get("div"), t.get("rdtDiv")],
    )


# ── Main ─────────────────────────────────────────────────────────────────

def main() -> int:
    p = argparse.ArgumentParser(description="Seed DB from inline S array.")
    p.add_argument("--html", default=str(DEFAULT_HTML))
    p.add_argument("--db", default=str(DEFAULT_DB))
    p.add_argument("--year", type=int, default=2025,
                   help="Reference year for the fundamentals/dividend snapshot")
    p.add_argument("--dry-run", action="store_true", help="Parse only, don't write DB")
    args = p.parse_args()

    html_path = Path(args.html)
    db_path = Path(args.db)
    if not html_path.exists():
        print(f"[seed] {html_path} missing", file=sys.stderr)
        return 1

    print(f"[seed] parsing {html_path}")
    tickers = parse_s_array(html_path)
    print(f"[seed] parsed {len(tickers)} tickers")

    if args.dry_run:
        for t in tickers[:5]:
            name = (t.get("n", "") or "").encode("ascii", "replace").decode("ascii")
            print(f"  - {t.get('t'):6} {name[:40]:40}  per={t.get('per')}  div={t.get('div')}  rdt={t.get('rdtDiv')}")
        print(f"[seed] dry-run complete ({len(tickers)} tickers)")
        return 0

    if not db_path.exists():
        print(f"[seed] {db_path} missing — run db_init.py first", file=sys.stderr)
        return 1

    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON")
    n_tickers = n_fund = n_div = 0
    for t in tickers:
        full = upsert_ticker(conn, t)
        n_tickers += 1
        if t.get("per") or t.get("pbr") or t.get("roe"):
            upsert_fundamentals(conn, full, t, args.year)
            n_fund += 1
        if t.get("div"):
            upsert_dividend(conn, full, t, args.year)
            n_div += 1
    conn.commit()
    conn.close()

    print(f"[seed] wrote {n_tickers} tickers, {n_fund} fundamentals, {n_div} dividends")
    return 0


if __name__ == "__main__":
    sys.exit(main())
