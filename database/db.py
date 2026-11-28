# Step 1 — Database Setup
#   get_db()   — returns a SQLite connection with row_factory and foreign keys enabled
#   init_db()  — creates all tables using CREATE TABLE IF NOT EXISTS
#   seed_db()  — inserts sample data for development

import os
import sqlite3

from werkzeug.security import generate_password_hash

# Absolute path to expense_tracker.db in the project root, so the same file is
# used no matter which folder the app is started from.
DB_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "expense_tracker.db",
)


def get_db():
    """Open a new connection to the SQLite database."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row  # rows behave like dicts: row["email"]
    conn.execute("PRAGMA foreign_keys = ON")  # SQLite has these off by default
    return conn


def init_db():
    """Create all tables. Safe to run repeatedly."""
    conn = get_db()
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS users (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            name          TEXT    NOT NULL,
            email         TEXT    NOT NULL UNIQUE,
            password_hash TEXT    NOT NULL,
            created_at    TEXT    NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS expenses (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id     INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            amount      REAL    NOT NULL CHECK (amount > 0),
            category    TEXT    NOT NULL,
            date        TEXT    NOT NULL,  -- 'YYYY-MM-DD'
            description TEXT,
            created_at  TEXT    NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        CREATE INDEX IF NOT EXISTS idx_expenses_user_date
            ON expenses (user_id, date);
        """
    )
    conn.commit()
    conn.close()


def seed_db():
    """Insert a demo user and sample expenses. Does nothing if users already exist."""
    conn = get_db()

    if conn.execute("SELECT COUNT(*) FROM users").fetchone()[0] > 0:
        conn.close()
        return

    cursor = conn.execute(
        "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
        ("Demo User", "demo@spendly.com", generate_password_hash("demo1234")),
    )
    user_id = cursor.lastrowid

    sample_expenses = [
        (user_id, 450.00, "Food", "2026-11-01", "Groceries"),
        (user_id, 1200.00, "Transport", "2026-11-03", "Monthly metro pass"),
        (user_id, 799.00, "Entertainment", "2026-11-07", "Movie tickets"),
        (user_id, 2500.00, "Bills", "2026-11-10", "Electricity bill"),
        (user_id, 320.50, "Food", "2026-11-15", "Dinner with friends"),
        (user_id, 1599.00, "Shopping", "2026-11-20", "New headphones"),
    ]
    conn.executemany(
        "INSERT INTO expenses (user_id, amount, category, date, description) "
        "VALUES (?, ?, ?, ?, ?)",
        sample_expenses,
    )

    conn.commit()
    conn.close()
