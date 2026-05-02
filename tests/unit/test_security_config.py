"""Tests covering P0-4, P0-5, P0-6 security configuration.

These verify behavior at module import time and at first request.
"""

from __future__ import annotations

import importlib
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SERVER_DIR = ROOT / "server"


def _fresh_import(server_dir=SERVER_DIR):
    """Force a clean re-import of api_server to re-evaluate env-driven checks."""
    sys.path.insert(0, str(server_dir))
    sys.modules.pop("api_server", None)
    return importlib.import_module("api_server")


# ── P0-6 ──────────────────────────────────────────────────────────────────

class TestSecretEnforcement:
    def test_production_without_secret_raises(self, monkeypatch, tmp_path):
        monkeypatch.setenv("FLASK_ENV", "production")
        monkeypatch.delenv("MANSA_SECRET", raising=False)
        monkeypatch.setenv("MANSA_DB", str(tmp_path / "x.db"))
        with pytest.raises(RuntimeError, match="MANSA_SECRET"):
            _fresh_import()

    def test_production_with_short_secret_raises(self, monkeypatch, tmp_path):
        monkeypatch.setenv("FLASK_ENV", "production")
        monkeypatch.setenv("MANSA_SECRET", "tooshort")
        monkeypatch.setenv("MANSA_DB", str(tmp_path / "x.db"))
        with pytest.raises(RuntimeError, match="MANSA_SECRET"):
            _fresh_import()

    def test_production_without_admin_token_raises(self, monkeypatch, tmp_path):
        monkeypatch.setenv("FLASK_ENV", "production")
        monkeypatch.setenv("MANSA_SECRET", "x" * 48)
        monkeypatch.delenv("MANSA_ADMIN_TOKEN", raising=False)
        monkeypatch.setenv("MANSA_DB", str(tmp_path / "x.db"))
        with pytest.raises(RuntimeError, match="MANSA_ADMIN_TOKEN"):
            _fresh_import()

    def test_dev_mode_auto_generates_secret(self, monkeypatch, tmp_path):
        monkeypatch.setenv("FLASK_ENV", "development")
        monkeypatch.delenv("MANSA_SECRET", raising=False)
        monkeypatch.delenv("MANSA_ADMIN_TOKEN", raising=False)
        monkeypatch.setenv("MANSA_DB", str(tmp_path / "x.db"))
        mod = _fresh_import()
        assert len(mod.SECRET_KEY) >= 32
        assert len(mod.ADMIN_TOKEN) >= 32

    def test_secret_and_admin_token_are_independent(self, monkeypatch, tmp_path):
        """SECRET_KEY must NOT derive from MANSA_ADMIN_TOKEN nor vice versa."""
        monkeypatch.setenv("FLASK_ENV", "development")
        monkeypatch.setenv("MANSA_SECRET", "a" * 48)
        monkeypatch.setenv("MANSA_ADMIN_TOKEN", "b" * 48)
        monkeypatch.setenv("MANSA_DB", str(tmp_path / "x.db"))
        mod = _fresh_import()
        assert mod.SECRET_KEY != mod.ADMIN_TOKEN


# ── P0-5 ──────────────────────────────────────────────────────────────────

class TestCORSRestriction:
    def test_production_without_origins_raises(self, monkeypatch, tmp_path):
        monkeypatch.setenv("FLASK_ENV", "production")
        monkeypatch.setenv("MANSA_SECRET", "x" * 48)
        monkeypatch.setenv("MANSA_ADMIN_TOKEN", "y" * 48)
        monkeypatch.delenv("MANSA_ALLOWED_ORIGINS", raising=False)
        monkeypatch.setenv("MANSA_DB", str(tmp_path / "x.db"))
        with pytest.raises(RuntimeError, match="MANSA_ALLOWED_ORIGINS"):
            _fresh_import()

    def test_origins_parsed_as_list(self, monkeypatch, tmp_path):
        monkeypatch.setenv("FLASK_ENV", "development")
        monkeypatch.setenv("MANSA_SECRET", "x" * 48)
        monkeypatch.setenv("MANSA_ADMIN_TOKEN", "y" * 48)
        monkeypatch.setenv(
            "MANSA_ALLOWED_ORIGINS",
            "https://mansa.finance, https://www.mansa.finance ,http://localhost:8080",
        )
        monkeypatch.setenv("MANSA_DB", str(tmp_path / "x.db"))
        mod = _fresh_import()
        assert mod.ALLOWED_ORIGINS == [
            "https://mansa.finance",
            "https://www.mansa.finance",
            "http://localhost:8080",
        ]

    def test_no_wildcard_origin_in_app(self, monkeypatch, tmp_path):
        monkeypatch.setenv("FLASK_ENV", "development")
        monkeypatch.setenv("MANSA_SECRET", "x" * 48)
        monkeypatch.setenv("MANSA_ADMIN_TOKEN", "y" * 48)
        monkeypatch.setenv("MANSA_ALLOWED_ORIGINS", "http://localhost:8080")
        monkeypatch.setenv("MANSA_DB", str(tmp_path / "x.db"))
        mod = _fresh_import()
        assert "*" not in mod.ALLOWED_ORIGINS


# ── P0-4 ──────────────────────────────────────────────────────────────────

class TestDebugMode:
    def test_session_cookies_secure_in_prod(self, monkeypatch, tmp_path):
        monkeypatch.setenv("FLASK_ENV", "production")
        monkeypatch.setenv("MANSA_SECRET", "x" * 48)
        monkeypatch.setenv("MANSA_ADMIN_TOKEN", "y" * 48)
        monkeypatch.setenv("MANSA_ALLOWED_ORIGINS", "https://mansa.finance")
        monkeypatch.setenv("MANSA_DB", str(tmp_path / "x.db"))
        mod = _fresh_import()
        assert mod.app.config["SESSION_COOKIE_SECURE"] is True
        assert mod.app.config["SESSION_COOKIE_HTTPONLY"] is True
        assert mod.app.config["SESSION_COOKIE_SAMESITE"] == "Lax"

    def test_session_cookies_relaxed_in_dev(self, monkeypatch, tmp_path):
        monkeypatch.setenv("FLASK_ENV", "development")
        monkeypatch.setenv("MANSA_SECRET", "x" * 48)
        monkeypatch.setenv("MANSA_ADMIN_TOKEN", "y" * 48)
        monkeypatch.setenv("MANSA_ALLOWED_ORIGINS", "http://localhost:8080")
        monkeypatch.setenv("MANSA_DB", str(tmp_path / "x.db"))
        mod = _fresh_import()
        # Dev allows HTTP for local testing.
        assert mod.app.config["SESSION_COOKIE_SECURE"] is False
        assert mod.app.config["SESSION_COOKIE_HTTPONLY"] is True
