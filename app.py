import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from functools import wraps

from flask import Flask, flash, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY") or os.urandom(32)
app.config["MAX_CONTENT_LENGTH"] = 2 * 1024 * 1024
DB_PATH = os.path.join(os.path.dirname(__file__), "hostel_reports.db")
ROLES = ["Student", "Technician", "Warden", "Director"]
CATEGORIES = [
    "Electrical",
    "Plumbing",
    "Building",
    "Furniture",
    "Internet / Wi-Fi",
    "Cleanliness",
    "Other",
]
REPORT_STATUSES = ["Pending", "Assigned", "Resolved"]


@contextmanager
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db():
    with get_db() as db:
        db.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                full_name TEXT NOT NULL,
                username TEXT NOT NULL UNIQUE,
                email TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL DEFAULT 'Student',
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS reports (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                room TEXT NOT NULL,
                category TEXT NOT NULL,
                issue TEXT NOT NULL,
                details TEXT NOT NULL,
                image_name TEXT,
                status TEXT NOT NULL DEFAULT 'Pending',
                created_at TEXT NOT NULL,
                FOREIGN KEY(user_id) REFERENCES users(id)
            );
            """
        )
        user_count = db.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        if user_count == 0:
            created_at = datetime.now().isoformat(timespec="minutes")
            demo_users = [
                (
                    "Demo Student",
                    "student",
                    "student@example.com",
                    generate_password_hash("student123"),
                    "Student",
                    created_at,
                ),
                (
                    "Demo Technician",
                    "technician",
                    "technician@example.com",
                    generate_password_hash("tech12345"),
                    "Technician",
                    created_at,
                ),
            ]
            db.executemany(
                """
                INSERT INTO users(full_name, username, email, password_hash, role, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                demo_users,
            )


def login_required(view):
    @wraps(view)
    def wrapped_view(*args, **kwargs):
        if not session.get("user_id"):
            flash("Please log in to continue.", "info")
            return redirect(url_for("login"))
        return view(*args, **kwargs)

    return wrapped_view


def visible_reports_query(db, user_id, role):
    query = """
        SELECT r.*, u.full_name, u.email
        FROM reports r
        JOIN users u ON u.id = r.user_id
    """
    if role == "Student":
        query += " WHERE r.user_id = ?"
        return db.execute(query + " ORDER BY r.created_at DESC", (user_id,))
    return db.execute(query + " ORDER BY r.created_at DESC")


@app.context_processor
def inject_globals():
    return {"current_user": session.get("full_name"), "current_role": session.get("role")}


@app.route("/")
def index():
    if session.get("user_id"):
        return redirect(url_for("dashboard"))
    return render_template("welcome.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        full_name = request.form.get("full_name", "").strip()
        username = request.form.get("username", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        role = request.form.get("role", "Student")

        if not all([full_name, username, email, password]):
            flash("Please complete all required fields.", "error")
        elif len(full_name) > 100 or len(username) > 50 or len(email) > 254:
            flash(
                "Please keep your name, username, and email within the allowed lengths.",
                "error",
            )
        elif len(username) < 3:
            flash("Username must be at least 3 characters long.", "error")
        elif len(password) < 8:
            flash("Password must be at least 8 characters long.", "error")
        elif role not in ROLES:
            flash("Please select a valid account role.", "error")
        else:
            try:
                with get_db() as db:
                    db.execute(
                        """
                        INSERT INTO users(full_name, username, email, password_hash, role, created_at)
                        VALUES (?, ?, ?, ?, ?, ?)
                        """,
                        (
                            full_name,
                            username,
                            email,
                            generate_password_hash(password),
                            role,
                            datetime.now().isoformat(timespec="minutes"),
                        ),
                    )
            except sqlite3.IntegrityError:
                flash("That username or email is already registered.", "error")
            else:
                flash("Your account has been created. Please log in.", "success")
                return redirect(url_for("login"))

    return render_template("register.html", roles=ROLES)


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        identity = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        with get_db() as db:
            user = db.execute(
                "SELECT * FROM users WHERE username = ? OR email = ?",
                (identity, identity.lower()),
            ).fetchone()

        if user is None or not check_password_hash(user["password_hash"], password):
            flash("Invalid username/email or password.", "error")
        else:
            session.clear()
            session["user_id"] = user["id"]
            session["full_name"] = user["full_name"]
            session["role"] = user["role"]
            return redirect(url_for("dashboard"))

    return render_template("login.html")


@app.route("/logout", methods=["POST"])
def logout():
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for("index"))


@app.route("/dashboard")
@login_required
def dashboard():
    user_id = session["user_id"]
    role = session.get("role")
    with get_db() as db:
        stats_query = """
            SELECT COUNT(*) AS total,
                   SUM(CASE WHEN status = 'Pending' THEN 1 ELSE 0 END) AS pending,
                   SUM(CASE WHEN status = 'Assigned' THEN 1 ELSE 0 END) AS assigned,
                   SUM(CASE WHEN status = 'Resolved' THEN 1 ELSE 0 END) AS resolved
            FROM reports
        """
        if role == "Student":
            stats_query += " WHERE user_id = ?"
            stats_row = db.execute(stats_query, (user_id,)).fetchone()
        else:
            stats_row = db.execute(stats_query).fetchone()
        reports = visible_reports_query(db, user_id, role).fetchmany(5)

    stats = {key: stats_row[key] or 0 for key in ("total", "pending", "assigned", "resolved")}
    return render_template("dashboard.html", stats=stats, reports=reports)


@app.route("/reports")
@login_required
def reports():
    selected_status = request.args.get("status", "").strip()
    if selected_status not in REPORT_STATUSES:
        selected_status = ""

    with get_db() as db:
        report_query = """
            SELECT r.*, u.full_name, u.email
            FROM reports r
            JOIN users u ON u.id = r.user_id
        """
        conditions = []
        params = []
        if session.get("role") == "Student":
            conditions.append("r.user_id = ?")
            params.append(session["user_id"])
        if selected_status:
            conditions.append("r.status = ?")
            params.append(selected_status)
        if conditions:
            report_query += " WHERE " + " AND ".join(conditions)
        report_query += " ORDER BY r.created_at DESC"
        report_rows = db.execute(report_query, params).fetchall()

    return render_template(
        "reports.html",
        reports=report_rows,
        selected_status=selected_status,
    )


@app.route("/report/new", methods=["GET", "POST"])
@login_required
def new_report():
    if session.get("role") != "Student":
        flash("Only student accounts can submit reports.", "error")
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        room = request.form.get("room", "").strip()
        category = request.form.get("category", "").strip()
        issue = request.form.get("issue", "").strip()
        details = request.form.get("details", "").strip()
        attachment = request.files.get("attachment")
        image_name = None
        if attachment and attachment.filename:
            image_name = secure_filename(attachment.filename) or None

        if not all([room, category, issue, details]):
            flash("Please complete all required report fields.", "error")
        elif len(room) > 50 or len(issue) > 120 or len(details) > 5000:
            flash(
                "Please keep the room, issue title, and details within the allowed lengths.",
                "error",
            )
        elif category not in CATEGORIES:
            flash("Please select a valid report category.", "error")
        else:
            with get_db() as db:
                db.execute(
                    """
                    INSERT INTO reports(user_id, room, category, issue, details, image_name, status, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, 'Pending', ?)
                    """,
                    (
                        session["user_id"],
                        room,
                        category,
                        issue,
                        details,
                        image_name,
                        datetime.now().isoformat(timespec="minutes"),
                    ),
                )
            flash("Your report has been submitted.", "success")
            return redirect(url_for("reports"))

    return render_template("report_form.html", categories=CATEGORIES)


@app.route("/report/<int:report_id>")
@login_required
def report_detail(report_id):
    with get_db() as db:
        report = db.execute(
            """
            SELECT r.*, u.full_name, u.email
            FROM reports r
            JOIN users u ON u.id = r.user_id
            WHERE r.id = ?
            """,
            (report_id,),
        ).fetchone()

    if report is None:
        flash("Report not found.", "error")
        return redirect(url_for("dashboard"))

    if session.get("role") == "Student" and report["user_id"] != session["user_id"]:
        flash("You are not authorized to view this report.", "error")
        return redirect(url_for("dashboard"))

    return render_template("report_detail.html", report=report)


@app.route("/report/<int:report_id>/update-status", methods=["POST"])
@login_required
def update_status(report_id):
    if session.get("role") not in ROLES or session.get("role") == "Student":
        flash("Unauthorized action.", "error")
        return redirect(url_for("dashboard"))

    new_status = request.form.get("status", "").strip()
    if new_status not in REPORT_STATUSES:
        flash("Invalid status update selection.", "error")
        return redirect(url_for("report_detail", report_id=report_id))

    with get_db() as db:
        result = db.execute(
            "UPDATE reports SET status = ? WHERE id = ?",
            (new_status, report_id),
        )
        if result.rowcount == 0:
            flash("Report not found.", "error")
            return redirect(url_for("reports"))

    flash("Report status updated successfully.", "success")
    return redirect(url_for("report_detail", report_id=report_id))


if __name__ == "__main__":
    init_db()
    app.run(debug=os.environ.get("FLASK_DEBUG") == "1")
