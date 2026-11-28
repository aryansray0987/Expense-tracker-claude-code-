import pytest

import app as app_module
import database.db as db
from app import parse_expense_filters

SAMPLE = [
    (100.0, "Food", "2026-10-05", "October lunch"),
    (200.0, "Bills", "2026-10-20", "October internet"),
    (300.0, "Food", "2026-11-03", "November groceries"),
    (400.0, "Transport", "2026-11-15", "November metro"),
    (500.0, "Food", "2026-11-28", "November dinner"),
]


@pytest.fixture
def signed_in_with_sample(client, register):
    register()
    conn = db.get_db()
    user_id = conn.execute("SELECT id FROM users").fetchone()[0]
    conn.executemany(
        "INSERT INTO expenses (user_id, amount, category, date, description) VALUES (?, ?, ?, ?, ?)",
        [(user_id, *row) for row in SAMPLE],
    )
    conn.commit()
    conn.close()
    return client


def descriptions(html):
    return [row[3] for row in SAMPLE if f">{row[3]}<" in html]


def test_no_filters_shows_everything(signed_in_with_sample):
    html = signed_in_with_sample.get("/expenses").get_data(as_text=True)

    assert len(descriptions(html)) == 5
    assert "5 expenses · ₹1,500.00 in total" in html
    assert ">Clear<" not in html


def test_filter_by_category(signed_in_with_sample):
    html = signed_in_with_sample.get("/expenses?category=Food").get_data(as_text=True)

    assert descriptions(html) == ["October lunch", "November groceries", "November dinner"]
    assert "3 of 5 expenses match · ₹900.00" in html
    assert '<option value="Food" selected' in html
    assert ">Clear<" in html


def test_filter_by_date_range_is_inclusive(signed_in_with_sample):
    html = signed_in_with_sample.get(
        "/expenses?start=2026-10-20&end=2026-11-15"
    ).get_data(as_text=True)

    assert descriptions(html) == ["October internet", "November groceries", "November metro"]
    assert 'value="2026-10-20"' in html and 'value="2026-11-15"' in html


def test_open_ended_ranges(signed_in_with_sample):
    from_only = signed_in_with_sample.get("/expenses?start=2026-11-15").get_data(as_text=True)
    to_only = signed_in_with_sample.get("/expenses?end=2026-10-31").get_data(as_text=True)

    assert descriptions(from_only) == ["November metro", "November dinner"]
    assert descriptions(to_only) == ["October lunch", "October internet"]


def test_category_and_dates_combine(signed_in_with_sample):
    html = signed_in_with_sample.get(
        "/expenses?category=Food&start=2026-11-01&end=2026-11-30"
    ).get_data(as_text=True)

    assert descriptions(html) == ["November groceries", "November dinner"]
    assert "2 of 5 expenses match · ₹800.00" in html


def test_reversed_range_is_swapped(signed_in_with_sample):
    html = signed_in_with_sample.get(
        "/expenses?start=2026-11-30&end=2026-11-01"
    ).get_data(as_text=True)

    assert len(descriptions(html)) == 3
    assert 'value="2026-11-01"' in html  # shown in the corrected order


def test_no_matches_shows_message(signed_in_with_sample):
    html = signed_in_with_sample.get("/expenses?category=Health").get_data(as_text=True)

    assert "No matching expenses" in html
    assert "0 of 5 expenses match · ₹0.00" in html
    assert "No expenses yet" not in html


def test_empty_form_submit_means_no_filter(signed_in_with_sample):
    html = signed_in_with_sample.get("/expenses?category=&start=&end=").get_data(as_text=True)

    assert len(descriptions(html)) == 5
    assert ">Clear<" not in html


@pytest.mark.parametrize("query", [
    "category=Gambling",
    "category=food",                    # case matters, like the stored values
    "start=not-a-date",
    "end=2026-02-30",
    "category=' OR 1=1 --",
])
def test_invalid_filters_are_ignored(signed_in_with_sample, query):
    response = signed_in_with_sample.get(f"/expenses?{query}")

    assert response.status_code == 200
    assert len(descriptions(response.get_data(as_text=True))) == 5


def test_filters_do_not_leak_other_users_expenses(client, register, signed_in_with_sample):
    client.get("/logout")
    register(email="other@example.com")

    html = client.get("/expenses?category=Food").get_data(as_text=True)

    assert descriptions(html) == []
    assert "No expenses yet" in html


def test_pagination_keeps_filters(client, register, monkeypatch):
    monkeypatch.setattr(app_module, "PER_PAGE", 2)
    register()
    conn = db.get_db()
    user_id = conn.execute("SELECT id FROM users").fetchone()[0]
    conn.executemany(
        "INSERT INTO expenses (user_id, amount, category, date, description) VALUES (?, ?, ?, ?, ?)",
        [(user_id, *row) for row in SAMPLE],
    )
    conn.commit()
    conn.close()

    page1 = client.get("/expenses?category=Food").get_data(as_text=True)
    page2 = client.get("/expenses?category=Food&page=2").get_data(as_text=True)

    assert "Page 1 of 2" in page1
    assert 'href="/expenses?page=2&amp;category=Food"' in page1
    assert descriptions(page2) == ["October lunch"]
    assert 'href="/expenses?category=Food" class="btn-ghost" rel="prev"' in page2


def test_edit_link_returns_to_filtered_list(signed_in_with_sample):
    html = signed_in_with_sample.get("/expenses?category=Bills").get_data(as_text=True)

    assert "next=/expenses?category%3DBills" in html


def test_parse_expense_filters_unit():
    assert parse_expense_filters({}) == {"category": None, "start": None, "end": None}
    assert parse_expense_filters(
        {"category": " Food ", "start": "2026-11-30", "end": "2026-11-01"}
    ) == {"category": "Food", "start": "2026-11-01", "end": "2026-11-30"}
