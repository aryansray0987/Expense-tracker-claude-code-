import pytest

import database.db as db
from app import app as flask_app


@pytest.fixture
def app(tmp_path, monkeypatch):
    # Point the app at a throwaway database for each test.
    monkeypatch.setattr(db, "DB_PATH", str(tmp_path / "test.db"))
    db.init_db()
    flask_app.config.update(TESTING=True)
    yield flask_app


@pytest.fixture
def register(client):
    def _register(name="Test User", email="test@example.com", password="password123"):
        return client.post(
            "/register", data={"name": name, "email": email, "password": password}
        )

    return _register
