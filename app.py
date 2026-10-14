from flask import Flask, render_template, request, redirect, url_for, session, flash
import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
from datetime import datetime
import os

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "change-this-secret-key-before-deployment")
DB_PATH = os.path.join(os.path.dirname(__file__), "hostel_reports.db")
ROLES = ["Student", "Technician", "Warden", "Director"]
CATEGORIES = ["Electrical", "Plumbing", "Building", "Furniture", "Internet / Wi-Fi", "Cleanliness", "Other"]

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

def init_db():
    with get_db() as db:
        db.executescript("""
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
        """)
        # Demo accounts are created only when the database is first empty.
        count = db.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        if count == 0:
            db.execute("""INSERT INTO users(full_name, username, email, password_hash, role, created_at)
                          VALUES (?, ?, ?, ?, ?, ?)""",
                       ("Demo Student", "student", "student@example.com",
                        generate_password_hash("student123"), "Student", datetime.now().isoformat(timespec="minutes")))
            db.execute("""INSERT INTO users(full_name, username, email, password_hash, role, created_at)
                          VALUES (?, ?, ?, ?, ?, ?)""",
                       ("Demo Technician", "technician", "technician@example.com",
                        generate_password_hash("tech12345"), "Technician", datetime.now().isoformat(timespec="minutes")))

def login_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not session.get("user_id"):
            flash("Please log in to continue.", "info")
            return redirect(url_for("login"))
        return fn(*args, **kwargs)
    return wrapper

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
        elif len(password) < 8:
            flash("Password must contain at least 8 characters.", "error")
        elif role not in ROLES:
            flash("Please choose a valid role.", "error")
        else:
            try:
                with get_db() as db:
                    db.execute("""INSERT INTO users(full_name, username, email, password_hash, role, created_at)
                                  VALUES (?, ?, ?, ?, ?, ?)""",
                               (full_name, username, email, generate_password_hash(password), role,
                                datetime.now().isoformat(timespec="minutes")))
                flash("Account created. You can now log in.", "success")
                return redirect(url_for("login"))
            except sqlite3.IntegrityError:
                flash("That username or email is already registered.", "error")
    return render_template("register.html", roles=ROLES)

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        identity = request.form.get("identity", "").strip()
        password = request.form.get("password", "")
        with get_db() as db:
            user = db.execute("SELECT * FROM users WHERE username = ? OR email = ?", (identity, identity.lower())).fetchone()
        if user and check_password_hash(user["password_hash"], password):
            session.clear()
            session["user_id"] = user["id"]
            session["full_name"] = user["full_name"]
            session["username"] = user["username"]
            session["role"] = user["role"]
            flash("Welcome back, " + user["full_name"] + "!", "success")
            return redirect(url_for("dashboard"))
        flash("Incorrect username/email or password. Please try again.", "error")
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for("index"))

@app.route("/dashboard")
@login_required
def dashboard():
    with get_db() as db:
        stats = {
            "total": db.execute("SELECT COUNT(*) FROM reports").fetchone()[0],
            "pending": db.execute("SELECT COUNT(*) FROM reports WHERE status='Pending'").fetchone()[0],
            "assigned": db.execute("SELECT COUNT(*) FROM reports WHERE status='Assigned'").fetchone()[0],
            "resolved": db.execute("SELECT COUNT(*) FROM reports WHERE status='Resolved'").fetchone()[0],
        }
        if session.get("role") == "Student":
            reports = db.execute("""SELECT r.*, u.full_name FROM reports r JOIN users u ON u.id=r.user_id
                                    WHERE r.user_id=? ORDER BY r.id DESC LIMIT 8""", (session["user_id"],)).fetchall()
        else:
            reports = db.execute("""SELECT r.*, u.full_name FROM reports r JOIN users u ON u.id=r.user_id
                                    ORDER BY r.id DESC LIMIT 8""").fetchall()
    return render_template("dashboard.html", stats=stats, reports=reports)

@app.route("/report/new", methods=["GET", "POST"])
@login_required
def new_report():
    if request.method == "POST":
        room = request.form.get("room", "").strip()
        category = request.form.get("category", "")
        issue = request.form.get("issue", "").strip()
        details = request.form.get("details", "").strip()
        image = request.files.get("attachment")
        image_name = image.filename if image and image.filename else None
        if not all([room, category, issue, details]):
            flash("Please complete every field except the attachment.", "error")
        elif category not in CATEGORIES:
            flash("Please choose a valid category.", "error")
        else:
            with get_db() as db:
                db.execute("""INSERT INTO reports(user_id, room, category, issue, details, image_name, status, created_at)
                              VALUES (?, ?, ?, ?, ?, ?, 'Pending', ?)""",
                           (session["user_id"], room, category, issue, details, image_name,
                            datetime.now().isoformat(timespec="minutes")))
            flash("Report submitted successfully. You can track its status below.", "success")
            return redirect(url_for("dashboard"))
    return render_template("report_form.html", categories=CATEGORIES)

@app.route("/reports")
@login_required
def reports():
    status = request.args.get("status", "").strip()
    query = """SELECT r.*, u.full_name FROM reports r JOIN users u ON u.id=r.user_id"""
    params = []
    clauses = []
    if session.get("role") == "Student":
        clauses.append("r.user_id=?")
        params.append(session["user_id"])
    if status in ["Pending", "Assigned", "Resolved"]:
        clauses.append("r.status=?")
        params.append(status)
    if clauses:
        query += " WHERE " + " AND ".join(clauses)
    query += " ORDER BY r.id DESC"
    with get_db() as db:
        rows = db.execute(query, params).fetchall()
    return render_template("reports.html", reports=rows, selected_status=status)

@app.route("/reports/<int:report_id>/status", methods=["POST"])
@login_required
def update_status(report_id):
    if session.get("role") == "Student":
        flash("Only staff members can update report status.", "error")
        return redirect(url_for("reports"))
    status = request.form.get("status")
    if status not in ["Pending", "Assigned", "Resolved"]:
        flash("Invalid status.", "error")
        return redirect(url_for("reports"))
    with get_db() as db:
        row = db.execute("SELECT id FROM reports WHERE id=?", (report_id,)).fetchone()
        if not row:
            flash("Report not found.", "error")
        else:
            db.execute("UPDATE reports SET status=? WHERE id=?", (status, report_id))
            flash("Report status updated.", "success")
    return redirect(request.referrer or url_for("reports"))

@app.route("/reports/<int:report_id>")
@login_required
def report_detail(report_id):
    with get_db() as db:
        report = db.execute("""SELECT r.*, u.full_name, u.email FROM reports r
                               JOIN users u ON u.id=r.user_id WHERE r.id=?""", (report_id,)).fetchone()
    if not report or (session.get("role") == "Student" and report["user_id"] != session["user_id"]):
        flash("Report not found.", "error")
        return redirect(url_for("reports"))
    return render_template("report_detail.html", report=report)

if __name__ == "__main__":
    init_db()
    app.run(debug=True)
