"""Repository behind patterns: ownership, links, cascades, conditional reviews."""

from datetime import date, datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from app.config import settings
from app.db.models import (
    PatternDB,
    PatternLinkDB,
    PatternReviewDB,
    PrivateTaskDB,
    SubmissionDB,
    SubmissionStatus,
    UserDB,
)
from app.db.patterns import PatternRepository
from app.db.session import Base

USER_ID = "user-1"
OTHER_USER_ID = "user-2"
TODAY = date(2026, 10, 1)


@pytest.fixture
def db(monkeypatch):
    monkeypatch.setattr(settings, "session_secret_key", "test-secret-key")
    engine = create_engine("sqlite://")

    # SQLite enforces ON DELETE rules only with this pragma
    @event.listens_for(engine, "connect")
    def _fk_on(dbapi_connection, _):
        dbapi_connection.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine)()
    session.add(UserDB(google_sub=USER_ID, email="a@example.com"))
    session.add(UserDB(google_sub=OTHER_USER_ID, email="b@example.com"))
    session.add(
        PrivateTaskDB(
            id="privtask0001", user_id=USER_ID, title="Invented", content="Invented task text here.",
            hints=[], source_images=[], origin="typed",
        )
    )
    session.commit()
    yield session
    session.close()


@pytest.fixture
def repo(db):
    return PatternRepository(db)


def create(repo, user_id=USER_ID, category="teoria_liczb", due_on=TODAY):
    return repo.create(
        user_id,
        trigger="Pytają, czy da się dojść do stanu",
        action="Szukaj niezmiennika, np. parzystości sumy",
        example=None,
        category=category,
        skills=["parity"],
        origin="own",
        refinement=[],
        due_on=due_on,
    )


class TestCreateAndOwnership:
    def test_create_sets_initial_schedule(self, repo):
        p = create(repo)
        assert len(p.id) == 12
        assert (p.srs_level, p.srs_streak, p.due_on) == (1, 0, TODAY)
        assert p.review_count == 0

    def test_get_owned_hides_other_users_pattern(self, repo):
        p = create(repo)
        assert repo.get_owned(p.id, USER_ID).id == p.id
        assert repo.get_owned(p.id, OTHER_USER_ID) is None


class TestLinks:
    def test_link_needs_exactly_one_reference(self, db, repo):
        p = create(repo)
        db.add(PatternLinkDB(pattern_id=p.id, task_key="2024_etap1_1", private_task_id="privtask0001",
                             role="practice", origin="manual", status="accepted"))
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()
        db.add(PatternLinkDB(pattern_id=p.id, role="practice", origin="manual", status="accepted"))
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()

    def test_duplicate_link_returns_none(self, repo):
        p = create(repo)
        q = create(repo)
        assert repo.add_link(p, task_key="2024_etap1_1", role="practice", origin="manual", status="accepted")
        assert repo.add_link(p, task_key="2024_etap1_1", role="practice", origin="manual", status="accepted") is None
        assert repo.add_link(p, task_key="2024_etap1_1", role="practice", origin="ai", status="suggested") is None
        assert repo.add_link(q, task_key="2024_etap1_1", role="practice", origin="manual", status="accepted")

    def test_manual_link_accepts_pending_suggestion_in_place(self, repo):
        p = create(repo)
        suggested = repo.add_link(p, task_key="2024_etap1_1", role="practice", origin="ai",
                                  status="suggested", reason="Ta sama parzystość")
        link = repo.add_link(p, task_key="2024_etap1_1", role="practice", origin="manual", status="accepted")
        assert (link.id, link.status, link.origin, link.reason) == (suggested.id, "accepted", "manual", None)

    def test_deleting_private_task_removes_link_but_keeps_pattern(self, db, repo):
        p = create(repo)
        repo.add_link(p, private_task_id="privtask0001", role="source", origin="manual", status="accepted")
        task = db.get(PrivateTaskDB, "privtask0001")
        db.delete(task)
        db.commit()
        db.expire_all()
        survivor = repo.get_owned(p.id, USER_ID)
        assert survivor is not None
        assert survivor.links == []


class TestCascades:
    def test_deleting_pattern_keeps_submission_with_null_pattern_id(self, db, repo):
        p = create(repo)
        repo.add_link(p, task_key="2024_etap1_1", role="source", origin="manual", status="accepted")
        repo.apply_review(p, seen_due_on=TODAY, new_level=1, new_streak=1, new_due=TODAY + timedelta(days=4),
                          outcome="ok", kind="recall", recall_text="parzystość sumy")
        db.add(SubmissionDB(id="sub00001", user_id=USER_ID, year="2024", etap="etap1", task_number=1,
                            images=[], status=SubmissionStatus.COMPLETED, score=3, pattern_id=p.id))
        db.commit()

        repo.delete(p)
        db.expire_all()

        assert db.query(PatternLinkDB).count() == 0
        assert db.query(PatternReviewDB).count() == 0
        assert db.get(SubmissionDB, "sub00001").pattern_id is None

    def test_deleting_user_removes_patterns(self, db, repo):
        create(repo)
        db.delete(db.get(UserDB, USER_ID))
        db.commit()
        assert db.query(PatternDB).count() == 0


class TestReviews:
    def test_conditional_review_counts_once(self, repo):
        p = create(repo)
        args = dict(seen_due_on=TODAY, new_level=1, new_streak=1, new_due=TODAY + timedelta(days=4),
                    outcome="ok", kind="recall", recall_text="parzystość sumy")
        assert repo.apply_review(p, **args) is not None
        assert repo.apply_review(p, **args) is None
        assert p.review_count == 1
        assert p.due_on == TODAY + timedelta(days=4)
        assert len(p.reviews) == 1

    def test_fail_increments_lapses(self, repo):
        p = create(repo)
        repo.apply_review(p, seen_due_on=TODAY, new_level=1, new_streak=0, new_due=TODAY + timedelta(days=1),
                          outcome="fail", kind="recall", recall_text="nie pamiętam tego")
        assert p.lapse_count == 1
        review = p.reviews[0]
        assert (review.level_before, review.level_after) == (1, 1)
        assert review.due_before == TODAY

    def test_unconditional_task_review_and_lookup_by_submission(self, db, repo):
        p = create(repo, due_on=TODAY + timedelta(days=10))
        db.add(SubmissionDB(id="sub00002", user_id=USER_ID, year="2024", etap="etap1", task_number=1,
                            images=[], status=SubmissionStatus.COMPLETED, score=3, pattern_id=p.id))
        db.commit()
        assert not repo.has_review_for_submission("sub00002")
        row = repo.apply_review(p, seen_due_on=TODAY, new_level=1, new_streak=1, new_due=TODAY,
                                outcome="ok", kind="task", submission_id="sub00002", conditional=False)
        assert row is not None
        assert repo.has_review_for_submission("sub00002")


class TestListing:
    def test_filter_by_linked_task_and_archived(self, repo):
        linked = create(repo)
        other = create(repo)
        archived = create(repo)
        repo.add_link(linked, task_key="2024_etap1_1", role="source", origin="manual", status="accepted")
        repo.add_link(other, task_key="2024_etap1_1", role="practice", origin="ai", status="suggested")
        repo.update_fields(archived, archived_at=datetime.now(timezone.utc).replace(tzinfo=None))

        assert [p.id for p in repo.list_for_user(USER_ID, task_key="2024_etap1_1")] == [linked.id]
        assert {p.id for p in repo.list_for_user(USER_ID)} == {linked.id, other.id}
        assert [p.id for p in repo.list_for_user(USER_ID, archived=True)] == [archived.id]

    def test_due_excludes_future_and_archived(self, repo):
        due = create(repo, due_on=TODAY)
        create(repo, due_on=TODAY + timedelta(days=1))
        assert [p.id for p in repo.due(USER_ID, TODAY)] == [due.id]


class TestSubmissionPatternId:
    def test_create_submission_with_pattern_id(self, db, repo):
        from app.db.repositories import SubmissionRepository

        p = create(repo)
        submissions = SubmissionRepository(db)
        row = submissions.create(
            id="sub00003", user_id=USER_ID, year="2024", etap="etap1", task_number=1,
            images=[], pattern_id=p.id, hints_used=2,
        )
        assert row.pattern_id == p.id
        assert submissions.to_pydantic(row).pattern_id == p.id
