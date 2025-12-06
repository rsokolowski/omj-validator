"""Gemini API provider implementation."""

import asyncio
from pathlib import Path
from typing import Optional

from ...config import settings
from ...models import SubmissionResult
from ..parsing import parse_ai_response

try:
    import google.generativeai as genai

    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False
    genai = None


class GeminiProvider:
    """AI provider using Google Gemini API for solution analysis."""

    def __init__(self):
        """Initialize Gemini provider with API key."""
        if not GEMINI_AVAILABLE:
            raise ImportError(
                "google-generativeai package not installed. "
                "Install with: pip install google-generativeai"
            )

        if not settings.gemini_api_key:
            raise ValueError("GEMINI_API_KEY is required. Set it in your .env file.")

        genai.configure(api_key=settings.gemini_api_key)
        self._model = genai.GenerativeModel(settings.gemini_model)

    def _load_prompt(self) -> str:
        """Load Gemini-specific prompt from file."""
        with open(settings.gemini_prompt_path, "r", encoding="utf-8") as f:
            return f.read()

    def get_timeout(self) -> int:
        """Return timeout in seconds for Gemini API."""
        return settings.gemini_timeout

    async def analyze_solution(
        self,
        task_pdf_path: Path,
        solution_pdf_path: Optional[Path],
        image_paths: list[Path],
        task_number: int,
    ) -> SubmissionResult:
        """
        Analyze a student's solution using Gemini API.

        Args:
            task_pdf_path: Path to the task PDF
            solution_pdf_path: Path to the official solution PDF (for reference)
            image_paths: Paths to uploaded images of student's solution
            task_number: The task number (1-5)

        Returns:
            SubmissionResult with score and feedback
        """
        uploaded_files = []

        try:
            # Build content parts for multimodal request
            content_parts = []

            # Add system prompt
            prompt_text = self._load_prompt()
            prompt_text += f"\n\n## Zadanie {task_number}\n"
            prompt_text += "Przeanalizuj poniższe pliki.\n\n"

            # Upload task PDF
            prompt_text += "### Treść zadania (PDF):\n"
            task_file = await self._upload_file(task_pdf_path)
            uploaded_files.append(task_file)
            content_parts.append(task_file)
            prompt_text += (
                f"Znajdź 'Zadanie {task_number}.' w dokumencie powyżej.\n\n"
            )

            # Upload solution PDF if exists
            if solution_pdf_path and solution_pdf_path.exists():
                prompt_text += "### Oficjalne rozwiązanie (TYLKO do weryfikacji, NIE pokazuj uczniowi):\n"
                solution_file = await self._upload_file(solution_pdf_path)
                uploaded_files.append(solution_file)
                content_parts.append(solution_file)
                prompt_text += "\n"

            # Upload student images
            prompt_text += "### Rozwiązanie ucznia:\n"
            for i, img_path in enumerate(image_paths, 1):
                prompt_text += f"Zdjęcie {i}:\n"
                img_file = await self._upload_file(img_path)
                uploaded_files.append(img_file)
                content_parts.append(img_file)

            prompt_text += "\n\nOceń rozwiązanie i odpowiedz WYŁĄCZNIE w formacie JSON."

            # Prepend prompt text to content
            content_parts.insert(0, prompt_text)

            # Generate response with timeout
            response = await asyncio.wait_for(
                asyncio.to_thread(
                    self._model.generate_content,
                    content_parts,
                ),
                timeout=self.get_timeout(),
            )

            # Extract text from response
            if not response.text:
                return SubmissionResult(
                    score=0,
                    feedback="Gemini nie zwrócił odpowiedzi. Spróbuj ponownie.",
                )

            # Use shared parsing utility
            return parse_ai_response(response.text, provider_name="Gemini")

        except asyncio.TimeoutError:
            return SubmissionResult(
                score=0,
                feedback="Przekroczono limit czasu analizy Gemini. Spróbuj ponownie.",
            )
        except Exception as e:
            error_msg = str(e)
            # Handle common Gemini API errors with user-friendly messages
            if "quota" in error_msg.lower():
                return SubmissionResult(
                    score=0,
                    feedback="Przekroczono limit zapytań do Gemini API. Spróbuj ponownie później.",
                )
            elif "invalid" in error_msg.lower() and "key" in error_msg.lower():
                return SubmissionResult(
                    score=0,
                    feedback="Nieprawidłowy klucz API Gemini. Sprawdź konfigurację.",
                )
            return SubmissionResult(
                score=0,
                feedback=f"Błąd Gemini API: {error_msg}",
            )
        finally:
            # Clean up uploaded files from Gemini servers
            await self._cleanup_files(uploaded_files)

    async def _upload_file(self, file_path: Path) -> "genai.File":
        """
        Upload a file to Gemini File API.

        Args:
            file_path: Path to the file to upload

        Returns:
            Gemini File object reference
        """
        # Gemini upload is sync, wrap in thread
        return await asyncio.to_thread(
            genai.upload_file,
            str(file_path),
        )

    async def _cleanup_files(self, files: list) -> None:
        """
        Delete uploaded files from Gemini servers.

        Args:
            files: List of Gemini File objects to delete
        """
        for file in files:
            try:
                await asyncio.to_thread(genai.delete_file, file.name)
            except Exception:
                # Log but don't fail if cleanup fails
                pass
