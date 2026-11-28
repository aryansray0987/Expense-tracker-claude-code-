import pytest

import app as app_module
import database.db as db


def add_expenses(email, count, start_day=1):
    """Insert `count` expenses dated 2026-01-01 onwards, described 'Item 1', 'Item 2', ..."""
    conn = db.get_db()
    user_id = conn.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()[0]
    conn.executemany(
        "INSERT INTO expenses (user_id, amount, category, date, description) VALUES (?, ?, ?, ?, ?)",
        [
            (user_id, 100.0, "Food", f"2026-{1 + (n - 1) // 28:02d}-{1 + (n - 1) % 28:02d}", f"Item {n}")
            for n in range(start_day, start_day + count)
        ],
    )
    conn.commit()
    conn.close()


def first_expense_id():
    conn = db.get_db()
    expense_id = conn.execute("SELECT MIN(id) FROM expenses").fetchone()[0]
    conn.close()
    return expense_id


def test_requires_login(client):
    assert client.get("/expenses").headers["Location"] == "/login"


def test_empty_state(client, register):
    register()

    html = client.get("/expenses").get_data(as_text=True)

    assert "All expenses" in html
    assert "No expenses yet" in html
    assert "0 expenses · ₹0.00 in total" in html


def test_lists_all_expenses_with_totals(client, register):
    register()
    add_expenses("test@example.com", 12)

    html = client.get("/expenses").get_data(as_text=True)

    assert "12 expenses · ₹1,200.00 in total" in html
    for n in range(1, 13):
        assert f">Item {n}<" in html          # all 12, unlike the profile's 10
    assert html.index("Item 12") < html.index("Item 1<")  # newest first
    assert 'class="pagination"' not in html    # fits on one page


def test_only_shows_own_expenses(client, register):
    register(email="other@example.com")
    add_expenses("other@example.com", 3)
    client.get("/logout")
    register(email="me@example.com")

    html = client.get("/expenses").get_data(as_text=True)

    assert "Item 1" not in html
    assert "No expenses yet" in html


def test_paginates(client, register):
    register()
    add_expenses("test@example.com", app_module.PER_PAGE + 5)  # 25

    page1 = client.get("/expenses").get_data(as_text=True)
    page2 = client.get("/expenses?page=2").get_data(as_text=True)

    assert "1–20 of 25" in page1 and "Page 1 of 2" in page1
    assert ">Item 25<" in page1 and ">Item 5<" not in page1
    assert 'href="/expenses?page=2"' in page1

    assert "21–25 of 25" in page2 and "Page 2 of 2" in page2
    assert ">Item 5<" in page2 and ">Item 25<" not in page2
    assert 'href="/expenses?page=1"' in page2


@pytest.mark.parametrize("page, expected", [("0", "Page 1 of 2"), ("-3", "Page 1 of 2"),
                                            ("99", "Page 2 of 2"), ("abc", "Page 1 of 2")])
def test_out_of_range_pages_are_clamped(client, register, page, expected):
    register()
    add_expenses("test@example.com", 25)

    response = client.get(f"/expenses?page={page}")

    assert response.status_code == 200
    assert expected in response.get_data(as_text=True)


def test_rows_link_to_edit_and_delete_with_return_path(client, register):
    register()
    add_expenses("test@example.com", 25)

    html = client.get("/expenses?page=2").get_data(as_text=True)

    expense_id = first_expense_id()  # Item 1, the oldest, is on page 2
    assert f'href="/expenses/{expense_id}/edit?next=/expenses?page%3D2"' in html
    assert f'href="/expenses/{expense_id}/delete?next=/expenses?page%3D2"' in html


def test_edit_returns_to_list_page(client, register):
    register()
    add_expenses("test@example.com", 1)
    expense_id = first_expense_id()
    data = {"amount": "50", "category": "Bills", "date": "2026-01-01", "description": "Edited"}

    form = client.get(f"/expenses/{expense_id}/edit?next=/expenses").get_data(as_text=True)
    response = client.post(f"/expenses/{expense_id}/edit?next=/expenses", data=data)

    assert 'href="/expenses">← Back' in form
    assert response.headers["Location"] == "/expenses"


def test_delete_returns_to_list_page(client, register):
    register()
    add_expenses("test@example.com", 1)
    expense_id = first_expense_id()

    page = client.get(f"/expenses/{expense_id}/delete?next=/expenses").get_data(as_text=True)
    response = client.post(f"/expenses/{expense_id}/delete?next=/expenses")

    assert 'href="/expenses" class="btn-ghost btn-block">Cancel' in page
    assert response.headers["Location"] == "/expenses"


def test_add_from_list_returns_to_list(client, register):
    register()
    data = {"amount": "50", "category": "Bills", "date": "2026-01-01", "description": ""}

    response = client.post("/expenses/add?next=/expenses", data=data)

    assert response.headers["Location"] == "/expenses"


def test_without_next_still_returns_to_profile(client, register):
    register()
    add_expenses("test@example.com", 1)
    expense_id = first_expense_id()

    response = client.post(f"/expenses/{expense_id}/delete")

    assert response.headers["Location"] == "/profile"


@pytest.mark.parametrize("evil", [
    "https://evil.com",
    "//evil.com",
    "/\\evil.com",
    "/\t/evil.com",
    "evil.com",
    "javascript:alert(1)",
])
def test_next_cannot_redirect_off_site(client, register, evil):
    register()
    add_expenses("test@example.com", 1)
    expense_id = first_expense_id()

    response = client.post(f"/expenses/{expense_id}/delete", query_string={"next": evil})

    assert response.headers["Location"] == "/profile"


def test_profile_links_to_all_expenses(client, register):
    register()
    add_expenses("test@example.com", 12)

    html = client.get("/profile").get_data(as_text=True)

    assert 'href="/expenses"' in html
    assert "See all 12" in html


def test_navbar_has_expenses_link_when_signed_in(client, register):
    assert 'href="/expenses"' not in client.get("/").get_data(as_text=True)
    register()
    assert 'href="/expenses"' in client.get("/").get_data(as_text=True)
