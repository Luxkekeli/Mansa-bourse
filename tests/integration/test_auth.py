"""End-to-end tests for the P0-2 auth flow.

Covers:
- register → me → logout → me (401)
- login flow + wrong password
- duplicate registration
- email format / weak password validation
- forgot → reset cycle (consumes token, second use rejected)
- email verification token
"""

from __future__ import annotations


def _register(c, email="alice@example.com", pwd="strongpass123", prenom="Alice"):
    return c.post(
        "/api/auth/register",
        json={"email": email, "password": pwd, "prenom": prenom, "profil": "debutant"},
    )


def _login(c, email="alice@example.com", pwd="strongpass123"):
    return c.post("/api/auth/login", json={"email": email, "password": pwd})


# ── Register ─────────────────────────────────────────────────────────────

class TestRegister:
    def test_register_success(self, client):
        c, _ = client
        rv = _register(c)
        assert rv.status_code == 201
        body = rv.get_json()
        assert body["user"]["email"] == "alice@example.com"
        assert body["user"]["plan"] == "free"
        assert body["user"]["email_verified"] == 0

    def test_register_rejects_duplicate(self, client):
        c, _ = client
        assert _register(c).status_code == 201
        rv = _register(c)
        assert rv.status_code == 409

    def test_register_rejects_invalid_email(self, client):
        c, _ = client
        rv = c.post(
            "/api/auth/register",
            json={"email": "not-an-email", "password": "strongpass123", "prenom": "X"},
        )
        assert rv.status_code == 400

    def test_register_rejects_short_password(self, client):
        c, _ = client
        rv = c.post(
            "/api/auth/register",
            json={"email": "x@y.com", "password": "short", "prenom": "X"},
        )
        assert rv.status_code == 400

    def test_register_rejects_missing_prenom(self, client):
        c, _ = client
        rv = c.post(
            "/api/auth/register",
            json={"email": "bob@example.com", "password": "strongpass123"},
        )
        assert rv.status_code == 400


# ── Login + session ──────────────────────────────────────────────────────

class TestLoginSession:
    def test_register_opens_session(self, client):
        c, _ = client
        _register(c)
        rv = c.get("/api/auth/me")
        assert rv.status_code == 200
        assert rv.get_json()["user"]["email"] == "alice@example.com"

    def test_logout_drops_session(self, client):
        c, _ = client
        _register(c)
        c.post("/api/auth/logout")
        rv = c.get("/api/auth/me")
        assert rv.status_code == 401

    def test_login_after_logout(self, client):
        c, _ = client
        _register(c)
        c.post("/api/auth/logout")
        rv = _login(c)
        assert rv.status_code == 200

    def test_login_wrong_password_fails(self, client):
        c, _ = client
        _register(c)
        c.post("/api/auth/logout")
        rv = _login(c, pwd="wrongpassword99")
        assert rv.status_code == 401

    def test_login_unknown_user_fails(self, client):
        c, _ = client
        rv = _login(c, email="ghost@nope.com")
        assert rv.status_code == 401


# ── Password reset ───────────────────────────────────────────────────────

class TestPasswordReset:
    def test_forgot_always_returns_200(self, client):
        """User-enumeration protection: same response whether user exists or not."""
        c, _ = client
        rv1 = c.post("/api/auth/forgot", json={"email": "ghost@nope.com"})
        rv2 = c.post("/api/auth/forgot", json={"email": "alice@example.com"})
        assert rv1.status_code == 200
        assert rv2.status_code == 200

    def test_forgot_then_reset_then_login(self, client):
        c, mod = client
        _register(c)
        c.post("/api/auth/logout")
        c.post("/api/auth/forgot", json={"email": "alice@example.com"})

        # Pull the token straight from the DB (in real life: from email).
        with mod.app.app_context():
            db = mod.get_db()
            row = db.execute(
                "SELECT token FROM password_resets WHERE consumed_at IS NULL"
            ).fetchone()
            assert row, "expected a reset token to be issued"
            token = row["token"]

        rv = c.post("/api/auth/reset", json={"token": token, "password": "newpassword456"})
        assert rv.status_code == 200

        # Old password should fail; new one should work.
        c.post("/api/auth/logout")
        assert _login(c, pwd="strongpass123").status_code == 401
        assert _login(c, pwd="newpassword456").status_code == 200

    def test_reset_token_is_one_shot(self, client):
        c, mod = client
        _register(c)
        c.post("/api/auth/forgot", json={"email": "alice@example.com"})
        with mod.app.app_context():
            row = mod.get_db().execute("SELECT token FROM password_resets").fetchone()
            token = row["token"]
        assert c.post("/api/auth/reset", json={"token": token, "password": "newpw99999"}).status_code == 200
        # Second use is rejected.
        rv = c.post("/api/auth/reset", json={"token": token, "password": "anotherpw9"})
        assert rv.status_code == 400

    def test_reset_rejects_unknown_token(self, client):
        c, _ = client
        rv = c.post(
            "/api/auth/reset",
            json={"token": "totally-bogus-token", "password": "newpw99999"},
        )
        assert rv.status_code == 400


# ── Email verification ───────────────────────────────────────────────────

class TestEmailVerification:
    def test_register_starts_with_unverified_email(self, client):
        c, _ = client
        rv = _register(c)
        assert rv.get_json()["user"]["email_verified"] == 0

    def test_verify_email_with_valid_token(self, client):
        c, mod = client
        _register(c)
        with mod.app.app_context():
            row = mod.get_db().execute(
                "SELECT verification_token FROM users WHERE email = 'alice@example.com'"
            ).fetchone()
            token = row["verification_token"]
        rv = c.get(f"/api/auth/verify?token={token}")
        assert rv.status_code == 200
        # me() now reports verified=1.
        me = c.get("/api/auth/me").get_json()
        assert me["user"]["email_verified"] == 1

    def test_verify_rejects_bogus_token(self, client):
        c, _ = client
        _register(c)
        rv = c.get("/api/auth/verify?token=xxx")
        assert rv.status_code == 400


# ── Password hashing properties ──────────────────────────────────────────

class TestPasswordHashing:
    def test_hashes_are_argon2id(self, client):
        from auth import _hash_password

        h = _hash_password("hello-world-123")
        assert h.startswith("$argon2id$"), f"expected argon2id prefix, got {h[:20]}"
        # Hashes are non-deterministic.
        assert h != _hash_password("hello-world-123")

    def test_verify_password_round_trip(self, client):
        from auth import _hash_password, _verify_password

        h = _hash_password("correct horse battery staple")
        assert _verify_password(h, "correct horse battery staple") is True
        assert _verify_password(h, "wrong password") is False
