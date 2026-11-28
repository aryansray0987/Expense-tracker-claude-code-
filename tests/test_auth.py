import database.db as db


def test_register_creates_user_with_hashed_password(client, register):
    response = register()

    assert response.status_code == 302
    assert response.headers["Location"] == "/profile"

    conn = db.get_db()
    user = conn.execute(
        "SELECT * FROM users WHERE email = ?", ("test@example.com",)
    ).fetchone()
    conn.close()
    assert user["name"] == "Test User"
    assert user["password_hash"] != "password123"

    with client.session_transaction() as session:
        assert session["user_id"] == user["id"]


def test_register_normalizes_email(register):
    register(email="  Test@Example.COM ")

    conn = db.get_db()
    count = conn.execute(
        "SELECT COUNT(*) FROM users WHERE email = ?", ("test@example.com",)
    ).fetchone()[0]
    conn.close()
    assert count == 1


def test_register_rejects_duplicate_email(client, register):
    register()
    client.get("/logout")  # registering signs you in; sign out to try again
    response = register(name="Someone Else")

    assert response.status_code == 200
    assert b"already exists" in response.data


def test_register_rejects_short_password(register):
    response = register(password="short")

    assert response.status_code == 200
    assert b"at least 8 characters" in response.data


def test_register_rejects_missing_fields(register):
    response = register(name="  ")

    assert response.status_code == 200
    assert b"All fields are required" in response.data


def test_register_keeps_typed_values_on_error(register):
    response = register(password="short")

    assert b'value="Test User"' in response.data
    assert b'value="test@example.com"' in response.data


def test_login_success(client, register):
    register()
    with client.session_transaction() as session:  # start logged out
        session.clear()

    response = client.post(
        "/login", data={"email": "TEST@example.com", "password": "password123"}
    )

    assert response.status_code == 302
    assert response.headers["Location"] == "/profile"
    with client.session_transaction() as session:
        assert "user_id" in session


def test_login_wrong_password(client, register):
    register()
    with client.session_transaction() as session:
        session.clear()

    response = client.post(
        "/login", data={"email": "test@example.com", "password": "wrongpass1"}
    )

    assert response.status_code == 200
    assert b"Invalid email or password" in response.data
    with client.session_transaction() as session:
        assert "user_id" not in session


def test_login_unknown_email_gives_same_error(client):
    response = client.post(
        "/login", data={"email": "nobody@example.com", "password": "password123"}
    )

    assert response.status_code == 200
    assert b"Invalid email or password" in response.data


def test_get_pages_still_render(client):
    assert client.get("/login").status_code == 200
    assert client.get("/register").status_code == 200
