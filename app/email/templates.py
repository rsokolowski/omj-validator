"""Rendering of the e-mail templates in templates/email/ (HTML + plain text).

Every message is a pair: ``<name>.html`` (extends layout.html, email-safe:
tables, inline styles, no external CSS, no data-URI images) and
``<name>.txt``. Both get the same context plus the shared values below.
"""

from functools import lru_cache

from jinja2 import Environment, FileSystemLoader, StrictUndefined, select_autoescape

from ..config import settings

# The name the site uses; also the sender name (EMAIL_FROM) and the subjects
APP_NAME = "Trener OMJ"
OPERATOR_NAME = "Rafał Sokołowski"


# Zero-width space: invisible, but no linkifier treats it as part of a domain
_ZWSP = "\u200b"


def nolink(value) -> str:
    """Text a mail client must not turn into a link: a zero-width space after
    every "." and "@". For identifiers someone typed at registration (a login
    created while dots were allowed, e.g. "www.example.com", or an address)
    that a parent's mail client would otherwise auto-link."""
    return str(value).replace(".", "." + _ZWSP).replace("@", "@" + _ZWSP)


@lru_cache(maxsize=1)
def _env() -> Environment:
    env = Environment(
        loader=FileSystemLoader(str(settings.base_dir / "templates" / "email")),
        autoescape=select_autoescape(enabled_extensions=("html",), default_for_string=False),
        undefined=StrictUndefined,
        trim_blocks=True,
        lstrip_blocks=True,
        keep_trailing_newline=True,
    )
    env.filters["nolink"] = nolink
    return env


def base_url() -> str:
    return settings.public_base_url.rstrip("/")


def months_pl(n: int) -> str:
    """'24 miesiące', '36 miesięcy', '1 miesiąc'."""
    if n == 1:
        return "1 miesiąc"
    if n % 10 in (2, 3, 4) and n % 100 not in (12, 13, 14):
        return f"{n} miesiące"
    return f"{n} miesięcy"


def shared_context() -> dict:
    base = base_url()
    return {
        "app_name": APP_NAME,
        "operator_name": OPERATOR_NAME,
        "base_url": base,
        "site_label": base.split("://", 1)[-1],
        "logo_url": f"{base}/images/logo-email.png",
        "terms_url": f"{base}/regulamin",
        "parent_page_url": f"{base}/rodzic",
        "contact_email": settings.email_reply_to,
    }


def render(name: str, **context) -> tuple[str, str]:
    """Return (html, text) for templates/email/<name>.html / .txt."""
    env = _env()
    values = {**shared_context(), **context}
    html = env.get_template(f"{name}.html").render(**values)
    text = env.get_template(f"{name}.txt").render(**values)
    return html, text
