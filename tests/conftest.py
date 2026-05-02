"""Shared pytest fixtures for MANSA tests.

These fixtures set up:
- A throwaway SQLite database with the production schema.
- Strong dev-mode env vars so api_server can import without raising.
- A Flask test client wired to the temp DB.

Tests do not touch the real mansa.db at the repo root.
"""

from __future__ import annotations

import secrets
import sqlite3
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SERVER_DIR = ROOT / "server"
sys.path.insert(0, str(ROOT))


# ── Test DB schema (mirrors db_init.py for the bits we test) ──
SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS tickers (
    symbol TEXT PRIMARY KEY,
    name   TEXT NOT NULL,
    sector TEXT,
    type   TEXT,
    country TEXT
);

CREATE TABLE IF NOT EXISTS prices (
    symbol TEXT NOT NULL,
    date   TEXT NOT NULL,
    open   REAL,
    high   REAL,
    low    REAL,
    close  REAL,
    volume INTEGER,
    PRIMARY KEY (symbol, date)
);

CREATE TABLE IF NOT EXISTS dividends (
    symbol   TEXT NOT NULL,
    year     INTEGER NOT NULL,
    amount   REAL,
    ex_date  TEXT,
    pay_date TEXT,
    yield_pct    REAL,
    payout_ratio REAL,
    PRIMARY KEY (symbol, year)
);

-- P0-8: fundamentals table (mirrors db_init.py)
CREATE TABLE IF NOT EXISTS fundamentals (
    symbol      TEXT NOT NULL,
    year        INTEGER NOT NULL,
    revenue     REAL,
    ebitda      REAL,
    net_income  REAL,
    eps         REAL,
    equity      REAL,
    total_debt  REAL,
    total_assets REAL,
    shares_outstanding INTEGER,
    per         REAL,
    pbr         REAL,
    roe         REAL,
    roa         REAL,
    margin_net  REAL,
    debt_equity REAL,
    PRIMARY KEY (symbol, year)
);

CREATE TABLE IF NOT EXISTS subscriptions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_email TEXT NOT NULL,
    plan TEXT NOT NULL,
    status TEXT NOT NULL,
    payment_method TEXT,
    payment_ref TEXT UNIQUE,
    amount INTEGER,
    start_date TEXT DEFAULT (datetime('now')),
    end_date TEXT,
    updated_at TEXT
);

CREATE TABLE IF NOT EXISTS pipeline_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT DEFAULT (datetime('now')),
    source TEXT,
    status TEXT,
    tickers_updated INTEGER DEFAULT 0,
    rows_inserted INTEGER DEFAULT 0,
    duration_ms INTEGER DEFAULT 0,
    message TEXT
);

CREATE TABLE IF NOT EXISTS analytics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT DEFAULT (datetime('now')),
    session_id TEXT,
    event_type TEXT,
    tab TEXT,
    ticker TEXT,
    metadata TEXT,
    user_agent TEXT,
    ip_hash TEXT
);

-- ── P0-2: users + password_resets ──
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT NOT NULL UNIQUE COLLATE NOCASE,
    password_hash TEXT NOT NULL,
    prenom TEXT NOT NULL,
    nom TEXT,
    pays TEXT,
    profil TEXT,
    plan TEXT DEFAULT 'free',
    email_verified INTEGER DEFAULT 0,
    verification_token TEXT,
    created_at TEXT DEFAULT (datetime('now')),
    last_login_at TEXT
);
CREATE TABLE IF NOT EXISTS password_resets (
    token TEXT PRIMARY KEY,
    user_id INTEGER NOT NULL,
    expires_at TEXT NOT NULL,
    consumed_at TEXT,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- ── P0-1: community_posts ──
CREATE TABLE IF NOT EXISTS community_posts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    room TEXT NOT NULL,
    user_email TEXT NOT NULL,
    user_prenom TEXT,
    parent_id INTEGER,
    content TEXT NOT NULL,
    sanitized_content TEXT NOT NULL,
    created_at TEXT DEFAULT (datetime('now')),
    deleted_at TEXT,
    FOREIGN KEY (parent_id) REFERENCES community_posts(id) ON DELETE CASCADE
);
"""


@pytest.fixture
def temp_db(tmp_path):
    """Create a temp SQLite DB with the prod schema and a few sample tickers."""
    db_path = tmp_path / "mansa_test.db"
    conn = sqlite3.connect(db_path)
    conn.executescript(SCHEMA_SQL)
    # Seed a couple of tickers + prices so /api/tickers returns rows.
    conn.executemany(
        "INSERT INTO tickers (symbol, name, sector, type, country) VALUES (?, ?, ?, ?, ?)",
        [
            ("SGBC.ci", "Société Générale CI", "Banques", "equity", "CI"),
            ("SNTS.sn", "Sonatel", "Télécoms", "equity", "SN"),
            ("BRVMC", "BRVM Composite", "Indice", "index", "REG"),
        ],
    )
    conn.executemany(
        "INSERT INTO prices (symbol, date, open, high, low, close, volume) VALUES (?, ?, ?, ?, ?, ?, ?)",
        [
            ("SGBC.ci", "2026-04-24", 12000, 12100, 11950, 12050, 1500),
            ("SGBC.ci", "2026-04-25", 12050, 12200, 12000, 12150, 2000),
            ("SNTS.sn", "2026-04-25", None, None, None, 18500, 5000),  # P0-7: NULL OHLC allowed
            ("BRVMC", "2026-04-25", None, None, None, 245.32, 0),
        ],
    )
    conn.commit()
    conn.close()
    return db_path


@pytest.fixture
def strong_env(temp_db, monkeypatch):
    """Set env so api_server.py imports cleanly in dev mode."""
    monkeypatch.setenv("FLASK_ENV", "development")
    monkeypatch.setenv("MANSA_DB", str(temp_db))
    monkeypatch.setenv("MANSA_SECRET", secrets.token_urlsafe(48))
    monkeypatch.setenv("MANSA_ADMIN_TOKEN", secrets.token_urlsafe(32))
    monkeypatch.setenv("MANSA_ALLOWED_ORIGINS", "http://localhost:8080")
    # P1-10: keep tests deterministic — Turnstile bypass instead of stub network.
    monkeypatch.setenv("MANSA_CAPTCHA_BYPASS", "1")
    yield


@pytest.fixture
def client(strong_env):
    """Flask test client. Imports api_server fresh each test (env-driven)."""
    # Clear any prior import so module-level checks re-run with our env.
    # Also clear `auth` and `community` so blueprint references rebind to the new app.
    for mod in list(sys.modules):
        if (
            mod in {"api_server", "auth", "community", "captcha", "data_pipeline", "server"}
            or mod.startswith("server.")
        ):
            del sys.modules[mod]

    # Add server/ to path so we can `import api_server` directly.
    sys.path.insert(0, str(SERVER_DIR))
    import api_server  # noqa: E402

    api_server.app.config["TESTING"] = True
    # Disable rate limiting in tests — the in-memory bucket would otherwise
    # leak counts across tests and cause spurious 429s.
    api_server.app.config["RATELIMIT_ENABLED"] = False
    if api_server.limiter is not None:
        api_server.limiter.enabled = False
        # Reset any counters from a previous test that may have leaked.
        import contextlib
        with contextlib.suppress(Exception):
            api_server.limiter.reset()
    return api_server.app.test_client(), api_server


@pytest.fixture
def admin_headers(client):
    """Headers carrying a valid X-Admin-Token for the running app."""
    _, mod = client
    return {"X-Admin-Token": mod.ADMIN_TOKEN}


# ── Cleanup: ensure no test leaks env vars or modules ──
@pytest.fixture(autouse=True)
def _isolate_modules():
    yield
    for mod in list(sys.modules):
        if mod in {"api_server", "auth", "community", "captcha", "data_pipeline", "server"} or mod.startswith("server."):
            del sys.modules[mod]
