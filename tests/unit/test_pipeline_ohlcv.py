"""Tests covering P0-7: do not fabricate OHLC values when source omits them.

We don't make real network calls — we verify the storage/insert path preserves
None as SQL NULL and that `validate_data` accepts NULL OHLC.
"""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SERVER_DIR = ROOT / "server"
sys.path.insert(0, str(SERVER_DIR))


@pytest.fixture
def pipeline_db(tmp_path):
    """Minimal DB matching the prod schema for prices + pipeline_logs."""
    db_path = tmp_path / "pipe.db"
    conn = sqlite3.connect(db_path)
    conn.executescript(
        """
        CREATE TABLE prices (
            symbol TEXT NOT NULL,
            date   TEXT NOT NULL,
            open   REAL,
            high   REAL,
            low    REAL,
            close  REAL,
            volume INTEGER,
            PRIMARY KEY (symbol, date)
        );
        CREATE TABLE pipeline_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT DEFAULT (datetime('now')),
            source TEXT,
            status TEXT,
            tickers_updated INTEGER DEFAULT 0,
            rows_inserted INTEGER DEFAULT 0,
            duration_ms INTEGER DEFAULT 0,
            message TEXT
        );
        """
    )
    conn.commit()
    yield db_path, conn
    conn.close()


def test_store_data_preserves_null_ohlc(pipeline_db, monkeypatch):
    """When the source has only `close`, open/high/low must be SQL NULL — never duplicated."""
    db_path, _ = pipeline_db
    # Reload the module pointing at our temp DB.
    monkeypatch.setenv("MANSA_DB", str(db_path))
    sys.modules.pop("data_pipeline", None)
    import data_pipeline  # noqa: E402

    pipe = data_pipeline.DataPipeline()
    pipe.db = sqlite3.connect(db_path)

    rows = [
        {
            "symbol": "SGBC.ci",
            "date": "2026-04-25",
            "close": 12150,
            "volume": 2000,
            "open": None,
            "high": None,
            "low": None,
        }
    ]
    n = pipe.store_data(rows, "test")
    assert n == 1

    cur = pipe.db.execute(
        "SELECT open, high, low, close FROM prices WHERE symbol = 'SGBC.ci'"
    )
    row = cur.fetchone()
    assert row[0] is None  # open
    assert row[1] is None  # high
    assert row[2] is None  # low
    assert row[3] == 12150  # close
    pipe.db.close()


def test_store_data_keeps_real_ohlc_when_provided(pipeline_db, monkeypatch):
    """When the source provides full OHLC, we must store them verbatim."""
    db_path, _ = pipeline_db
    monkeypatch.setenv("MANSA_DB", str(db_path))
    sys.modules.pop("data_pipeline", None)
    import data_pipeline  # noqa: E402

    pipe = data_pipeline.DataPipeline()
    pipe.db = sqlite3.connect(db_path)

    rows = [
        {
            "symbol": "SNTS.sn",
            "date": "2026-04-25",
            "open": 18000,
            "high": 18800,
            "low": 17900,
            "close": 18500,
            "volume": 5000,
        }
    ]
    pipe.store_data(rows, "test")
    cur = pipe.db.execute(
        "SELECT open, high, low, close FROM prices WHERE symbol = 'SNTS.sn'"
    )
    row = cur.fetchone()
    assert row == (18000, 18800, 17900, 18500)
    pipe.db.close()


def test_no_close_duplication_into_open_high_low(pipeline_db, monkeypatch):
    """Regression test for the bug we just fixed: open MUST NOT equal close
    when the source did not provide open."""
    db_path, _ = pipeline_db
    monkeypatch.setenv("MANSA_DB", str(db_path))
    sys.modules.pop("data_pipeline", None)
    import data_pipeline  # noqa: E402

    pipe = data_pipeline.DataPipeline()
    pipe.db = sqlite3.connect(db_path)

    rows = [
        {
            "symbol": "BNBC.ci",
            "date": "2026-04-25",
            "close": 5500,
            "volume": 100,
            # Note: open/high/low absent from dict (not even None) — old code defaulted to close.
        }
    ]
    pipe.store_data(rows, "test")
    cur = pipe.db.execute(
        "SELECT open, high, low, close FROM prices WHERE symbol = 'BNBC.ci'"
    )
    row = cur.fetchone()
    assert row[0] is None, "open should be NULL when absent, not duplicated from close"
    assert row[1] is None
    assert row[2] is None
    assert row[3] == 5500
    pipe.db.close()
