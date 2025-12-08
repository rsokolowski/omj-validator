"""AI Provider Protocol - defines contract for all AI providers."""

from pathlib import Path
from typing import Optional, Protocol, runtime_checkable

from ..models import SubmissionResult


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
    ) -> SubmissionResult:
        """
        Analyze a student's solution.

        Args:
            task_pdf_path: Path to the task PDF
            solution_pdf_path: Path to the official solution PDF (for reference)
            image_paths: Paths to uploaded images of student's solution
            task_number: The task number (1-7 for etap1, 1-5 for etap2/etap3)
            etap: The competition stage ("etap1", "etap2", or "etap3")

        Returns:
            SubmissionResult with score and feedback
        """
        ...

    def get_timeout(self) -> int:
        """Return timeout in seconds for this provider."""
        ...
