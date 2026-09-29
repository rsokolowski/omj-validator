"""AI Provider Protocol - defines contract for all AI providers."""

from pathlib import Path
from typing import Optional, Protocol, runtime_checkable

from ..models import (
    LinkResult,
    PrivateExtractionResult,
    PrivateTaskMeta,
    RefineResult,
    SubmissionResult,
    SuggestResult,
)


@runtime_checkable
class AIProvider(Protocol):
    """Protocol defining the interface for AI solution analyzers."""

    async def analyze_solution(
        self,
        task_pdf_path: Path,
        solution_pdf_path: Optional[Path],
        image_paths: list[Path],
        task_number: int,
        etap: str = "etap2",
        solution_text: Optional[str] = None,
    ) -> SubmissionResult:
        """
        Analyze a student's solution.

        Args:
            task_pdf_path: Path to the task PDF
            solution_pdf_path: Path to the official solution PDF (for reference)
            image_paths: Paths to uploaded images of student's solution
            task_number: The task number (1-7 for etap1, 1-5 for etap2/etap3)
            etap: The competition stage ("etap1", "etap2", or "etap3")
            solution_text: Typed solution, plain text with $LaTeX$; None when photos only

        Returns:
            SubmissionResult with score and feedback
        """
        ...

    async def extract_private_tasks(self, image_paths: list[Path]) -> PrivateExtractionResult:
        """Read every problem statement off photos of a page (private tasks)."""
        ...

    async def generate_private_task_meta(self, title: str, content: str) -> PrivateTaskMeta:
        """Hints, category and difficulty for a private task statement."""
        ...

    async def analyze_private_solution_stream(
        self,
        task_title: str,
        task_content: str,
        image_paths: list[Path],
        on_thinking=None,
        on_upload_complete=None,
        solution_text: Optional[str] = None,
    ) -> SubmissionResult:
        """Grade a solution to a private task (no official solution exists)."""
        ...

    async def refine_pattern(
        self, draft: dict, source_text: Optional[str], history: list[dict], answer: Optional[str]
    ) -> RefineResult:
        """One guided refine round for a pattern (versions, verdict, questions)."""
        ...

    async def suggest_patterns(self, task_text: str, feedback: str, draft: Optional[str]) -> SuggestResult:
        """Patterns worth remembering, from a graded solution's feedback."""
        ...

    async def link_pattern_tasks(self, pattern: dict, candidates: list[dict]) -> LinkResult:
        """Pick the candidate OMJ tasks that exercise a pattern."""
        ...

    def get_timeout(self) -> int:
        """Return timeout in seconds for this provider."""
        ...
