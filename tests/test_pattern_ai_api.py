"""AI endpoints for patterns: refine rounds, suggestions from a solution, OMJ links."""

import pytest

from app.ai.factory import AIContentBlockedError, AIProviderError
from app.config import settings
from app.db.models import AIUsageDB, PatternLinkDB, SubmissionDB, SubmissionStatus
from app.models import (
    LinkResult,
    LinkSuggestion,
    PatternSuggestion,
    PatternVariant,
    RefineResult,
    SuggestResult,
    TaskInfo,
    TaskPdf,
)
from app.patterns import routes as pattern_routes
from app.patterns import service

from test_pattern_api import (  # noqa: F401 - fixtures
    OTHER_USER_ID,
    PRIVATE_ID,
    USER_ID,
    client,
    create,
    current_user,
    db,
    omj,
    today,
)

V1 = PatternVariant(trigger="Pytają o możliwość dojścia do stanu", action="Szukaj niezmiennika")
V2 = PatternVariant(trigger="Operacje zmieniają liczby", action="Sprawdź, co się nie zmienia")


class StubProvider:
    def __init__(self):
        self.refine = RefineResult(variants=[V1, V2], questions=["Czy to działa dla iloczynu?"],
                                   verdict="ok", comment="Dobrze", category="kombinatoryka",
                                   skills=["parity"], meta={"model": "stub"})
        self.suggest = SuggestResult(suggestions=[PatternSuggestion(**V1.model_dump(), why="Często")],
                                     meta={"model": "stub"})
        self.links = None
        self.error = None
        self.calls = []

    async def refine_pattern(self, draft, source_text, history, answer):
        self.calls.append(("refine", draft, source_text, history, answer))
        if self.error:
            raise self.error
        return self.refine

    async def suggest_patterns(self, task_text, feedback, draft):
        self.calls.append(("suggest", task_text, feedback, draft))
        if self.error:
            raise self.error
        return self.suggest

    async def link_pattern_tasks(self, pattern, candidates):
        self.calls.append(("link", pattern, candidates))
        if self.error:
            raise self.error
        if self.links is not None:
            return self.links
        return LinkResult(links=[LinkSuggestion(task_key=candidates[0]["task_key"], reason="Pasuje")],
                          meta={"model": "stub"})


@pytest.fixture
def provider(monkeypatch):
    stub = StubProvider()
    monkeypatch.setattr(pattern_routes, "create_ai_provider", lambda: stub)
    return stub


def usage(db, kind):
    return db.query(AIUsageDB).filter_by(kind=kind).count()


def refine(client, **overrides):
    body = {"draft": {"raw": "Jak pytają czy się da, to patrz na parzystość"}}
    body.update(overrides)
    return client.post("/api/patterns/refine", json=body)


class TestRefine:
    def test_round(self, client, provider, db):
        r = refine(client, source={"private_task_id": PRIVATE_ID}, answer="Tak")
        assert r.status_code == 200, r.text
        round_ = r.json()["round"]
        assert [v["trigger"] for v in round_["variants"]] == [V1.trigger, V2.trigger]
        assert round_["questions"] == ["Czy to działa dla iloczynu?"]
        assert round_["category"] == "kombinatoryka"
        _, draft, source_text, history, answer = provider.calls[0]
        assert "Wymyślone zadanie o parzystości." in source_text
        assert answer == "Tak"
        assert usage(db, service.KIND_REFINE) == 1

    def test_history_is_compacted_to_the_chosen_variants(self, client, provider):
        history = [{"draft": {"raw": "x"}, "variants": [V1.model_dump(), V2.model_dump()],
                    "questions": ["q?"], "answer": "a", "chosen": 1}] * 5
        refine(client, history=history)
        sent = provider.calls[0][3]
        assert len(sent) == 3
        assert sent[0] == {"chosen": V2.model_dump(), "questions": ["q?"], "answer": "a"}

    def test_empty_draft_is_422(self, client, provider):
        assert client.post("/api/patterns/refine", json={"draft": {}}).status_code == 422
        assert provider.calls == []

    def test_existing_pattern_uses_stored_text(self, client, provider):
        p = create(client, source={"private_task_id": PRIVATE_ID})
        r = client.post("/api/patterns/refine", json={"pattern_id": p["id"]})
        assert r.status_code == 200
        _, draft, source_text, _, _ = provider.calls[0]
        assert draft["trigger"] == p["trigger"]
        assert "Wymyślone zadanie" in source_text

    def test_other_users_pattern_is_404(self, client, provider, current_user):
        p = create(client)
        current_user["id"] = OTHER_USER_ID
        assert client.post("/api/patterns/refine", json={"pattern_id": p["id"]}).status_code == 404

    def test_limit(self, client, provider, db, monkeypatch):
        monkeypatch.setattr(settings, "rate_limit_pattern_refines_per_user_per_day", 2)
        assert refine(client).status_code == 200
        assert refine(client).status_code == 200
        r = refine(client)
        assert r.status_code == 429
        assert "Retry-After" in r.headers
        assert usage(db, service.KIND_REFINE) == 2

    def test_allowlisted_user_not_limited(self, client, provider, monkeypatch):
        import app.private_tasks.routes as private_routes

        monkeypatch.setattr(settings, "rate_limit_pattern_refines_per_user_per_day", 1)
        monkeypatch.setattr(private_routes, "_get_allowed_emails", lambda: {f"{USER_ID}@example.com"})
        assert refine(client).status_code == 200
        assert refine(client).status_code == 200

    def test_racing_requests_never_exceed_the_cap(self, client, provider, db, monkeypatch):
        from app.db.private_tasks import AIUsageRepository

        monkeypatch.setattr(settings, "rate_limit_pattern_refines_per_user_per_day", 1)
        original = AIUsageRepository.user_window
        state = {"raced": False}

        def racing_window(self, user_id, kinds, hours=24):
            result = original(self, user_id, kinds, hours)
            if not state["raced"]:
                state["raced"] = True
                state["b"] = refine(client).status_code
            return result

        monkeypatch.setattr(AIUsageRepository, "user_window", racing_window)
        a = refine(client).status_code
        assert sorted([a, state["b"]]).count(200) <= 1
        assert len(provider.calls) <= 1

    @pytest.mark.parametrize(
        "setup,code",
        [
            (lambda p: setattr(p.refine, "abuse_score", 80), 422),
            (lambda p: setattr(p, "error", AIContentBlockedError("blocked")), 422),
            (lambda p: setattr(p, "error", AIProviderError("timeout")), 502),
            (lambda p: setattr(p.refine, "variants", [V1]), 502),
        ],
    )
    def test_failures_still_count(self, client, provider, db, setup, code):
        setup(provider)
        assert refine(client).status_code == code
        assert usage(db, service.KIND_REFINE) == 1


class TestSuggest:
    def add_submission(self, db, sid="sub00001", user_id=USER_ID, status=SubmissionStatus.COMPLETED):
        db.add(SubmissionDB(id=sid, user_id=user_id, private_task_id=PRIVATE_ID if user_id == USER_ID else None,
                            year=None if user_id == USER_ID else "2024",
                            etap=None if user_id == USER_ID else "etap1",
                            task_number=None if user_id == USER_ID else 1,
                            images=[], status=status, score=5, feedback="Uczeń użył parzystości."))
        db.commit()

    def test_happy_path(self, client, provider, db):
        self.add_submission(db)
        r = client.post("/api/patterns/suggest", json={"submission_id": "sub00001", "draft": "parzystość"})
        assert r.status_code == 200, r.text
        assert r.json()["suggestions"][0]["why"] == "Często"
        _, task_text, feedback, draft = provider.calls[0]
        assert "Wymyślone zadanie" in task_text
        assert feedback == "Uczeń użył parzystości."
        assert draft == "parzystość"
        assert usage(db, service.KIND_SUGGEST) == 1

    def test_foreign_submission_is_404(self, client, provider, db):
        self.add_submission(db, user_id=OTHER_USER_ID)
        assert client.post("/api/patterns/suggest", json={"submission_id": "sub00001"}).status_code == 404
        assert provider.calls == []

    def test_pending_submission_is_409(self, client, provider, db):
        self.add_submission(db, status=SubmissionStatus.PENDING)
        assert client.post("/api/patterns/suggest", json={"submission_id": "sub00001"}).status_code == 409

    def test_no_suggestions_is_502(self, client, provider, db):
        self.add_submission(db)
        provider.suggest.suggestions = []
        assert client.post("/api/patterns/suggest", json={"submission_id": "sub00001"}).status_code == 502


CANDIDATES = [
    TaskInfo(year="2023", etap="etap1", number=n, title=f"Zadanie {n}", pdf=TaskPdf(tasks="t.pdf"),
             difficulty=2, categories=["kombinatoryka"], hints=["a", "b", "c", "d"])
    for n in (1, 2, 3)
]


class TestSuggestLinks:
    @pytest.fixture
    def all_tasks(self, monkeypatch):
        tasks = list(CANDIDATES)
        monkeypatch.setattr(service, "all_omj_tasks", lambda: tasks)
        return tasks

    def test_stores_suggested_links(self, client, provider, db, all_tasks, omj):
        for t in all_tasks:
            omj[(t.year, t.etap, t.number)] = t
        p = create(client, category="kombinatoryka")
        provider.links = LinkResult(links=[LinkSuggestion(task_key="2023_etap1_2", reason="Pasuje")])
        r = client.post(f"/api/patterns/{p['id']}/suggest-links")
        assert r.status_code == 200, r.text
        [link] = r.json()["links"]
        assert (link["task_key"], link["status"], link["origin"], link["reason"]) == (
            "2023_etap1_2", "suggested", "ai", "Pasuje")
        _, _, candidates = provider.calls[0]
        assert [c["task_key"] for c in candidates] == ["2023_etap1_1", "2023_etap1_2", "2023_etap1_3"]
        assert usage(db, service.KIND_LINK) == 1

    def test_linked_and_rejected_tasks_are_not_candidates(self, client, provider, db, all_tasks, omj):
        for t in all_tasks:
            omj[(t.year, t.etap, t.number)] = t
        p = create(client, category="kombinatoryka", source={"task_key": "2023_etap1_1"})
        link = client.post(f"/api/patterns/{p['id']}/links", json={"task_key": "2023_etap1_2"}).json()["link"]
        client.patch(f"/api/patterns/{p['id']}/links/{link['id']}", json={"status": "rejected"})
        client.post(f"/api/patterns/{p['id']}/suggest-links")
        _, _, candidates = provider.calls[0]
        assert [c["task_key"] for c in candidates] == ["2023_etap1_3"]

    def test_no_candidates_no_ai_call(self, client, provider, db, all_tasks):
        p = create(client, category="geometria")
        r = client.post(f"/api/patterns/{p['id']}/suggest-links")
        assert r.json() == {"links": []}
        assert provider.calls == []
        assert usage(db, service.KIND_LINK) == 0

    def test_abuse_refused(self, client, provider, db, all_tasks):
        p = create(client, category="kombinatoryka")
        provider.links = LinkResult(links=[LinkSuggestion(task_key="2023_etap1_2")], abuse_score=90)
        assert client.post(f"/api/patterns/{p['id']}/suggest-links").status_code == 422
        assert db.query(PatternLinkDB).filter_by(origin="ai").count() == 0


class TestLongSessions:
    def test_refine_with_many_rounds_of_history(self, client, provider):
        history = [{"draft": {"raw": "x"}, "variants": [V1.model_dump(), V2.model_dump()],
                    "questions": [], "answer": None, "chosen": 0}] * 14
        assert refine(client, history=history).status_code == 200


def test_history_pairs_each_answer_with_the_questions_it_answers():
    # A round stores the answer sent to REQUEST it - the reply to the round before
    rounds = [
        {"variants": [V1.model_dump()], "chosen": 0, "questions": ["Q0?"], "answer": None},
        {"variants": [V2.model_dump()], "chosen": 0, "questions": ["Q1?"], "answer": "odpowiedź na Q0"},
    ]
    compacted = service.compact_history(rounds, current_answer="odpowiedź na Q1")
    assert [(r["questions"], r["answer"]) for r in compacted] == [
        (["Q0?"], "odpowiedź na Q0"),
        (["Q1?"], "odpowiedź na Q1"),
    ]
    assert compacted[1]["chosen"] == V2.model_dump()
