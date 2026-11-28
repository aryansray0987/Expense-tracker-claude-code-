from datetime import date

import pytest

import database.db as db

VALID = {"amount": "250.75", "category": "Food", "date": "2026-11-20", "description": "Lunch"}


def expenses_in_db():
    conn = db.get_db()
    rows = conn.execute(
        "SELECT user_id, amount, category, date, description FROM expenses"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def test_form_renders_with_today_and_categories(client, register):
    register()

    html = client.get("/expenses/add").get_data(as_text=True)

    assert "Add an expense" in html
    assert f'value="{date.today().isoformat()}"' in html
    for cat in ["Food", "Transport", "Bills", "Other"]:
        assert f'<option value="{cat}"' in html


def test_add_expense_saves_and_redirects_with_message(client, register):
    register()

    response = client.post("/expenses/add", data=VALID)

    assert response.status_code == 302
    assert response.headers["Location"] == "/profile"
    rows = expenses_in_db()
    assert len(rows) == 1
    assert rows[0]["amount"] == 250.75
    assert rows[0]["category"] == "Food"
    assert rows[0]["date"] == "2026-11-20"
    assert rows[0]["description"] == "Lunch"

    html = client.get("/profile").get_data(as_text=True)
    assert "Added ₹250.75 for Food." in html
    assert "Lunch" in html


def test_flash_message_shows_only_once(client, register):
    register()
    client.post("/expenses/add", data=VALID)

    client.get("/profile")
    html = client.get("/profile").get_data(as_text=True)

    assert "Added ₹250.75" not in html


def test_expense_belongs_to_signed_in_user(client, register):
    register(email="me@example.com")
    conn = db.get_db()
    my_id = conn.execute("SELECT id FROM users WHERE email = 'me@example.com'").fetchone()[0]
    conn.close()

    client.post("/expenses/add", data=VALID)

    assert expenses_in_db()[0]["user_id"] == my_id


def test_blank_description_is_stored_as_null(client, register):
    register()

    client.post("/expenses/add", data={**VALID, "description": "   "})

    assert expenses_in_db()[0]["description"] is None


def test_amount_is_rounded_to_paise(client, register):
    register()

    client.post("/expenses/add", data={**VALID, "amount": "10.999"})

    assert expenses_in_db()[0]["amount"] == 11.0


@pytest.mark.parametrize("field, value, message", [
    ("amount", "", "valid amount"),
    ("amount", "abc", "valid amount"),
    ("amount", "0", "greater than zero"),
    ("amount", "-50", "greater than zero"),
    ("amount", "nan", "greater than zero"),
    ("amount", "inf", "greater than zero"),
    ("amount", "10000001", "too large"),
    ("category", "", "choose a category"),
    ("category", "Gambling", "choose a category"),
    ("date", "", "valid date"),
    ("date", "2026-13-45", "valid date"),
    ("date", "20/11/2026", "valid date"),
    ("description", "x" * 201, "200 characters"),
])
def test_invalid_input_is_rejected(client, register, field, value, message):
    register()

    response = client.post("/expenses/add", data={**VALID, field: value})

    assert response.status_code == 200
    assert message in response.get_data(as_text=True)
    assert expenses_in_db() == []


def test_form_keeps_values_after_error(client, register):
    register()

    html = client.post(
        "/expenses/add", data={**VALID, "amount": "-5"}
    ).get_data(as_text=True)

    assert 'value="-5"' in html
    assert '<option value="Food" selected' in html
    assert 'value="2026-11-20"' in html
    assert 'value="Lunch"' in html


def test_add_requires_login(client):
    response = client.post("/expenses/add", data=VALID)

    assert response.headers["Location"] == "/login"
    assert expenses_in_db() == []
