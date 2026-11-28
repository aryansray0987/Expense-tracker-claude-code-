import pytest

import database.db as db
from app import format_inr, pretty_date


def add_expenses(email, rows):
    """Insert (amount, category, date, description) rows for the user with this email."""
    conn = db.get_db()
    user_id = conn.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()[0]
    conn.executemany(
        "INSERT INTO expenses (user_id, amount, category, date, description) "
        "VALUES (?, ?, ?, ?, ?)",
        [(user_id, *row) for row in rows],
    )
    conn.commit()
    conn.close()


def test_profile_shows_user_details(client, register):
    register(name="Asha Rao", email="asha@example.com")

    html = client.get("/profile").get_data(as_text=True)

    assert "Asha Rao" in html
    assert "asha@example.com" in html
    assert "Member since" in html


def test_profile_empty_state(client, register):
    register()

    html = client.get("/profile").get_data(as_text=True)

    assert "No expenses yet" in html
    assert "₹0.00" in html


def test_profile_shows_totals_categories_and_recent(client, register):
    register()
    add_expenses("test@example.com", [
        (100.0, "Food", "2026-11-01", "Lunch"),
        (250.5, "Food", "2026-11-05", "Groceries"),
        (1000.0, "Bills", "2026-11-10", "Internet"),
    ])

    html = client.get("/profile").get_data(as_text=True)

    assert "₹1,350.50" in html          # total
    assert "Bills" in html and "Food" in html
    assert "Internet" in html and "Lunch" in html
    assert "10 Nov 2026" in html        # formatted date
    assert html.index("Internet") < html.index("Lunch")  # newest first
    assert "No expenses yet" not in html


def test_profile_only_shows_own_expenses(client, register):
    register(email="other@example.com")
    add_expenses("other@example.com", [(999.0, "Travel", "2026-11-02", "Secret trip")])
    client.get("/logout")

    register(email="me@example.com")
    html = client.get("/profile").get_data(as_text=True)

    assert "Secret trip" not in html
    assert "No expenses yet" in html


def test_profile_limits_recent_to_ten(client, register):
    register()
    add_expenses("test@example.com", [
        (10.0, "Food", f"2026-11-{day:02d}", f"Item {day}") for day in range(1, 13)
    ])

    html = client.get("/profile").get_data(as_text=True)

    assert "Item 12" in html
    assert "Item 2<" not in html         # 11th newest is cut off
    assert "10 most recent of 12" in html


def test_profile_with_deleted_user_logs_out(client, register):
    register()
    conn = db.get_db()
    conn.execute("DELETE FROM users")
    conn.commit()
    conn.close()

    response = client.get("/profile")

    assert response.headers["Location"] == "/login"
    with client.session_transaction() as session:
        assert "user_id" not in session


@pytest.mark.parametrize("amount, expected", [
    (0, "₹0.00"),
    (999, "₹999.00"),
    (1000, "₹1,000.00"),
    (123456.5, "₹1,23,456.50"),
    (12345678, "₹1,23,45,678.00"),
    (-1500, "-₹1,500.00"),
])
def test_format_inr(amount, expected):
    assert format_inr(amount) == expected


def test_pretty_date():
    assert pretty_date("2026-11-01") == "01 Nov 2026"
    assert pretty_date("2026-11-01 10:30:00", "%b %Y") == "Nov 2026"
    assert pretty_date("not a date") == "not a date"
