"""MANSA — P0-1: Community endpoints (replace community/bridge.php).

Endpoints:
- POST /api/community/post   — create a new message in a room (auth required)
- GET  /api/community/poll   — fetch new messages since a given ISO timestamp

Security model
--------------
- Authenticated users only (require_auth) for posting.
- Server-side sanitization via bleach. Only `sanitized_content` is ever returned.
- The raw `content` field is kept in DB for moderation/audit but never exposed.
- Rate limit: 30 posts / 5 min / IP (best-effort if flask-limiter present).
"""

from __future__ import annotations

import logging

from flask import Blueprint, g, jsonify, request

log = logging.getLogger("mansa_community")

# ── Bleach allow-lists (intentionally tight) ─────────────────────────────
try:
    import bleach
    _BLEACH_AVAILABLE = True
except ImportError:  # pragma: no cover — package is in requirements.txt
    bleach = None
    _BLEACH_AVAILABLE = False
    log.warning("bleach not installed — falling back to plain-text escaping. "
                "Install with: pip install bleach")

ALLOWED_TAGS = ["b", "i", "em", "strong", "code", "pre", "br", "p", "a", "ul", "ol", "li", "blockquote"]
ALLOWED_ATTRS = {"a": ["href", "title", "rel", "target"]}
ALLOWED_PROTOCOLS = ["http", "https", "mailto"]


def _sanitize(html: str) -> str:
    """Return a safe HTML version of user-provided content."""
    if not html:
        return ""
    if not _BLEACH_AVAILABLE:
        # Last-resort: escape everything (no markup).
        from html import escape
        return escape(html)
    cleaned = bleach.clean(
        html,
        tags=ALLOWED_TAGS,
        attributes=ALLOWED_ATTRS,
        protocols=ALLOWED_PROTOCOLS,
        strip=True,
    )
    # Ensure links open in a new tab and don't leak the referrer.
    cleaned = bleach.linkify(
        cleaned,
        callbacks=[
            lambda attrs, new=False: {
                **attrs,
                (None, "target"): "_blank",
                (None, "rel"): "noopener noreferrer nofollow",
            }
        ],
    )
    return cleaned


# ── Blueprint ────────────────────────────────────────────────────────────

community_bp = Blueprint("community", __name__, url_prefix="/api/community")


def _db():
    try:
        from .api_server import get_db  # type: ignore[import-not-found]
    except ImportError:
        from api_server import get_db  # type: ignore[no-redef]
    return get_db()


def _limit_post():
    try:
        try:
            from .api_server import limiter  # type: ignore[import-not-found]
        except ImportError:
            from api_server import limiter  # type: ignore[no-redef]
        if limiter is None:
            return lambda f: f
        return limiter.limit("30 per 5 minutes")
    except Exception:
        return lambda f: f


@community_bp.route("/post", methods=["POST"])
def post_message():
    """Create a new community post. Authenticated users only."""
    # Late import to avoid circular dep with auth_bp.
    try:
        from .auth import require_auth  # type: ignore[import-not-found]
    except ImportError:
        from auth import require_auth  # type: ignore[no-redef]

    @require_auth
    def _inner():
        data = request.get_json(silent=True) or {}

        # P1-10: Turnstile gate (no-op when secret unset).
        try:
            try:
                from .captcha import verify as _cap_verify  # type: ignore[import-not-found]
            except ImportError:
                from captcha import verify as _cap_verify  # type: ignore[no-redef]
            cap_ok, cap_err = _cap_verify(
                data.get("captcha_token") or "", request.remote_addr
            )
            if not cap_ok:
                return jsonify({"error": cap_err}), 400
        except ImportError:
            pass

        room = (data.get("room") or "general").strip()[:64]
        content = (data.get("content") or "").strip()
        parent_id = data.get("parent_id")

        if not content:
            return jsonify({"error": "Contenu vide"}), 400
        if len(content) > 4000:
            return jsonify({"error": "Message trop long (4000 caractères max)"}), 400
        if not room or not room.replace("-", "").replace("_", "").isalnum():
            return jsonify({"error": "Room invalide"}), 400

        sanitized = _sanitize(content)
        if not sanitized.strip():
            return jsonify({"error": "Contenu invalide après filtrage"}), 400

        u = g.user
        cur = _db().execute(
            "INSERT INTO community_posts (room, user_email, user_prenom, parent_id, "
            "content, sanitized_content) VALUES (?, ?, ?, ?, ?, ?)",
            [room, u["email"], u["prenom"], parent_id, content, sanitized],
        )
        _db().commit()
        return jsonify({
            "id": cur.lastrowid,
            "room": room,
            "user_prenom": u["prenom"],
            "sanitized_content": sanitized,
            "parent_id": parent_id,
        }), 201

    # Apply rate-limit then auth.
    return _limit_post()(_inner)()


@community_bp.route("/poll", methods=["GET"])
def poll_messages():
    """Fetch posts in a room newer than `since` (ISO timestamp). Public read."""
    room = (request.args.get("room") or "general").strip()[:64]
    since = (request.args.get("since") or "1970-01-01T00:00:00").strip()
    limit = min(int(request.args.get("limit", 50)), 200)

    if not room or not room.replace("-", "").replace("_", "").isalnum():
        return jsonify({"error": "Room invalide"}), 400

    rows = _db().execute(
        "SELECT id, room, user_prenom, parent_id, sanitized_content, created_at "
        "FROM community_posts "
        "WHERE room = ? AND created_at > ? AND deleted_at IS NULL "
        "ORDER BY created_at ASC LIMIT ?",
        [room, since, limit],
    ).fetchall()

    return jsonify({
        "room": room,
        "since": since,
        "count": len(rows),
        "messages": [dict(r) for r in rows],
    })


__all__ = ["community_bp", "_sanitize"]
