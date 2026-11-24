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

pytest                               # run all tests (pytest + pytest-flask installed; no tests exist yet)
pytest tests/test_x.py::test_name    # run a single test
```

There is no linter, formatter, or build step configured.

## Architecture

- `app.py` holds the Flask app and every route; there are no blueprints. Routes that are already built only render templates. Placeholder routes (`/logout`, `/profile`, `/expenses/add`, `/expenses/<id>/edit`, `/expenses/<id>/delete`) return stub strings until their step is built.
- `database/db.py` is currently an empty stub. Step 1 defines its contract: `get_db()` returns a SQLite connection with `row_factory` set and foreign keys enabled, `init_db()` creates tables with `CREATE TABLE IF NOT EXISTS`, and `seed_db()` inserts sample dev data. The database file is `expense_tracker.db` (gitignored). Use plain `sqlite3`; there is no ORM.
- `templates/` uses Jinja inheritance from `base.html`, which provides the navbar, footer, and the `title`, `head`, `content`, and `scripts` blocks. Link with `url_for('<endpoint>')`.
- `login.html` and `register.html` already `POST` to `/login` and `/register`, but those routes only accept `GET` so far. Submitting the forms will fail with 405 until auth is implemented.
- `static/css/style.css` is a single stylesheet for every page. The fonts are DM Serif Display and DM Sans from Google Fonts.
- `static/js/main.js` is a single script loaded on every page. Each feature is wrapped in an IIFE that returns early when its DOM elements are missing (see the landing-page video modal). Follow that pattern for page-specific JS.

## Conventions

- Commit messages: `feat(scope): message` / `feat: message`.
- `.env` is gitignored; do not read or commit it.
