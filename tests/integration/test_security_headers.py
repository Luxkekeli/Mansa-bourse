"""Tests for P1-3 security headers (Talisman + custom after_request)."""

from __future__ import annotations

# Talisman in dev mode disables HSTS + force_https, but still emits CSP / X-Frame /
# Referrer-Policy. We assert on the headers that should be present in BOTH modes.
COMMON_HEADERS = [
    "Content-Security-Policy",
    "X-Frame-Options",
    "Referrer-Policy",
    "X-Content-Type-Options",
    "Permissions-Policy",
]


class TestCommonHeaders:
    def test_health_endpoint_has_csp(self, client):
        c, _ = client
        rv = c.get("/api/health")
        assert "Content-Security-Policy" in rv.headers
        csp = rv.headers["Content-Security-Policy"]
        assert "default-src 'self'" in csp
        assert "object-src 'none'" in csp
        assert "frame-ancestors 'none'" in csp

    def test_x_frame_options_deny(self, client):
        c, _ = client
        rv = c.get("/api/health")
        assert rv.headers.get("X-Frame-Options") == "DENY"

    def test_x_content_type_options_nosniff(self, client):
        c, _ = client
        rv = c.get("/api/health")
        assert rv.headers.get("X-Content-Type-Options") == "nosniff"

    def test_referrer_policy_strict(self, client):
        c, _ = client
        rv = c.get("/api/health")
        assert "strict-origin" in rv.headers.get("Referrer-Policy", "")

    def test_permissions_policy_blocks_powerful_apis(self, client):
        c, _ = client
        rv = c.get("/api/health")
        pp = rv.headers.get("Permissions-Policy", "")
        assert "geolocation=()" in pp
        assert "camera=()" in pp
        assert "microphone=()" in pp


class TestCSPAllowList:
    """Confirm the CSP whitelists only what we explicitly need."""

    def test_chartjs_self_hosted_no_external_cdn(self, client):
        """Charts.js + DOMPurify are now self-hosted in /vendor/.
        CSP must NOT whitelist cdn.jsdelivr.net (smaller attack surface)."""
        c, _ = client
        rv = c.get("/api/health")
        csp = rv.headers["Content-Security-Policy"]
        assert "https://cdn.jsdelivr.net" not in csp
        # 'self' covers the /vendor/ files served by Flask.
        assert "'self'" in csp.split("script-src")[1].split(";")[0]

    def test_no_wildcard_in_csp(self, client):
        c, _ = client
        rv = c.get("/api/health")
        csp = rv.headers["Content-Security-Policy"]
        # The only wildcard-ish thing tolerated is 'unsafe-inline' (transitional).
        # Reject any "*" source value as a regression guard.
        assert " * " not in csp
        # script-src and connect-src must not contain `*` as a host source.
        for directive in csp.split(";"):
            d = directive.strip()
            if d.startswith("script-src") or d.startswith("connect-src"):
                assert "*" not in d.split()


class TestProdOnlyHeaders:
    """HSTS is gated by FLASK_ENV != development. Verify activation in prod."""

    def test_hsts_present_in_production(self, monkeypatch, tmp_path):
        import sys
        # Need real prod env to flip HSTS on.
        for mod in ("api_server", "auth", "community"):
            sys.modules.pop(mod, None)
        monkeypatch.setenv("FLASK_ENV", "production")
        monkeypatch.setenv("MANSA_DB", str(tmp_path / "prod.db"))
        monkeypatch.setenv("MANSA_SECRET", "x" * 48)
        monkeypatch.setenv("MANSA_ADMIN_TOKEN", "y" * 48)
        monkeypatch.setenv("MANSA_ALLOWED_ORIGINS", "https://mansa.finance")
        # Build empty schema so /api/health doesn't crash.
        import sqlite3
        sqlite3.connect(tmp_path / "prod.db").executescript(
            "CREATE TABLE tickers(symbol TEXT PRIMARY KEY);"
            "CREATE TABLE prices(symbol TEXT, date TEXT);"
            "CREATE TABLE pipeline_logs(id INTEGER PRIMARY KEY, status TEXT, timestamp TEXT);"
        )

        from pathlib import Path
        sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "server"))
        import api_server  # noqa: E402

        api_server.app.config["TESTING"] = True
        if api_server.limiter is not None:
            api_server.limiter.enabled = False
        c = api_server.app.test_client()
        rv = c.get("/api/health", base_url="https://localhost")
        assert "Strict-Transport-Security" in rv.headers
        sts = rv.headers["Strict-Transport-Security"]
        assert "max-age=31536000" in sts
        assert "includeSubDomains" in sts
