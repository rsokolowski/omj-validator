"""Which OMJ tasks the AI may link to a pattern (chosen by the server)."""

from app.models import TaskInfo, TaskPdf
from app.patterns.linking import MAX_CANDIDATES, candidate_payload, select_candidates, task_key


def task(year="2024", etap="etap1", number=1, *, skills=(), categories=(), difficulty=3):
    return TaskInfo(
        year=year,
        etap=etap,
        number=number,
        title=f"Zadanie {number}",
        content="Invented statement that must never be sent.",
        pdf=TaskPdf(tasks="t.pdf"),
        difficulty=difficulty,
        categories=list(categories),
        hints=["h1 understand", "h2 strategy", "h3 direction", "h4 hint"],
        skills_required=list(skills),
    )


def keys(tasks):
    return [task_key(t) for t in tasks]


def test_skill_match_beats_category_only():
    by_category = task(number=1, categories=["kombinatoryka"])
    by_skill = task(number=2, skills=["parity"])
    result = select_candidates([by_category, by_skill], skills=["parity"], category="kombinatoryka",
                               excluded_keys=set(), solved_keys=set())
    assert keys(result) == ["2024_etap1_2", "2024_etap1_1"]


def test_unrelated_and_excluded_dropped():
    related = task(number=1, skills=["parity"])
    excluded = task(number=2, skills=["parity"])
    unrelated = task(number=3, categories=["geometria"])
    result = select_candidates([related, excluded, unrelated], skills=["parity"], category=None,
                               excluded_keys={"2024_etap1_2"}, solved_keys=set())
    assert keys(result) == ["2024_etap1_1"]


def test_unsolved_first_then_easier():
    solved = task(number=1, skills=["parity"], difficulty=1)
    hard = task(number=2, skills=["parity"], difficulty=5)
    easy = task(number=3, skills=["parity"], difficulty=2)
    result = select_candidates([solved, hard, easy], skills=["parity"], category=None,
                               excluded_keys=set(), solved_keys={"2024_etap1_1"})
    assert keys(result) == ["2024_etap1_3", "2024_etap1_2", "2024_etap1_1"]


def test_skills_gained_count_too():
    t = task(number=1)
    t.skills_gained = ["parity"]
    assert keys(select_candidates([t], skills=["parity"], category=None,
                                  excluded_keys=set(), solved_keys=set())) == ["2024_etap1_1"]


def test_capped():
    tasks = [task(number=n, skills=["parity"]) for n in range(1, MAX_CANDIDATES + 10)]
    assert len(select_candidates(tasks, skills=["parity"], category=None,
                                 excluded_keys=set(), solved_keys=set())) == MAX_CANDIDATES


def test_payload_has_strategy_hints_and_no_statement():
    payload = candidate_payload(task(number=4, categories=["logika"], difficulty=2))
    assert payload == {
        "task_key": "2024_etap1_4",
        "difficulty": 2,
        "categories": ["logika"],
        "hints": ["h2 strategy", "h3 direction"],
    }


def test_refine_candidates_spread_ties_over_the_years():
    from app.models import TaskInfo, TaskPdf
    from app.patterns.linking import MAX_REFINE_CANDIDATES, refine_candidates

    tasks = [
        TaskInfo(year=str(year), etap="etap1", number=n, title="t", pdf=TaskPdf(tasks="t.pdf"),
                 categories=["geometria"], hints=[])
        for year in range(2005, 2026) for n in range(1, 8)
    ]
    picked = refine_candidates(tasks, skills=[], category="geometria")
    assert len(picked) == MAX_REFINE_CANDIDATES
    assert {t.year for t in picked} == {str(y) for y in range(2005, 2026)}
    assert picked[0].year == "2025"
