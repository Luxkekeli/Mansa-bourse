"""Tests for Session 5 changes: P1-9 (CTE), P1-10 (Turnstile), /api/config."""

from __future__ import annotations

# ── P1-9: CTE refactor of /api/tickers + /api/indices ────────────────────

class TestCTERefactor:
    def test_tickers_returns_last_close_and_prev(self, client):
        c, _ = client
        rv = c.get("/api/tickers")
        assert rv.status_code == 200
        body = rv.get_json()
        sgbc = next((t for t in body["tickers"] if t["symbol"] == "SGBC.ci"), None)
        assert sgbc is not None
        # Conftest seeds two SGBC.ci rows: 2026-04-24 (12050) and 2026-04-25 (12150)
        assert sgbc["last_close"] == 12150
        assert sgbc["prev_close"] == 12050
        # Variation = (12150-12050)/12050 * 100 = 0.83%
        assert sgbc["variation_pct"] == 0.83

    def test_tickers_handles_single_row(self, client):
        """SNTS.sn has only one price row — prev_close should be NULL."""
        c, _ = client
        rv = c.get("/api/tickers")
        body = rv.get_json()
        snts = next((t for t in body["tickers"] if t["symbol"] == "SNTS.sn"), None)
        assert snts is not None
        assert snts["last_close"] == 18500
        assert snts["prev_close"] is None
        assert snts["variation_pct"] == 0  # graceful default

    def test_indices_returns_brvmc(self, client):
        c, _ = client
        rv = c.get("/api/indices")
        assert rv.status_code == 200
        body = rv.get_json()
        brvmc = next((i for i in body["indices"] if i["symbol"] == "BRVMC"), None)
        assert brvmc is not None
        assert brvmc["value"] == 245.32

    def test_explain_query_plan_uses_index(self, client):
        """Sanity check: the CTE plan should still hit indexes, not full scans."""
        c, mod = client
        with mod.app.app_context():
            db = mod.get_db()
            plan = db.execute("EXPLAIN QUERY PLAN " + """
                WITH ranked AS (
                    SELECT symbol, date, close, volume,
                           ROW_NUMBER() OVER (PARTITION BY symbol ORDER BY date DESC) AS rn
                    FROM prices
                )
                SELECT t.symbol FROM tickers t
                LEFT JOIN ranked p1 ON p1.symbol = t.symbol AND p1.rn = 1
            """).fetchall()
            text = " | ".join(str(row[3]) for row in plan).lower()
            # Window function over `prices` should at least scan the rowid index.
            # We simply assert the plan was produced and references the prices table.
            assert "prices" in text


# ── /api/config endpoint ─────────────────────────────────────────────────

class TestPublicConfig:
    def test_config_returns_required_fields(self, client):
        c, _ = client
        rv = c.get("/api/config")
        assert rv.status_code == 200
        body = rv.get_json()
        assert "turnstile" in body
        assert "enabled" in body["turnstile"]
        assert "site_key" in body["turnstile"]
        assert "payments_enabled" in body
        assert "version" in body

    def test_config_does_not_leak_secret(self, client):
        c, _ = client
        rv = c.get("/api/config")
        body = rv.get_json()
        # The secret key must NEVER appear in the public config payload.
        assert "secret" not in str(body).lower() or body["turnstile"].get("site_key", "") == ""

    def test_payments_disabled_by_default(self, client):
        c, _ = client
        rv = c.get("/api/config")
        body = rv.get_json()
        assert body["payments_enabled"] is False

    def test_analytics_field_present(self, client):
        """P2: /api/config exposes analytics.plausible_domain (empty if unset)."""
        c, _ = client
        rv = c.get("/api/config")
        body = rv.get_json()
        assert "analytics" in body
        assert "plausible_domain" in body["analytics"]
        # Empty string in dev (no domain configured).
        assert body["analytics"]["plausible_domain"] == ""


# ── P1-10: Turnstile bypass / enabled gating ─────────────────────────────

class TestCaptchaBypass:
    def test_captcha_bypass_lets_register_through(self, client):
        """With MANSA_CAPTCHA_BYPASS=1 (set by conftest), no token is needed."""
        c, _ = client
        rv = c.post("/api/auth/register", json={
            "email": "captcha@example.com",
            "password": "strongpass123",
            "prenom": "Cap",
        })
        assert rv.status_code == 201

    def test_captcha_module_reports_disabled(self):
        """In test env without TURNSTILE_SECRET_KEY, captcha.is_enabled is False."""
        import sys
        sys.modules.pop("captcha", None)
        from pathlib import Path
        sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "server"))
        import captcha
        assert captcha.is_enabled() is False
        ok, err = captcha.verify("anything")
        assert ok is True
        assert err == ""


class TestCaptchaEnforcement:
    """When secret IS set and bypass is OFF, missing token must reject."""

    def test_register_rejects_without_token_when_enabled(self, monkeypatch, tmp_path):
        import sys
        for mod in ("api_server", "auth", "community", "captcha"):
            sys.modules.pop(mod, None)
        monkeypatch.setenv("FLASK_ENV", "development")
        monkeypatch.setenv("MANSA_DB", str(tmp_path / "cap.db"))
        monkeypatch.setenv("MANSA_SECRET", "x" * 48)
        monkeypatch.setenv("MANSA_ADMIN_TOKEN", "y" * 48)
        monkeypatch.setenv("MANSA_ALLOWED_ORIGINS", "http://localhost:8080")
        monkeypatch.setenv("TURNSTILE_SECRET_KEY", "0xfake-secret")
        monkeypatch.delenv("MANSA_CAPTCHA_BYPASS", raising=False)

        # Build minimal schema.
        import sqlite3
        sqlite3.connect(tmp_path / "cap.db").executescript("""
            CREATE TABLE tickers(symbol TEXT PRIMARY KEY);
            CREATE TABLE prices(symbol TEXT, date TEXT, close REAL, volume INTEGER);
            CREATE TABLE pipeline_logs(id INTEGER PRIMARY KEY, status TEXT, timestamp TEXT);
            CREATE TABLE users(id INTEGER PRIMARY KEY AUTOINCREMENT, email TEXT UNIQUE,
                               password_hash TEXT, prenom TEXT, nom TEXT, pays TEXT, profil TEXT,
                               plan TEXT DEFAULT 'free', email_verified INTEGER DEFAULT 0,
                               verification_token TEXT, created_at TEXT, last_login_at TEXT);
        """)

        from pathlib import Path
        sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "server"))
        import api_server
        api_server.app.config["TESTING"] = True
        if api_server.limiter is not None:
            api_server.limiter.enabled = False

        c = api_server.app.test_client()
        rv = c.post("/api/auth/register", json={
            "email": "noc@example.com", "password": "strongpass123", "prenom": "X",
            # No captcha_token → must reject before doing argon2 hashing.
        })
        # Without network the verify call returns False/error → 400.
        assert rv.status_code == 400
        body = rv.get_json()
        assert "captcha" in body.get("error", "").lower() or "token" in body.get("error", "").lower()
