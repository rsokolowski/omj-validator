"""Daily submission limits hold under parallel requests.

Audit finding: the submit endpoints counted today's rows, then awaited the photo
upload, then inserted - so 60 parallel requests against a limit of 30 created
60 rows and 60 paid gradings. A submission now reserves its row before any
photo is processed and recounts with the reservation in place.
"""

import asyncio
import io
import os
import pathlib
from datetime import datetime, timedelta, timezone

import httpx
import pytest
from PIL import Image
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.main as main
import app.private_tasks.routes as private_routes
import app.websocket.handler as handler
from app.config import settings
from app.db import get_db
from app.db import DeletedAccountQuotaRepository
from app.db.models import PrivateTaskDB, SubmissionDB, SubmissionStatus, UserDB
from app.db.session import Base

USER_ID = "user-1"
PRIVATE_ID = "privtask0001"
FIXTURE_TASK_PDF = (
    pathlib.Path(__file__).parent / "fixtures" / "task_corpus" / "tasks" / "1999" / "etap1" / "zadania.pdf"
)


def big_jpeg() -> bytes:
    """Over 1 MB: Starlette spools it to disk, so reading it yields to the loop."""
    side = 1100
    img = Image.frombytes("RGB", (side, side), os.urandom(side * side * 3))
    buffer = io.BytesIO()
    img.save(buffer, "JPEG", quality=95)
    data = buffer.getvalue()
    assert len(data) > 1024 * 1024
    return data


@pytest.fixture
def db(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "data_dir", str(tmp_path))
    monkeypatch.setattr(settings, "auth_disabled", False)
    monkeypatch.setattr(settings, "admin_emails", None)
    monkeypatch.setattr(settings, "public_access", True)
    monkeypatch.setattr(settings, "allowed_emails", None)
    monkeypatch.setattr(settings, "session_secret_key", "test-secret-key")
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine)()
    session.add(UserDB(id=USER_ID, google_sub=USER_ID, email="kid@example.com", name="Kid"))
    session.add(PrivateTaskDB(id=PRIVATE_ID, user_id=USER_ID, title="T", content="Treść", hints=[],
                                source_images=[], origin="typed"))
    session.commit()
    yield session
    session.close()


@pytest.fixture
def started(monkeypatch):
    calls = []

    async def fake_process(**kwargs):
        calls.append(kwargs)

    monkeypatch.setattr(handler, "process_submission_background", fake_process)
    monkeypatch.setattr(private_routes, "process_submission_background", fake_process)
    return calls


@pytest.fixture
def app(db, monkeypatch, started):
    def override_get_db():
        yield db

    main.app.dependency_overrides[get_db] = override_get_db
    monkeypatch.setattr(main, "get_task_pdf_path", lambda year, etap: FIXTURE_TASK_PDF)

    user = {"user_id": USER_ID, "email": "kid@example.com", "name": "Kid"}

    async def member(request):
        return True

    for module in (main, private_routes):
        monkeypatch.setattr(module, "verify_auth", lambda request: True)
        monkeypatch.setattr(module, "get_current_user_id", lambda request: USER_ID)
        monkeypatch.setattr(module, "get_current_user", lambda request: user)
        monkeypatch.setattr(module, "is_group_member_async", member)
        monkeypatch.setattr(module, "_get_allowed_emails", lambda: set())
    yield main.app
    main.app.dependency_overrides.clear()


OMJ_URL = "/task/2024/etap1/1/submit"
PRIVATE_URL = f"/api/private-tasks/{PRIVATE_ID}/submit"


async def fire(app, url: str, n: int, photo: bytes) -> list[int]:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        responses = await asyncio.gather(*[
            client.post(url, files=[("images", (f"{i}.jpg", photo, "image/jpeg"))])
            for i in range(n)
        ])
    return [r.status_code for r in responses]


def files_left() -> list[pathlib.Path]:
    root = settings.uploads_dir
    return [p for p in root.rglob("*") if p.is_file()] if root.exists() else []


class TestParallelSubmissionsRespectTheDailyLimit:
    @pytest.mark.parametrize("url", [OMJ_URL, PRIVATE_URL])
    def test_limit_holds(self, app, db, monkeypatch, url):
        monkeypatch.setattr(settings, "rate_limit_submissions_per_user_per_day", 3)
        monkeypatch.setattr(settings, "rate_limit_submissions_in_flight_per_user", 100)

        codes = asyncio.run(fire(app, url, 8, big_jpeg()))

        assert codes.count(200) <= 3, codes
        assert set(codes) <= {200, 429}, codes
        rows = db.query(SubmissionDB).all()
        assert len(rows) <= 3
        assert all(r.status == SubmissionStatus.PENDING for r in rows)
        # Refused requests leave neither a row nor a photo behind
        assert len(files_left()) == sum(len(r.images) for r in rows)

    def test_global_limit_holds(self, app, db, monkeypatch):
        monkeypatch.setattr(settings, "rate_limit_submissions_global_per_day", 2)
        monkeypatch.setattr(settings, "rate_limit_submissions_in_flight_per_user", 100)

        codes = asyncio.run(fire(app, OMJ_URL, 6, big_jpeg()))

        assert codes.count(200) <= 2, codes
        assert db.query(SubmissionDB).count() <= 2


class TestInFlightCap:
    def test_parallel_requests_beyond_the_cap_are_429(self, app, db, monkeypatch):
        monkeypatch.setattr(settings, "rate_limit_submissions_in_flight_per_user", 2)

        codes = asyncio.run(fire(app, OMJ_URL, 6, big_jpeg()))

        assert codes.count(200) <= 2, codes
        assert db.query(SubmissionDB).count() <= 2

    def test_pending_submission_blocks_until_it_is_graded(self, app, db, monkeypatch):
        monkeypatch.setattr(settings, "rate_limit_submissions_in_flight_per_user", 1)
        db.add(SubmissionDB(id="busy0001", user_id=USER_ID, year="2024", etap="etap1",
                            task_number=2, images=[], status=SubmissionStatus.PROCESSING))
        db.commit()

        [code] = asyncio.run(fire(app, OMJ_URL, 1, b"x"))
        assert code == 429

        db.get(SubmissionDB, "busy0001").status = SubmissionStatus.COMPLETED
        db.commit()
        [code] = asyncio.run(fire(app, OMJ_URL, 1, small_jpeg()))
        assert code == 200

    def test_stale_pending_row_does_not_block_forever(self, app, db, monkeypatch):
        monkeypatch.setattr(settings, "rate_limit_submissions_in_flight_per_user", 1)
        db.add(SubmissionDB(id="stale001", user_id=USER_ID, year="2024", etap="etap1",
                            task_number=2, images=[], status=SubmissionStatus.PENDING,
                            timestamp=datetime.now(timezone.utc) - timedelta(hours=1)))
        db.commit()

        [code] = asyncio.run(fire(app, OMJ_URL, 1, small_jpeg()))
        assert code == 200

    def test_in_flight_message_is_polish(self, app, db, monkeypatch):
        monkeypatch.setattr(settings, "rate_limit_submissions_in_flight_per_user", 1)
        db.add(SubmissionDB(id="busy0002", user_id=USER_ID, private_task_id=PRIVATE_ID,
                            images=[], status=SubmissionStatus.PENDING))
        db.commit()

        async def one():
            transport = httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
                return await client.post(PRIVATE_URL, data={"solution_text": "abc"})

        response = asyncio.run(one())
        assert response.status_code == 429
        assert "oceniane" in response.json()["error"]
        assert response.headers.get("Retry-After")
        assert db.query(SubmissionDB).count() == 1


def small_jpeg() -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (40, 30), (10, 120, 200)).save(buffer, "JPEG")
    return buffer.getvalue()


class TestRejectedPhotosStillCount:
    def test_unreadable_photo_keeps_a_failed_row(self, app, db, monkeypatch):
        """A refused batch costs one daily submission, so it cannot be repeated for free."""
        monkeypatch.setattr(settings, "rate_limit_submissions_per_user_per_day", 1)

        [code] = asyncio.run(fire(app, OMJ_URL, 1, b"not an image"))
        assert code == 400
        row = db.query(SubmissionDB).one()
        assert row.status == SubmissionStatus.FAILED
        assert row.images == [] and row.solution_text is None
        assert "Nie udało się przetworzyć" in row.error_message
        assert files_left() == []

        [code] = asyncio.run(fire(app, OMJ_URL, 1, small_jpeg()))
        assert code == 429

    def test_tombstone_still_counts(self, app, db, monkeypatch):
        monkeypatch.setattr(settings, "rate_limit_submissions_per_user_per_day", 2)
        recent = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=1)
        DeletedAccountQuotaRepository(db).record_deletion(USER_ID, 2, recent, recent)

        [code] = asyncio.run(fire(app, OMJ_URL, 1, small_jpeg()))

        assert code == 429
        assert db.query(SubmissionDB).count() == 0


async def post_text(app, url: str, text: str = "abc") -> httpx.Response:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        return await client.post(url, data={"solution_text": text})


class TestReservationCleanup:
    def test_private_refused_photo_keeps_a_failed_row(self, app, db):
        [code] = asyncio.run(fire(app, PRIVATE_URL, 1, b"not an image"))

        assert code == 400
        row = db.query(SubmissionDB).one()
        assert row.status == SubmissionStatus.FAILED
        assert row.private_task_id == PRIVATE_ID
        assert files_left() == []

    @pytest.mark.parametrize("url", [OMJ_URL, PRIVATE_URL])
    def test_server_failure_gives_the_slot_back(self, app, db, monkeypatch, url):
        import app.uploads as uploads

        def boom(path):
            raise RuntimeError("disk exploded")

        monkeypatch.setattr(main, "_normalize_uploaded_image", boom)
        monkeypatch.setattr(uploads, "normalize_uploaded_image", boom)

        with pytest.raises(RuntimeError):
            asyncio.run(fire(app, url, 1, small_jpeg()))

        assert db.query(SubmissionDB).count() == 0
        assert files_left() == []

    def test_success_headers_count_the_new_submission(self, app, db, monkeypatch):
        monkeypatch.setattr(settings, "rate_limit_submissions_per_user_per_day", 5)

        response = asyncio.run(post_text(app, OMJ_URL))

        assert response.status_code == 200
        assert response.headers["X-RateLimit-Remaining"] == "4"
        row = db.query(SubmissionDB).one()
        assert row.solution_text == "abc" and row.status == SubmissionStatus.PENDING


class TestOmjSubmitRequiresAccess:
    """Audit finding: OMJ submit only checked sign-in, unlike private tasks and patterns."""

    def test_non_member_is_403_and_reserves_nothing(self, app, db, monkeypatch):
        async def not_member(request):
            return False

        monkeypatch.setattr(main, "is_group_member_async", not_member)

        [code] = asyncio.run(fire(app, OMJ_URL, 1, small_jpeg()))

        assert code == 403
        assert db.query(SubmissionDB).count() == 0
        assert files_left() == []
