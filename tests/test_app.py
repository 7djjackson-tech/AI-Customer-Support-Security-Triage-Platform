import io
import re
import sqlite3
from pathlib import Path

import pytest

from app import create_app, parse_csv


@pytest.fixture
def app(tmp_path):
    app = create_app(
        {
            "TESTING": True,
            "SECRET_KEY": "test-only-key",
            "DATABASE": str(tmp_path / "test.sqlite3"),
        }
    )
    from werkzeug.security import generate_password_hash

    with sqlite3.connect(app.config["DATABASE"]) as db:
        db.execute(
            "INSERT INTO staff(username,password_hash,role) VALUES (?,?,?)",
            ("admin", generate_password_hash("test-password-123"), "admin"),
        )
    return app


def authenticated(app):
    client = app.test_client()
    with client.session_transaction() as session:
        session["user_id"] = 1
    return client


def upload(client, content, **overrides):
    page = client.get("/").get_data(as_text=True)
    token = re.search(r'name="csrf_token" value="([^"]+)"', page)[1]
    data = {
        "csrf_token": token,
        "fictional": "yes",
        "file": (io.BytesIO(content), "tickets.csv"),
    }
    data.update(overrides)
    return client.post("/import", data=data, follow_redirects=True)


def count(app):
    with sqlite3.connect(app.config["DATABASE"]) as db:
        return db.execute("SELECT count(*) FROM tickets").fetchone()[0]


def test_sample_import_and_duplicate_idempotence(app):
    client = authenticated(app)
    sample = Path("data/development.csv").read_bytes()
    assert b"Imported 8 tickets" in upload(client, sample).data
    assert b"Imported 0 tickets. Skipped 8" in upload(client, sample).data
    assert count(app) == 8
    assert b"Someone changed my email" in client.get("/tickets/5").data
    assert client.get("/tickets/999").status_code == 404
    # A second app instance reads the same persistent database.
    other = create_app({"TESTING": True, "DATABASE": app.config["DATABASE"]})
    assert b"Missing parcel" in authenticated(other).get("/").data


@pytest.mark.parametrize(
    "content",
    [
        b"wrong,headers\na,b\n",
        b"external_id,customer_name,subject,message\n",
        b"external_id,customer_name,subject,message\na,A,S,M\nb,B,S,\n",
        b"external_id,customer_name,subject,message\na,A,S,M\na,B,S,M\n",
        b"external_id,customer_name,subject,message\na,A,S,M,extra\n",
        b"external_id,customer_name,subject,message\na,A,S\n",
        b'external_id,customer_name,subject,message\na,A,S,"unclosed\n',
        b"\xff",
        b"external_id,customer_name,subject,message\na,A,S,\x00\n",
    ],
)
def test_invalid_import_is_atomic(app, content):
    response = upload(authenticated(app), content)
    assert b"flash error" in response.data
    assert count(app) == 0


def test_csrf_and_fictional_confirmation(app):
    client = authenticated(app)
    assert client.post("/import").status_code == 400
    sample = Path("data/development.csv").read_bytes()
    assert b"Confirm the file" in upload(client, sample, fictional="no").data
    assert count(app) == 0


def test_safe_rendering_and_parameterized_queries(app):
    client = authenticated(app)
    content = b"external_id,customer_name,subject,message\nx,Demo,<script>alert(1)</script>,<img src=x onerror=alert(1)>\n"
    response = upload(client, content)
    assert b"<script>alert(1)</script>" not in response.data
    assert b"&lt;script&gt;" in response.data
    detail = client.get("/tickets/1")
    assert b"<img src=x" not in detail.data
    assert b"&lt;img" in detail.data
    assert (
        b"No matching tickets"
        in client.get("/", query_string={"q": "' OR 1=1 --"}).data
    )
    assert count(app) == 1


def test_csv_limits_and_utf8_bom():
    header = b"external_id,customer_name,subject,message\n"
    with pytest.raises(ValueError, match="200"):
        parse_csv(header + b"".join(f"{i},A,S,M\n".encode() for i in range(201)))
    with pytest.raises(ValueError, match="subject"):
        parse_csv(header + b"a,A," + b"x" * 161 + b",M\n")
    assert (
        parse_csv(b"\xef\xbb\xbf" + header + b'a,A,S,"one\ntwo"\n')[0]["message"]
        == "one\ntwo"
    )


def test_upload_limit_and_security_headers(app):
    client = authenticated(app)
    assert (
        client.post(
            "/import",
            data=b"x" * (1024 * 1024 + 1),
            content_type="application/octet-stream",
        ).status_code
        == 413
    )
    response = client.get("/")
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert "frame-ancestors 'none'" in response.headers["Content-Security-Policy"]
