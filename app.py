import math
import os
import sqlite3
from datetime import date, datetime
from functools import wraps

from dotenv import load_dotenv
from flask import Flask, abort, flash, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

from database.db import get_db, init_db, seed_db

load_dotenv()  # read variables from .env into os.environ

app = Flask(__name__)
# Signs the session cookie. Set SECRET_KEY in .env; the fallback is for local dev only.
app.secret_key = os.environ.get("SECRET_KEY", "dev-only-insecure-key")
# Don't send the session cookie on form POSTs from other websites, so a
# malicious page can't submit forms (like delete) as the signed-in user.
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"

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
# Expense form validation                                             #
# ------------------------------------------------------------------ #

CATEGORIES = [
    "Food",
    "Transport",
    "Bills",
    "Shopping",
    "Entertainment",
    "Health",
    "Education",
    "Other",
]

MAX_AMOUNT = 10_000_000  # ₹1 crore — guards against typos like an extra zero or five
MAX_DESCRIPTION = 200


def validate_expense_form(form):
    """Check submitted expense fields.

    Returns (values, error). `values` always holds what the user typed, so the
    form can be refilled; `error` is None when everything is valid, and then
    values["amount"] is a float rounded to paise.
    """
    values = {
        "amount": form.get("amount", "").strip(),
        "category": form.get("category", "").strip(),
        "date": form.get("date", "").strip(),
        "description": form.get("description", "").strip(),
    }

    try:
        amount = float(values["amount"])
    except ValueError:
        return values, "Please enter a valid amount."
    if not math.isfinite(amount) or amount <= 0:  # float() accepts "nan" and "inf"
        return values, "Amount must be greater than zero."
    if amount > MAX_AMOUNT:
        return values, "Amount is too large."

    if values["category"] not in CATEGORIES:
        return values, "Please choose a category."

    try:
        datetime.strptime(values["date"], "%Y-%m-%d")
    except ValueError:
        return values, "Please enter a valid date."

    if len(values["description"]) > MAX_DESCRIPTION:
        return values, f"Description must be {MAX_DESCRIPTION} characters or fewer."

    values["amount"] = round(amount, 2)
    return values, None


def render_expense_form(
    heading, submit_label, action, values, error=None, delete_url=None, back_url=None
):
    """Render expense_form.html, shared by the add and edit pages."""
    return render_template(
        "expense_form.html",
        heading=heading,
        submit_label=submit_label,
        action=action,
        categories=CATEGORIES,
        values=values,
        error=error,
        today=date.today().isoformat(),
        delete_url=delete_url,
        back_url=back_url or url_for("profile"),
    )


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
# Expenses (all routes require a signed-in user)                      #
# ------------------------------------------------------------------ #


def get_own_expense_or_404(conn, expense_id):
    """Fetch an expense owned by the signed-in user, or abort with 404.

    Filtering by user_id means other users' expenses look exactly like
    missing ones: both return 404, so ids can't be probed.
    """
    expense = conn.execute(
        "SELECT id, amount, category, date, description FROM expenses "
        "WHERE id = ? AND user_id = ?",
        (expense_id, session["user_id"]),
    ).fetchone()
    if expense is None:
        conn.close()
        abort(404)
    return expense


def get_next_param():
    """The page to return to after add/edit/delete (?next=), or None.

    Only same-site paths are accepted ("/expenses?page=2"). Anything that
    could point to another site ("https://evil.com", "//evil.com", "/\\evil.com",
    or paths with whitespace that browsers strip) is ignored, so ?next= can't
    be abused as an open redirect. Callers fall back to the profile on None;
    url_for() drops next=None, so links stay clean when there's no ?next=.
    """
    target = request.args.get("next", "")
    if (
        target.startswith("/")
        and not target.startswith("//")
        and not any(c == "\\" or ord(c) < 33 for c in target)
    ):
        return target
    return None


PER_PAGE = 20


@app.route("/expenses")
@login_required
def list_expenses():
    user_id = session["user_id"]
    conn = get_db()

    totals = conn.execute(
        "SELECT COUNT(*) AS count, COALESCE(SUM(amount), 0) AS total "
        "FROM expenses WHERE user_id = ?",
        (user_id,),
    ).fetchone()

    pages = max(1, math.ceil(totals["count"] / PER_PAGE))
    # Clamp out-of-range pages, e.g. after deleting the last item on the last page.
    page = min(max(request.args.get("page", 1, type=int), 1), pages)

    expenses = conn.execute(
        "SELECT id, amount, category, date, description "
        "FROM expenses WHERE user_id = ? "
        "ORDER BY date DESC, id DESC LIMIT ? OFFSET ?",
        (user_id, PER_PAGE, (page - 1) * PER_PAGE),
    ).fetchall()
    conn.close()

    return render_template(
        "expenses.html",
        expenses=expenses,
        count=totals["count"],
        total=totals["total"],
        page=page,
        pages=pages,
        first_index=(page - 1) * PER_PAGE + 1,
        back_url=url_for("list_expenses", page=page) if page > 1 else url_for("list_expenses"),
    )


@app.route("/expenses/add", methods=["GET", "POST"])
@login_required
def add_expense():
    next_url = get_next_param()

    def show_form(values, error=None):
        return render_expense_form(
            "Add an expense",
            "Add expense",
            url_for("add_expense", next=next_url),
            values,
            error,
            back_url=next_url or url_for("profile"),
        )

    if request.method == "GET":
        return show_form({"date": date.today().isoformat()})

    values, error = validate_expense_form(request.form)
    if error:
        return show_form(values, error)

    conn = get_db()
    conn.execute(
        "INSERT INTO expenses (user_id, amount, category, date, description) "
        "VALUES (?, ?, ?, ?, ?)",
        (
            session["user_id"],
            values["amount"],
            values["category"],
            values["date"],
            values["description"] or None,
        ),
    )
    conn.commit()
    conn.close()

    flash(f"Added {format_inr(values['amount'])} for {values['category']}.")
    return redirect(next_url or url_for("profile"))


@app.route("/expenses/<int:id>/edit", methods=["GET", "POST"])
@login_required
def edit_expense(id):
    conn = get_db()
    expense = get_own_expense_or_404(conn, id)
    next_url = get_next_param()

    def show_form(values, error=None):
        return render_expense_form(
            "Edit expense",
            "Save changes",
            url_for("edit_expense", id=id, next=next_url),
            values,
            error,
            delete_url=url_for("delete_expense", id=id, next=next_url),
            back_url=next_url or url_for("profile"),
        )

    if request.method == "GET":
        conn.close()
        return show_form({
            "amount": f"{expense['amount']:.2f}",
            "category": expense["category"],
            "date": expense["date"],
            "description": expense["description"] or "",
        })

    values, error = validate_expense_form(request.form)
    if error:
        conn.close()
        return show_form(values, error)

    conn.execute(
        "UPDATE expenses SET amount = ?, category = ?, date = ?, description = ? "
        "WHERE id = ? AND user_id = ?",
        (
            values["amount"],
            values["category"],
            values["date"],
            values["description"] or None,
            id,
            session["user_id"],
        ),
    )
    conn.commit()
    conn.close()

    flash(f"Updated expense: {format_inr(values['amount'])} for {values['category']}.")
    return redirect(next_url or url_for("profile"))


@app.route("/expenses/<int:id>/delete", methods=["GET", "POST"])
@login_required
def delete_expense(id):
    conn = get_db()
    expense = get_own_expense_or_404(conn, id)
    next_url = get_next_param()

    # GET only shows a confirmation page; nothing is deleted until the
    # user submits its form. Deleting on GET would let link prefetching
    # or a link on another site remove data.
    if request.method == "GET":
        conn.close()
        return render_template(
            "delete_expense.html",
            expense=expense,
            action=url_for("delete_expense", id=id, next=next_url),
            back_url=next_url or url_for("profile"),
        )

    conn.execute(
        "DELETE FROM expenses WHERE id = ? AND user_id = ?",
        (id, session["user_id"]),
    )
    conn.commit()
    conn.close()

    flash(f"Deleted {format_inr(expense['amount'])} for {expense['category']}.")
    return redirect(next_url or url_for("profile"))


if __name__ == "__main__":
    app.run(debug=True, port=5001)
