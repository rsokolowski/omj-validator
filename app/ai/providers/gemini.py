"""Gemini API provider implementation."""

import asyncio
import hashlib
import logging
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from ...config import settings
from ...models import SubmissionResult
from ..parsing import parse_ai_response
from ..factory import AIProviderError

try:
    import google.generativeai as genai

    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False
    genai = None

logger = logging.getLogger(__name__)


@dataclass
class CachedFile:
    """Cached Gemini file reference."""
    gemini_name: str  # e.g., "files/abc123"
    file_hash: str    # MD5 hash of file content
    cached_at: float  # time.time() when cached


# In-memory cache: local file path -> CachedFile
# Files persist on Gemini for 48 hours, we use 24h to be safe
_file_cache: dict[str, CachedFile] = {}
_CACHE_TTL_SECONDS = 24 * 60 * 60  # 24 hours

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
            # Prepare all upload tasks in parallel
            upload_tasks = []
            upload_labels = []  # For logging

            # Task PDF (cached - static file)
            logger.debug(f"[Gemini] Queueing task PDF: {task_pdf_path}")
            upload_tasks.append(self._upload_file(task_pdf_path, use_cache=True))
            upload_labels.append(("task_pdf", task_pdf_path.name))

            # Solution PDF if exists (cached - static file)
            has_solution_pdf = solution_pdf_path and solution_pdf_path.exists()
            if has_solution_pdf:
                logger.debug(f"[Gemini] Queueing solution PDF: {solution_pdf_path}")
                upload_tasks.append(self._upload_file(solution_pdf_path, use_cache=True))
                upload_labels.append(("solution_pdf", solution_pdf_path.name))

            # Student images (NOT cached - unique per submission)
            for i, img_path in enumerate(image_paths, 1):
                logger.debug(f"[Gemini] Queueing image {i}: {img_path.name}")
                upload_tasks.append(self._upload_file(img_path, use_cache=False))
                upload_labels.append((f"image_{i}", img_path.name))

            # Upload all files in parallel
            logger.info(f"[Gemini] Uploading {len(upload_tasks)} files in parallel...")
            upload_results = await asyncio.gather(*upload_tasks)

            # Log which files were cached vs uploaded
            for (label, name), result in zip(upload_labels, upload_results):
                # Check if it was a cache hit by looking at the cache
                cache_key = str(task_pdf_path) if label == "task_pdf" else (
                    str(solution_pdf_path) if label == "solution_pdf" else None
                )
                was_cached = cache_key and cache_key in _file_cache
                status = "cached" if was_cached else "uploaded"
                logger.debug(f"[Gemini] {label}: {name} ({status})")

            # Build content parts in correct order
            content_parts = []
            result_idx = 0

            # Add system prompt (etap-specific scoring criteria)
            prompt_text = self._load_prompt(etap)
            prompt_text += f"\n\n## Zadanie {task_number}\n"
            prompt_text += "Przeanalizuj poniższe pliki.\n\n"

            # Task PDF
            prompt_text += "### Treść zadania (PDF):\n"
            task_file = upload_results[result_idx]
            result_idx += 1
            uploaded_files.append(task_file)
            content_parts.append(task_file)
            prompt_text += (
                f"Znajdź 'Zadanie {task_number}.' w dokumencie powyżej.\n\n"
            )

            # Solution PDF if exists
            if has_solution_pdf:
                prompt_text += "### Oficjalne rozwiązanie (TYLKO do weryfikacji, NIE pokazuj uczniowi):\n"
                solution_file = upload_results[result_idx]
                result_idx += 1
                uploaded_files.append(solution_file)
                content_parts.append(solution_file)
                prompt_text += "\n"

            # Student images
            prompt_text += "### Rozwiązanie ucznia:\n"
            for i in range(len(image_paths)):
                prompt_text += f"Zdjęcie {i + 1}:\n"
                img_file = upload_results[result_idx]
                result_idx += 1
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

            # Extract text from response safely
            # response.text accessor raises exception if no parts returned
            try:
                response_text = response.text
            except ValueError as e:
                # Empty response - model returned no content
                logger.error(f"[Gemini Error] Empty response: {e}")
                raise AIProviderError(
                    "Nie udało się odczytać rozwiązania. Upewnij się, że zdjęcie "
                    "jest wyraźne, dobrze oświetlone i zawiera całe rozwiązanie."
                )

            if not response_text:
                logger.warning("[Gemini] Empty response text received")
                raise AIProviderError(
                    "Nie udało się odczytać rozwiązania. Spróbuj ponownie."
                )

            # Use shared parsing utility with etap-specific scoring
            return parse_ai_response(response_text, provider_name="Gemini", etap=etap)

        except AIProviderError:
            # Re-raise our own errors
            raise
        except asyncio.TimeoutError:
            elapsed = time.time() - start_time
            logger.error(f"[Gemini Error] Timeout after {elapsed:.1f}s (limit: {self.get_timeout()}s)")
            raise AIProviderError(
                "Analiza trwa zbyt długo. Spróbuj ponownie za chwilę."
            )
        except Exception as e:
            elapsed = time.time() - start_time
            error_msg = str(e)
            logger.error(f"[Gemini Error] {error_msg} (after {elapsed:.1f}s)")

            # Map technical errors to user-friendly messages
            if "quota" in error_msg.lower():
                raise AIProviderError(
                    "System jest obecnie przeciążony. Spróbuj ponownie za kilka minut."
                )
            elif "invalid" in error_msg.lower() and "key" in error_msg.lower():
                raise AIProviderError(
                    "Przepraszamy, wystąpił problem techniczny. Spróbuj ponownie później."
                )
            elif "safety" in error_msg.lower() or "blocked" in error_msg.lower():
                raise AIProviderError(
                    "Nie udało się przetworzyć zdjęcia. Upewnij się, że zdjęcie "
                    "zawiera tylko rozwiązanie zadania."
                )
            else:
                # Generic error - don't expose technical details
                raise AIProviderError(
                    "Przepraszamy, coś poszło nie tak. Spróbuj ponownie za chwilę."
                )
        finally:
            # Clean up uploaded files from Gemini servers
            await self._cleanup_files(uploaded_files)

    def _get_file_hash(self, file_path: Path) -> str:
        """Compute MD5 hash of file for cache validation."""
        hasher = hashlib.md5()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                hasher.update(chunk)
        return hasher.hexdigest()

    async def _check_cached_file(self, file_path: Path) -> Optional["genai.File"]:
        """
        Check if file is cached and still valid on Gemini.

        Returns:
            Gemini File object if cached and valid, None otherwise
        """
        cache_key = str(file_path)
        cached = _file_cache.get(cache_key)

        if not cached:
            return None

        # Check TTL
        if time.time() - cached.cached_at > _CACHE_TTL_SECONDS:
            logger.debug(f"[Gemini Cache] TTL expired for {file_path.name}")
            del _file_cache[cache_key]
            return None

        # Check file hasn't changed
        current_hash = self._get_file_hash(file_path)
        if current_hash != cached.file_hash:
            logger.debug(f"[Gemini Cache] File changed: {file_path.name}")
            del _file_cache[cache_key]
            return None

        # Verify file still exists on Gemini
        try:
            gemini_file = await asyncio.to_thread(genai.get_file, cached.gemini_name)
            logger.info(f"[Gemini Cache] HIT for {file_path.name}")
            return gemini_file
        except Exception as e:
            logger.debug(f"[Gemini Cache] File gone from Gemini: {file_path.name} ({e})")
            del _file_cache[cache_key]
            return None

    async def _upload_file(self, file_path: Path, use_cache: bool = True) -> "genai.File":
        """
        Upload a file to Gemini File API with optional caching.

        Args:
            file_path: Path to the file to upload
            use_cache: Whether to use caching (default True, disable for user uploads)

        Returns:
            Gemini File object reference
        """
        # Check cache first for static files (PDFs)
        if use_cache:
            cached_file = await self._check_cached_file(file_path)
            if cached_file:
                return cached_file

        # Upload to Gemini
        gemini_file = await asyncio.to_thread(
            genai.upload_file,
            str(file_path),
        )

        # Cache the reference for static files
        if use_cache:
            _file_cache[str(file_path)] = CachedFile(
                gemini_name=gemini_file.name,
                file_hash=self._get_file_hash(file_path),
                cached_at=time.time(),
            )
            logger.info(f"[Gemini Cache] STORED {file_path.name} -> {gemini_file.name}")

        return gemini_file

    async def _cleanup_files(self, files: list, skip_cached: bool = True) -> None:
        """
        Delete uploaded files from Gemini servers.

        Args:
            files: List of Gemini File objects to delete
            skip_cached: If True, don't delete files that are in our cache
        """
        # Get set of cached gemini file names
        cached_names = {c.gemini_name for c in _file_cache.values()} if skip_cached else set()

        for file in files:
            if file.name in cached_names:
                logger.debug(f"[Gemini Cleanup] Skipping cached file: {file.name}")
                continue
            try:
                await asyncio.to_thread(genai.delete_file, file.name)
                logger.debug(f"[Gemini Cleanup] Deleted: {file.name}")
            except Exception:
                # Log but don't fail if cleanup fails
                pass
