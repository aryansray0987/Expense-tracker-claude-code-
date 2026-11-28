import pytest

import database.db as db


def create_expense(client, **overrides):
    data = {"amount": "250.75", "category": "Food", "date": "2026-11-20", "description": "Lunch"}
    data.update(overrides)
    client.post("/expenses/add", data=data)
    conn = db.get_db()
    expense_id = conn.execute("SELECT MAX(id) FROM expenses").fetchone()[0]
    conn.close()
    return expense_id


def expense_exists(expense_id):
    conn = db.get_db()
    row = conn.execute("SELECT 1 FROM expenses WHERE id = ?", (expense_id,)).fetchone()
    conn.close()
    return row is not None


def test_get_shows_confirmation_without_deleting(client, register):
    register()
    expense_id = create_expense(client)

    response = client.get(f"/expenses/{expense_id}/delete")

    html = response.get_data(as_text=True)
    assert response.status_code == 200
    assert "Delete this expense?" in html
    assert "₹250.75" in html and "Lunch" in html and "20 Nov 2026" in html
    assert f'action="/expenses/{expense_id}/delete"' in html
    assert 'method="POST"' in html
    assert expense_exists(expense_id)


def test_post_deletes_and_redirects_with_message(client, register):
    register()
    expense_id = create_expense(client)

    response = client.post(f"/expenses/{expense_id}/delete")

    assert response.status_code == 302
    assert response.headers["Location"] == "/profile"
    assert not expense_exists(expense_id)
    html = client.get("/profile").get_data(as_text=True)
    assert "Deleted ₹250.75 for Food." in html


def test_delete_only_removes_that_expense(client, register):
    register()
    keep_id = create_expense(client, description="Keep me")
    delete_id = create_expense(client, description="Remove me")

    client.post(f"/expenses/{delete_id}/delete")

    assert expense_exists(keep_id)
    assert not expense_exists(delete_id)


def test_deleting_twice_returns_404(client, register):
    register()
    expense_id = create_expense(client)
    client.post(f"/expenses/{expense_id}/delete")

    assert client.post(f"/expenses/{expense_id}/delete").status_code == 404


def test_missing_expense_returns_404(client, register):
    register()

    assert client.get("/expenses/9999/delete").status_code == 404
    assert client.post("/expenses/9999/delete").status_code == 404


@pytest.mark.parametrize("method", ["get", "post"])
def test_cannot_delete_another_users_expense(client, register, method):
    register(email="owner@example.com")
    expense_id = create_expense(client)
    client.get("/logout")
    register(email="intruder@example.com")

    response = getattr(client, method)(f"/expenses/{expense_id}/delete")

    assert response.status_code == 404
    assert expense_exists(expense_id)


def test_delete_requires_login(client, register):
    register()
    expense_id = create_expense(client)
    client.get("/logout")

    response = client.post(f"/expenses/{expense_id}/delete")

    assert response.headers["Location"] == "/login"
    assert expense_exists(expense_id)


def test_profile_and_edit_page_link_to_delete(client, register):
    register()
    expense_id = create_expense(client)

    profile = client.get("/profile").get_data(as_text=True)
    edit = client.get(f"/expenses/{expense_id}/edit").get_data(as_text=True)

    assert f'href="/expenses/{expense_id}/delete"' in profile
    assert f'href="/expenses/{expense_id}/delete"' in edit


def test_add_page_has_no_delete_link(client, register):
    register()

    html = client.get("/expenses/add").get_data(as_text=True)

    assert "Delete this expense" not in html


def test_session_cookie_is_samesite_lax(client, register):
    response = register()

    cookie = response.headers.get("Set-Cookie", "")
    assert "SameSite=Lax" in cookie
