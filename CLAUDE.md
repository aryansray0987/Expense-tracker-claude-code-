# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

**Spendly** is a Flask expense tracker (amounts in rupees). It is a step-by-step learning project: many routes and files are placeholders labelled "coming in Step N" or "Students will write this file in Step N". Implement only the step being asked for, and keep the existing step comments intact unless the step is being completed.

## Commands (Windows, PowerShell)

```powershell
python -m venv venv                  # one-time setup
venv\Scripts\activate
pip install -r requirements.txt

python app.py                        # dev server with debug reload at http://localhost:5001 (not 5000)

python -m pytest                                   # run all tests
python -m pytest tests/test_auth.py::test_login_success   # run a single test
```

There is no linter, formatter, or build step configured.

## Architecture

- `app.py` holds the Flask app and every route; there are no blueprints. Steps 1–5 and 7–9 are built. Step 6 is not named anywhere in the code.
- All expenses (Step 5, done): `/expenses` (`list_expenses`) lists every expense for the user, newest first, `PER_PAGE` (20) per page via `?page=`. Out-of-range pages are clamped rather than returning 404. The rows come from the `_expense_table.html` partial, which `profile.html` also uses; it takes `expenses` and `return_to`.
- Return-to flow: add, edit and delete accept `?next=<path>` and redirect there afterwards, falling back to `/profile`. `get_next_param()` accepts only same-site paths (no `//`, backslashes or whitespace) to prevent open redirects. Always pass `next` through it, never `request.args["next"]` directly.
- Add expense (Step 7, done): `/expenses/add` renders `expense_form.html` through `render_expense_form()`, which add and edit share. `validate_expense_form()` returns `(values, error)`: amount must be finite, greater than 0 and at most `MAX_AMOUNT` (rounded to paise), category must be in `CATEGORIES`, date must be `YYYY-MM-DD`, and description is at most 200 characters (blank is stored as NULL). On success it calls `flash()` and redirects to `/profile`. `base.html` renders flashed messages above every page.
- Edit expense (Step 8, done): `/expenses/<id>/edit` loads the expense with `get_own_expense_or_404()` (`WHERE id = ? AND user_id = ?`, otherwise `abort(404)`), so another user's expense looks the same as a missing one. The `UPDATE` also filters by `user_id`.
- Delete expense (Step 9, done): `GET /expenses/<id>/delete` only shows a confirmation page (`delete_expense.html`), and `POST` performs the `DELETE` (filtered by `user_id`), flashes a message, and redirects to `/profile`. Never delete on GET. Delete links appear on profile rows and on the edit page (via `render_expense_form(delete_url=...)`). `SESSION_COOKIE_SAMESITE = "Lax"` stops other sites from submitting POST forms as the user. There are no CSRF tokens. It reuses `validate_expense_form()` and the shared form. The profile's recent-expenses table has an Edit link on each row.
- Profile (Step 4, done): `/profile` renders `profile.html` with the user's details, total and count, per-category totals (`GROUP BY`), and the 10 most recent expenses. Every expense query must filter by `session["user_id"]`. If the session's user no longer exists, the route clears the session and redirects to `/login`.
- Template filters in `app.py`: `inr` formats rupees with Indian digit grouping (`₹1,23,456.50`), and `pretty_date` turns `YYYY-MM-DD` into `01 Nov 2026` (it takes an optional strftime format). Use them for all money and dates in templates.
- Sessions (Step 3, done): `@login_required` (defined in `app.py`, placed below `@app.route`) redirects signed-out visitors to `/login`. `/logout` clears the session and redirects to `/`. Signed-in users who open `/login` or `/register` are sent to `/profile`. `base.html` switches the navbar on `session.user_id`, showing the user's name and "Log out" instead of "Sign in / Get started".
- `database/db.py` (Step 1, done): `get_db()` opens a new connection per call (`row_factory = sqlite3.Row`, foreign keys on) and callers must close it. `init_db()` creates the `users` and `expenses` tables, and `seed_db()` adds a demo user (`demo@spendly.com` / `demo1234`) plus sample expenses only when the users table is empty. `app.py` runs both at import time. The database file is `expense_tracker.db` in the project root (gitignored). Use plain `sqlite3` with `?` placeholders; there is no ORM. To reset the data, delete the `.db` file and restart.
- `templates/` uses Jinja inheritance from `base.html`, which provides the navbar, footer, and the `title`, `head`, `content`, and `scripts` blocks. Link with `url_for('<endpoint>')`.
- Auth (Step 2, done): `/register` and `/login` handle `GET` and `POST`. Passwords are hashed with `werkzeug.security`, and emails are stored lowercased. On success the route sets `session["user_id"]` and `session["user_name"]` and redirects to `/profile`. On failure it re-renders the template with `error` (plus `name`/`email` to refill the form). `app.secret_key` comes from `SECRET_KEY` in `.env` (loaded by python-dotenv), with an insecure fallback for local dev.
- Tests: `tests/conftest.py` points `database.db.DB_PATH` at a temp file for each test, so tests never touch the real database. pytest-flask provides the `client` fixture from the `app` fixture.
- `static/css/style.css` is a single stylesheet for every page. The fonts are DM Serif Display and DM Sans from Google Fonts.
- `static/js/main.js` is a single script loaded on every page. Each feature is wrapped in an IIFE that returns early when its DOM elements are missing (see the landing-page video modal). Follow that pattern for page-specific JS.

## Conventions

- Commit messages: `feat(scope): message` / `feat: message`.
- `.env` is gitignored; do not read or commit it.
