"""The task statements are not part of this repository - the app must cope.

`data/tasks/**/task_*.json` holds this project's own metadata (difficulty,
categories, hints, prerequisites, skills) and is tracked in git. The statement of
each task - its title and its full text - is OMJ competition material, so it is
generated locally into `data/task_content/{year}/{etap}.json` and never
committed (see NOTICE). A fresh clone therefore has metadata but no statements,
and that has to be a working state, not a broken one.

Everything here runs against the synthetic corpus in tests/fixtures/task_corpus/
(invented tasks, no OMJ text), so the suite passes on a fresh clone.
"""

import json
import shutil
from pathlib import Path

import pytest

from app.config import settings
from app.storage import (
    _load_all_tasks,
    clear_task_cache,
    get_available_years,
    get_task,
    get_task_pdf_path,
    get_tasks_for_etap,
)

FIXTURE_CORPUS = Path(__file__).parent / "fixtures" / "task_corpus"
REPO_ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture
def corpus(tmp_path, monkeypatch):
    """A writable copy of the synthetic corpus, wired into the app settings."""
    root = tmp_path / "corpus"
    shutil.copytree(FIXTURE_CORPUS, root)
    monkeypatch.setattr(settings, "base_dir", root)
    clear_task_cache()
    yield root
    clear_task_cache()


def write_statements(root: Path, year: str, etap: str, payload: dict) -> None:
    path = root / "data" / "task_content" / year / f"{etap}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    clear_task_cache()


class TestStatementPresent:
    def test_title_and_content_come_from_the_generated_file(self, corpus):
        task = get_task("1999", "etap1", 1)

        assert task.title == "Suma dwóch liczb testowych"
        assert "$a + b = 7$" in task.content
        assert task.has_content is True

    def test_metadata_still_comes_from_the_tracked_file(self, corpus):
        task = get_task("1999", "etap1", 1)

        assert task.difficulty == 2
        assert task.categories == ["algebra"]
        assert len(task.hints) == 4
        assert task.skills_required == ["fixture_skill_a"]


class TestStatementMissing:
    def test_task_still_loads(self, corpus):
        """No statement for task 2, and no statement file at all for etap2."""
        assert get_task("1999", "etap1", 2) is not None
        assert get_task("1999", "etap2", 1) is not None
        assert get_available_years() == ["1999"]
        assert len(_load_all_tasks()) == 3

    def test_content_is_none_and_flagged(self, corpus):
        task = get_task("1999", "etap1", 2)

        assert task.content is None
        assert task.has_content is False

    def test_title_falls_back_to_the_task_number(self, corpus):
        """Every consumer of `title` (graph, notifications, history) keeps working."""
        assert get_task("1999", "etap1", 2).title == "Zadanie 2"
        assert get_task("1999", "etap2", 1).title == "Zadanie 1"

    def test_metadata_is_unaffected(self, corpus):
        task = get_task("1999", "etap1", 2)

        assert task.difficulty == 4
        assert task.categories == ["geometria", "logika"]
        assert task.prerequisites == ["1999_etap1_1"]

    def test_the_task_pdf_is_still_offered(self, corpus):
        """The degraded UI links to the PDF, so the path must still resolve."""
        pdf = get_task_pdf_path("1999", "etap1")

        assert pdf is not None
        assert pdf.exists()

    def test_serialization_keeps_the_flag(self, corpus):
        dumped = get_task("1999", "etap1", 2).model_dump(mode="json")

        assert dumped["content"] is None
        assert dumped["has_content"] is False
        assert dumped["title"] == "Zadanie 2"


class TestCorruptStatementFile:
    def test_broken_json_degrades_instead_of_crashing(self, corpus):
        path = corpus / "data" / "task_content" / "1999" / "etap1.json"
        path.write_text("{ not json", encoding="utf-8")
        clear_task_cache()

        tasks = get_tasks_for_etap("1999", "etap1")

        assert [t.number for t in tasks] == [1, 2]
        assert all(t.has_content is False for t in tasks)

    def test_unexpected_shape_degrades_instead_of_crashing(self, corpus):
        write_statements(corpus, "1999", "etap1", {"year": "1999", "tasks": []})

        assert get_task("1999", "etap1", 1).has_content is False

    def test_wrong_entry_type_degrades_instead_of_crashing(self, corpus):
        write_statements(
            corpus,
            "1999",
            "etap1",
            {"year": "1999", "etap": "etap1", "tasks": {"1": "just a string"}},
        )

        task = get_task("1999", "etap1", 1)
        assert task is not None
        assert task.has_content is False
        assert task.title == "Zadanie 1"

    def test_blank_statement_counts_as_missing(self, corpus):
        write_statements(
            corpus,
            "1999",
            "etap1",
            {"year": "1999", "etap": "etap1", "tasks": {"1": {"title": "", "content": "   "}}},
        )

        task = get_task("1999", "etap1", 1)
        assert task.content is None
        assert task.title == "Zadanie 1"


class TestStalePreSplitMetadata:
    def test_generated_statement_wins_over_a_stale_inline_one(self, corpus):
        """An old clone may still have title/content inside the metadata file."""
        path = corpus / "data" / "tasks" / "1999" / "etap1" / "task_1.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        data["title"] = "Stary tytuł"
        data["content"] = "Stara treść"
        path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        clear_task_cache()

        task = get_task("1999", "etap1", 1)

        assert task.title == "Suma dwóch liczb testowych"
        assert "Stara treść" not in (task.content or "")

    def test_inline_statement_is_used_when_nothing_was_generated(self, corpus):
        path = corpus / "data" / "tasks" / "1999" / "etap2" / "task_1.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        data["title"] = "Stary tytuł"
        data["content"] = "Stara treść"
        path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        clear_task_cache()

        task = get_task("1999", "etap2", 1)

        assert task.title == "Stary tytuł"
        assert task.has_content is True


class TestRepositoryStaysClean:
    """Guard rail: OMJ material must not creep back into the tracked files."""

    def test_no_tracked_task_file_carries_a_statement(self):
        offenders = []
        for path in (REPO_ROOT / "data" / "tasks").rglob("task_*.json"):
            data = json.loads(path.read_text(encoding="utf-8"))
            if "title" in data or "content" in data:
                offenders.append(str(path.relative_to(REPO_ROOT)))

        assert offenders == [], (
            "These tracked metadata files still contain OMJ task statements. "
            "Run: python scripts/split_task_content.py"
        )

    def test_generated_statements_are_git_ignored(self):
        gitignore = (REPO_ROOT / ".gitignore").read_text(encoding="utf-8")

        assert "data/task_content/*" in gitignore
        assert "tasks/*" in gitignore
