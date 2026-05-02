"""Tests for the small P0-1 endpoints: /api/chat and /api/quiz/email."""

from __future__ import annotations


class TestChat:
    def test_chat_returns_canned_reply(self, client):
        c, _ = client
        rv = c.post("/api/chat", json={"message": "Bonjour MANSA"})
        assert rv.status_code == 200
        body = rv.get_json()
        assert "reply" in body
        assert "MANSA" in body["reply"]

    def test_chat_rejects_empty(self, client):
        c, _ = client
        rv = c.post("/api/chat", json={"message": ""})
        assert rv.status_code == 400

    def test_chat_rejects_too_long(self, client):
        c, _ = client
        rv = c.post("/api/chat", json={"message": "x" * 5000})
        assert rv.status_code == 400


class TestQuizEmail:
    def test_quiz_email_accepted(self, client):
        c, _ = client
        rv = c.post(
            "/api/quiz/email",
            json={
                "email": "alice@example.com",
                "profil": "Modéré",
                "score": 24,
                "maxScore": 40,
                "date": "26/04/2026",
            },
        )
        assert rv.status_code == 202
        assert rv.get_json()["email"] == "alice@example.com"

    def test_quiz_email_rejects_invalid(self, client):
        c, _ = client
        rv = c.post("/api/quiz/email", json={"email": "not-an-email"})
        assert rv.status_code == 400
