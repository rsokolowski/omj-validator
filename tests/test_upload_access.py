"""/uploads/{path} may only ever serve the caller's own files (or an admin's view).

The owner check looked at the first path segment only, so a path starting
with your own id and then climbing out with ".." reached another user's
photos - now including the problem photos of their private tasks.
"""

import pytest
from fastapi.testclient import TestClient

import app.main as main
from app.config import settings

USER_ID = "user-1"
OTHER_ID = "user-2"


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "data_dir", str(tmp_path))
    monkeypatch.setattr(settings, "admin_emails", None)
    for owner in (USER_ID, OTHER_ID):
        photo = settings.uploads_dir / owner / "private" / "abcdefghijkl" / "source" / "p.jpg"
        photo.parent.mkdir(parents=True)
        photo.write_bytes(f"photo of {owner}".encode())
    monkeypatch.setattr(main, "require_auth_redirect", lambda request: None)
    monkeypatch.setattr(main, "get_current_user_id", lambda request: USER_ID)
    monkeypatch.setattr(main, "get_current_user", lambda request: {"google_sub": USER_ID, "email": "a@example.com"})
    return TestClient(main.app)


def test_own_private_photo_is_served(client):
    response = client.get(f"/uploads/{USER_ID}/private/abcdefghijkl/source/p.jpg")
    assert response.status_code == 200
    assert response.content == f"photo of {USER_ID}".encode()


@pytest.mark.parametrize("path", [
    f"/uploads/{USER_ID}/..%2F{OTHER_ID}/private/abcdefghijkl/source/p.jpg",
    f"/uploads/{USER_ID}/%2E%2E/{OTHER_ID}/private/abcdefghijkl/source/p.jpg",
])
def test_climbing_into_another_users_folder_is_refused(client, path):
    response = client.get(path)
    assert response.status_code in (403, 404)
    assert f"photo of {OTHER_ID}".encode() not in response.content
