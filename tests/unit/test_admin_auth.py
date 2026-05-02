"""Tests for the require_admin decorator (P0-6)."""

from __future__ import annotations


class TestAdminAuth:
    def test_admin_endpoint_rejects_missing_token(self, client):
        c, _ = client
        rv = c.get("/api/analytics/report")
        assert rv.status_code == 401

    def test_admin_endpoint_rejects_wrong_token(self, client):
        c, _ = client
        rv = c.get("/api/analytics/report", headers={"X-Admin-Token": "definitely-wrong"})
        assert rv.status_code == 401

    def test_admin_endpoint_accepts_valid_token(self, client, admin_headers):
        c, _ = client
        rv = c.get("/api/analytics/report", headers=admin_headers)
        assert rv.status_code == 200

    def test_admin_endpoint_legacy_header_still_works_with_admin_token(self, client, admin_headers):
        """Backwards compat: X-Admin-Key accepts the new ADMIN_TOKEN value
        (single deprecation cycle)."""
        c, _ = client
        rv = c.get(
            "/api/analytics/report",
            headers={"X-Admin-Key": admin_headers["X-Admin-Token"]},
        )
        assert rv.status_code == 200

    def test_admin_endpoint_no_longer_accepts_secret_derived_key(self, client):
        """Old behaviour derived admin key from SECRET_KEY hash. Must no longer work."""
        import hashlib

        c, mod = client
        old_derived = hashlib.sha256(mod.SECRET_KEY.encode()).hexdigest()[:32]
        rv = c.get("/api/analytics/report", headers={"X-Admin-Token": old_derived})
        assert rv.status_code == 401
