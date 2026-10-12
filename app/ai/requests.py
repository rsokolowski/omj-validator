"""Provider-neutral text of every AI request.

Both providers send exactly these strings, so an A/B compares models, not prompts.

Pure functions: no SDK types, no I/O beyond loading the prompt files. A provider
decides only how the strings and the files/photos are packaged into its request.
Gemini's output is pinned by tests/test_ai_requests_snapshot.py.
"""

from typing import Optional

from .prompt_builder import build_private_scoring_prompt, load_private_prompt, solution_shape_line

# ------------------------------------------------------------------ grading


def photo_label(index: int) -> str:
    """Label placed before the index-th (1-based) student photo."""
    return f"Zdjęcie {index}:"


def omj_grading_text(
    prompt_text: str, task_number: int, has_solution_pdf: bool, num_images: int, has_text: bool
) -> str:
    """The text that opens an OMJ grading request.

    The parts that follow it, in order: task PDF, official solution PDF (if
    any), the photos, the typed solution block (if any), the closing line.
    """
    full_prompt = prompt_text
    full_prompt += f"\n\n## Zadanie {task_number}\n"
    full_prompt += "Przeanalizuj poniższe pliki.\n\n"
    full_prompt += "### Treść zadania (PDF):\n"
    full_prompt += f"Znajdź 'Zadanie {task_number}.' w dokumencie powyżej.\n\n"
    if has_solution_pdf:
        full_prompt += "### Oficjalne rozwiązanie (TYLKO do weryfikacji, NIE pokazuj uczniowi):\n"
        full_prompt += "\n"
    full_prompt += "### Rozwiązanie ucznia:\n"
    full_prompt += solution_shape_line(num_images, has_text)
    for i in range(num_images):
        full_prompt += f"{photo_label(i + 1)}\n"
    return full_prompt


def private_grading_text(task_title: str, task_content: str, num_images: int, has_text: bool) -> str:
    """The text that opens a private-task grading request (photos labelled after it)."""
    return (
        f"{build_private_scoring_prompt()}\n\n"
        f"## Treść zadania (tekst podany przez ucznia)\n"
        f"### {task_title}\n{task_content}\n\n"
        f"### Rozwiązanie ucznia:\n{solution_shape_line(num_images, has_text)}"
    )


# ------------------------------------------------------------ private tasks


def extract_text() -> str:
    """Instruction sent before the photos of a page to read problems off."""
    return load_private_prompt("extract")


def meta_text(title: str, content: str) -> str:
    """Request for hints, category and difficulty of a private task statement."""
    return (
        f"{load_private_prompt('meta')}\n\n"
        f"## Tytuł zadania\n{title}\n\n"
        f"## Treść zadania\n{content}\n"
    )


# ----------------------------------------------------------------- patterns


def student_text(text: Optional[str]) -> str:
    """Student-controlled text as fenced data (the fence cannot be closed early)."""
    cleaned = (text or "").replace("<<<", "").replace(">>>", "").strip()
    return f"<<<\n{cleaned or '(brak)'}\n>>>"


def draft_text(draft: dict) -> str:
    """A pattern draft as labelled lines (trigger/action/example/note), else its raw note."""
    if draft.get("trigger") or draft.get("action"):
        lines = [
            f"Wyzwalacz: {draft.get('trigger', '')}",
            f"Akcja: {draft.get('action', '')}",
        ]
        if draft.get("example"):
            lines.append(f"Przykład: {draft['example']}")
        if draft.get("raw"):
            lines.append(f"Notatka: {draft['raw']}")
        return "\n".join(lines)
    return draft.get("raw", "")


def answers_text(pairs: list[dict]) -> str:
    """The student's answers to the previous round's questions, question by question."""
    return "\n".join(f"Pytanie: {p['question']}\nOdpowiedź: {p['answer']}" for p in pairs)


def conversation_text(history: list[dict]) -> str:
    """The refine rounds so far, turn by turn, including the versions offered."""
    blocks = []
    for number, turn in enumerate(history, 1):
        lines = [f"### Runda {number}"]
        if turn.get("draft"):
            lines.append(f"Uczeń - szkic: {draft_text(turn['draft'])}")
        if turn.get("answers"):
            lines.append(f"Uczeń - odpowiedzi:\n{answers_text(turn['answers'])}")
        if turn.get("message"):
            lines.append(f"Uczeń - wiadomość: {turn['message']}")
        if turn.get("reply"):
            lines.append(f"Ty - odpowiedź: {turn['reply']}")
        lines.append(f"Ty - ocena szkicu: {turn.get('verdict')}; {turn.get('comment') or ''}")
        for index, variant in enumerate(turn.get("variants") or [], 1):
            tasks = ", ".join(variant.get("tasks") or []) or "brak"
            lines.append(
                f"Ty - wersja {index}: Kiedy widzę {variant.get('trigger')} -> {variant.get('action')}"
                f" (uwaga: {variant.get('note') or '-'}; zadania: {tasks})"
            )
        if turn.get("questions"):
            lines.append(f"Ty - pytania: {' / '.join(turn['questions'])}")
        chosen = turn.get("chosen")
        lines.append(
            f"Uczeń wybrał wersję {chosen + 1}" if isinstance(chosen, int) else "Uczeń nie wybrał żadnej wersji"
        )
        blocks.append("\n".join(lines))
    return "\n\n".join(blocks)


def _candidate_lines(candidates: list[dict]) -> list[str]:
    """One line per candidate OMJ task: key | difficulty | categories | our hints."""
    lines = []
    for c in candidates:
        hints = " | ".join(c.get("hints") or [])
        lines.append(
            f"- {c['task_key']} | trudność {c.get('difficulty') or '?'} | "
            f"{', '.join(c.get('categories') or [])} | {hints}"
        )
    return lines


def refine_text(
    draft: dict,
    source_text: Optional[str],
    history: list[dict],
    current: dict,
    candidates: list[dict],
    skills: list,
) -> str:
    """One refine turn. ``skills``: objects with ``.id`` and ``.name``."""
    skill_lines = "\n".join(f"- {s.id}: {s.name}" for s in skills)
    task_lines = _candidate_lines(candidates)
    return (
        f"{load_private_prompt('pattern_refine')}\n\n"
        f"## Lista umiejętności (skills)\n{skill_lines}\n\n"
        f"## Zadania OMJ (klucz | trudność | działy | nasze wskazówki)\n"
        f"{chr(10).join(task_lines) or '(brak listy - nie podawaj zadań)'}\n\n"
        f"## Zadanie, przy którym uczeń zauważył wzorzec\n{student_text(source_text)}\n\n"
        f"## Dotychczasowa rozmowa\n{student_text(conversation_text(history))}\n\n"
        f"## Aktualny szkic wzorca ucznia (z formularza)\n{student_text(draft_text(draft))}\n\n"
        f"## Odpowiedzi ucznia na Twoje ostatnie pytania\n"
        f"{student_text(answers_text(current.get('answers') or []))}\n\n"
        f"## Wiadomość ucznia do Ciebie\n{student_text(current.get('message'))}\n"
    )


def suggest_text(task_text: str, feedback: str, draft: Optional[str]) -> str:
    """Request for patterns worth remembering from a graded solution (all inputs fenced)."""
    return (
        f"{load_private_prompt('pattern_suggest')}\n\n"
        f"## Treść zadania\n{student_text(task_text)}\n\n"
        f"## Ocena rozwiązania ucznia\n{student_text(feedback)}\n\n"
        f"## Szkic wzorca ucznia\n{student_text(draft)}\n"
    )


def link_text(pattern: dict, candidates: list[dict]) -> str:
    """Request to pick OMJ tasks exercising a pattern from server-chosen candidates."""
    return (
        f"{load_private_prompt('pattern_link')}\n\n"
        f"## Wzorzec ucznia\n{student_text(draft_text(pattern))}\n\n"
        f"## Kandydaci\n" + "\n".join(_candidate_lines(candidates)) + "\n"
    )
