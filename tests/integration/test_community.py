"""Tests for /api/community/* (P0-1).

Covers:
- Post requires auth (401 anonymous, 201 authed)
- bleach sanitization removes script tags and dangerous attrs
- Sanitized HTML is what gets served back via /poll (NEVER raw)
- Room name validation
- Empty / oversized content rejected
"""

from __future__ import annotations


def _register(c, email="bob@example.com"):
    return c.post(
        "/api/auth/register",
        json={"email": email, "password": "strongpass123", "prenom": "Bob"},
    )


# ── Auth-gated posting ───────────────────────────────────────────────────

class TestPostAuth:
    def test_post_anonymous_rejected(self, client):
        c, _ = client
        rv = c.post("/api/community/post", json={"room": "general", "content": "Hello"})
        assert rv.status_code == 401

    def test_post_authed_succeeds(self, client):
        c, _ = client
        _register(c)
        rv = c.post("/api/community/post", json={"room": "general", "content": "Hello world"})
        assert rv.status_code == 201
        body = rv.get_json()
        assert body["room"] == "general"
        assert body["user_prenom"] == "Bob"
        assert "id" in body


# ── Sanitization ─────────────────────────────────────────────────────────

class TestSanitization:
    def test_script_tag_stripped(self, client):
        """The <script> TAG must be removed; bleach renders inner text as plaintext,
        which is harmless once the tag is gone."""
        c, _ = client
        _register(c)
        evil = '<p>Hi</p><script>alert("xss")</script>'
        rv = c.post("/api/community/post", json={"room": "general", "content": evil})
        assert rv.status_code == 201
        sanitized = rv.get_json()["sanitized_content"]
        assert "<script" not in sanitized.lower()
        assert "</script" not in sanitized.lower()
        # The <p>Hi</p> wrapper survives; the script body becomes inert text.
        assert "<p>Hi</p>" in sanitized

    def test_onclick_attr_stripped(self, client):
        c, _ = client
        _register(c)
        evil = '<a href="https://evil.com" onclick="steal()">click</a>'
        rv = c.post("/api/community/post", json={"room": "general", "content": evil})
        sanitized = rv.get_json()["sanitized_content"]
        assert "onclick" not in sanitized.lower()

    def test_javascript_url_blocked(self, client):
        c, _ = client
        _register(c)
        evil = '<a href="javascript:alert(1)">click</a>'
        rv = c.post("/api/community/post", json={"room": "general", "content": evil})
        sanitized = rv.get_json()["sanitized_content"]
        assert "javascript:" not in sanitized.lower()

    def test_safe_markup_preserved(self, client):
        c, _ = client
        _register(c)
        ok = "<p>Hello <b>world</b> with <em>emphasis</em></p>"
        rv = c.post("/api/community/post", json={"room": "general", "content": ok})
        sanitized = rv.get_json()["sanitized_content"]
        assert "<b>world</b>" in sanitized
        assert "<em>emphasis</em>" in sanitized

    def test_poll_returns_sanitized_only(self, client):
        """The /poll endpoint must NEVER return raw `content` field."""
        c, _ = client
        _register(c)
        evil = '<p>safe</p><script>bad()</script>'
        c.post("/api/community/post", json={"room": "general", "content": evil})

        rv = c.get("/api/community/poll?room=general&since=1970-01-01T00:00:00")
        assert rv.status_code == 200
        body = rv.get_json()
        assert body["count"] == 1
        msg = body["messages"][0]
        # Ensure key is absent — even leaking the field name is bad.
        assert "content" not in msg
        assert "<script" not in msg["sanitized_content"].lower()


# ── Validation ───────────────────────────────────────────────────────────

class TestValidation:
    def test_empty_content_rejected(self, client):
        c, _ = client
        _register(c)
        rv = c.post("/api/community/post", json={"room": "general", "content": "   "})
        assert rv.status_code == 400

    def test_content_too_long_rejected(self, client):
        c, _ = client
        _register(c)
        rv = c.post("/api/community/post", json={"room": "general", "content": "x" * 5000})
        assert rv.status_code == 400

    def test_invalid_room_name_rejected(self, client):
        c, _ = client
        _register(c)
        rv = c.post("/api/community/post", json={"room": "../etc/passwd", "content": "hi"})
        assert rv.status_code == 400

    def test_poll_invalid_room_rejected(self, client):
        c, _ = client
        rv = c.get("/api/community/poll?room=../bad")
        assert rv.status_code == 400


# ── Threading ────────────────────────────────────────────────────────────

class TestThreading:
    def test_replies_carry_parent_id(self, client):
        c, _ = client
        _register(c)
        first = c.post("/api/community/post", json={"room": "general", "content": "parent"}).get_json()
        reply = c.post(
            "/api/community/post",
            json={"room": "general", "content": "child", "parent_id": first["id"]},
        ).get_json()
        assert reply["parent_id"] == first["id"]
