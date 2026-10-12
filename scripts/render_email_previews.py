#!/usr/bin/env python3
"""Render every e-mail template with sample data for review.

    ./venv/bin/python scripts/render_email_previews.py

Writes tmp/email-previews/<name>.html and <name>.txt (git-ignored). The HTML
references the logo at PUBLIC_BASE_URL/images/logo-email.png, so set
PUBLIC_BASE_URL=http://localhost:3000 to see a local logo.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.config import settings  # noqa: E402
from app.email.templates import months_pl, render  # noqa: E402

SAMPLE_TOKEN = "PRZYKLADOWY-TOKEN"


def samples() -> dict[str, tuple[str, dict]]:
    base = settings.public_base_url.rstrip("/")
    manage = f"{base}/rodzic?t={SAMPLE_TOKEN}"
    consent = f"{base}/rodzic/zgoda?t={SAMPLE_TOKEN}"
    return {
        "consent_request": (
            "Prośba o zgodę — konto Twojego dziecka w serwisie Trener OMJ",
            {
                "child_identifier_label": "Konto Google dziecka",
                "child_identifier": "jan.kowalski.2013@gmail.com",
                "consent_url": consent,
                "decline_url": f"{consent}&decyzja=nie",
                "manage_url": manage,
                "submission_retention": months_pl(settings.retention_submission_months or 24),
                "inactive_retention": months_pl(settings.retention_inactive_account_months or 36),
                "deadline": "26 października 2026",
            },
        ),
        "consent_request_login": (
            "Prośba o zgodę — konto Twojego dziecka w serwisie Trener OMJ",
            {
                "child_identifier_label": "Login dziecka",
                "child_identifier": "kuba_m",
                "consent_url": consent,
                "decline_url": f"{consent}&decyzja=nie",
                "manage_url": manage,
                "submission_retention": months_pl(settings.retention_submission_months or 24),
                "inactive_retention": months_pl(settings.retention_inactive_account_months or 36),
                "deadline": "26 października 2026",
            },
        ),
        "account_active": (
            "Konto Twojego dziecka jest aktywne",
            {
                "child_identifier_label": "Login dziecka",
                "child_identifier": "kuba_m",
                "is_login_account": True,
                "manage_url": manage,
            },
        ),
        "password_reset": (
            "Zmiana hasła — konto kuba_m",
            {"login": "kuba_m", "reset_url": f"{base}/reset-hasla/nowe?t={SAMPLE_TOKEN}", "manage_url": manage},
        ),
        "manage_link": ("Link do strony rodzica — Trener OMJ", {"manage_url": manage}),
    }


def main() -> None:
    out = ROOT / "tmp" / "email-previews"
    out.mkdir(parents=True, exist_ok=True)
    for name, (subject, context) in samples().items():
        template = name.removesuffix("_login")
        html, text = render(template, subject=subject, **context)
        (out / f"{name}.html").write_text(html, encoding="utf-8")
        (out / f"{name}.txt").write_text(f"Subject: {subject}\n\n{text}", encoding="utf-8")
        print(out / f"{name}.html")


if __name__ == "__main__":
    main()
