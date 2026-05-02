"""P1-10 — Cloudflare Turnstile verification.

Why Turnstile and not hCaptcha/reCAPTCHA?
- Free, no per-request quota.
- No tracking / no fingerprinting (privacy-aligned with our values).
- Server-side verification is a single POST.

Setup
-----
1. Sign up at https://www.cloudflare.com/products/turnstile/
2. Create a site key + secret pair for `mansa.finance`.
3. Set env vars:
       TURNSTILE_SITE_KEY=0x4AAA...      (public, embedded in HTML)
       TURNSTILE_SECRET_KEY=0x4AAA...    (server-only, NEVER commit)
4. The frontend reads window.MANSA_CONFIG.turnstileSiteKey at load.

Failure mode
------------
If the secret is unset, verification is **skipped with a warning** so dev
environments and CI don't break. Production deployments must set it (see
docs/RELEASE_CHECKLIST.md).
"""

from __future__ import annotations

import logging
import os

log = logging.getLogger("mansa_captcha")

VERIFY_URL = "https://challenges.cloudflare.com/turnstile/v0/siteverify"

SITE_KEY = os.environ.get("TURNSTILE_SITE_KEY", "")
SECRET_KEY = os.environ.get("TURNSTILE_SECRET_KEY", "")

# In dev/test, allow a "bypass" token to keep tests deterministic without
# actually hitting Cloudflare. Set MANSA_CAPTCHA_BYPASS=1 to enable.
BYPASS = os.environ.get("MANSA_CAPTCHA_BYPASS", "") == "1"


def is_enabled() -> bool:
    """Return True if Turnstile verification is wired and enforced."""
    return bool(SECRET_KEY) and not BYPASS


def verify(token: str, remote_ip: str | None = None) -> tuple[bool, str]:
    """Verify a Turnstile token with Cloudflare.

    Returns (ok, error_message). ok=True when the token validates OR when
    verification is disabled (no secret configured / bypass flag set).
    """
    if not is_enabled():
        return True, ""

    if not token:
        return False, "Captcha token manquant"

    try:
        import requests  # local import: only needed when actually verifying
    except ImportError:
        log.warning("`requests` not installed — captcha verification skipped")
        return True, ""

    payload = {"secret": SECRET_KEY, "response": token}
    if remote_ip:
        payload["remoteip"] = remote_ip

    try:
        r = requests.post(VERIFY_URL, data=payload, timeout=5)
        if not r.ok:
            return False, f"Captcha verification HTTP {r.status_code}"
        body = r.json()
        if body.get("success"):
            return True, ""
        codes = ",".join(body.get("error-codes") or []) or "invalid"
        return False, f"Captcha refusé: {codes}"
    except Exception as e:  # network glitch, JSON error, etc.
        log.warning("Turnstile verify failed: %s", e)
        # Fail-closed in prod — don't let users bypass by knocking out CF.
        return False, "Captcha indisponible, réessayez"


__all__ = ["verify", "is_enabled", "SITE_KEY"]
