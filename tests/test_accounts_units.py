"""Pure rules of the account feature: age arithmetic, logins, passwords."""

import pytest

from app.accounts import age, passwords
from app.privacy import mask_email_for_display


class TestAge:
    def test_offered_years(self):
        years = age.allowed_birth_years(2026)
        assert years[0] == 1926
        assert years[-1] == 2020
        assert 2021 not in years

    @pytest.mark.parametrize("birth_year, expected", [(2009, True), (2000, True), (2011, False), (2020, False)])
    def test_clear_cases_need_no_follow_up(self, birth_year, expected):
        assert age.can_consent_alone(birth_year, None, year=2026) is expected

    def test_sixteen_this_year_is_ambiguous(self):
        assert age.is_ambiguous(2010, 2026)
        assert not age.is_ambiguous(2009, 2026)
        with pytest.raises(age.AgeAnswerError):
            age.can_consent_alone(2010, None, year=2026)

    def test_sixteen_this_year_follows_the_answer(self):
        assert age.can_consent_alone(2010, True, year=2026) is True
        assert age.can_consent_alone(2010, False, year=2026) is False

    def test_follow_up_answer_ignored_when_not_ambiguous(self):
        assert age.can_consent_alone(2012, True, year=2026) is False

    @pytest.mark.parametrize("birth_year", [1925, 2021, 2030])
    def test_years_outside_the_select_are_refused(self, birth_year):
        with pytest.raises(age.AgeAnswerError):
            age.can_consent_alone(birth_year, True, year=2026)


class TestLogin:
    @pytest.mark.parametrize("login", ["abc", "kuba_m", "a.b-c_1", "x" * 32, "007"])
    def test_valid(self, login):
        assert passwords.login_problem(login) is None

    @pytest.mark.parametrize(
        "login", ["ab", "x" * 33, "_kuba", "kuba m", "żaba", "kuba@", ".abc"]
    )
    def test_invalid(self, login):
        assert passwords.login_problem(login) is not None

    def test_normalised_lower_case(self):
        assert passwords.normalize_login("  Kuba_M ") == "kuba_m"


class TestPassword:
    def test_minimum_length(self):
        assert passwords.password_problem("krotkie") is not None
        assert passwords.password_problem("dobre haslo kota") is None

    @pytest.mark.parametrize("common", ["password", "12345678", "qwertyuiop", "Password1", "zaq12wsx"])
    def test_common_passwords_refused(self, common):
        assert "popularne" in passwords.password_problem(common)

    def test_not_equal_to_login(self):
        assert "login" in passwords.password_problem("Kuba_Mazur", "kuba_mazur")

    def test_no_composition_rules(self):
        assert passwords.password_problem("zielony rower w lesie") is None

    def test_hash_is_argon2id_and_verifies(self):
        hashed = passwords.hash_password("zielony rower w lesie")
        assert hashed.startswith("$argon2id$")
        assert passwords.verify_password(hashed, "zielony rower w lesie")
        assert not passwords.verify_password(hashed, "zielony rower w lesie!")

    def test_missing_hash_never_verifies(self):
        assert passwords.verify_password(None, "anything at all") is False


def test_display_mask_keeps_domain_only():
    assert mask_email_for_display("anna.nowak@gmail.com") == "a***@gmail.com"
    assert mask_email_for_display(None) == ""
