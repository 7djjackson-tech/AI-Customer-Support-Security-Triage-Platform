"""Small staff-reviewed support and security triage application."""

import csv
import io
import os
import secrets
import sqlite3
import json
import click
from functools import wraps
from datetime import datetime, timedelta, timezone
from pathlib import Path

from flask import (
    Flask,
    abort,
    flash,
    g,
    redirect,
    render_template,
    request,
    url_for,
    session,
)
from flask_wtf.csrf import CSRFProtect
from werkzeug.security import generate_password_hash, check_password_hash
from triage import CATEGORIES, PRIORITIES, recommend, security_evidence
from werkzeug.exceptions import RequestEntityTooLarge

HEADERS = ["external_id", "customer_name", "subject", "message"]
LIMITS = {"external_id": 80, "customer_name": 100, "subject": 160, "message": 5000}


def parse_csv(raw):
    """Validate the complete batch before any database changes."""
    try:
        reader = csv.DictReader(io.StringIO(raw.decode("utf-8-sig")), strict=True)
        if reader.fieldnames != HEADERS:
            raise ValueError("Use exactly these CSV headers: " + ", ".join(HEADERS))
        rows, seen = [], set()
        for number, row in enumerate(reader, 2):
            if len(rows) >= 200:
                raise ValueError("Import at most 200 tickets per file.")
            if None in row or any(value is None for value in row.values()):
                raise ValueError(f"Row {number}: incorrect number of columns.")
            row = {key: value.strip() for key, value in row.items()}
            for key, limit in LIMITS.items():
                if not row[key] or len(row[key]) > limit or "\x00" in row[key]:
                    raise ValueError(
                        f"Row {number}: {key} must contain 1–{limit} characters without null bytes."
                    )
            if row["external_id"] in seen:
                raise ValueError(f"Row {number}: duplicate external_id in this file.")
            seen.add(row["external_id"])
            rows.append(row)
        if not rows:
            raise ValueError("The file must contain at least one ticket.")
        return rows
    except (UnicodeDecodeError, csv.Error) as exc:
        raise ValueError("Upload a valid UTF-8 CSV file.") from exc


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(g.app_database)
        g.db.row_factory = sqlite3.Row
    return g.db


def create_app(test_config=None):
    app = Flask(__name__)
    app.config.update(
        SECRET_KEY=os.environ.get("SECRET_KEY") or secrets.token_hex(32),
        DATABASE=os.environ.get(
            "DATABASE_PATH", str(Path(app.instance_path) / "supportshield.sqlite3")
        ),
        MAX_CONTENT_LENGTH=1024 * 1024,
        PERMANENT_SESSION_LIFETIME=timedelta(hours=8),
        SESSION_COOKIE_SECURE=os.environ.get("COOKIE_SECURE") == "true",
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
    )
    if test_config:
        app.config.update(test_config)
    if os.environ.get("PRODUCTION") == "true" and not os.environ.get("SECRET_KEY"):
        raise RuntimeError("Production requires a private stable SECRET_KEY")
    CSRFProtect(app)
    Path(app.config["DATABASE"]).parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(app.config["DATABASE"]) as db:
        db.execute(
            """CREATE TABLE IF NOT EXISTS tickets (
            id INTEGER PRIMARY KEY, external_id TEXT NOT NULL UNIQUE,
            customer_name TEXT NOT NULL, subject TEXT NOT NULL, message TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'New',
            created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%d %H:%M:%S', 'now'))
        )"""
        )

    with sqlite3.connect(app.config["DATABASE"]) as db:
        existing = {row[1] for row in db.execute("PRAGMA table_info(tickets)")}
        for column, definition in {
            "security": "INTEGER NOT NULL DEFAULT 0",
            "category": "TEXT NOT NULL DEFAULT 'Unclassified'",
            "priority": "TEXT NOT NULL DEFAULT 'Normal'",
            "routing": "TEXT NOT NULL DEFAULT 'customer_service'",
            "recommendation": "TEXT",
            "source": "TEXT",
            "review_state": "TEXT NOT NULL DEFAULT 'Pending'",
            "approved_draft": "TEXT",
            "recommendation_id": "INTEGER",
        }.items():
            if column not in existing:
                db.execute(f"ALTER TABLE tickets ADD COLUMN {column} {definition}")
        db.execute(
            "CREATE TABLE IF NOT EXISTS staff (id INTEGER PRIMARY KEY, username TEXT UNIQUE NOT NULL, password_hash TEXT NOT NULL, role TEXT NOT NULL CHECK(role IN ('customer_service','security','admin')))"
        )
        db.execute(
            "CREATE TABLE IF NOT EXISTS recommendations (id INTEGER PRIMARY KEY, ticket_id INTEGER NOT NULL, actor_id INTEGER NOT NULL, source TEXT NOT NULL, output TEXT NOT NULL, created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%d %H:%M:%S','now')))"
        )
        db.execute(
            "CREATE TABLE IF NOT EXISTS audit (id INTEGER PRIMARY KEY, ticket_id INTEGER, actor_id INTEGER NOT NULL, action TEXT NOT NULL, detail TEXT NOT NULL, created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%d %H:%M:%S','now')))"
        )
        db.execute(
            "CREATE TABLE IF NOT EXISTS login_attempts (username TEXT PRIMARY KEY, failures INTEGER NOT NULL, blocked_until REAL NOT NULL)"
        )
        # Upgrade previously imported tickets conservatively before access checks.
        for row in db.execute(
            "SELECT id, subject, message FROM tickets WHERE security = 0"
        ).fetchall():
            if recommend(row[1] + "\n" + row[2])[0]["routing"] == "security":
                db.execute(
                    "UPDATE tickets SET security=1, routing='security', category=? WHERE id=?",
                    (CATEGORIES[4], row[0]),
                )

    def protected(role=None):
        def decorator(fn):
            @wraps(fn)
            def wrapped(*args, **kwargs):
                if not g.user:
                    return redirect(url_for("login"))
                if role and g.user["role"] not in [role, "admin"]:
                    abort(403)
                return fn(*args, **kwargs)

            return wrapped

        return decorator

    def allowed_ticket(ticket_id):
        ticket = (
            get_db()
            .execute("SELECT * FROM tickets WHERE id=?", (ticket_id,))
            .fetchone()
        )
        if not ticket:
            abort(404)
        if g.user["role"] != "admin" and bool(ticket["security"]) != (
            g.user["role"] == "security"
        ):
            abort(403)
        return ticket

    def audit(db, ticket_id, action, detail=""):
        db.execute(
            "INSERT INTO audit(ticket_id, actor_id, action, detail) VALUES (?,?,?,?)",
            (ticket_id, g.user["id"], action, detail),
        )

    @app.cli.command("create-staff")
    @click.option("--username", prompt=True)
    @click.option(
        "--role",
        type=click.Choice(["customer_service", "security", "admin"]),
        default="admin",
    )
    @click.option("--password", prompt=True, hide_input=True, confirmation_prompt=True)
    def create_staff(username, role, password):
        if not 1 <= len(username.strip()) <= 80 or not 12 <= len(password) <= 1024:
            raise click.ClickException(
                "Username must be 1–80 characters and password at least 12 characters."
            )
        with sqlite3.connect(app.config["DATABASE"]) as db:
            try:
                db.execute(
                    "INSERT INTO staff(username,password_hash,role) VALUES (?,?,?)",
                    (username.strip(), generate_password_hash(password), role),
                )
            except sqlite3.IntegrityError:
                raise click.ClickException("Username already exists.")
        click.echo("Staff account created.")

    @app.get("/evaluation")
    @protected()
    def evaluation():
        result = json.loads(
            (Path(app.root_path) / "docs/evaluation-demo.json").read_text(
                encoding="utf-8"
            )
        )
        return render_template("evaluation.html", result=result)

    @app.get("/demo")
    def public_demo():
        # Only repository-supplied fictional examples: no public access to SQLite tickets.
        examples = parse_csv(
            (Path(app.root_path) / "data/development.csv").read_bytes()
        )
        selected = request.args.get("example", examples[0]["external_id"])
        example = next(
            (item for item in examples if item["external_id"] == selected), None
        )
        if example is None:
            abort(404)
        value, source, _ = recommend(
            example["subject"] + "\n" + example["message"], "demo"
        )
        return render_template(
            "demo.html",
            examples=examples,
            example=example,
            recommendation=value,
            source=source,
        )

    @app.get("/health")
    def health():
        get_db().execute("SELECT 1").fetchone()
        return {"status": "ok"}

    @app.route("/login", methods=["GET", "POST"])
    def login():
        if request.method == "POST":
            username = request.form.get("username", "").strip()[:80]
            password = request.form.get("password", "")[:1024]
            db = get_db()
            user = db.execute(
                "SELECT * FROM staff WHERE username=?", (username,)
            ).fetchone()
            attempt = db.execute(
                "SELECT * FROM login_attempts WHERE username=?", (username,)
            ).fetchone()
            now = datetime.now(timezone.utc).timestamp()
            if attempt and attempt["blocked_until"] > now:
                flash("Too many attempts. Try again in 15 minutes.", "error")
            elif (
                check_password_hash(
                    user["password_hash"] if user else app.config["DUMMY_HASH"],
                    password,
                )
                and user is not None
            ):
                session.clear()
                session["user_id"] = user["id"]
                session.permanent = True
                with db:
                    db.execute(
                        "DELETE FROM login_attempts WHERE username=?", (username,)
                    )
                return redirect(url_for("dashboard"))
            else:
                failures = (
                    attempt["failures"]
                    if attempt and attempt["blocked_until"] == 0
                    else 0
                ) + 1
                with db:
                    db.execute(
                        "INSERT INTO login_attempts VALUES (?,?,?) ON CONFLICT(username) DO UPDATE SET failures=excluded.failures, blocked_until=excluded.blocked_until",
                        (username, failures, now + 900 if failures >= 5 else 0),
                    )
                flash("Invalid username or password.", "error")
        return render_template("login.html")

    @app.post("/logout")
    @protected()
    def logout():
        session.clear()
        return redirect(url_for("login"))

    @app.route("/staff", methods=["GET", "POST"])
    @protected("admin")
    def staff():
        db = get_db()
        if request.method == "POST":
            db.execute("BEGIN IMMEDIATE")
            if request.form.get("operation") == "create":
                username = request.form.get("username", "").strip()
                password = request.form.get("password", "")
                role = request.form.get("role")
                if (
                    not 1 <= len(username) <= 80
                    or not 12 <= len(password) <= 1024
                    or role not in ["admin", "security", "customer_service"]
                ):
                    abort(400)
                try:
                    with db:
                        db.execute(
                            "INSERT INTO staff(username,password_hash,role) VALUES (?,?,?)",
                            (username, generate_password_hash(password), role),
                        )
                        audit(db, None, "staff_created", "role=" + role)
                except sqlite3.IntegrityError:
                    flash("Username already exists.", "error")
            else:
                target = db.execute(
                    "SELECT * FROM staff WHERE id=?", (request.form.get("staff_id"),)
                ).fetchone()
                role = request.form.get("role")
                if not target or role not in ["admin", "security", "customer_service"]:
                    abort(400)
                if (
                    target["role"] == "admin"
                    and role != "admin"
                    and db.execute(
                        "SELECT count(*) FROM staff WHERE role='admin'"
                    ).fetchone()[0]
                    <= 1
                ):
                    flash("Keep at least one administrator.", "error")
                else:
                    with db:
                        db.execute(
                            "UPDATE staff SET role=? WHERE id=?", (role, target["id"])
                        )
                        audit(
                            db,
                            None,
                            "role_changed",
                            f"staff_id={target['id']};role={role}",
                        )
            return redirect(url_for("staff"))
        return render_template(
            "staff.html",
            staff=db.execute(
                "SELECT id,username,role FROM staff ORDER BY id"
            ).fetchall(),
        )

    @app.post("/tickets/<int:ticket_id>/recommend")
    @protected()
    def generate(ticket_id):
        ticket = allowed_ticket(ticket_id)
        if ticket["review_state"] != "Pending":
            flash(
                "Reviewed recommendations are locked; the audit history is retained.",
                "error",
            )
            return redirect(url_for("ticket_detail", ticket_id=ticket_id))
        mode = request.form.get("mode", "demo")
        if mode not in ["demo", "live"]:
            abort(400)
        if mode == "live" and request.form.get("consent") != "yes":
            abort(400)
        value, source, error = recommend(
            ticket["subject"] + "\n" + ticket["message"], mode
        )
        secure = bool(ticket["security"]) or value["routing"] == "security"
        with get_db() as db:
            db.execute("BEGIN IMMEDIATE")
            g.user = db.execute(
                "SELECT id,username,role FROM staff WHERE id=?",
                (session.get("user_id"),),
            ).fetchone()
            current = allowed_ticket(ticket_id)
            if current["review_state"] != "Pending":
                abort(409)
            secure = bool(current["security"]) or secure
            stored = db.execute(
                "INSERT INTO recommendations(ticket_id,actor_id,source,output) VALUES (?,?,?,?)",
                (ticket_id, g.user["id"], source, json.dumps(value)),
            )
            db.execute(
                "UPDATE tickets SET recommendation=?,source=?,security=?,routing=?,recommendation_id=? WHERE id=?",
                (
                    json.dumps(value),
                    source,
                    int(secure),
                    "security" if secure else "customer_service",
                    stored.lastrowid,
                    ticket_id,
                ),
            )
            audit(db, ticket_id, "recommendation_generated", "source=" + source)
        if error:
            flash(error, "error")
        if secure and g.user["role"] == "customer_service":
            flash("Ticket routed to security. Your access to it has ended.", "success")
            return redirect(url_for("dashboard"))
        return redirect(url_for("ticket_detail", ticket_id=ticket_id))

    @app.post("/tickets/<int:ticket_id>/review")
    @protected()
    def review(ticket_id):
        get_db().execute("BEGIN IMMEDIATE")
        ticket = allowed_ticket(ticket_id)
        action = request.form.get("action")
        status = request.form.get("status")
        if action not in ["approve", "edit", "reject"] or status not in [
            "New",
            "In progress",
            "Resolved",
        ]:
            abort(400)
        category = request.form.get("category")
        priority = request.form.get("priority")
        draft = request.form.get("draft", "").strip()
        note = request.form.get("note", "").strip()
        if not 1 <= len(note) <= 500 or len(draft) > 2000:
            abort(400)
        if ticket["review_state"] != "Pending" or request.form.get(
            "recommendation_id", "0"
        ) != str(ticket["recommendation_id"] or 0):
            abort(409)
        if action == "approve":
            if not ticket["recommendation"]:
                abort(400)
            saved = json.loads(ticket["recommendation"])
            category, priority, draft = (
                saved["category"],
                saved["priority"],
                saved["draft"],
            )
        if action != "reject" and (
            category not in CATEGORIES or priority not in PRIORITIES or not draft
        ):
            abort(400)
        secure = bool(ticket["security"]) or category == CATEGORIES[4]
        if secure and action != "reject":
            category = CATEGORIES[
                4
            ]  # reviewers cannot silently downgrade a security handoff
        with get_db() as db:
            db.execute(
                "UPDATE tickets SET category=?,priority=?,security=?,routing=?,review_state=?,approved_draft=?,status=? WHERE id=?",
                (
                    ticket["category"] if action == "reject" else category,
                    ticket["priority"] if action == "reject" else priority,
                    int(secure),
                    "security" if secure else "customer_service",
                    action,
                    None if action == "reject" else draft,
                    status,
                    ticket_id,
                ),
            )
            audit(db, ticket_id, "review_" + action, note)
        if secure and g.user["role"] == "customer_service":
            return redirect(url_for("dashboard"))
        return redirect(url_for("ticket_detail", ticket_id=ticket_id))

    @app.post("/tickets/<int:ticket_id>/status")
    @protected()
    def update_status(ticket_id):
        get_db().execute("BEGIN IMMEDIATE")
        allowed_ticket(ticket_id)
        status = request.form.get("status")
        if status not in ["New", "In progress", "Resolved"]:
            abort(400)
        with get_db() as db:
            db.execute("UPDATE tickets SET status=? WHERE id=?", (status, ticket_id))
            audit(db, ticket_id, "status_changed", status)
        return redirect(url_for("ticket_detail", ticket_id=ticket_id))

    app.config["DUMMY_HASH"] = generate_password_hash(secrets.token_hex(16))

    @app.before_request
    def database_path():
        g.app_database = app.config["DATABASE"]
        g.user = (
            get_db()
            .execute(
                "SELECT id,username,role FROM staff WHERE id=?",
                (session.get("user_id"),),
            )
            .fetchone()
        )

    @app.teardown_appcontext
    def close_db(error=None):
        db = g.pop("db", None)
        if db:
            db.close()

    @app.after_request
    def security_headers(response):
        response.headers["Cache-Control"] = "no-store"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; style-src 'self'; form-action 'self'; frame-ancestors 'none'"
        )
        return response

    @app.get("/")
    def dashboard():
        if not g.user:
            return redirect(url_for("public_demo"))
        query = request.args.get("q", "").strip()[:160]
        # instr gives literal substring search, including SQL wildcard characters.
        scope = (
            "1=1"
            if g.user["role"] == "admin"
            else ("security=1" if g.user["role"] == "security" else "security=0")
        )
        tickets = (
            get_db()
            .execute(
                f"""SELECT * FROM tickets
            WHERE {scope} AND instr(lower(subject || ' ' || customer_name || ' ' || external_id), lower(?)) > 0
            ORDER BY id DESC""",
                (query,),
            )
            .fetchall()
        )
        total = (
            get_db()
            .execute("SELECT count(*) FROM tickets WHERE " + scope)
            .fetchone()[0]
        )
        return render_template(
            "dashboard.html", tickets=tickets, total=total, query=query
        )

    @app.post("/import")
    @protected("admin")
    def import_tickets():
        upload = request.files.get("file")
        if request.form.get("fictional") != "yes":
            flash("Confirm the file contains fictional data only.", "error")
            return redirect(url_for("dashboard"))
        if not upload or not upload.filename.lower().endswith(".csv"):
            flash("Choose a CSV file.", "error")
            return redirect(url_for("dashboard"))
        try:
            rows = parse_csv(upload.read())
            db = get_db()
            inserted = 0
            with db:
                for row in rows:
                    handoff = recommend(row["subject"] + "\n" + row["message"])[0][
                        "routing"
                    ]
                    cursor = db.execute(
                        """INSERT INTO tickets
                        (external_id, customer_name, subject, message, security, routing) VALUES (?, ?, ?, ?, ?, ?)
                        ON CONFLICT(external_id) DO NOTHING""",
                        tuple(row[key] for key in HEADERS)
                        + (int(handoff == "security"), handoff),
                    )
                    if cursor.rowcount:
                        audit(db, cursor.lastrowid, "imported", "fictional_csv")
                    inserted += cursor.rowcount
            flash(
                f"Imported {inserted} tickets. Skipped {len(rows) - inserted} existing IDs.",
                "success",
            )
        except ValueError as exc:
            flash(str(exc), "error")
        return redirect(url_for("dashboard"))

    @app.get("/tickets/<int:ticket_id>")
    @protected()
    def ticket_detail(ticket_id):
        ticket = allowed_ticket(ticket_id)
        logs = (
            get_db()
            .execute(
                "SELECT audit.*, staff.username FROM audit JOIN staff ON staff.id=actor_id WHERE ticket_id=? ORDER BY audit.id DESC",
                (ticket_id,),
            )
            .fetchall()
        )
        return render_template(
            "ticket.html",
            ticket=ticket,
            recommendation=(
                json.loads(ticket["recommendation"])
                if ticket["recommendation"]
                else None
            ),
            logs=logs,
            history=get_db()
            .execute(
                "SELECT * FROM recommendations WHERE ticket_id=? ORDER BY id DESC",
                (ticket_id,),
            )
            .fetchall(),
            categories=CATEGORIES,
            priorities=PRIORITIES,
            live_enabled=os.environ.get("LIVE_AI_ENABLED") == "true",
        )

    @app.errorhandler(RequestEntityTooLarge)
    def too_large(error):
        return (
            render_template(
                "error.html", message="Upload too large. Maximum request size is 1 MB."
            ),
            413,
        )

    @app.errorhandler(400)
    def bad_request(error):
        return (
            render_template(
                "error.html",
                message="Invalid or expired form. Return to the dashboard and try again.",
            ),
            400,
        )

    @app.errorhandler(403)
    def forbidden(error):
        return (
            render_template(
                "error.html", message="Your staff role cannot access this resource."
            ),
            403,
        )

    @app.errorhandler(409)
    def conflict(error):
        return (
            render_template(
                "error.html", message="This recommendation has already been reviewed."
            ),
            409,
        )

    @app.errorhandler(404)
    def missing(error):
        return render_template("error.html", message="Ticket or page not found."), 404

    return app
