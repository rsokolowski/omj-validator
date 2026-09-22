"""Guards the curated practice lists in the frontend constants file.

The mock sets and prep lists are hand-maintained arrays of task keys in
``frontend/src/lib/utils/constants.ts``.  A typo there is invisible until a
student opens the page and sees a short set, so we parse the file here and
check the keys against the task metadata on disk.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
CONSTANTS_FILE = REPO_ROOT / "frontend" / "src" / "lib" / "utils" / "constants.ts"
TASKS_DIR = REPO_ROOT / "data" / "tasks"

# Number of tasks a full mock set must contain, per etap (OMJ regulamin 4.2:
# etap 1 "czesc zadaniowa" = 7 zadan, etap 2 = 5 zadan).
TASKS_PER_SET = {"etap1": 7, "etap2": 5}

TASK_KEY_RE = re.compile(r'"(\d{4}_etap\d_\d+)"')


def _array_body(name: str, source: str) -> str:
    """Return the raw text between the brackets of ``export const <name> = [...]``."""
    start_marker = re.search(
        rf"export const {re.escape(name)}\s*(?::[^=]+)?=\s*\[", source
    )
    assert start_marker, f"{name} not found in {CONSTANTS_FILE}"
    depth = 1
    i = start_marker.end()
    while depth:
        assert i < len(source), f"unterminated array for {name}"
        if source[i] == "[":
            depth += 1
        elif source[i] == "]":
            depth -= 1
        i += 1
    return source[start_marker.end() : i - 1]


@pytest.fixture(scope="module")
def source() -> str:
    return CONSTANTS_FILE.read_text(encoding="utf-8")


def _prep_tasks(source: str, name: str) -> list[str]:
    return TASK_KEY_RE.findall(_array_body(name, source))


def _mock_sets(source: str, name: str) -> list[list[str]]:
    """Return one list of task keys per set in the given MOCK_* array."""
    body = _array_body(name, source)
    return [
        TASK_KEY_RE.findall(tasks_block)
        for tasks_block in re.findall(r"tasks:\s*\[(.*?)\]", body, re.DOTALL)
    ]


def _metadata_path(key: str) -> Path:
    year, etap, number = key.split("_")
    return TASKS_DIR / year / etap / f"task_{number}.json"


def _all_lists(source: str) -> dict[str, dict[str, object]]:
    return {
        etap: {
            "prep": _prep_tasks(source, f"{etap.upper()}_PREP_TASKS"),
            "sets": _mock_sets(source, f"MOCK_{etap.upper()}_SETS"),
        }
        for etap in TASKS_PER_SET
    }


def test_constants_file_parses(source: str) -> None:
    lists = _all_lists(source)
    # The etap2 lists are populated today; if the parser silently returned
    # nothing, every other assertion below would pass vacuously.
    assert lists["etap2"]["prep"], "ETAP2_PREP_TASKS parsed as empty"
    assert lists["etap2"]["sets"], "MOCK_ETAP2_SETS parsed as empty"


def test_every_key_has_task_metadata(source: str) -> None:
    lists = _all_lists(source)
    keys = set()
    for entry in lists.values():
        keys.update(entry["prep"])
        for task_set in entry["sets"]:
            keys.update(task_set)

    missing = sorted(key for key in keys if not _metadata_path(key).exists())
    assert not missing, f"no task metadata for: {missing}"

    # The metadata must actually describe the task the key names.
    for key in sorted(keys):
        number = int(key.split("_")[2])
        data = json.loads(_metadata_path(key).read_text(encoding="utf-8"))
        assert data["number"] == number, f"{key}: metadata number is {data['number']}"


@pytest.mark.parametrize("etap", sorted(TASKS_PER_SET))
def test_keys_belong_to_their_etap(source: str, etap: str) -> None:
    entry = _all_lists(source)[etap]
    keys = list(entry["prep"]) + [k for s in entry["sets"] for k in s]
    wrong = sorted(key for key in keys if key.split("_")[1] != etap)
    assert not wrong, f"{etap} lists contain keys from another etap: {wrong}"


@pytest.mark.parametrize("etap", sorted(TASKS_PER_SET))
def test_mock_sets_are_complete_and_without_repeats(source: str, etap: str) -> None:
    sets = _all_lists(source)[etap]["sets"]
    seen: set[str] = set()
    for index, task_set in enumerate(sets):
        assert len(task_set) == len(set(task_set)), (
            f"MOCK_{etap.upper()}_SETS[{index}] repeats a task"
        )
        assert len(task_set) == TASKS_PER_SET[etap], (
            f"MOCK_{etap.upper()}_SETS[{index}] has {len(task_set)} tasks, "
            f"expected {TASKS_PER_SET[etap]}"
        )
        overlap = seen & set(task_set)
        assert not overlap, (
            f"MOCK_{etap.upper()}_SETS[{index}] reuses tasks from an earlier set: "
            f"{sorted(overlap)}"
        )
        seen.update(task_set)


@pytest.mark.parametrize("etap", sorted(TASKS_PER_SET))
def test_prep_and_mock_lists_are_disjoint(source: str, etap: str) -> None:
    entry = _all_lists(source)[etap]
    prep = set(entry["prep"])
    mock = {key for task_set in entry["sets"] for key in task_set}
    overlap = sorted(prep & mock)
    assert not overlap, (
        f"{etap}: tasks appear both in the prep list and in a mock set: {overlap}"
    )


@pytest.mark.parametrize("etap", sorted(TASKS_PER_SET))
def test_prep_list_has_no_duplicates(source: str, etap: str) -> None:
    prep = _all_lists(source)[etap]["prep"]
    duplicates = sorted({key for key in prep if prep.count(key) > 1})
    assert not duplicates, f"{etap.upper()}_PREP_TASKS repeats: {duplicates}"
