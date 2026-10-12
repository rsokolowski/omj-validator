"""The guard on write endpoints: an account waiting for parent consent (or for
its year of birth) can read but not write.

The route-table test walks every write route of the app, so a new endpoint
that is not guarded - or a new exemption nobody reviewed - fails here.
"""

import re

import pytest
from fastapi.routing import APIRoute

import app.main as main
from app.db.models import UserDB

from accounts_support import *  # noqa: F401,F403 - fixtures
from accounts_support import register_login, signed_cookie

WRITE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}

# Write endpoints a pending / incomplete account may call. Adding one here is
# a deliberate decision: it must be about the account's own lifecycle.
EXEMPT = {
    ("POST", "/api/account/delete"),
    ("POST", "/api/account/consent/resend"),
    ("POST", "/api/account/parent-email"),
    ("POST", "/api/auth/login"),
    ("POST", "/api/auth/profile"),
    ("POST", "/api/auth/register/google"),
    ("POST", "/api/auth/register/login"),
    ("POST", "/api/auth/password-reset/request"),
    ("POST", "/api/auth/password-reset/confirm"),
    ("POST", "/api/parent/consent"),
    ("POST", "/api/parent/consent/resend"),
    ("POST", "/api/parent/request-link"),
    ("POST", "/api/parent/children/{child_id}/delete"),
    ("POST", "/api/parent/children/{child_id}/password"),
}

SAMPLE_PARAMS = {"year": "2024", "etap": "etap1", "num": "1", "n": "1", "link_id": "1"}


def api_routes(routes):
    """Every APIRoute, including those of included routers (FastAPI keeps
    those behind a lazy wrapper with the original router inside)."""
    for route in routes:
        if isinstance(route, APIRoute):
            yield route
        elif hasattr(route, "original_router"):
            yield from api_routes(route.original_router.routes)


def write_routes():
    for route in api_routes(main.app.routes):
        for method in sorted(route.methods & WRITE_METHODS):
            yield method, route


def test_route_walk_sees_the_included_routers():
    paths = {route.path for route in api_routes(main.app.routes)}
    assert "/api/private-tasks/{task_id}/submit" in paths
    assert "/api/patterns/refine" in paths
    assert "/api/auth/register/login" in paths


def concrete_path(path: str) -> str:
    return re.sub(r"\{(\w+)(?::\w+)?\}", lambda m: SAMPLE_PARAMS.get(m.group(1), "abcdefghijkl"), path)


def guarded_routes():
    return [
        pytest.param(method, route.path, id=f"{method} {route.path}")
        for method, route in write_routes()
        if (method, route.path) not in EXEMPT
    ]


def test_exemptions_are_exactly_the_reviewed_list():
    marked = {
        (method, route.path)
        for method, route in write_routes()
        if getattr(route.endpoint, "__allow_inactive_account__", False)
    }
    assert marked == EXEMPT


@pytest.fixture
def pending_client(client, db):
    register_login(client)
    return client


@pytest.fixture
def incomplete_client(client, db):
    db.add(UserDB(id="old", google_sub="old", email="old@gmail.com"))
    db.commit()
    client.cookies.set("session", signed_cookie({"user": {"google_sub": "old", "is_group_member": True}}))
    return client


@pytest.mark.parametrize("method, path", guarded_routes())
def test_pending_account_cannot_write(pending_client, method, path):
    response = pending_client.request(method, concrete_path(path))
    assert response.status_code == 403, response.text
    assert response.json()["code"] == "parent_consent_pending"


@pytest.mark.parametrize("method, path", guarded_routes())
def test_incomplete_account_cannot_write(incomplete_client, method, path):
    response = incomplete_client.request(method, concrete_path(path))
    assert response.status_code == 403, response.text
    assert response.json()["code"] == "profile_incomplete"


def test_pending_account_can_read(pending_client):
    assert pending_client.get("/api/auth/me").status_code == 200
    assert pending_client.get("/api/years").status_code == 200


def test_pending_account_can_delete_itself(pending_client, db):
    response = pending_client.post("/api/account/delete", json={"confirmation": "USUWAM KONTO"})
    assert response.status_code == 200, response.text
    assert db.query(UserDB).count() == 0


def test_active_account_passes_the_guard(client, db):
    db.add(UserDB(id="a1", google_sub="a1", email="a@gmail.com", birth_year=2000))
    db.commit()
    client.cookies.set("session", signed_cookie({"user": {"user_id": "a1", "session_version": 0, "is_group_member": True}}))
    # Reaches the endpoint (its own validation answers), not the guard
    response = client.post("/api/patterns", json={})
    assert response.status_code == 422


def test_anonymous_requests_reach_the_endpoints_own_auth(client):
    response = client.post("/api/patterns", json={})
    assert response.status_code in (401, 422)
