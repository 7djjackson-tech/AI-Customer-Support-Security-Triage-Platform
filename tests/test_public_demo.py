import sqlite3

import pytest

from app import create_app


@pytest.fixture
def app(tmp_path):
    return create_app(
        {
            "TESTING": True,
            "SECRET_KEY": "test-only",
            "DATABASE": str(tmp_path / "public.sqlite3"),
        }
    )


def test_public_entry_and_all_fictional_scenarios(app):
    client = app.test_client()
    assert client.get("/").location.endswith("/demo")
    for number in range(1, 9):
        response = client.get("/demo", query_string={"example": f"DEV-{number:03}"})
        assert response.status_code == 200
        assert b"deterministic rules" in response.data
        assert b"No account required" in response.data
    assert b"Mandatory rule escalation" in client.get("/demo?example=DEV-005").data
    assert client.get("/demo?example=private-ticket").status_code == 404


def test_public_demo_cannot_access_or_mutate_staff_data(app):
    with sqlite3.connect(app.config["DATABASE"]) as db:
        db.execute(
            "INSERT INTO tickets(external_id,customer_name,subject,message) VALUES ('private','Private','PRIVATE-STAFF-TICKET','PRIVATE-BODY')"
        )
    client = app.test_client()
    assert b"PRIVATE-" not in client.get("/demo").data
    assert client.get("/tickets/1").status_code == 302
    assert client.get("/staff").status_code == 302
    assert client.post("/demo").status_code in (400, 405)
    with sqlite3.connect(app.config["DATABASE"]) as db:
        assert db.execute("SELECT count(*) FROM tickets").fetchone()[0] == 1
        assert db.execute("SELECT count(*) FROM recommendations").fetchone()[0] == 0
        assert db.execute("SELECT count(*) FROM audit").fetchone()[0] == 0


def test_public_demo_never_calls_live_ai(app, monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("Public demo must not use the provider")

    monkeypatch.setenv("LIVE_AI_ENABLED", "true")
    monkeypatch.setattr("triage.live", forbidden)
    assert app.test_client().get("/demo?example=DEV-005").status_code == 200


def test_production_requires_signing_key(monkeypatch, tmp_path):
    monkeypatch.setenv("PRODUCTION", "true")
    monkeypatch.delenv("SECRET_KEY", raising=False)
    with pytest.raises(RuntimeError, match="SECRET_KEY"):
        create_app({"DATABASE": str(tmp_path / "production.sqlite3")})
