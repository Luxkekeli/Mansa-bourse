"""Smoke tests for public API endpoints — confirm they still work post-hardening."""

from __future__ import annotations


class TestPublicEndpoints:
    def test_health_returns_200(self, client):
        c, _ = client
        rv = c.get("/api/health")
        assert rv.status_code == 200
        body = rv.get_json()
        assert body["status"] == "healthy"
        assert "version" in body
        assert body["database"]["tickers"] >= 1

    def test_tickers_listing(self, client):
        c, _ = client
        rv = c.get("/api/tickers")
        assert rv.status_code == 200
        body = rv.get_json()
        assert body["count"] >= 1
        symbols = [t["symbol"] for t in body["tickers"]]
        assert "SGBC.ci" in symbols

    def test_ticker_detail(self, client):
        c, _ = client
        rv = c.get("/api/ticker/SGBC.ci")
        assert rv.status_code == 200
        body = rv.get_json()
        assert body["ticker"]["symbol"] == "SGBC.ci"
        assert isinstance(body["prices"], list)

    def test_ticker_not_found(self, client):
        c, _ = client
        rv = c.get("/api/ticker/DOES_NOT_EXIST_XYZ")
        assert rv.status_code == 404

    def test_prices_with_date_filter(self, client):
        c, _ = client
        rv = c.get("/api/prices/SGBC.ci?from=2026-01-01&to=2026-12-31")
        assert rv.status_code == 200
        body = rv.get_json()
        assert body["symbol"] == "SGBC.ci"
        assert all("2026-" in p["date"] for p in body["prices"])

    def test_search(self, client):
        c, _ = client
        rv = c.get("/api/search?q=SGBC")
        assert rv.status_code == 200
        body = rv.get_json()
        assert body["count"] >= 1

    def test_indices(self, client):
        c, _ = client
        rv = c.get("/api/indices")
        assert rv.status_code == 200
        body = rv.get_json()
        assert "indices" in body

    def test_404_returns_json(self, client):
        c, _ = client
        rv = c.get("/api/this/does/not/exist")
        assert rv.status_code == 404
        body = rv.get_json()
        assert body["code"] == 404


class TestNullOHLCHandling:
    """Endpoints must serve rows where open/high/low are NULL without crashing."""

    def test_ticker_detail_with_null_ohlc(self, client):
        c, _ = client
        # SNTS.sn was seeded with NULL open/high/low.
        rv = c.get("/api/ticker/SNTS.sn")
        assert rv.status_code == 200
        body = rv.get_json()
        # At least one price row should have None values for open/high/low.
        prices = body["prices"]
        assert any(p["open"] is None for p in prices)

    def test_prices_with_null_ohlc(self, client):
        c, _ = client
        rv = c.get("/api/prices/SNTS.sn")
        assert rv.status_code == 200
        body = rv.get_json()
        assert body["count"] == 1
        assert body["prices"][0]["open"] is None
        assert body["prices"][0]["close"] == 18500
