"""Cross-site request forgery: the Origin / Sec-Fetch-Site guard, SameSite=Lax
session cookie and logout by POST (security audit 2026-10)."""

import pytest
from starlette.middleware.sessions import SessionMiddleware

import app.main as main
from app.csrf import CrossSiteRequestGuard, request_allowed, trusted_netlocs
from app.db.models import UserDB

from accounts_support import *  # noqa: F401,F403 - fixtures
from accounts_support import PASSWORD, me, register_login, user_by_login

TRUSTED = trusted_netlocs(("https://omj-validator.pl", "http://localhost:3200", None))


def allowed(method="POST", scheme="https", **headers):
    return request_allowed(method, {k.replace("_", "-"): v for k, v in headers.items()}, scheme, TRUSTED)


class TestRequestAllowed:
    @pytest.mark.parametrize("method", ["GET", "HEAD", "OPTIONS"])
    def test_safe_methods_always_pass(self, method):
        assert allowed(method, origin="https://evil.example", sec_fetch_site="cross-site")

    @pytest.mark.parametrize("method", ["POST", "PUT", "PATCH", "DELETE"])
    def test_cross_site_origin_is_refused(self, method):
        assert not allowed(method, host="omj-validator.pl", origin="https://evil.example")

    def test_same_host_passes(self):
        assert allowed(host="omj-validator.pl", origin="https://omj-validator.pl")

    def test_host_comparison_ignores_default_port_and_case(self):
        assert allowed(host="OMJ-validator.pl:443", origin="https://omj-validator.pl")

    def test_proxy_forwarded_host_passes(self):
        """Next.js rewrites to http://api:8100 and keeps the browser's host in X-Forwarded-Host."""
        assert allowed(scheme="http", host="api:8100", x_forwarded_host="localhost:3000",
                       x_forwarded_proto="http", origin="http://localhost:3000")

    def test_trusted_origins_pass(self):
        assert allowed(host="api:8100", origin="https://omj-validator.pl")
        assert allowed(host="api:8100", origin="http://localhost:3200")

    def test_sibling_subdomain_is_not_same_origin(self):
        assert not allowed(host="omj-validator.pl", origin="https://evil.omj-validator.pl")
        assert not allowed(host="omj-validator.pl", origin="https://omj-validator.pl.evil.example")

    def test_other_port_is_another_origin(self):
        assert not allowed(host="localhost:8000", origin="http://localhost:9999")

    @pytest.mark.parametrize("origin", ["null", "", "file://", "omj-validator.pl", "javascript:alert(1)"])
    def test_opaque_or_garbage_origin_is_refused(self, origin):
        assert not allowed(host="omj-validator.pl", origin=origin)

    @pytest.mark.parametrize("site", ["cross-site", "same-site", "Cross-Site"])
    def test_no_origin_but_cross_site_fetch_metadata_is_refused(self, site):
        assert not allowed(host="omj-validator.pl", sec_fetch_site=site)

    @pytest.mark.parametrize("site", ["same-origin", "none"])
    def test_no_origin_same_origin_fetch_metadata_passes(self, site):
        assert allowed(host="omj-validator.pl", sec_fetch_site=site)

    def test_non_browser_client_passes(self):
        """No Origin and no Sec-Fetch-Site: curl, server-side code - not a CSRF vector."""
        assert allowed(host="omj-validator.pl")

    def test_origin_decides_over_fetch_metadata(self):
        """A split deployment's frontend is cross-site but trusted."""
        assert allowed(host="api.example", origin="http://localhost:3200", sec_fetch_site="cross-site")


EVIL = {"origin": "https://evil.example", "sec-fetch-site": "cross-site"}


class TestGuardOnTheApp:
    def test_guard_is_installed_outside_the_session(self):
        classes = [m.cls for m in main.app.user_middleware]
        assert CrossSiteRequestGuard in classes
        assert classes.index(CrossSiteRequestGuard) < classes.index(SessionMiddleware)

    def test_forged_json_post_is_refused(self, client, db):
        response = client.post(
            "/api/auth/register/login",
            headers=EVIL,
            json={"birth_year": 2013, "login": "kuba_m", "password": PASSWORD, "parent_email": "m@example.com"},
        )
        assert response.status_code == 403
        assert response.json()["code"] == "cross_site"
        assert db.query(UserDB).count() == 0

    def test_forged_multipart_submit_is_refused(self, client, db):
        response = client.post(
            "/task/2024/etap1/1/submit",
            headers=EVIL,
            data={"solution_text": "x"},
            files={"images": ("a.jpg", b"\xff\xd8\xff", "image/jpeg")},
        )
        assert response.status_code == 403
        assert response.json()["code"] == "cross_site"

    def test_forged_bodyless_post_is_refused(self, client, db):
        register_login(client)
        response = client.post("/api/account/consent/resend", headers={"sec-fetch-site": "cross-site"})
        assert response.status_code == 403

    def test_same_origin_post_passes(self, client, db):
        response = client.post(
            "/api/auth/register/login",
            headers={"origin": "https://testserver", "sec-fetch-site": "same-origin"},
            json={"birth_year": 2013, "login": "kuba_m", "password": PASSWORD, "parent_email": "m@example.com"},
        )
        assert response.status_code == 200, response.text

    def test_preflight_and_reads_pass(self, client, db):
        assert client.get("/api/auth/me", headers=EVIL).status_code == 200

    def test_refusal_does_not_log_the_query_string(self, client, db, caplog):
        client.post("/api/parent/consent?t=secret-token", headers=EVIL, json={})
        assert "secret-token" not in caplog.text
        assert "/api/parent/consent" in caplog.text


class TestSessionCookie:
    def test_prod_like_frontend_url_alone_is_not_a_split_deployment(self):
        assert main.settings.split_deployment is False
        assert main.is_split_deployment is False

    def test_session_cookie_is_samesite_lax(self, client, db):
        response = register_login(client)
        cookie = response.headers["set-cookie"].lower()
        assert "samesite=lax" in cookie
        assert "httponly" in cookie
        # Secure is decided at import from AUTH_DISABLED (a local .env may set it)
        session_mw = next(m for m in main.app.user_middleware if m.cls is SessionMiddleware)
        if session_mw.kwargs["https_only"]:
            assert "secure" in cookie


class TestLogout:
    def _logged_in(self, client, db):
        register_login(client)
        assert me(client)["is_authenticated"] is True

    def test_post_logs_out(self, client, db):
        self._logged_in(client, db)
        response = client.post("/logout", headers={"origin": "https://testserver"}, follow_redirects=False)
        assert response.status_code == 303 and response.headers["location"] == "/years"
        assert me(client)["is_authenticated"] is False

    def test_pending_account_can_log_out(self, client, db):
        """The account from register_login waits for its parent: logging out
        must not be one of the writes a pending account is refused."""
        self._logged_in(client, db)
        assert user_by_login(db, "kuba_m").status == "pending_parent"
        client.post("/logout", follow_redirects=False)
        assert me(client)["is_authenticated"] is False

    def test_forged_post_does_not_log_out(self, client, db):
        self._logged_in(client, db)
        assert client.post("/logout", headers=EVIL, follow_redirects=False).status_code == 403
        assert me(client)["is_authenticated"] is True

    @pytest.mark.parametrize("site", ["cross-site", "same-site", None])
    def test_get_from_elsewhere_does_not_log_out(self, client, db, site):
        self._logged_in(client, db)
        headers = {"sec-fetch-site": site} if site else {}
        response = client.get("/logout", headers=headers, follow_redirects=False)
        assert response.status_code == 303
        assert me(client)["is_authenticated"] is True

    @pytest.mark.parametrize("site", ["same-origin", "none"])
    def test_get_from_this_site_still_logs_out(self, client, db, site):
        self._logged_in(client, db)
        client.get("/logout", headers={"sec-fetch-site": site}, follow_redirects=False)
        assert me(client)["is_authenticated"] is False
        assert user_by_login(db, "kuba_m") is not None
