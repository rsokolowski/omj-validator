"""A rejected submission must not leave a child's photo on disk.

The submit endpoint writes files BEFORE it inserts the DB row, so every exit
between those two points has to clean up after itself. Nothing else would: an
unreferenced file is invisible to the retention passes that walk the database,
and in local dev (RETENTION_* = 0, no sweep) it would sit there forever.
"""

import io
import pathlib
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.main as main
from app.config import settings
from app.db import get_db
from app.db.models import SubmissionDB, UserDB
from app.db.session import Base

USER_ID = "user-1"
USER_EMAIL = "kid@example.com"


def jpeg_bytes(size=(400, 300)) -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", size, color=(10, 120, 200)).save(buffer, "JPEG")
    return buffer.getvalue()


@pytest.fixture
def db(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "data_dir", str(tmp_path))
    monkeypatch.setattr(settings, "auth_disabled", False)
    monkeypatch.setattr(settings, "admin_emails", None)
    monkeypatch.setattr(settings, "public_access", True)
    monkeypatch.setattr(settings, "allowed_emails", None)
    monkeypatch.setattr(settings, "session_secret_key", "test-secret-key")

    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine)()
    session.add(UserDB(google_sub=USER_ID, email=USER_EMAIL, name="Kid"))
    session.commit()
    yield session
    session.close()


# The OMJ task PDFs are not in the repository (see NOTICE), so the submit
# endpoint's "does the task PDF exist?" check has nothing real to look at on a
# fresh clone. Point it at the synthetic PDF in tests/fixtures/task_corpus/
# instead - what these tests care about is the uploaded photos, not the task.
FIXTURE_TASK_PDF = (
    pathlib.Path(__file__).parent
    / "fixtures"
    / "task_corpus"
    / "tasks"
    / "1999"
    / "etap1"
    / "zadania.pdf"
)


@pytest.fixture
def client(db, monkeypatch):
    def override_get_db():
        yield db

    main.app.dependency_overrides[get_db] = override_get_db

    monkeypatch.setattr(main, "get_task_pdf_path", lambda year, etap: FIXTURE_TASK_PDF)
    monkeypatch.setattr(main, "get_solution_pdf_path", lambda year, etap: None)

    user = {"google_sub": USER_ID, "email": USER_EMAIL, "name": "Kid"}
    monkeypatch.setattr(main, "verify_auth", lambda request: True)
    monkeypatch.setattr(main, "get_current_user_id", lambda request: USER_ID)
    monkeypatch.setattr(main, "get_current_user", lambda request: user)
    monkeypatch.setattr(main, "_get_allowed_emails", lambda: set())

    yield TestClient(main.app)

    main.app.dependency_overrides.clear()


def files_left() -> list[str]:
    root = settings.uploads_dir
    return sorted(str(p.relative_to(root)) for p in root.rglob("*") if p.is_file())


def submit(client, files):
    return client.post("/task/2024/etap1/1/submit", files=files)


def image_part(name: str, data: bytes, content_type: str = "image/jpeg"):
    return ("images", (name, data, content_type))


def text_part(name: str, text: str, content_type: str = "text/plain"):
    return ("images", (name, text.encode("utf-8"), content_type))


class TestSuccessfulSubmissionKeepsFiles:
    def test_accepted_upload_is_stored_and_referenced(self, client, db):
        response = submit(client, [image_part("a.jpg", jpeg_bytes())])

        assert response.status_code == 200, response.text
        stored = db.query(SubmissionDB).one()
        assert len(stored.images) == 1
        # Every stored path must point at a file that actually exists
        assert files_left() == sorted(stored.images)

    def test_txt_upload_is_stored_and_referenced(self, client, db):
        response = submit(client, [text_part("rozwiazanie.txt", "Dowód: ...")])

        assert response.status_code == 200, response.text
        stored = db.query(SubmissionDB).one()
        assert len(stored.images) == 1
        path = settings.uploads_dir / stored.images[0]
        assert path.suffix == ".txt"
        assert path.read_text(encoding="utf-8") == "Dowód: ..."

    def test_txt_with_generic_mime_type_is_accepted(self, client):
        response = submit(
            client,
            [text_part("rozwiazanie.txt", "Treść rozwiązania", "application/octet-stream")],
        )

        assert response.status_code == 200, response.text


class TestHeicUploadIsAccepted:
    """Regression: HEIC passed both allowlists and then always got a 400,
    because normalization refused everything Pillow could not decode and there
    was no HEIF decoder installed. iPhone users could not submit at all."""

    def _heic_bytes(self, size=(640, 480)) -> bytes:
        pillow_heif = pytest.importorskip("pillow_heif")
        import tempfile
        import pathlib

        with tempfile.TemporaryDirectory() as tmp:
            path = pathlib.Path(tmp) / "x.heic"
            pillow_heif.from_pillow(Image.new("RGB", size, color=(30, 60, 90))).save(
                str(path), quality=70
            )
            return path.read_bytes()

    def test_iphone_heic_upload_succeeds(self, client, db):
        response = submit(
            client, [image_part("IMG_0042.heic", self._heic_bytes(), "image/heic")]
        )

        assert response.status_code == 200, response.text
        stored = db.query(SubmissionDB).one()
        assert len(stored.images) == 1

    def test_stored_heic_is_a_jpeg_without_metadata(self, client, db):
        submit(client, [image_part("IMG_0042.heic", self._heic_bytes(), "image/heic")])

        stored = db.query(SubmissionDB).one()
        path = settings.uploads_dir / stored.images[0]
        assert path.is_file(), "DB references a file that does not exist"
        assert path.suffix == ".jpg"
        with Image.open(path) as img:
            assert img.format == "JPEG"
            assert not (img.getexif() or {})

    def test_heic_mime_type_passes_validation(self, client, db):
        """The content_type allowlist must not reject what we can now process."""
        response = submit(
            client, [image_part("IMG_0042.heif", self._heic_bytes(), "image/heif")]
        )

        assert response.status_code == 200, response.text


class TestRejectedSubmissionLeavesNothing:
    def test_empty_txt_is_rejected_and_removed(self, client, db):
        response = submit(client, [text_part("puste.txt", "   \n")])

        assert response.status_code == 400
        assert db.query(SubmissionDB).count() == 0
        assert files_left() == []

    def test_unprocessable_second_image_discards_the_first(self, client, db):
        """The regression this guards: the good file was already on disk."""
        response = submit(
            client,
            [
                image_part("good.jpg", jpeg_bytes()),
                image_part("broken.jpg", b"this is not an image"),
            ],
        )

        assert response.status_code == 400
        assert db.query(SubmissionDB).count() == 0
        assert files_left() == []

    def test_oversized_second_image_discards_the_first(self, client, db, monkeypatch):
        monkeypatch.setattr(settings, "upload_max_size_mb", 1)
        too_big = b"\xff" * (2 * 1024 * 1024)

        response = submit(
            client,
            [image_part("good.jpg", jpeg_bytes()), image_part("huge.jpg", too_big)],
        )

        assert response.status_code == 400
        assert db.query(SubmissionDB).count() == 0
        assert files_left() == []

    def test_missing_task_pdf_discards_everything(self, client, db, monkeypatch):
        """500 after the loop: files are on disk, no row will ever reference them."""
        monkeypatch.setattr(main, "get_task_pdf_path", lambda year, etap: None)

        response = submit(
            client,
            [image_part("a.jpg", jpeg_bytes()), image_part("b.jpg", jpeg_bytes())],
        )

        assert response.status_code == 500
        assert db.query(SubmissionDB).count() == 0
        assert files_left() == []

    def test_crash_while_reading_discards_everything(self, client, db, monkeypatch):
        """The bare `except: ... raise` path used to keep the earlier files."""
        original = main._normalize_uploaded_image
        calls = {"n": 0}

        def boom(path):
            calls["n"] += 1
            if calls["n"] == 1:
                return original(path)
            raise RuntimeError("disk exploded")

        monkeypatch.setattr(main, "_normalize_uploaded_image", boom)

        with pytest.raises(RuntimeError):
            submit(
                client,
                [image_part("a.jpg", jpeg_bytes()), image_part("b.jpg", jpeg_bytes())],
            )

        assert db.query(SubmissionDB).count() == 0
        assert files_left() == []

    def test_rejected_upload_does_not_touch_another_users_files(self, client, db):
        other = settings.uploads_dir / "someone-else" / "2024" / "etap1" / "1"
        other.mkdir(parents=True)
        (other / "theirs.jpg").write_bytes(b"keep me")

        submit(client, [image_part("broken.jpg", b"not an image")])

        assert (other / "theirs.jpg").is_file()
