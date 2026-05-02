"""Tests for P0-3 (payment gating) and P0-8 (fundamentals endpoint)."""

from __future__ import annotations

# ── P0-3: Payment gating ─────────────────────────────────────────────────

class TestPaymentsDisabled:
    """By default MANSA_PAYMENTS_ENABLED is unset → all /api/payment/* return 503."""

    def test_payment_plans_returns_503(self, client):
        c, _ = client
        rv = c.get("/api/payment/plans")
        assert rv.status_code == 503
        assert "not yet available" in rv.get_json()["error"].lower()

    def test_payment_initiate_returns_503(self, client):
        c, _ = client
        rv = c.post("/api/payment/initiate", json={
            "email": "x@y.com", "plan": "pro_monthly", "method": "wave"
        })
        assert rv.status_code == 503

    def test_payment_webhook_returns_503(self, client):
        c, _ = client
        rv = c.post("/api/payment/webhook", json={"reference": "X"})
        assert rv.status_code == 503


class TestPaymentsEnabled:
    """When MANSA_PAYMENTS_ENABLED=1, the endpoints respond normally."""

    def test_payment_plans_with_flag(self, monkeypatch, strong_env):
        import sys
        monkeypatch.setenv("MANSA_PAYMENTS_ENABLED", "1")
        for mod in ("api_server", "auth", "community"):
            sys.modules.pop(mod, None)
        sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[2] / "server"))
        import api_server  # noqa: E402

        api_server.app.config["TESTING"] = True
        if api_server.limiter is not None:
            api_server.limiter.enabled = False
        c = api_server.app.test_client()
        rv = c.get("/api/payment/plans")
        assert rv.status_code == 200
        assert "plans" in rv.get_json()


# ── P0-8: Fundamentals endpoint ──────────────────────────────────────────

class TestFundamentalsEndpoint:
    def test_returns_empty_for_unknown_ticker(self, client):
        c, _ = client
        rv = c.get("/api/fundamentals/UNKNOWN")
        assert rv.status_code == 200
        assert rv.get_json()["count"] == 0

    def test_returns_data_after_seed(self, client):
        """Insert a fundamentals row directly and verify the endpoint reads it."""
        c, mod = client
        with mod.app.app_context():
            db = mod.get_db()
            db.execute(
                """INSERT INTO fundamentals (symbol, year, per, pbr, roe, roa, margin_net, debt_equity)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                ["SGBC.ci", 2025, 8.5, 1.2, 15.0, 1.8, 22.0, 0.55],
            )
            db.commit()
        rv = c.get("/api/fundamentals/SGBC.ci")
        assert rv.status_code == 200
        body = rv.get_json()
        assert body["count"] == 1
        f = body["fundamentals"][0]
        assert f["per"] == 8.5
        assert f["roe"] == 15.0

    def test_short_symbol_resolves_via_like(self, client):
        """A user querying 'SGBC' should still find 'SGBC.ci'."""
        c, mod = client
        with mod.app.app_context():
            db = mod.get_db()
            db.execute(
                """INSERT INTO fundamentals (symbol, year, per, pbr, roe)
                   VALUES (?, ?, ?, ?, ?)""",
                ["SGBC.ci", 2025, 8.5, 1.2, 15.0],
            )
            db.commit()
        rv = c.get("/api/fundamentals/SGBC")
        assert rv.status_code == 200
        # The endpoint matches via "symbol = ? OR symbol LIKE ?".
        assert rv.get_json()["count"] >= 1

    def test_orders_by_year_desc(self, client):
        c, mod = client
        with mod.app.app_context():
            db = mod.get_db()
            db.executemany(
                """INSERT INTO fundamentals (symbol, year, per) VALUES (?, ?, ?)""",
                [("SNTS.sn", 2023, 10.0), ("SNTS.sn", 2025, 12.0), ("SNTS.sn", 2024, 11.0)],
            )
            db.commit()
        rv = c.get("/api/fundamentals/SNTS.sn")
        years = [r["year"] for r in rv.get_json()["fundamentals"]]
        assert years == [2025, 2024, 2023]
