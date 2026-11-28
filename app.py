import os
import sqlite3
from datetime import datetime
from functools import wraps

from dotenv import load_dotenv
from flask import Flask, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

from database.db import get_db, init_db, seed_db

load_dotenv()  # read variables from .env into os.environ

app = Flask(__name__)
# Signs the session cookie. Set SECRET_KEY in .env; the fallback is for local dev only.
app.secret_key = os.environ.get("SECRET_KEY", "dev-only-insecure-key")

# Create tables (if missing) and add sample data on startup.
init_db()
seed_db()


def login_required(view):
    """Redirect to the login page unless a user is signed in."""

    @wraps(view)
    def wrapped(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("login"))
        return view(*args, **kwargs)

    return wrapped


# ------------------------------------------------------------------ #
# Template filters                                                    #
# ------------------------------------------------------------------ #

@app.template_filter("inr")
def format_inr(amount):
    """Format a number as rupees with Indian digit grouping: 123456.5 -> ₹1,23,456.50"""
    rupees, paise = f"{abs(amount):.2f}".split(".")
    if len(rupees) > 3:
        head, tail = rupees[:-3], rupees[-3:]
        groups = []
        while len(head) > 2:
            groups.insert(0, head[-2:])
            head = head[:-2]
        groups.insert(0, head)
        rupees = ",".join(groups) + "," + tail
    sign = "-" if amount < 0 else ""
    return f"{sign}₹{rupees}.{paise}"


@app.template_filter("pretty_date")
def pretty_date(value, fmt="%d %b %Y"):
    """'2026-11-01' (or '2026-11-01 10:00:00') -> '01 Nov 2026'"""
    try:
        return datetime.strptime(value[:10], "%Y-%m-%d").strftime(fmt)
    except (TypeError, ValueError):
        return value


# ------------------------------------------------------------------ #
# Routes                                                              #
# ------------------------------------------------------------------ #

@app.route("/")
def landing():
    return render_template("landing.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if "user_id" in session:  # already signed in
        return redirect(url_for("profile"))
    if request.method == "GET":
        return render_template("register.html")

    name = request.form.get("name", "").strip()
    email = request.form.get("email", "").strip().lower()
    password = request.form.get("password", "")

    def fail(message):
        return render_template("register.html", error=message, name=name, email=email)

    if not name or not email or not password:
        return fail("All fields are required.")
    if "@" not in email:
        return fail("Please enter a valid email address.")
    if len(password) < 8:
        return fail("Password must be at least 8 characters.")

    conn = get_db()
    try:
        cursor = conn.execute(
            "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
            (name, email, generate_password_hash(password)),
        )
        conn.commit()
    except sqlite3.IntegrityError:  # UNIQUE constraint on email
        return fail("An account with this email already exists.")
    finally:
        conn.close()

    # Log the new user in straight away.
    session.clear()
    session["user_id"] = cursor.lastrowid
    session["user_name"] = name
    return redirect(url_for("profile"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if "user_id" in session:  # already signed in
        return redirect(url_for("profile"))
    if request.method == "GET":
        return render_template("login.html")

    email = request.form.get("email", "").strip().lower()
    password = request.form.get("password", "")

    conn = get_db()
    user = conn.execute(
        "SELECT id, name, password_hash FROM users WHERE email = ?", (email,)
    ).fetchone()
    conn.close()

    # Same message for unknown email and wrong password, so attackers
    # can't use the form to discover which emails are registered.
    if user is None or not check_password_hash(user["password_hash"], password):
        return render_template(
            "login.html", error="Invalid email or password.", email=email
        )

    session.clear()
    session["user_id"] = user["id"]
    session["user_name"] = user["name"]
    return redirect(url_for("profile"))


@app.route("/terms")
def terms():
    return render_template("terms.html")


@app.route("/privacy")
def privacy():
    return render_template("privacy.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("landing"))


@app.route("/profile")
@login_required
def profile():
    user_id = session["user_id"]
    conn = get_db()

    user = conn.execute(
        "SELECT name, email, created_at FROM users WHERE id = ?", (user_id,)
    ).fetchone()
    if user is None:
        # The session points at a user that no longer exists
        # (e.g. the database file was deleted). Start over.
        conn.close()
        session.clear()
        return redirect(url_for("login"))

    totals = conn.execute(
        "SELECT COUNT(*) AS count, COALESCE(SUM(amount), 0) AS total "
        "FROM expenses WHERE user_id = ?",
        (user_id,),
    ).fetchone()

    categories = conn.execute(
        "SELECT category, SUM(amount) AS total, COUNT(*) AS count "
        "FROM expenses WHERE user_id = ? "
        "GROUP BY category ORDER BY total DESC",
        (user_id,),
    ).fetchall()

    recent = conn.execute(
        "SELECT id, amount, category, date, description "
        "FROM expenses WHERE user_id = ? "
        "ORDER BY date DESC, id DESC LIMIT 10",
        (user_id,),
    ).fetchall()

    conn.close()

    return render_template(
        "profile.html",
        user=user,
        total=totals["total"],
        count=totals["count"],
        categories=categories,
        recent=recent,
    )


# ------------------------------------------------------------------ #
# Placeholder routes — students will implement these                  #
# (already protected: signed-out visitors are sent to /login)        #
# ------------------------------------------------------------------ #


@app.route("/expenses/add")
@login_required
def add_expense():
    return "Add expense — coming in Step 7"


@app.route("/expenses/<int:id>/edit")
@login_required
def edit_expense(id):
    return "Edit expense — coming in Step 8"


@app.route("/expenses/<int:id>/delete")
@login_required
def delete_expense(id):
    return "Delete expense — coming in Step 9"


if __name__ == "__main__":
    app.run(debug=True, port=5001)
