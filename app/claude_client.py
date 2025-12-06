"""
Backward-compatible wrapper for AI solution analysis.

This module maintains the existing analyze_solution() function signature
while delegating to the new AI provider abstraction layer.
"""

from pathlib import Path
from typing import Optional

from .ai import create_ai_provider
from .models import SubmissionResult


async def analyze_solution(
    task_pdf_path: Path,
    solution_pdf_path: Optional[Path],
    image_paths: list[Path],
    task_number: int,
) -> SubmissionResult:
    """
    Analyze a student's solution using the configured AI provider.

    This function maintains backward compatibility with existing code
    while supporting multiple AI providers (Claude, Gemini) based on
    the AI_PROVIDER setting.

    Args:
        task_pdf_path: Path to the task PDF
        solution_pdf_path: Path to the official solution PDF (for reference)
        image_paths: Paths to uploaded images of student's solution
        task_number: The task number (1-5)

    Returns:
        SubmissionResult with score and feedback
    """
    try:
        provider = create_ai_provider()
        return await provider.analyze_solution(
            task_pdf_path=task_pdf_path,
            solution_pdf_path=solution_pdf_path,
            image_paths=image_paths,
            task_number=task_number,
        )
    except Exception as e:
        # Catch factory errors (missing config, unknown provider)
        return SubmissionResult(
            score=0,
            feedback=f"Błąd konfiguracji AI: {str(e)}",
        )
