"""Logins and passwords of login accounts (children without an e-mail).

Rules (NIST SP 800-63B style, no composition rules): at least 8 characters,
not one of the most common passwords, not the login itself. Hashes are
argon2id (argon2-cffi defaults).
"""

import re
from functools import lru_cache
from pathlib import Path
from typing import Optional

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

# No dots in NEW logins: the login is shown in e-mails to the parent, and
# "www.example.com" would turn into a link there. Accounts created while dots
# were allowed keep their login - signing in never re-checks this rule.
LOGIN_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{2,31}$")
LOGIN_MIN, LOGIN_MAX = 3, 32
PASSWORD_MIN = 8
# argon2 hashes anything, but a megabyte "password" is a cheap DoS
PASSWORD_MAX = 200

_COMMON_PASSWORDS_FILE = Path(__file__).parent / "data" / "common-passwords.txt"
_hasher = PasswordHasher()
# Verified against for unknown logins so both answers take the same time
_DUMMY_HASH = _hasher.hash("not-a-real-password-just-timing")


def normalize_login(login: Optional[str]) -> str:
    return (login or "").strip().lower()


def login_problem(login: str) -> Optional[str]:
    """Polish message describing what is wrong with a new (normalised) login."""
    if len(login) < LOGIN_MIN:
        return "Login musi mieć co najmniej 3 znaki."
    if len(login) > LOGIN_MAX:
        return "Login może mieć najwyżej 32 znaki."
    if not LOGIN_RE.match(login):
        if not login[0].isalnum() or not login[0].isascii():
            return "Login musi zaczynać się od litery lub cyfry."
        return "Login może zawierać tylko litery bez polskich znaków, cyfry oraz znaki _ i -"
    return None


@lru_cache(maxsize=1)
def _common_passwords() -> frozenset:
    lines = _COMMON_PASSWORDS_FILE.read_text(encoding="utf-8").splitlines()
    return frozenset(line.strip() for line in lines if line.strip() and not line.startswith("#"))


def password_problem(password: Optional[str], login: Optional[str] = None) -> Optional[str]:
    """Polish message describing why a password is refused, or None."""
    password = password or ""
    if len(password) < PASSWORD_MIN:
        return "Hasło musi mieć co najmniej 8 znaków."
    if len(password) > PASSWORD_MAX:
        return "Hasło może mieć najwyżej 200 znaków."
    if login and password.strip().lower() == normalize_login(login):
        return "Hasło nie może być takie samo jak login."
    if password.lower() in _common_passwords():
        return "To hasło jest zbyt popularne i łatwe do odgadnięcia. Wymyśl inne."
    return None


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password_hash: Optional[str], password: str) -> bool:
    """Constant-ish time check; an absent hash still costs one verification."""
    try:
        return _hasher.verify(password_hash or _DUMMY_HASH, password) and bool(password_hash)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def needs_rehash(password_hash: str) -> bool:
    try:
        return _hasher.check_needs_rehash(password_hash)
    except InvalidHashError:
        return False
