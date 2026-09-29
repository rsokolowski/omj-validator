"""Private tasks share the submissions table with OMJ tasks.

That is only safe if every OMJ aggregate keeps ignoring private rows and the
database refuses a submission that points at both kinds of task (or neither).
"""

from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from app.db.models import PrivateTaskDB, SubmissionDB, SubmissionStatus, UserDB
from app.db.repositories import SubmissionRepository
from app.db.session import Base

USER_ID = "user-1"


@pytest.fixture
def db():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine)()
    session.add(UserDB(google_sub=USER_ID, email="a@example.com", name="A"))
    session.commit()
    yield session
    session.close()


def make_task(db, task_id="abcdefghijkl") -> PrivateTaskDB:
    task = PrivateTaskDB(
        id=task_id,
        user_id=USER_ID,
        title="Invented task",
        content="Prove that the sum of two even numbers is even.",
        hints=["Write the numbers as 2a and 2b."],
        source_images=[],
        origin="typed",
    )
    db.add(task)
    db.commit()
    return task


def omj_submission(db, sid="omj00001", score=5, task_number=1):
    sub = SubmissionDB(
        id=sid,
        user_id=USER_ID,
        year="2024",
        etap="etap1",
        task_number=task_number,
        images=[],
        status=SubmissionStatus.COMPLETED,
        score=score,
    )
    db.add(sub)
    db.commit()
    return sub


def private_submission(db, task, sid="prv00001", score=6, hints_used=0):
    sub = SubmissionDB(
        id=sid,
        user_id=USER_ID,
        private_task_id=task.id,
        images=[],
        status=SubmissionStatus.COMPLETED,
        score=score,
        hints_used=hints_used,
    )
    db.add(sub)
    db.commit()
    return sub


def test_submission_with_both_task_references_is_refused(db):
    task = make_task(db)
    db.add(
        SubmissionDB(
            id="both0001", user_id=USER_ID, year="2024", etap="etap1",
            task_number=1, private_task_id=task.id, images=[],
        )
    )
    with pytest.raises(IntegrityError):
        db.commit()


def test_submission_with_no_task_reference_is_refused(db):
    db.add(SubmissionDB(id="none0001", user_id=USER_ID, images=[]))
    with pytest.raises(IntegrityError):
        db.commit()


def test_private_submission_round_trips_to_pydantic(db):
    task = make_task(db)
    sub = private_submission(db, task, hints_used=2)

    model = SubmissionRepository(db).to_pydantic(sub)

    assert model.year is None
    assert model.etap is None
    assert model.task_number is None
    assert model.private_task_id == task.id
    assert model.hints_used == 2


def test_omj_progress_ignores_private_submissions(db):
    omj_submission(db, score=2)
    private_submission(db, make_task(db), score=6)

    progress = SubmissionRepository(db).get_user_progress(USER_ID)

    assert progress == {"2024_etap1_1": 2}


def test_task_stats_ignore_private_submissions(db):
    omj_submission(db, score=2)
    private_submission(db, make_task(db), score=6)

    count, highest = SubmissionRepository(db).get_task_stats(USER_ID, "2024", "etap1", 1)

    assert (count, highest) == (1, 2)


def test_my_submissions_year_filter_excludes_private(db):
    omj_submission(db)
    private_submission(db, make_task(db))
    repo = SubmissionRepository(db)

    filtered, filtered_total = repo.get_user_submissions_paginated(USER_ID, year_filter="2024")
    everything, total = repo.get_user_submissions_paginated(USER_ID)

    assert [s.id for s in filtered] == ["omj00001"]
    assert filtered_total == 1
    assert total == 2


def test_aggregate_stats_count_private_tasks(db):
    omj_submission(db, sid="omj00001", score=5, task_number=1)
    omj_submission(db, sid="omj00002", score=0, task_number=2)
    task_a = make_task(db, "aaaaaaaaaaaa")
    task_b = make_task(db, "bbbbbbbbbbbb")
    private_submission(db, task_a, sid="prv00001", score=6)
    private_submission(db, task_a, sid="prv00002", score=2)
    private_submission(db, task_b, sid="prv00003", score=2)

    stats = SubmissionRepository(db).get_user_aggregate_stats(USER_ID)

    assert stats["total_submissions"] == 5
    # 2 OMJ tasks + 2 private tasks
    assert stats["tasks_attempted"] == 4
    # OMJ etap1 task 1 (5 >= 2) + private task A (6 >= 5)
    assert stats["tasks_mastered"] == 2


def test_deleting_private_task_cascades_submissions(db):
    task = make_task(db)
    private_submission(db, task)
    omj_submission(db)

    db.delete(task)
    db.commit()

    assert [s.id for s in db.query(SubmissionDB).all()] == ["omj00001"]


def test_private_task_defaults(db):
    task = make_task(db)

    assert task.hints_revealed == 0
    assert task.pending_hints_used == 0
    assert task.last_activity_at is not None
    assert task.last_activity_at <= datetime.now(timezone.utc).replace(tzinfo=None)
