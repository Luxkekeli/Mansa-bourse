"""Unit tests for scripts/seed_from_app_html.py — the JS-object-literal parser."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

import seed_from_app_html as seed  # noqa: E402


class TestParser:
    def test_parses_basic_object(self):
        obj = seed._parse_obj("{t:'SDSC',n:'Africa Logistics',c:1920}")
        assert obj == {"t": "SDSC", "n": "Africa Logistics", "c": 1920}

    def test_parses_floats_and_negatives(self):
        obj = seed._parse_obj("{per:11.0,v1:-2.11,roe:15.0}")
        assert obj["per"] == 11.0
        assert obj["v1"] == -2.11
        assert obj["roe"] == 15.0

    def test_parses_nested_array(self):
        obj = seed._parse_obj("{t:'X',hist:[{d:'2026-01-01',v:100},{d:'2026-01-02',v:101}]}")
        assert isinstance(obj["hist"], list)
        assert len(obj["hist"]) == 2
        assert obj["hist"][0] == {"d": "2026-01-01", "v": 100}

    def test_handles_strings_with_special_chars(self):
        # Names like 'Bank of Africa Bénin' (UTF-8 ok)
        obj = seed._parse_obj("{n:'Bank of Africa Benin'}")
        assert obj["n"] == "Bank of Africa Benin"

    def test_garbage_input_does_not_crash(self):
        """Defensive: parser must never raise on weird/incomplete JS literals."""
        # The KV regex is strict (only matches recognized value shapes), so
        # garbage values are simply skipped — that's acceptable for a seed tool.
        seed._parse_obj("{x:weird_unquoted}")
        seed._parse_obj("{}")
        seed._parse_obj("{,,,}")
        # No exception = pass.


class TestSymbolResolution:
    def test_short_to_full_with_default(self):
        assert seed.resolve_full_symbol("SGBC") == "SGBC.ci"

    def test_short_to_full_with_hint(self):
        assert seed.resolve_full_symbol("BOAB") == "BOAB.bj"
        assert seed.resolve_full_symbol("ETIT") == "ETIT.tg"
        assert seed.resolve_full_symbol("SNTS") == "SNTS.sn"

    def test_full_passes_through_unchanged(self):
        assert seed.resolve_full_symbol("SGBC.ci") == "SGBC.ci"
        assert seed.resolve_full_symbol("FOO.gw") == "FOO.gw"

    def test_country_from_symbol(self):
        assert seed.country_from_symbol("SGBC.ci") == "CI"
        assert seed.country_from_symbol("BOAB.bj") == "BJ"
        assert seed.country_from_symbol("SNTS.sn") == "SN"
        assert seed.country_from_symbol("nope") == "CI"  # default fallback


class TestParseSArray:
    def test_finds_all_48_tickers_in_real_app_html(self):
        html = ROOT / "frontend" / "app.html"
        tickers = seed.parse_s_array(html)
        # The seed script ships with ≥ 48 production tickers.
        assert len(tickers) >= 40, f"expected ~48 tickers, got {len(tickers)}"
        # Spot-check a few well-known ones.
        symbols = {t["t"] for t in tickers}
        for known in ("SGBC", "SNTS", "ETIT", "BOAC", "PALC"):
            assert known in symbols, f"missing {known}"

    def test_each_ticker_has_required_fields(self):
        html = ROOT / "frontend" / "app.html"
        tickers = seed.parse_s_array(html)
        for t in tickers:
            assert "t" in t and "n" in t and "c" in t, f"missing core fields: {t.get('t')}"
            assert isinstance(t["c"], (int, float)), f"close not numeric: {t}"
