"""The rules both submit endpoints apply to a typed solution before touching the disk.

normalize_solution_text mirrors normalizeSolutionText in
frontend/src/lib/utils/solutionText.ts - the counter in the browser and the cap
on the server must agree on what the text is and how long it is.
"""

import asyncio
import io

import pytest
from fastapi import UploadFile
from starlette.datastructures import Headers

from app.config import settings
from app.uploads import (
    normalize_solution_text,
    save_uploaded_images,
    validate_image_batch,
    validate_submission_input,
)


def upload(name: str = "a.jpg", content_type: str = "image/jpeg") -> UploadFile:
    return UploadFile(
        file=io.BytesIO(b"x"),
        filename=name,
        headers=Headers({"content-type": content_type}),
    )


def error_of(response) -> str:
    import json

    return json.loads(response.body)["error"]


class TestNormalize:
    def test_crlf_and_cr_become_lf(self):
        assert normalize_solution_text("a\r\nb\rc") == "a\nb\nc"

    def test_cr_only_and_nul(self):
        # Pasted from a PDF viewer: CR line endings and a NUL PostgreSQL would refuse
        assert normalize_solution_text("linia 1\rlinia 2\x00koniec") == "linia 1\nlinia 2koniec"

    def test_control_chars_dropped_except_tab_and_newline(self):
        assert normalize_solution_text("a\x00b\tc\x07d\n\x1be") == "ab\tcd\ne"

    def test_surrounding_whitespace_stripped(self):
        assert normalize_solution_text("  \n Niech $n$. \n\t") == "Niech $n$."

    def test_blank_is_none(self):
        assert normalize_solution_text("   \n\t ") is None
        assert normalize_solution_text("") is None
        assert normalize_solution_text(None) is None

    def test_polish_letters_and_latex_untouched(self):
        text = "Zatem $\\frac{a}{b} \\le 1$ – gdyż ąęśćżźół."
        assert normalize_solution_text(text) == text


class TestValidateSubmissionInput:
    def test_nothing_provided(self):
        text, error = validate_submission_input([], None)
        assert text is None
        assert error.status_code == 400
        assert error_of(error) == "Prześlij zdjęcia, rysunek albo wpisz rozwiązanie"

    def test_whitespace_only_text_counts_as_nothing(self):
        text, error = validate_submission_input([], "  \n ")
        assert text is None
        assert error.status_code == 400

    def test_text_only_is_normalised(self):
        text, error = validate_submission_input([], "  Niech $n$.\r\n")
        assert error is None
        assert text == "Niech $n$."

    def test_photos_only_gives_none_text(self):
        text, error = validate_submission_input([upload()], None)
        assert (text, error) == (None, None)

    def test_photos_and_text(self):
        text, error = validate_submission_input([upload()], "x")
        assert (text, error) == ("x", None)

    def test_over_cap(self, monkeypatch):
        monkeypatch.setattr(settings, "submission_text_max_chars", 5)
        text, error = validate_submission_input([], "abcdef")
        assert text is None
        assert error.status_code == 400
        assert error_of(error) == "Rozwiązanie jest za długie (maksymalnie 5 znaków)"

    def test_cap_message_uses_thin_thousands_separator(self, monkeypatch):
        monkeypatch.setattr(settings, "submission_text_max_chars", 20000)
        _, error = validate_submission_input([], "x" * 20001)
        assert error_of(error) == "Rozwiązanie jest za długie (maksymalnie 20 000 znaków)"

    def test_astral_characters_count_once(self, monkeypatch):
        """Code points, not UTF-16 units or bytes: the browser counter says 20 000."""
        monkeypatch.setattr(settings, "submission_text_max_chars", 20000)
        assert validate_submission_input([], "\U0001d465" * 20000)[1] is None
        assert validate_submission_input([], "\U0001d465" * 20001)[1].status_code == 400

    def test_too_many_images_keeps_old_message(self):
        _, error = validate_submission_input([upload(f"{i}.jpg") for i in range(11)], None)
        assert error.status_code == 400
        assert error_of(error) == "Maksymalnie 10 zdjęć na raz"

    def test_wrong_mime_type_keeps_old_message(self):
        _, error = validate_submission_input([upload("a.txt", "text/plain")], "tekst")
        assert error.status_code == 400
        assert error_of(error).startswith("Niedozwolony typ pliku")


class TestBatchHelpers:
    def test_empty_batch_is_no_longer_an_error(self):
        assert validate_image_batch([]) is None

    def test_saving_an_empty_batch_creates_no_directory(self, tmp_path):
        target = tmp_path / "user" / "2024" / "etap1" / "1"
        saved, error = asyncio.run(save_uploaded_images([], target))
        assert (saved, error) == ([], None)
        assert not target.exists()
