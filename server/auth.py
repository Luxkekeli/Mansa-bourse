"""MANSA — P0-2: Real authentication module.

Replaces the localStorage/btoa() pseudo-auth in the frontend with:
- argon2-cffi password hashing (Argon2id, recommended OWASP defaults).
- Server-side Flask sessions (Secure, HttpOnly, SameSite=Lax cookies).
- Rate-limited login (5 / 15 min / IP) via flask-limiter.
- Email verification (stub SMTP — logs to console until WAVE-grade SMTP is wired).
- Password reset with one-shot, 1-hour tokens.

Routes registered as a Blueprint mounted at /api/auth/* by api_server.py.

Dependencies:
- argon2-cffi >= 23.1
- bleach (already used by the community module)
- flask-limiter (best-effort; no-ops if absent)
"""

from __future__ import annotations

import logging
import os
import re
import secrets
import sqlite3
from datetime import datetime, timedelta
from functools import wraps

from flask import Blueprint, g, jsonify, request, session

log = logging.getLogger("mansa_auth")

# ── Argon2 ───────────────────────────────────────────────────────────────
# argon2-cffi raises a clear error if the C extension is missing.
try:
    from argon2 import PasswordHasher
    from argon2.exceptions import VerifyMismatchError
    _hasher = PasswordHasher(
        # OWASP 2024 recommended baseline for Argon2id.
        time_cost=3,
        memory_cost=64 * 1024,  # 64 MiB
        parallelism=4,
        hash_len=32,
        salt_len=16,
    )
    _ARGON2_AVAILABLE = True
except ImportError:
    _hasher = None
    _ARGON2_AVAILABLE = False
    log.warning("argon2-cffi not installed — auth module disabled. "
                "Install with: pip install argon2-cffi")

    class VerifyMismatchError(Exception):
        """Stub so tests using import-paths still load."""


# ── Public Blueprint ─────────────────────────────────────────────────────

auth_bp = Blueprint("auth", __name__, url_prefix="/api/auth")


# ── DB helpers (rely on api_server's get_db via Flask g) ─────────────────

def _db():
    """Lazy-resolve the api_server.get_db() so we don't create circular imports.
    Tries package-relative import first, falls back to absolute when running
    via tests where `server/` is on sys.path."""
    try:
        from .api_server import get_db  # type: ignore[import-not-found]
    except ImportError:
        from api_server import get_db  # type: ignore[no-redef]
    return get_db()


# ── Validation helpers ───────────────────────────────────────────────────

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _valid_email(s: str) -> bool:
    return bool(s and len(s) <= 254 and _EMAIL_RE.match(s))


def _valid_password(s: str) -> tuple[bool, str]:
    if not s or len(s) < 8:
        return False, "Mot de passe trop court (8 caractères minimum)."
    if len(s) > 200:
        return False, "Mot de passe trop long (200 caractères maximum)."
    return True, ""


def _hash_password(pwd: str) -> str:
    if not _ARGON2_AVAILABLE:
        raise RuntimeError("argon2-cffi not available — auth disabled.")
    return _hasher.hash(pwd)


def _verify_password(stored_hash: str, pwd: str) -> bool:
    if not _ARGON2_AVAILABLE:
        return False
    try:
        return _hasher.verify(stored_hash, pwd)
    except VerifyMismatchError:
        return False
    except Exception as e:
        log.warning("Argon2 verify error: %s", e)
        return False


def _send_email_stub(to: str, subject: str, body: str) -> None:
    """Stub SMTP: log to console (and a file if MANSA_SMTP_LOG is set).

    Replace with real Sendgrid/Mailgun/SES integration post-launch.
    """
    line = f"[EMAIL→{to}] {subject}\n{body}\n{'─' * 60}"
    log.info(line)
    log_file = os.environ.get("MANSA_SMTP_LOG")
    if log_file:
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(line + "\n")


# ── Rate limiter (optional) ──────────────────────────────────────────────

def _limit_decorator():
    """Return either the real flask-limiter decorator or a no-op."""
    try:
        try:
            from .api_server import limiter  # type: ignore[import-not-found]
        except ImportError:
            from api_server import limiter  # type: ignore[no-redef]
        if limiter is None:
            return lambda f: f
        return limiter.limit("5 per 15 minutes")
    except Exception:
        return lambda f: f


# ── require_auth decorator ───────────────────────────────────────────────

def require_auth(f):
    """Reject unauthenticated requests with 401.

    Usage:
        @app.route('/api/portfolio')
        @require_auth
        def portfolio(): ...

    Sets ``g.user`` to the authenticated user dict.
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        uid = session.get("user_id")
        if not uid:
            return jsonify({"error": "Authentication required", "code": 401}), 401
        row = _db().execute(
            "SELECT id, email, prenom, nom, pays, profil, plan, email_verified "
            "FROM users WHERE id = ?",
            [uid],
        ).fetchone()
        if not row:
            session.clear()
            return jsonify({"error": "Session invalidated", "code": 401}), 401
        g.user = dict(row)
        return f(*args, **kwargs)
    return decorated


# ── Routes ───────────────────────────────────────────────────────────────

def _verify_captcha(data: dict) -> tuple[bool, str]:
    """Best-effort Turnstile check. Lazy-imported to avoid circular deps."""
    try:
        try:
            from .captcha import verify  # type: ignore[import-not-found]
        except ImportError:
            from captcha import verify  # type: ignore[no-redef]
    except ImportError:
        return True, ""
    token = data.get("captcha_token") or data.get("cf_turnstile_response") or ""
    return verify(token, request.remote_addr)


@auth_bp.route("/register", methods=["POST"])
@_limit_decorator()
def register():
    """Create a new user. Returns 201 + sets session cookie on success."""
    if not _ARGON2_AVAILABLE:
        return jsonify({"error": "Auth backend unavailable"}), 503

    data = request.get_json(silent=True) or {}

    # P1-10: Turnstile gate (no-op in dev when secret is unset).
    cap_ok, cap_err = _verify_captcha(data)
    if not cap_ok:
        return jsonify({"error": cap_err}), 400

    email = (data.get("email") or "").strip().lower()
    pwd = data.get("password") or ""
    prenom = (data.get("prenom") or "").strip()
    nom = (data.get("nom") or "").strip()
    pays = (data.get("pays") or "").strip()
    profil = (data.get("profil") or "debutant").strip()

    if not _valid_email(email):
        return jsonify({"error": "Email invalide"}), 400
    pwd_ok, pwd_err = _valid_password(pwd)
    if not pwd_ok:
        return jsonify({"error": pwd_err}), 400
    if not prenom:
        return jsonify({"error": "Prénom requis"}), 400
    if profil not in {"debutant", "intermediaire", "avance"}:
        profil = "debutant"

    db = _db()
    # Check uniqueness (case-insensitive thanks to COLLATE NOCASE on the column).
    existing = db.execute("SELECT id FROM users WHERE email = ?", [email]).fetchone()
    if existing:
        return jsonify({"error": "Cet email est déjà utilisé"}), 409

    token = secrets.token_urlsafe(32)
    try:
        db.execute(
            "INSERT INTO users (email, password_hash, prenom, nom, pays, profil, "
            "plan, email_verified, verification_token) "
            "VALUES (?, ?, ?, ?, ?, ?, 'free', 0, ?)",
            [email, _hash_password(pwd), prenom, nom, pays, profil, token],
        )
        db.commit()
    except sqlite3.IntegrityError:
        return jsonify({"error": "Cet email est déjà utilisé"}), 409

    user_row = db.execute(
        "SELECT id, email, prenom, nom, pays, profil, plan, email_verified FROM users WHERE email = ?",
        [email],
    ).fetchone()
    user = dict(user_row)

    # Send verification email (stub).
    verify_url = f"{request.host_url.rstrip('/')}/api/auth/verify?token={token}"
    _send_email_stub(
        email,
        "Confirmez votre email MANSA",
        f"Bonjour {prenom},\n\nMerci de votre inscription. Confirmez votre email :\n{verify_url}\n\n"
        "Ce lien est valable 7 jours.",
    )

    # Open session immediately — user can browse, premium-protected actions
    # may still require email_verified=1 (frontend decides).
    session.clear()
    session["user_id"] = user["id"]
    session.permanent = True

    return jsonify({"user": user, "message": "Compte créé. Vérifiez votre email."}), 201


@auth_bp.route("/login", methods=["POST"])
@_limit_decorator()
def login():
    """Authenticate an existing user."""
    if not _ARGON2_AVAILABLE:
        return jsonify({"error": "Auth backend unavailable"}), 503

    data = request.get_json(silent=True) or {}
    email = (data.get("email") or "").strip().lower()
    pwd = data.get("password") or ""
    if not email or not pwd:
        return jsonify({"error": "Email et mot de passe requis"}), 400

    row = _db().execute(
        "SELECT id, email, password_hash, prenom, nom, pays, profil, plan, email_verified "
        "FROM users WHERE email = ?",
        [email],
    ).fetchone()
    if not row or not _verify_password(row["password_hash"], pwd):
        # Generic error — never leak which side was wrong.
        return jsonify({"error": "Email ou mot de passe incorrect"}), 401

    _db().execute("UPDATE users SET last_login_at = datetime('now') WHERE id = ?", [row["id"]])
    _db().commit()

    user = {k: row[k] for k in ("id", "email", "prenom", "nom", "pays", "profil", "plan", "email_verified")}
    session.clear()
    session["user_id"] = user["id"]
    session.permanent = True
    return jsonify({"user": user, "message": f"Bienvenue {user['prenom']} !"})


@auth_bp.route("/logout", methods=["POST"])
def logout():
    """Drop the session. Always returns 200 (idempotent)."""
    session.clear()
    return jsonify({"status": "logged_out"})


@auth_bp.route("/me", methods=["GET"])
def me():
    """Return the current authenticated user, or 401."""
    uid = session.get("user_id")
    if not uid:
        return jsonify({"error": "Not authenticated", "code": 401}), 401
    row = _db().execute(
        "SELECT id, email, prenom, nom, pays, profil, plan, email_verified FROM users WHERE id = ?",
        [uid],
    ).fetchone()
    if not row:
        session.clear()
        return jsonify({"error": "Session invalidated", "code": 401}), 401
    return jsonify({"user": dict(row)})


@auth_bp.route("/verify", methods=["GET"])
def verify_email():
    """Email verification link target."""
    token = request.args.get("token", "")
    if not token:
        return jsonify({"error": "Token manquant"}), 400
    db = _db()
    row = db.execute(
        "SELECT id FROM users WHERE verification_token = ? AND email_verified = 0",
        [token],
    ).fetchone()
    if not row:
        return jsonify({"error": "Token invalide ou déjà utilisé"}), 400
    db.execute(
        "UPDATE users SET email_verified = 1, verification_token = NULL WHERE id = ?",
        [row["id"]],
    )
    db.commit()
    return jsonify({"status": "verified"})


@auth_bp.route("/forgot", methods=["POST"])
@_limit_decorator()
def forgot():
    """Issue a one-shot reset token. Always returns 200 to avoid user enumeration."""
    data = request.get_json(silent=True) or {}

    # P1-10: Turnstile gate. Even though /forgot is always-200, blocking bots
    # here saves SMTP cost and reduces side-channel signal.
    cap_ok, _cap_err = _verify_captcha(data)
    if not cap_ok:
        # Still return 200 to preserve the always-200 guarantee.
        return jsonify({"status": "ok", "message": "Si cet email existe, un lien a été envoyé."})

    email = (data.get("email") or "").strip().lower()

    if _valid_email(email):
        row = _db().execute("SELECT id, prenom FROM users WHERE email = ?", [email]).fetchone()
        if row:
            token = secrets.token_urlsafe(32)
            expires = (datetime.utcnow() + timedelta(hours=1)).isoformat()
            _db().execute(
                "INSERT INTO password_resets (token, user_id, expires_at) VALUES (?, ?, ?)",
                [token, row["id"], expires],
            )
            _db().commit()
            reset_url = f"{request.host_url.rstrip('/')}/?reset_token={token}"
            _send_email_stub(
                email,
                "Réinitialisation de votre mot de passe MANSA",
                f"Bonjour {row['prenom']},\n\nUtilisez ce lien (valable 1 heure) :\n{reset_url}\n\n"
                "Si vous n'êtes pas à l'origine de cette demande, ignorez ce message.",
            )

    # Always 200, no information disclosure.
    return jsonify({"status": "ok", "message": "Si cet email existe, un lien a été envoyé."})


@auth_bp.route("/reset", methods=["POST"])
@_limit_decorator()
def reset():
    """Consume a reset token and set a new password."""
    if not _ARGON2_AVAILABLE:
        return jsonify({"error": "Auth backend unavailable"}), 503

    data = request.get_json(silent=True) or {}
    token = (data.get("token") or "").strip()
    pwd = data.get("password") or ""

    pwd_ok, pwd_err = _valid_password(pwd)
    if not pwd_ok:
        return jsonify({"error": pwd_err}), 400
    if not token:
        return jsonify({"error": "Token requis"}), 400

    db = _db()
    row = db.execute(
        "SELECT user_id, expires_at, consumed_at FROM password_resets WHERE token = ?",
        [token],
    ).fetchone()
    if not row:
        return jsonify({"error": "Token invalide"}), 400
    if row["consumed_at"]:
        return jsonify({"error": "Token déjà utilisé"}), 400
    if row["expires_at"] < datetime.utcnow().isoformat():
        return jsonify({"error": "Token expiré"}), 400

    db.execute("UPDATE users SET password_hash = ? WHERE id = ?", [_hash_password(pwd), row["user_id"]])
    db.execute("UPDATE password_resets SET consumed_at = datetime('now') WHERE token = ?", [token])
    db.commit()

    # Auto-login.
    user_row = db.execute(
        "SELECT id, email, prenom, nom, pays, profil, plan, email_verified FROM users WHERE id = ?",
        [row["user_id"]],
    ).fetchone()
    session.clear()
    session["user_id"] = row["user_id"]
    session.permanent = True
    return jsonify({"user": dict(user_row), "message": "Mot de passe réinitialisé."})


# Re-exported for tests / typing.
__all__ = [
    "auth_bp",
    "require_auth",
    "_hash_password",
    "_verify_password",
    "_valid_email",
    "_valid_password",
    "_ARGON2_AVAILABLE",
]
