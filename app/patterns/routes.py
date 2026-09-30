"""HTTP API for patterns ("Wzorce").

Same audience and rules as private tasks: a signed-in user with submit rights,
and a pattern id that does not exist or belongs to somebody else is a 404.
Every AI call is reserved in ai_usage before it is made and still counts when
it fails (it still cost Gemini money).
"""

import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from ..ai import AIContentBlockedError, AIProviderError, create_ai_provider
from ..config import settings
from ..db import get_db
from ..db.models import PatternDB, PatternLinkDB, PrivateTaskDB, SubmissionDB, SubmissionStatus
from ..db.patterns import PatternRepository
from ..db.private_tasks import PrivateTaskRepository
from ..db.repositories import ensure_utc
from ..models import (
    PATTERN_ROUNDS_MAX,
    PATTERN_SKILLS_MAX,
    PRIVATE_TASK_CATEGORIES,
    CreatePatternRequest,
    LinkStatusRequest,
    ManualLinkRequest,
    PatternSource,
    RefineRequest,
    RefineRoundIn,
    ReviewRequest,
    SuggestPatternRequest,
    UpdatePatternRequest,
)
from ..privacy import mask_user_id
from ..private_tasks import routes as private_routes
from ..private_tasks import service as private_service
from ..skills import get_skill
from . import linking, service, srs

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/patterns", tags=["patterns"])

NOT_FOUND = "Nie znaleziono wzorca"
TASK_NOT_FOUND = "Nie znaleziono zadania"
NOT_DUE = "Ten wzorzec nie czeka dziś na powtórkę."
REFUSED = "Tej treści nie możemy przetworzyć."
AI_FAILED = "Przepraszamy, coś poszło nie tak. Spróbuj ponownie za chwilę."


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


# --------------------------------------------------------------------- helpers


async def current_member_id(request: Request) -> str:
    """Signed-in user with submit rights, or 401/403 (same rule as private tasks)."""
    return await private_routes.current_member_id(request)


def is_allowlisted(request: Request) -> bool:
    return private_routes._is_allowlisted(request)


def owned_pattern(db: Session, pattern_id: str, user_id: str) -> PatternDB:
    if not service.PATTERN_ID_PATTERN.match(pattern_id or ""):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=NOT_FOUND)
    pattern = PatternRepository(db).get_owned(pattern_id, user_id)
    if pattern is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=NOT_FOUND)
    return pattern


def owned_private_task(db: Session, task_id: Optional[str], user_id: str) -> PrivateTaskDB:
    if not private_service.TASK_ID_PATTERN.match(task_id or ""):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=TASK_NOT_FOUND)
    task = PrivateTaskRepository(db).get_owned(task_id, user_id)
    if task is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=TASK_NOT_FOUND)
    return task


def resolve_source(db: Session, source: Optional[PatternSource], user_id: str) -> Optional[dict]:
    """{"task_key"} or {"private_task_id"} of an existing task, None for no source; 404 otherwise."""
    if source is None or not (source.task_key or source.private_task_id):
        return None
    if source.task_key and source.private_task_id:
        raise HTTPException(status_code=422, detail="Podaj jedno zadanie.")
    if source.task_key:
        task = service.omj_task(source.task_key)
        if task is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=TASK_NOT_FOUND)
        return {"task_key": linking.task_key(task)}  # canonical, so "_03" and "_3" dedupe
    task = owned_private_task(db, source.private_task_id, user_id)
    return {"private_task_id": task.id}


def known_skills(skills: list[str]) -> list[str]:
    result: list[str] = []
    for skill in skills:
        if skill not in result and get_skill(skill) is not None:
            result.append(skill)
    return result[:PATTERN_SKILLS_MAX]


def _round_time(value: Optional[str]) -> str:
    """The round's own ISO time when it is a sane past one, else now."""
    now = datetime.now(timezone.utc)
    try:
        at = datetime.fromisoformat(value or "")
    except ValueError:
        return now.isoformat()
    at = at if at.tzinfo else at.replace(tzinfo=timezone.utc)
    return at.isoformat() if at <= now else now.isoformat()


def stored_round(round_: RefineRoundIn) -> dict:
    """A round as saved: the proposal is filtered like the pattern's own fields."""
    data = round_.model_dump()
    data["category"] = round_.category if round_.category in PRIVATE_TASK_CATEGORIES else None
    data["skills"] = known_skills(round_.skills)
    data["at"] = _round_time(round_.at)
    return data


def link_target(db: Session, link: PatternLinkDB) -> dict:
    """Title, URL and availability of a linked task, never raising."""
    if link.task_key:
        task = service.omj_task(link.task_key)
        if task is None:
            return {"kind": "omj", "title": link.task_key, "url": None, "available": False}
        return {
            "kind": "omj",
            "title": task.title,
            "label": f"{task.year} · {task.etap} · zad. {task.number}",
            "url": f"/task/{task.year}/{task.etap}/{task.number}",
            "difficulty": task.difficulty,
            "available": True,
        }
    task = db.get(PrivateTaskDB, link.private_task_id)
    if task is None:
        return {"kind": "private", "title": "", "url": None, "available": False}
    return {
        "kind": "private",
        "title": task.title,
        "label": "Moje zadania",
        "url": f"/moje-zadania/{task.id}",
        "difficulty": task.difficulty,
        "available": True,
    }


def serialize_link(db: Session, link: PatternLinkDB) -> dict:
    return {
        "id": link.id,
        "role": link.role,
        "origin": link.origin,
        "status": link.status,
        "reason": link.reason,
        "task_key": link.task_key,
        "private_task_id": link.private_task_id,
        **link_target(db, link),
    }


def serialize_pattern(db: Session, pattern: PatternDB, *, detail: bool = False) -> dict:
    today = srs.today_warsaw()
    links = [l for l in pattern.links if l.status != "rejected"]
    data = {
        "id": pattern.id,
        "trigger": pattern.trigger,
        "action": pattern.action,
        "example": pattern.example,
        "category": pattern.category,
        "skills": list(pattern.skills or []),
        "origin": pattern.origin,
        "level": pattern.srs_level,
        "streak": pattern.srs_streak,
        "due_on": pattern.due_on.isoformat(),
        "is_due": pattern.archived_at is None and pattern.due_on <= today,
        "review_count": pattern.review_count,
        "lapse_count": pattern.lapse_count,
        "archived": pattern.archived_at is not None,
        "created_at": ensure_utc(pattern.created_at).isoformat(),
        "last_reviewed_at": ensure_utc(pattern.last_reviewed_at).isoformat() if pattern.last_reviewed_at else None,
        "links_count": sum(1 for l in links if l.status == "accepted"),
        "suggested_links_count": sum(1 for l in links if l.status == "suggested"),
    }
    if detail:
        data["links"] = [serialize_link(db, l) for l in links]
        data["refinement"] = list(pattern.refinement or [])
        data["reviews"] = [
            {
                "id": r.id,
                "kind": r.kind,
                "outcome": r.outcome,
                "recall_text": r.recall_text,
                "submission_id": r.submission_id,
                "level_before": r.level_before,
                "level_after": r.level_after,
                "due_after": r.due_after.isoformat(),
                "created_at": ensure_utc(r.created_at).isoformat(),
            }
            for r in sorted(pattern.reviews, key=lambda r: r.id, reverse=True)[:20]
        ]
    return data


# ------------------------------------------------------------------- patterns


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_pattern(request: Request, payload: CreatePatternRequest, db: Session = Depends(get_db)):
    user_id = await current_member_id(request)
    source = resolve_source(db, payload.source, user_id)
    repo = PatternRepository(db)
    pattern = repo.create(
        user_id,
        trigger=payload.trigger,
        action=payload.action,
        example=(payload.example or "").strip() or None,
        category=payload.category,
        skills=known_skills(payload.skills),
        origin=payload.origin,
        refinement=[stored_round(r) for r in payload.refinement][-PATTERN_ROUNDS_MAX:],
        due_on=srs.initial_due(srs.today_warsaw()),
    )
    if source is not None:
        repo.add_link(pattern, role="source", origin="manual", status="accepted", **source)
    return {"pattern": serialize_pattern(db, pattern, detail=True)}


@router.get("")
async def list_patterns(
    request: Request,
    category: Optional[str] = None,
    archived: bool = False,
    task_key: Optional[str] = None,
    private_task_id: Optional[str] = None,
    db: Session = Depends(get_db),
):
    user_id = await current_member_id(request)
    patterns = PatternRepository(db).list_for_user(
        user_id, category=category, archived=archived, task_key=task_key, private_task_id=private_task_id
    )
    return {"patterns": [serialize_pattern(db, p) for p in patterns]}


@router.get("/queue")
async def review_queue(request: Request, limit: int = 10, db: Session = Depends(get_db)):
    """Patterns to review today, most overdue first, categories interleaved.

    ``limit=0`` returns only the count (the header badge polls it).
    """
    user_id = await current_member_id(request)
    repo = PatternRepository(db)
    today = srs.today_warsaw()
    if limit <= 0:
        return {"items": [], "due_total": repo.count_due(user_id, today)}
    limit = min(limit, 50)
    due = repo.due(user_id, today)
    ordered = srs.interleave(due, key=lambda p: p.category)
    return {"items": [serialize_pattern(db, p) for p in ordered[:limit]], "due_total": len(due)}


@router.get("/{pattern_id}")
async def get_pattern(request: Request, pattern_id: str, db: Session = Depends(get_db)):
    user_id = await current_member_id(request)
    return {"pattern": serialize_pattern(db, owned_pattern(db, pattern_id, user_id), detail=True)}


@router.patch("/{pattern_id}")
async def update_pattern(
    request: Request, pattern_id: str, payload: UpdatePatternRequest, db: Session = Depends(get_db)
):
    user_id = await current_member_id(request)
    pattern = owned_pattern(db, pattern_id, user_id)
    sent = payload.model_dump(exclude_unset=True)

    fields: dict = {}
    for name in ("trigger", "action"):
        if sent.get(name):
            fields[name] = sent[name].strip()
    if "example" in sent:
        fields["example"] = (sent["example"] or "").strip() or None
    if "category" in sent:
        fields["category"] = sent["category"]
    if sent.get("skills") is not None:
        fields["skills"] = known_skills(sent["skills"])
    new_rounds = payload.append_rounds + ([payload.append_round] if payload.append_round else [])
    if new_rounds:
        rounds = list(pattern.refinement or []) + [stored_round(r) for r in new_rounds]
        fields["refinement"] = rounds[-PATTERN_ROUNDS_MAX:]
        # The last round's proposal fills what the pattern lacks: without skills or a
        # category, "Znajdź więcej zadań" has no candidates to offer the AI
        latest = new_rounds[-1]
        if not pattern.category and "category" not in fields and latest.category in PRIVATE_TASK_CATEGORIES:
            fields["category"] = latest.category
        if not pattern.skills and "skills" not in fields:
            fields["skills"] = known_skills(latest.skills)
    if payload.archived is not None:
        fields["archived_at"] = _now() if payload.archived else None

    PatternRepository(db).update_fields(pattern, **fields)
    return {"pattern": serialize_pattern(db, pattern, detail=True)}


@router.delete("/{pattern_id}")
async def delete_pattern(request: Request, pattern_id: str, db: Session = Depends(get_db)):
    user_id = await current_member_id(request)
    PatternRepository(db).delete(owned_pattern(db, pattern_id, user_id))
    return {"success": True}


# ---------------------------------------------------------------------- links


@router.post("/{pattern_id}/links", status_code=status.HTTP_201_CREATED)
async def add_link(request: Request, pattern_id: str, payload: ManualLinkRequest, db: Session = Depends(get_db)):
    user_id = await current_member_id(request)
    pattern = owned_pattern(db, pattern_id, user_id)
    if not payload.task_key and not payload.private_task_id:
        raise HTTPException(status_code=422, detail="Wybierz zadanie.")
    target = resolve_source(db, PatternSource(**payload.model_dump()), user_id)
    link = PatternRepository(db).add_link(pattern, role="practice", origin="manual", status="accepted", **target)
    if link is None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="To zadanie jest już połączone z wzorcem.")
    return {"link": serialize_link(db, link)}


def owned_link(db: Session, pattern: PatternDB, link_id: int) -> PatternLinkDB:
    link = PatternRepository(db).get_link(pattern, link_id)
    if link is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=TASK_NOT_FOUND)
    return link


@router.patch("/{pattern_id}/links/{link_id}")
async def set_link_status(
    request: Request, pattern_id: str, link_id: int, payload: LinkStatusRequest, db: Session = Depends(get_db)
):
    user_id = await current_member_id(request)
    pattern = owned_pattern(db, pattern_id, user_id)
    link = PatternRepository(db).set_link_status(owned_link(db, pattern, link_id), payload.status)
    return {"link": serialize_link(db, link)}


@router.delete("/{pattern_id}/links/{link_id}")
async def delete_link(request: Request, pattern_id: str, link_id: int, db: Session = Depends(get_db)):
    user_id = await current_member_id(request)
    pattern = owned_pattern(db, pattern_id, user_id)
    PatternRepository(db).delete_link(owned_link(db, pattern, link_id))
    return {"success": True}


# -------------------------------------------------------------------- reviews


@router.post("/{pattern_id}/review")
async def review_pattern(request: Request, pattern_id: str, payload: ReviewRequest, db: Session = Depends(get_db)):
    """A self-rated recall card. Only a due pattern can be reviewed, once."""
    user_id = await current_member_id(request)
    pattern = owned_pattern(db, pattern_id, user_id)
    today = srs.today_warsaw()
    if pattern.archived_at is not None or pattern.due_on > today:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=NOT_DUE)

    level, streak, due = srs.schedule(pattern.srs_level, pattern.srs_streak, payload.outcome, today)
    review = PatternRepository(db).apply_review(
        pattern,
        seen_due_on=pattern.due_on,
        new_level=level,
        new_streak=streak,
        new_due=due,
        outcome=payload.outcome,
        kind="recall",
        recall_text=payload.recall_text,
    )
    if review is None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=NOT_DUE)
    return {"pattern": serialize_pattern(db, pattern)}


@router.get("/{pattern_id}/practice")
async def practice_task(request: Request, pattern_id: str, db: Session = Depends(get_db)):
    """The linked task to solve instead of a recall card, when one is due."""
    user_id = await current_member_id(request)
    pattern = owned_pattern(db, pattern_id, user_id)
    if not srs.practice_offered(pattern.review_count, pattern.srs_level):
        return {"task": None}
    chosen = srs.choose_practice(service.practice_candidates(db, pattern, user_id), _now())
    if chosen is None:
        return {"task": None}
    if chosen.kind == "omj":
        year, etap, number = service.parse_task_key(chosen.ref)
        url = f"/task/{year}/{etap}/{number}"
    else:
        url = f"/moje-zadania/{chosen.ref}"
    return {"task": {"kind": chosen.kind, "ref": chosen.ref, "title": chosen.title, "url": url}}


# ------------------------------------------------------------------------- AI


def _reserve(db: Session, request: Request, user_id: str, kind: str, limit: int):
    [row] = private_service.reserve_ai_calls(db, user_id, kind, {kind}, limit, is_allowlisted(request))
    return row


async def _call(db: Session, usage_row, user_id: str, call):
    """Run an AI call; blocked or abusive -> 422, failure -> 502. The call counts either way."""
    try:
        result = await call
    except AIContentBlockedError:
        raise HTTPException(status_code=422, detail=REFUSED)
    except AIProviderError as e:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(e))
    except Exception:
        logger.exception("Pattern AI call crashed")
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=AI_FAILED)
    usage_row.meta = result.meta or None
    db.commit()
    if result.abuse_score >= settings.private_abuse_threshold:
        logger.warning(f"Pattern text flagged as manipulation for user {mask_user_id(user_id)}")
        raise HTTPException(status_code=422, detail=REFUSED)
    return result


def _source_text(db: Session, source: Optional[dict]) -> Optional[str]:
    if not source:
        return None
    if source.get("task_key"):
        return service.omj_task_text(source["task_key"])
    task = db.get(PrivateTaskDB, source["private_task_id"])
    return service.private_task_text(task) if task is not None else None


def _pattern_source(pattern: PatternDB) -> Optional[dict]:
    for link in pattern.links:
        if link.role == "source":
            if link.task_key:
                return {"task_key": link.task_key}
            return {"private_task_id": link.private_task_id}
    return None


def _task_hints(source: Optional[dict]) -> tuple[Optional[str], list[str]]:
    """Category and skills of an OMJ source task, to narrow the evidence list."""
    task = service.omj_task(source.get("task_key")) if source else None
    if task is None:
        return None, []
    skills = list(dict.fromkeys(list(task.skills_required) + list(task.skills_gained)))
    return (task.categories[0] if task.categories else None), skills


def refine_evidence(category: Optional[str], skills: list[str], history: list[dict],
                    source: Optional[dict]) -> list[dict]:
    """OMJ tasks the model may name as places where a version applies.

    Narrowed by what is known - the editor's category, else the latest AI
    proposal, else the source task - and the whole list when nothing is.
    """
    latest = history[-1] if history else {}
    source_category, source_skills = _task_hints(source)
    category = category or latest.get("category") or source_category
    skills = skills or list(latest.get("skills") or []) or source_skills
    category = category if category in PRIVATE_TASK_CATEGORIES else None
    skills = known_skills(skills)
    tasks = linking.refine_candidates(service.all_omj_tasks(), skills=skills, category=category)
    narrowed = bool(category or skills)
    return [linking.refine_payload(t, narrowed=narrowed) for t in tasks]


@router.post("/refine")
async def refine_pattern(request: Request, payload: RefineRequest, db: Session = Depends(get_db)):
    """One conversation turn: a reply, 2-3 versions with tasks, a verdict and questions."""
    user_id = await current_member_id(request)
    draft = payload.draft.model_dump()
    history = [r.model_dump() for r in payload.history]
    category, skills = payload.category, []
    if payload.pattern_id:
        pattern = owned_pattern(db, payload.pattern_id, user_id)
        if not (draft["trigger"] or draft["action"] or draft["raw"]):
            draft.update(trigger=pattern.trigger, action=pattern.action, example=pattern.example or "")
        source = _pattern_source(pattern)
        history = list(pattern.refinement or []) + history
        category = category or pattern.category
        skills = list(pattern.skills or [])
    else:
        source = resolve_source(db, payload.source, user_id)
    if not (draft["raw"].strip() or (draft["trigger"].strip() and draft["action"].strip())):
        raise HTTPException(status_code=422, detail="Napisz najpierw swój pomysł na wzorzec.")

    # An old client sends one answer for everything: treat it as the message
    message = payload.message if payload.message is not None else payload.answer
    last_questions = list(history[-1].get("questions") or []) if history else []
    current = {
        "answers": service.round_answers(last_questions, list(payload.answers)),
        "message": (message or "").strip() or None,
    }
    candidates = refine_evidence(category, skills, history, source)

    usage_row = _reserve(db, request, user_id, service.KIND_REFINE,
                         settings.rate_limit_pattern_refines_per_user_per_day)
    result = await _call(db, usage_row, user_id, create_ai_provider().refine_pattern(
        draft, _source_text(db, source), service.compact_history(history), current, candidates,
    ))
    if len(result.variants) < 2:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Nie udało się zaproponować wersji. Spróbuj jeszcze raz.",
        )
    return {
        "round": {
            "draft": draft,
            "answer": None,
            "answers": list(payload.answers),
            "message": current["message"],
            "reply": result.reply,
            "variants": [v.model_dump() for v in result.variants],
            "questions": result.questions,
            "verdict": result.verdict,
            "comment": result.comment,
            "category": result.category,
            "skills": result.skills,
            "at": datetime.now(timezone.utc).isoformat(),
        }
    }


@router.post("/suggest")
async def suggest_patterns(request: Request, payload: SuggestPatternRequest, db: Session = Depends(get_db)):
    """"Podpowiedz wzorzec": patterns worth remembering from a graded solution."""
    user_id = await current_member_id(request)
    submission = db.get(SubmissionDB, payload.submission_id)
    if submission is None or submission.user_id != user_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Nie znaleziono rozwiązania")
    if submission.status != SubmissionStatus.COMPLETED or not submission.feedback:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="To rozwiązanie nie zostało jeszcze ocenione.")
    if submission.private_task_id:
        task_text = _source_text(db, {"private_task_id": submission.private_task_id})
    else:
        task_text = service.omj_task_text(f"{submission.year}_{submission.etap}_{submission.task_number}")

    usage_row = _reserve(db, request, user_id, service.KIND_SUGGEST,
                         settings.rate_limit_pattern_suggests_per_user_per_day)
    result = await _call(db, usage_row, user_id, create_ai_provider().suggest_patterns(
        task_text or "", submission.feedback, payload.draft,
    ))
    if not result.suggestions:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Nie udało się zaproponować wzorca. Spróbuj jeszcze raz.",
        )
    return {"suggestions": [s.model_dump() for s in result.suggestions]}


@router.post("/{pattern_id}/suggest-links")
async def suggest_links(request: Request, pattern_id: str, db: Session = Depends(get_db)):
    """AI picks OMJ tasks that exercise the pattern, from candidates the server chose."""
    user_id = await current_member_id(request)
    pattern = owned_pattern(db, pattern_id, user_id)
    candidates = linking.select_candidates(
        service.all_omj_tasks(),
        skills=list(pattern.skills or []),
        category=pattern.category,
        excluded_keys={l.task_key for l in pattern.links if l.task_key},
        solved_keys=service.solved_omj_keys(db, user_id),
    )
    if not candidates:
        return {"links": []}

    usage_row = _reserve(db, request, user_id, service.KIND_LINK,
                         settings.rate_limit_pattern_links_per_user_per_day)
    result = await _call(db, usage_row, user_id, create_ai_provider().link_pattern_tasks(
        {"trigger": pattern.trigger, "action": pattern.action, "example": pattern.example or ""},
        [linking.candidate_payload(t) for t in candidates],
    ))
    repo = PatternRepository(db)
    created = []
    for suggestion in result.links:
        link = repo.add_link(pattern, task_key=suggestion.task_key, role="practice", origin="ai",
                             status="suggested", reason=suggestion.reason or None)
        if link is not None:
            created.append(serialize_link(db, link))
    return {"links": created}
