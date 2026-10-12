"""Cross-site request forgery guard: unsafe-method requests (POST, PUT, PATCH,
DELETE) must come from this site.

The session cookie is SameSite=Lax, which already keeps it off cross-site
POSTs in current browsers. This is the second layer, independent of cookie
attributes and of how a browser treats a "same-site" sibling domain:

- With an ``Origin`` header (every browser sends one on a cross-origin POST,
  and on same-origin ones too) the origin must be this site: the host the
  request was made to (``Host`` / ``X-Forwarded-Host`` - the Next.js proxy
  sets the latter), ``PUBLIC_BASE_URL`` or ``FRONTEND_URL``. ``Origin: null``
  (sandboxed frames, some redirects) is refused.
- Without ``Origin``, ``Sec-Fetch-Site`` decides when present: only
  ``same-origin`` and ``none`` (typed by the user) pass.
- Without either header the request did not come from a modern browser page
  (curl, server-side code, the test client) - no CSRF is possible through it,
  so it passes.

A page on another site cannot set ``Origin`` or ``Sec-Fetch-Site``, and it
cannot add ``X-Forwarded-Host`` without a CORS preflight, which this API does
not grant to other origins.

Websockets are not covered here (their handshake is a GET); the session
cookie is not sent on a cross-site handshake (SameSite=Lax).
"""

import json
import logging
from typing import Iterable, Optional
from urllib.parse import urlsplit

logger = logging.getLogger(__name__)

SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS", "TRACE"})
ALLOWED_FETCH_SITES = frozenset({"same-origin", "none"})

REJECTED_DETAIL = "To żądanie przyszło z innej strony, więc zostało zablokowane. Odśwież stronę i spróbuj ponownie."


def _netloc(url: Optional[str]) -> Optional[str]:
    """'host[:port]' of an absolute URL, lower case; None when there is none."""
    if not url:
        return None
    try:
        parts = urlsplit(url.strip())
    except ValueError:
        return None
    if parts.scheme not in ("http", "https") or not parts.hostname:
        return None
    netloc = parts.hostname.lower()
    if parts.port is not None:
        default = 443 if parts.scheme == "https" else 80
        if parts.port != default:
            netloc = f"{netloc}:{parts.port}"
    return netloc


def _host_netloc(value: str, scheme: str) -> Optional[str]:
    """Normalise a Host-style header value the same way as _netloc."""
    first = value.split(",")[0].strip()
    return _netloc(f"{scheme}://{first}") if first else None


def trusted_netlocs(origins: Iterable[Optional[str]]) -> frozenset:
    return frozenset(n for n in (_netloc(o) for o in origins) if n)


def request_allowed(
    method: str,
    headers: dict[str, str],
    scheme: str,
    trusted: frozenset,
) -> bool:
    """Whether an HTTP request may proceed (headers: lower-case names;
    trusted: netlocs from trusted_netlocs)."""
    if method.upper() in SAFE_METHODS:
        return True
    origin = headers.get("origin")
    if origin is not None:
        origin_netloc = _netloc(origin)
        if origin_netloc is None:  # "null" or garbage
            return False
        allowed = set(trusted)
        for header in ("host", "x-forwarded-host"):
            value = headers.get(header)
            if value:
                own = _host_netloc(value, headers.get("x-forwarded-proto", scheme).split(",")[0].strip())
                if own:
                    allowed.add(own)
        return origin_netloc in allowed
    fetch_site = headers.get("sec-fetch-site")
    if fetch_site is not None:
        return fetch_site.strip().lower() in ALLOWED_FETCH_SITES
    return True


class CrossSiteRequestGuard:
    """Pure ASGI middleware (does not touch websockets or streaming bodies)."""

    def __init__(self, app, trusted_origins: Iterable[str] = ()):
        self.app = app
        self.trusted = trusted_netlocs(trusted_origins)

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        headers = {k.decode("latin-1").lower(): v.decode("latin-1") for k, v in scope.get("headers", [])}
        if request_allowed(scope["method"], headers, scope.get("scheme", "http"), self.trusted):
            await self.app(scope, receive, send)
            return
        # Path only (never the query string): some carry tokens
        logger.warning(
            f"Blocked cross-site {scope['method']} {scope.get('path', '')} "
            f"(origin={headers.get('origin')!r}, sec-fetch-site={headers.get('sec-fetch-site')!r})"
        )
        body = json.dumps({"detail": REJECTED_DETAIL, "code": "cross_site"}, ensure_ascii=False).encode("utf-8")
        await send(
            {
                "type": "http.response.start",
                "status": 403,
                "headers": [
                    (b"content-type", b"application/json; charset=utf-8"),
                    (b"content-length", str(len(body)).encode()),
                ],
            }
        )
        await send({"type": "http.response.body", "body": body})
