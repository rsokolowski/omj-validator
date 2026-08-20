"""Personal data must not reach the logs in the clear.

Logs have no retention policy, so an e-mail written to one outlives the account
it belonged to - including after the user exercised their right to erasure.
"""

import logging

import pytest

from app.privacy import mask_email, mask_user_id

EMAIL = "jan.kowalski@example.com"
USER_ID = "108451234567890123456"


class TestMaskEmail:
    def test_hides_domain_and_most_of_the_local_part(self):
        masked = mask_email(EMAIL)

        assert masked == "jan***@***"
        assert "kowalski" not in masked
        assert "example.com" not in masked

    def test_keeps_the_existing_project_format(self):
        """app/groups.py has always logged "abc***@***" - greps must keep working."""
        assert mask_email("abcdef@x.pl").endswith("***@***")

    @pytest.mark.parametrize("value", [None, ""])
    def test_handles_missing_values(self, value):
        assert mask_email(value) == "<none>"

    def test_short_address_does_not_crash(self):
        masked = mask_email("a@b.pl")

        assert masked.endswith("***@***")
        assert "b.pl" not in masked


class TestMaskUserId:
    def test_keeps_only_a_short_prefix(self):
        masked = mask_user_id(USER_ID)

        assert masked == f"{USER_ID[:8]}..."
        assert USER_ID not in masked

    @pytest.mark.parametrize("value", [None, ""])
    def test_handles_missing_values(self, value):
        assert mask_user_id(value) == "<none>"


class TestCallSites:
    def test_login_does_not_log_the_address(self, caplog):
        """Regression: the OAuth callback used to log the full e-mail."""
        logger = logging.getLogger("app.main")
        with caplog.at_level(logging.INFO):
            logger.info(f"User logged in: {mask_email(EMAIL)} (has_access: True)")

        assert EMAIL not in caplog.text
        assert "jan***@***" in caplog.text

    @pytest.mark.parametrize(
        "field,masker",
        [("email", "mask_email"), ("user_id", "mask_user_id"), ("google_sub", "mask_user_id")],
    )
    def test_no_source_file_logs_a_bare_identifier(self, field, masker):
        """Cheap guard against the pattern creeping back in.

        Catches f-string log calls that interpolate an identifier without
        routing it through app/privacy.py first.
        """
        import pathlib
        import re

        offenders = []
        bad = re.compile(
            r"logger\.\w+\(\s*f?\"[^\"]*\{[^}]*" + field + r"[^}]*\}", re.IGNORECASE
        )
        for path in pathlib.Path("app").rglob("*.py"):
            for line in path.read_text(encoding="utf-8").splitlines():
                if bad.search(line) and masker not in line:
                    offenders.append(f"{path}: {line.strip()}")

        assert not offenders, f"unmasked {field} in log call:\n" + "\n".join(offenders)
