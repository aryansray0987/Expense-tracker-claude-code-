import pytest

import database.db as db

UPDATED = {"amount": "999.50", "category": "Bills", "date": "2026-11-15", "description": "Phone bill"}


def create_expense(client, **overrides):
    data = {"amount": "250.75", "category": "Food", "date": "2026-11-20", "description": "Lunch"}
    data.update(overrides)
    client.post("/expenses/add", data=data)
    conn = db.get_db()
    expense_id = conn.execute("SELECT MAX(id) FROM expenses").fetchone()[0]
    conn.close()
    return expense_id


def get_expense(expense_id):
    conn = db.get_db()
    row = conn.execute(
        "SELECT amount, category, date, description FROM expenses WHERE id = ?",
        (expense_id,),
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def test_edit_form_is_prefilled(client, register):
    register()
    expense_id = create_expense(client)

    html = client.get(f"/expenses/{expense_id}/edit").get_data(as_text=True)

    assert "Edit expense" in html
    assert "Save changes" in html
    assert 'value="250.75"' in html
    assert '<option value="Food" selected' in html
    assert 'value="2026-11-20"' in html
    assert 'value="Lunch"' in html
    assert f'action="/expenses/{expense_id}/edit"' in html


def test_edit_saves_changes_and_redirects(client, register):
    register()
    expense_id = create_expense(client)

    response = client.post(f"/expenses/{expense_id}/edit", data=UPDATED)

    assert response.status_code == 302
    assert response.headers["Location"] == "/profile"
    assert get_expense(expense_id) == {
        "amount": 999.5, "category": "Bills", "date": "2026-11-15", "description": "Phone bill",
    }
    html = client.get("/profile").get_data(as_text=True)
    assert "Updated expense: ₹999.50 for Bills." in html


def test_edit_does_not_create_new_rows(client, register):
    register()
    expense_id = create_expense(client)

    client.post(f"/expenses/{expense_id}/edit", data=UPDATED)

    conn = db.get_db()
    assert conn.execute("SELECT COUNT(*) FROM expenses").fetchone()[0] == 1
    conn.close()


def test_edit_can_clear_description(client, register):
    register()
    expense_id = create_expense(client)

    client.post(f"/expenses/{expense_id}/edit", data={**UPDATED, "description": ""})

    assert get_expense(expense_id)["description"] is None


def test_invalid_edit_keeps_original_and_shows_error(client, register):
    register()
    expense_id = create_expense(client)

    response = client.post(f"/expenses/{expense_id}/edit", data={**UPDATED, "amount": "0"})

    html = response.get_data(as_text=True)
    assert response.status_code == 200
    assert "greater than zero" in html
    assert 'value="Phone bill"' in html            # user's input kept
    assert get_expense(expense_id)["amount"] == 250.75  # database unchanged


def test_missing_expense_returns_404(client, register):
    register()

    assert client.get("/expenses/9999/edit").status_code == 404
    assert client.post("/expenses/9999/edit", data=UPDATED).status_code == 404


@pytest.mark.parametrize("method", ["get", "post"])
def test_cannot_edit_another_users_expense(client, register, method):
    register(email="owner@example.com")
    expense_id = create_expense(client)
    client.get("/logout")
    register(email="intruder@example.com")

    response = getattr(client, method)(f"/expenses/{expense_id}/edit", data=UPDATED)

    assert response.status_code == 404
    assert get_expense(expense_id)["amount"] == 250.75


def test_edit_requires_login(client, register):
    register()
    expense_id = create_expense(client)
    client.get("/logout")

    response = client.post(f"/expenses/{expense_id}/edit", data=UPDATED)

    assert response.headers["Location"] == "/login"
    assert get_expense(expense_id)["amount"] == 250.75


def test_profile_rows_link_to_edit(client, register):
    register()
    expense_id = create_expense(client)

    html = client.get("/profile").get_data(as_text=True)

    assert f'href="/expenses/{expense_id}/edit"' in html
