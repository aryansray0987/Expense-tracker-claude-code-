import pytest

PROTECTED_URLS = ["/profile", "/expenses/add", "/expenses/1/edit", "/expenses/1/delete"]


def test_logout_clears_session_and_redirects_home(client, register):
    register()

    response = client.get("/logout")

    assert response.status_code == 302
    assert response.headers["Location"] == "/"
    with client.session_transaction() as session:
        assert "user_id" not in session


def test_logout_when_signed_out_is_harmless(client):
    response = client.get("/logout")

    assert response.status_code == 302
    assert response.headers["Location"] == "/"


@pytest.mark.parametrize("url", PROTECTED_URLS)
def test_protected_pages_redirect_to_login_when_signed_out(client, url):
    response = client.get(url)

    assert response.status_code == 302
    assert response.headers["Location"] == "/login"


@pytest.mark.parametrize("url", PROTECTED_URLS)
def test_protected_pages_load_when_signed_in(client, register, url):
    register()

    assert client.get(url).status_code == 200


def test_after_logout_protected_pages_redirect_again(client, register):
    register()
    client.get("/logout")

    assert client.get("/profile").headers["Location"] == "/login"


@pytest.mark.parametrize("url", ["/login", "/register"])
def test_signed_in_users_skip_login_and_register(client, register, url):
    register()

    response = client.get(url)

    assert response.status_code == 302
    assert response.headers["Location"] == "/profile"


def test_navbar_shows_sign_in_when_signed_out(client):
    html = client.get("/").data

    assert b"Sign in" in html
    assert b"Log out" not in html


def test_navbar_shows_name_and_logout_when_signed_in(client, register):
    register(name="Asha Rao")

    html = client.get("/").data

    assert b"Asha Rao" in html
    assert b"Log out" in html
    assert b"Sign in" not in html
