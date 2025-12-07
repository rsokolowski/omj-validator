"""Gemini API provider implementation."""

import asyncio
import logging
import time
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

logger = logging.getLogger(__name__)

# Gemini pricing per 1M tokens (USD)
# See https://ai.google.dev/gemini-api/docs/pricing
GEMINI_PRICING = {
    # Gemini 3 series
    "gemini-3-pro-preview": {"input": 2.00, "output": 12.00},
    # Gemini 2.5 series
    "gemini-2.5-pro": {"input": 1.25, "output": 10.00},
    "gemini-2.5-flash": {"input": 0.30, "output": 2.50},
    "gemini-2.5-flash-lite": {"input": 0.10, "output": 0.40},
    # Default fallback (gemini-2.5-flash-lite pricing)
    "default": {"input": 0.10, "output": 0.40},
}


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
        self._model_name = settings.gemini_model

    def _calculate_cost(self, input_tokens: int, output_tokens: int) -> float:
        """Calculate estimated cost based on token usage."""
        pricing = GEMINI_PRICING.get(self._model_name, GEMINI_PRICING["default"])
        input_cost = (input_tokens / 1_000_000) * pricing["input"]
        output_cost = (output_tokens / 1_000_000) * pricing["output"]
        return input_cost + output_cost

    def _load_prompt(self, etap: str = "etap2") -> str:
        """Load Gemini-specific prompt from file for given etap."""
        with open(settings.gemini_prompt_path(etap), "r", encoding="utf-8") as f:
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
        etap: str = "etap2",
    ) -> SubmissionResult:
        """
        Analyze a student's solution using Gemini API.

        Args:
            task_pdf_path: Path to the task PDF
            solution_pdf_path: Path to the official solution PDF (for reference)
            image_paths: Paths to uploaded images of student's solution
            task_number: The task number (1-7 for etap1, 1-5 for etap2)
            etap: The competition stage ("etap1" or "etap2")

        Returns:
            SubmissionResult with score and feedback
        """
        uploaded_files = []
        start_time = time.time()

        # Log request metadata
        image_sizes = [p.stat().st_size for p in image_paths if p.exists()]
        total_image_size_kb = sum(image_sizes) / 1024
        logger.info(
            f"[Gemini Request] model={self._model_name}, etap={etap}, "
            f"task={task_number}, images={len(image_paths)}, "
            f"total_image_size={total_image_size_kb:.1f}KB"
        )

        try:
            # Build content parts for multimodal request
            content_parts = []

            # Add system prompt (etap-specific scoring criteria)
            prompt_text = self._load_prompt(etap)
            prompt_text += f"\n\n## Zadanie {task_number}\n"
            prompt_text += "Przeanalizuj poniższe pliki.\n\n"

            # Upload task PDF
            prompt_text += "### Treść zadania (PDF):\n"
            logger.debug(f"[Gemini] Uploading task PDF: {task_pdf_path}")
            task_file = await self._upload_file(task_pdf_path)
            uploaded_files.append(task_file)
            content_parts.append(task_file)
            prompt_text += (
                f"Znajdź 'Zadanie {task_number}.' w dokumencie powyżej.\n\n"
            )

            # Upload solution PDF if exists
            if solution_pdf_path and solution_pdf_path.exists():
                prompt_text += "### Oficjalne rozwiązanie (TYLKO do weryfikacji, NIE pokazuj uczniowi):\n"
                logger.debug(f"[Gemini] Uploading solution PDF: {solution_pdf_path}")
                solution_file = await self._upload_file(solution_pdf_path)
                uploaded_files.append(solution_file)
                content_parts.append(solution_file)
                prompt_text += "\n"

            # Upload student images
            prompt_text += "### Rozwiązanie ucznia:\n"
            for i, img_path in enumerate(image_paths, 1):
                prompt_text += f"Zdjęcie {i}:\n"
                logger.debug(f"[Gemini] Uploading image {i}: {img_path.name}")
                img_file = await self._upload_file(img_path)
                uploaded_files.append(img_file)
                content_parts.append(img_file)

            prompt_text += "\n\nOceń rozwiązanie i odpowiedz WYŁĄCZNIE w formacie JSON."

            # Prepend prompt text to content
            content_parts.insert(0, prompt_text)

            upload_time = time.time() - start_time
            logger.info(f"[Gemini] Files uploaded in {upload_time:.1f}s, sending to API...")

            # Generate response with timeout
            api_start_time = time.time()
            response = await asyncio.wait_for(
                asyncio.to_thread(
                    self._model.generate_content,
                    content_parts,
                ),
                timeout=self.get_timeout(),
            )
            api_time = time.time() - api_start_time

            # Log response metadata and usage
            input_tokens = 0
            output_tokens = 0
            if hasattr(response, "usage_metadata") and response.usage_metadata:
                input_tokens = response.usage_metadata.prompt_token_count or 0
                output_tokens = response.usage_metadata.candidates_token_count or 0
                estimated_cost = self._calculate_cost(input_tokens, output_tokens)
                logger.info(
                    f"[Gemini Response] api_time={api_time:.1f}s, "
                    f"input_tokens={input_tokens:,}, output_tokens={output_tokens:,}, "
                    f"estimated_cost=${estimated_cost:.4f}"
                )
            else:
                logger.info(f"[Gemini Response] api_time={api_time:.1f}s (no usage metadata)")

            total_time = time.time() - start_time
            logger.info(f"[Gemini] Total request time: {total_time:.1f}s")

            # Extract text from response
            if not response.text:
                logger.warning("[Gemini] Empty response text received")
                return SubmissionResult(
                    score=0,
                    feedback="Gemini nie zwrócił odpowiedzi. Spróbuj ponownie.",
                )

            # Use shared parsing utility with etap-specific scoring
            return parse_ai_response(response.text, provider_name="Gemini", etap=etap)

        except asyncio.TimeoutError:
            elapsed = time.time() - start_time
            logger.error(f"[Gemini Error] Timeout after {elapsed:.1f}s (limit: {self.get_timeout()}s)")
            return SubmissionResult(
                score=0,
                feedback="Przekroczono limit czasu analizy Gemini. Spróbuj ponownie.",
            )
        except Exception as e:
            elapsed = time.time() - start_time
            error_msg = str(e)
            logger.error(f"[Gemini Error] {error_msg} (after {elapsed:.1f}s)")
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
