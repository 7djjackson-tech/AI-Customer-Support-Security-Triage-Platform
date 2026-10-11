import http.cookiejar
import json
import os
from pathlib import Path
import re
import secrets
import socket
import subprocess
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request

root = Path.cwd()
with socket.socket() as listener:
    listener.bind(("127.0.0.1", 0))
    port = listener.getsockname()[1]
with tempfile.TemporaryDirectory(prefix="supportshield-smoke-") as directory:
    env = dict(
        os.environ,
        DATABASE_PATH=str(Path(directory) / "smoke.sqlite3"),
        SECRET_KEY=secrets.token_hex(32),
    )
    password = secrets.token_urlsafe(20)
    result = subprocess.run(
        [
            str(root / ".venv/bin/flask"),
            "--app",
            "app:create_app",
            "create-staff",
            "--username",
            "smoke-admin",
            "--role",
            "admin",
        ],
        input=password + "\n" + password + "\n",
        text=True,
        env=env,
        capture_output=True,
    )
    assert result.returncode == 0
    server = subprocess.Popen(
        [
            str(root / ".venv/bin/gunicorn"),
            "--bind",
            f"127.0.0.1:{port}",
            "--workers",
            "1",
            "--threads",
            "2",
            "--timeout",
            "60",
            "app:create_app()",
        ],
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        base = f"http://127.0.0.1:{port}"
        for _ in range(50):
            try:
                assert (
                    json.load(urllib.request.urlopen(base + "/health", timeout=2))[
                        "status"
                    ]
                    == "ok"
                )
                break
            except OSError:
                time.sleep(0.1)
        else:
            raise AssertionError("Server failed to start")
        opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar())
        )

        def get(path):
            return opener.open(base + path).read().decode()

        def token(path):
            return re.search(r'name="csrf_token" value="([^"]+)"', get(path))[1]

        def post(path, data):
            return (
                opener.open(
                    urllib.request.Request(
                        base + path, data=urllib.parse.urlencode(data).encode()
                    )
                )
                .read()
                .decode()
            )

        assert "No account required" in get("/demo")
        post(
            "/login",
            {
                "csrf_token": token("/login"),
                "username": "smoke-admin",
                "password": password,
            },
        )
        boundary = "supportshield-upload"
        csrf = token("/")
        body = (
            f'--{boundary}\r\nContent-Disposition: form-data; name="csrf_token"\r\n\r\n{csrf}\r\n'
            f'--{boundary}\r\nContent-Disposition: form-data; name="fictional"\r\n\r\nyes\r\n'
            f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="development.csv"\r\nContent-Type: text/csv\r\n\r\n'
            + (root / "data/development.csv").read_text()
            + f"\r\n--{boundary}--\r\n"
        )
        uploaded = (
            opener.open(
                urllib.request.Request(
                    base + "/import",
                    data=body.encode(),
                    headers={
                        "Content-Type": f"multipart/form-data; boundary={boundary}"
                    },
                )
            )
            .read()
            .decode()
        )
        assert "Imported 8 tickets." in uploaded
        post(
            "/staff",
            {
                "csrf_token": token("/staff"),
                "operation": "create",
                "username": "smoke-service",
                "password": password,
                "role": "customer_service",
            },
        )
        post(
            "/staff",
            {
                "csrf_token": token("/staff"),
                "operation": "create",
                "username": "smoke-security",
                "password": password,
                "role": "security",
            },
        )
        post("/logout", {"csrf_token": token("/")})
        post(
            "/login",
            {
                "csrf_token": token("/login"),
                "username": "smoke-service",
                "password": password,
            },
        )
        assert "Missing parcel" in get("/") and "Someone took over" not in get("/")
        try:
            get("/tickets/5")
            raise AssertionError("Role violation")
        except urllib.error.HTTPError as error:
            assert error.code == 403
        post(
            "/tickets/2/recommend", {"csrf_token": token("/tickets/2"), "mode": "demo"}
        )
        page = get("/tickets/2")
        version = re.search(r'name="recommendation_id" value="([^"]+)"', page)[1]
        post(
            "/tickets/2/review",
            {
                "csrf_token": token("/tickets/2"),
                "recommendation_id": version,
                "action": "approve",
                "status": "In progress",
                "note": "Reviewed fictional order policy.",
            },
        )
        assert "review_approve" in get("/tickets/2")
        post(
            "/tickets/2/status",
            {"csrf_token": token("/tickets/2"), "status": "Resolved"},
        )
        assert "Resolved" in get("/tickets/2")
        post("/logout", {"csrf_token": token("/")})
        post(
            "/login",
            {
                "csrf_token": token("/login"),
                "username": "smoke-security",
                "password": password,
            },
        )
        post(
            "/tickets/5/recommend", {"csrf_token": token("/tickets/5"), "mode": "demo"}
        )
        assert "Mandatory rule escalation" in get("/tickets/5")
        assert "87.5%" in get("/evaluation")
        # Restart the owned server with the same configuration and persistent database.
        server.terminate()
        server.wait(timeout=10)
        server = subprocess.Popen(
            [
                str(root / ".venv/bin/gunicorn"),
                "--bind",
                f"127.0.0.1:{port}",
                "--workers",
                "1",
                "--threads",
                "2",
                "app:create_app()",
            ],
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        for _ in range(50):
            try:
                page = get("/tickets/5")
                assert "recommendation_generated" in page
                break
            except OSError:
                time.sleep(0.1)
        else:
            raise AssertionError("Restart failed")
        print(
            "Live Gunicorn HTTP smoke passed: bootstrap, login, admin staff creation, CSRF import, role scopes/403, demo, approval/audit, status, security evidence, evaluation, and restart persistence."
        )
    finally:
        server.terminate()
        server.wait(timeout=10)
