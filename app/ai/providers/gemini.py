"""Gemini API provider implementation using google-genai SDK."""

import asyncio
import concurrent.futures
import hashlib
import logging
import queue
import threading
import time
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import AsyncIterator, Optional, Callable, Any

from ...config import settings
from ...models import SubmissionResult
from ..parsing import parse_ai_response
from ..prompt_builder import build_prompt
from ..factory import AIProviderError

try:
    from google import genai
    from google.genai import types

    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False
    genai = None
    types = None

logger = logging.getLogger(__name__)

# Media resolution levels, lowest to highest. Not every level exists in every
# google-genai release (ULTRA_HIGH is absent as of 2.13.0), so a configured level
# degrades to the highest one the installed SDK actually offers.
MEDIA_RESOLUTION_LADDER = [
    ("low", "MEDIA_RESOLUTION_LOW"),
    ("medium", "MEDIA_RESOLUTION_MEDIUM"),
    ("high", "MEDIA_RESOLUTION_HIGH"),
    ("ultra_high", "MEDIA_RESOLUTION_ULTRA_HIGH"),
]
MEDIA_RESOLUTION_MAP = dict(MEDIA_RESOLUTION_LADDER)

# Config levels / models already warned about, so a bad setting is reported once
# at startup instead of on every single request.
_resolution_warned: set[str] = set()
_pricing_warned: set[str] = set()


def _configure_debug_logging():
    """Configure debug logging for Gemini if enabled."""
    from ...config import settings
    if settings.gemini_debug_logs:
        logger.setLevel(logging.DEBUG)
        # Also enable debug for the handler module
        handler_logger = logging.getLogger("app.websocket.handler")
        handler_logger.setLevel(logging.DEBUG)


@dataclass
class CachedFile:
    """Cached Gemini file reference."""
    gemini_name: str  # e.g., "files/abc123"
    file_hash: str    # MD5 hash of file content
    cached_at: float  # time.time() when cached


@dataclass
class StreamChunk:
    """A chunk from streaming response."""
    type: str  # "thinking", "feedback", or "done"
    text: str = ""
    score: int = 0
    feedback: str = ""
    meta: Optional[dict] = None


# In-memory cache: local file path -> CachedFile
# Files persist on Gemini for 48 hours, we use 24h to be safe
_file_cache: dict[str, CachedFile] = {}
_CACHE_TTL_SECONDS = 24 * 60 * 60  # 24 hours

# Gemini pricing per 1M tokens (USD)
# See https://ai.google.dev/gemini-api/docs/pricing
#
# "output" covers response AND thinking tokens - Gemini bills thoughts at the
# output rate, so _calculate_cost must be given output + thoughts.
#
# Models with long-context tiers carry "long_input"/"long_output", applied when
# the prompt exceeds "long_threshold" tokens.
_FLASH_PRICING = {
    "input": 1.50, "output": 7.50,
    "promo_until": date(2027, 1, 1), "promo_input": 0.75, "promo_output": 3.75,
}

GEMINI_PRICING = {
    # Gemini 3.x series
    "gemini-3.1-pro-preview": {
        "input": 2.00, "output": 12.00,
        "long_threshold": 200_000, "long_input": 4.00, "long_output": 18.00,
    },
    "gemini-3-pro-preview": {"input": 2.00, "output": 12.00},
    "gemini-3-pro": {"input": 2.00, "output": 12.00},
    # Flash tier (3.6 / 3.7 / 3.8) shares one price list, promo-priced at half
    # rate through 2026-12-31, then reverting to the "input"/"output" rates.
    # Verified 2026-08-17 (3.6, 3.7) and 2026-09-05 (3.8) against
    # https://ai.google.dev/gemini-api/docs/pricing (paid tier, standard).
    # promo_until is compared against the server's local date, so the changeover
    # can land a few hours off Google's billing boundary - immaterial for an
    # estimate that only feeds logging.
    "gemini-3.8-flash": _FLASH_PRICING,
    "gemini-3.7-flash": _FLASH_PRICING,
    "gemini-3.6-flash": _FLASH_PRICING,
    "gemini-3.5-flash": {"input": 1.50, "output": 9.00},
    "gemini-3-flash-preview": {"input": 1.50, "output": 9.00},
    # Gemini 2.5 series
    "gemini-2.5-pro": {"input": 1.25, "output": 10.00},
    "gemini-2.5-flash": {"input": 0.30, "output": 2.50},
    "gemini-2.5-flash-lite": {"input": 0.10, "output": 0.40},
    # Legacy models
    "gemini-2.0-flash": {"input": 0.10, "output": 0.40},
    # Default fallback (gemini-2.5-flash-lite pricing)
    "default": {"input": 0.10, "output": 0.40},
}


def estimate_cost(
    model_name: str, input_tokens: int, output_tokens: int, thoughts_tokens: int = 0
) -> float:
    """Estimated USD cost of one call, from GEMINI_PRICING.

    Thinking tokens are billed at the output rate. Unknown models fall back to
    the "default" entry with a one-time warning. Shared by the provider and the
    offline eval scripts so both report the same number.
    """
    pricing = GEMINI_PRICING.get(model_name)
    if pricing is None:
        pricing = GEMINI_PRICING["default"]
        if model_name not in _pricing_warned:
            _pricing_warned.add(model_name)
            logger.warning(
                f"[Gemini] No pricing entry for model '{model_name}', "
                f"cost estimates use fallback rates and will be inaccurate. "
                f"Add it to GEMINI_PRICING."
            )

    threshold = pricing.get("long_threshold")
    if threshold and input_tokens > threshold:
        in_rate = pricing.get("long_input", pricing["input"])
        out_rate = pricing.get("long_output", pricing["output"])
    else:
        in_rate, out_rate = pricing["input"], pricing["output"]
        promo_until = pricing.get("promo_until")
        if promo_until and date.today() < promo_until:
            in_rate = pricing.get("promo_input", in_rate)
            out_rate = pricing.get("promo_output", out_rate)

    input_cost = (input_tokens / 1_000_000) * in_rate
    output_cost = ((output_tokens + thoughts_tokens) / 1_000_000) * out_rate
    return input_cost + output_cost

# JSON schema for structured output - forces Gemini to return valid JSON
RESPONSE_JSON_SCHEMA = {
    "type": "object",
    "properties": {
        "score": {
            "type": "integer",
            "description": "Score according to OMJ criteria (0, 2, 5, or 6 for etap2/3; 0, 1, or 3 for etap1)"
        },
        "feedback": {
            "type": "string",
            "description": "Constructive feedback in Polish explaining the score"
        },
        "issue_type": {
            "type": "string",
            "enum": ["none", "wrong_task", "injection"],
            "description": "Type of issue detected: none (normal), wrong_task (wrong problem), injection (manipulation attempt)"
        },
        "abuse_score": {
            "type": "integer",
            "description": "Confidence score 0-100 for abuse detection"
        }
    },
    "required": ["score", "feedback", "issue_type", "abuse_score"]
}


class GeminiProvider:
    """AI provider using Google Gemini API for solution analysis."""

    def __init__(self):
        """Initialize Gemini provider with API key."""
        if not GEMINI_AVAILABLE:
            raise ImportError(
                "google-genai package not installed. "
                "Install with: pip install google-genai"
            )

        if not settings.gemini_api_key:
            raise ValueError("GEMINI_API_KEY is required. Set it in your .env file.")

        # Configure debug logging if enabled
        _configure_debug_logging()

        # Support custom API endpoint for testing
        # Use v1alpha API for per-part media_resolution (Gemini 3 feature)
        if settings.gemini_api_base_url:
            http_options = types.HttpOptions(
                base_url=settings.gemini_api_base_url,
                api_version="v1alpha",
            )
            self._client = genai.Client(
                api_key=settings.gemini_api_key,
                http_options=http_options,
            )
            logger.info(f"[Gemini] Using custom API endpoint: {settings.gemini_api_base_url}")
        else:
            http_options = types.HttpOptions(api_version="v1alpha")
            self._client = genai.Client(
                api_key=settings.gemini_api_key,
                http_options=http_options,
            )

        self._model_name = settings.gemini_model
        self._is_gemini_3 = "gemini-3" in self._model_name.lower()

        # Log media resolution settings
        self._disable_file_cache = settings.gemini_disable_file_cache

        # Resolve up front so an unsupported level is reported at startup rather
        # than on the first submission, and log what is actually sent.
        effective_pdf = self._get_media_resolution().name
        effective_img = self._get_media_resolution(
            settings.gemini_media_resolution_images
        ).name

        logger.info(
            f"[Gemini] Initialized with model={self._model_name}, "
            f"media_resolution={settings.gemini_media_resolution} "
            f"(effective: {effective_pdf}), "
            f"image_resolution={settings.gemini_media_resolution_images} "
            f"(effective: {effective_img}), "
            f"is_gemini_3={self._is_gemini_3}, "
            f"file_cache={'disabled' if self._disable_file_cache else 'enabled'}"
        )

    def _get_media_resolution(self, level: str = None):
        """Get MediaResolution enum value from config string.

        Args:
            level: Resolution level string ("low", "medium", "high", "ultra_high").
                   If None, uses gemini_media_resolution from settings.

        Note: Degrades to the highest level the installed SDK supports if the
        requested one is unavailable, warning once per level.
        """
        level = (level or settings.gemini_media_resolution).lower()
        enum_name = MEDIA_RESOLUTION_MAP.get(level)
        if enum_name is None:
            if level not in _resolution_warned:
                _resolution_warned.add(level)
                logger.warning(
                    f"[Gemini] Unknown media resolution '{level}', using 'high'. "
                    f"Valid levels: {', '.join(n for n, _ in MEDIA_RESOLUTION_LADDER)}"
                )
            return types.MediaResolution.MEDIA_RESOLUTION_HIGH

        if hasattr(types.MediaResolution, enum_name):
            return getattr(types.MediaResolution, enum_name)

        # Requested level missing from this SDK - step down to the best available.
        idx = [n for n, _ in MEDIA_RESOLUTION_LADDER].index(level)
        for name, candidate in reversed(MEDIA_RESOLUTION_LADDER[:idx]):
            if hasattr(types.MediaResolution, candidate):
                if level not in _resolution_warned:
                    _resolution_warned.add(level)
                    logger.warning(
                        f"[Gemini] Media resolution '{level}' is NOT supported by "
                        f"google-genai {getattr(genai, '__version__', '?')} - "
                        f"actually sending '{name}'. This setting has no effect; "
                        f"either upgrade the SDK or set it to '{name}'."
                    )
                return getattr(types.MediaResolution, candidate)

        raise AIProviderError(
            f"No usable MediaResolution found in google-genai for level '{level}'"
        )

    def _calculate_cost(
        self, input_tokens: int, output_tokens: int, thoughts_tokens: int = 0
    ) -> float:
        """Calculate estimated cost based on token usage.

        Thinking tokens are billed at the output rate, so they must be counted
        with output_tokens - omitting them understates the true cost several-fold
        on high thinking_level models.
        """
        return estimate_cost(self._model_name, input_tokens, output_tokens, thoughts_tokens)

    @staticmethod
    def _read_usage(usage_metadata) -> tuple[int, int, int]:
        """Extract (input, output, thoughts) token counts from usage metadata."""
        if not usage_metadata:
            return 0, 0, 0
        return (
            getattr(usage_metadata, "prompt_token_count", 0) or 0,
            getattr(usage_metadata, "candidates_token_count", 0) or 0,
            getattr(usage_metadata, "thoughts_token_count", 0) or 0,
        )

    def _load_prompt(self, etap: str = "etap2") -> str:
        """Build complete prompt for given etap using prompt builder.

        The prompt is composed from:
        - Base instructions (role, language)
        - Etap-specific scoring criteria
        - Abuse detection instructions and JSON format
        """
        return build_prompt(etap)

    def get_timeout(self) -> int:
        """Return timeout in seconds for Gemini API."""
        return settings.gemini_timeout

    def _build_content_parts(
        self,
        prompt_text: str,
        uploaded_files: list,
        task_number: int,
        has_solution_pdf: bool,
        num_images: int,
        image_paths: list[Path] = None,
    ) -> list:
        """Build content parts list for API request.

        For Gemini 3 models, student images are wrapped with ULTRA_HIGH
        media resolution for better handwriting recognition.
        """
        content_parts = []
        result_idx = 0

        # Start with system prompt
        full_prompt = prompt_text
        full_prompt += f"\n\n## Zadanie {task_number}\n"
        full_prompt += "Przeanalizuj poniższe pliki.\n\n"

        # Task PDF
        full_prompt += "### Treść zadania (PDF):\n"
        task_file = uploaded_files[result_idx]
        result_idx += 1
        content_parts.append(task_file)
        full_prompt += f"Znajdź 'Zadanie {task_number}.' w dokumencie powyżej.\n\n"

        # Solution PDF if exists
        if has_solution_pdf:
            full_prompt += "### Oficjalne rozwiązanie (TYLKO do weryfikacji, NIE pokazuj uczniowi):\n"
            solution_file = uploaded_files[result_idx]
            result_idx += 1
            content_parts.append(solution_file)
            full_prompt += "\n"

        # Student images - use per-part ULTRA_HIGH resolution for Gemini 3
        full_prompt += "### Rozwiązanie ucznia:\n"
        image_resolution = self._get_media_resolution(settings.gemini_media_resolution_images)

        for i in range(num_images):
            full_prompt += f"Zdjęcie {i + 1}:\n"

            if self._is_gemini_3 and image_paths and i < len(image_paths):
                # Gemini 3: Use inline bytes with per-part ULTRA_HIGH resolution
                img_path = image_paths[i]
                try:
                    with open(img_path, "rb") as f:
                        image_bytes = f.read()

                    # Determine MIME type from extension
                    ext = img_path.suffix.lower()
                    mime_types = {
                        ".jpg": "image/jpeg",
                        ".jpeg": "image/jpeg",
                        ".png": "image/png",
                        ".webp": "image/webp",
                        ".heic": "image/heic",
                        ".heif": "image/heif",
                    }
                    mime_type = mime_types.get(ext, "image/jpeg")

                    # Create Part with per-part resolution
                    img_part = types.Part.from_bytes(
                        data=image_bytes,
                        mime_type=mime_type,
                        media_resolution=image_resolution,
                    )
                    content_parts.append(img_part)
                    logger.debug(
                        f"[Gemini] Image {i + 1} using per-part resolution: "
                        f"{settings.gemini_media_resolution_images}"
                    )
                    # Increment index to stay aligned with uploaded_files array.
                    # Even though we used inline bytes instead of the file reference,
                    # the file was still uploaded and occupies a slot in uploaded_files.
                    # This ensures fallback iterations access the correct file.
                    result_idx += 1
                    continue
                except (TypeError, AttributeError) as e:
                    # SDK doesn't support per-part media_resolution, fall back to file reference
                    logger.warning(
                        f"[Gemini] Per-part resolution not supported by SDK "
                        f"({type(e).__name__}: {e}). "
                        f"Falling back to file reference for image {i + 1}"
                    )
            # Non-Gemini 3 or fallback: use uploaded file reference
            img_file = uploaded_files[result_idx]
            result_idx += 1
            content_parts.append(img_file)

        full_prompt += "\n\nOceń rozwiązanie i odpowiedz WYŁĄCZNIE w formacie JSON."

        # Prepend prompt text to content
        content_parts.insert(0, full_prompt)

        return content_parts

    async def _upload_files(
        self,
        task_pdf_path: Path,
        solution_pdf_path: Optional[Path],
        image_paths: list[Path],
    ) -> tuple[list, bool]:
        """Upload all files to Gemini in parallel. Returns (files, has_solution_pdf)."""
        upload_start = time.time()
        upload_tasks = []
        upload_labels = []

        # Task PDF (cached unless disabled)
        use_cache = not self._disable_file_cache
        logger.debug(f"[Gemini Upload] Queueing task PDF: {task_pdf_path}")
        upload_tasks.append(self._upload_file(task_pdf_path, use_cache=use_cache))
        upload_labels.append(("task_pdf", task_pdf_path.name))

        # Solution PDF if exists (cached unless disabled)
        has_solution_pdf = solution_pdf_path and solution_pdf_path.exists()
        if has_solution_pdf:
            logger.debug(f"[Gemini Upload] Queueing solution PDF: {solution_pdf_path}")
            upload_tasks.append(self._upload_file(solution_pdf_path, use_cache=use_cache))
            upload_labels.append(("solution_pdf", solution_pdf_path.name))

        # Student images (NOT cached)
        for i, img_path in enumerate(image_paths, 1):
            size_kb = img_path.stat().st_size // 1024 if img_path.exists() else 0
            logger.debug(f"[Gemini Upload] Queueing image {i}: {img_path.name} ({size_kb}KB)")
            upload_tasks.append(self._upload_file(img_path, use_cache=False))
            upload_labels.append((f"image_{i}", img_path.name))

        # Upload all files in parallel
        logger.info(f"[Gemini Upload] Starting parallel upload of {len(upload_tasks)} files...")
        try:
            upload_results = await asyncio.gather(*upload_tasks)
        except Exception as e:
            upload_elapsed = time.time() - upload_start
            logger.error(f"[Gemini Upload] FAILED after {upload_elapsed:.1f}s: {type(e).__name__}: {e}")
            raise

        upload_elapsed = time.time() - upload_start

        # Log cache status
        cache_hits = 0
        for (label, name), _ in zip(upload_labels, upload_results):
            cache_key = str(task_pdf_path) if label == "task_pdf" else (
                str(solution_pdf_path) if label == "solution_pdf" else None
            )
            was_cached = cache_key and cache_key in _file_cache
            if was_cached:
                cache_hits += 1
            status = "cached" if was_cached else "uploaded"
            logger.debug(f"[Gemini Upload] {label}: {name} ({status})")

        logger.info(
            f"[Gemini Upload] Complete in {upload_elapsed:.1f}s - "
            f"{len(upload_tasks)} files, {cache_hits} cache hits"
        )

        return upload_results, has_solution_pdf

    async def analyze_solution(
        self,
        task_pdf_path: Path,
        solution_pdf_path: Optional[Path],
        image_paths: list[Path],
        task_number: int,
        etap: str = "etap2",
    ) -> SubmissionResult:
        """
        Analyze a student's solution using Gemini API (non-streaming).

        Args:
            task_pdf_path: Path to the task PDF
            solution_pdf_path: Path to the official solution PDF (for reference)
            image_paths: Paths to uploaded images of student's solution
            task_number: The task number (1-7 for etap1, 1-5 for etap2/etap3)
            etap: The competition stage ("etap1", "etap2", or "etap3")

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
            # Upload files
            uploaded_files, has_solution_pdf = await self._upload_files(
                task_pdf_path, solution_pdf_path, image_paths
            )

            # Build content (pass image_paths for Gemini 3 per-part resolution)
            prompt_text = self._load_prompt(etap)
            content_parts = self._build_content_parts(
                prompt_text, uploaded_files, task_number, has_solution_pdf, len(image_paths),
                image_paths=image_paths,
            )

            upload_time = time.time() - start_time
            logger.info(f"[Gemini] Files uploaded in {upload_time:.1f}s, sending to API...")

            # Generate response with timeout
            api_start_time = time.time()

            # Configure thinking mode based on model version
            # Gemini 3.x uses thinking_level, Gemini 2.x uses thinking_budget
            if self._is_gemini_3:
                thinking_config = types.ThinkingConfig(
                    include_thoughts=True,
                    thinking_level=settings.gemini_thinking_level,  # "low" or "high"
                )
            else:
                thinking_config = types.ThinkingConfig(
                    include_thoughts=True,
                    thinking_budget=8192,
                )

            # Use global media_resolution for PDFs (per-part resolution handles images for Gemini 3)
            media_resolution = self._get_media_resolution()
            logger.debug(
                f"[Gemini] Using thinking config: {thinking_config}, "
                f"media_resolution: {settings.gemini_media_resolution}"
            )

            config = types.GenerateContentConfig(
                thinking_config=thinking_config,
                response_mime_type="application/json",
                response_json_schema=RESPONSE_JSON_SCHEMA,
                media_resolution=media_resolution,
            )

            response = await asyncio.wait_for(
                asyncio.to_thread(
                    self._client.models.generate_content,
                    model=self._model_name,
                    contents=content_parts,
                    config=config,
                ),
                timeout=self.get_timeout(),
            )
            api_time = time.time() - api_start_time

            # Log response metadata and usage
            if hasattr(response, "usage_metadata") and response.usage_metadata:
                input_tokens, output_tokens, thoughts_tokens = self._read_usage(
                    response.usage_metadata
                )
                estimated_cost = self._calculate_cost(
                    input_tokens, output_tokens, thoughts_tokens
                )
                logger.info(
                    f"[Gemini Response] api_time={api_time:.1f}s, "
                    f"input_tokens={input_tokens:,}, output_tokens={output_tokens:,}, "
                    f"thoughts_tokens={thoughts_tokens:,}, "
                    f"estimated_cost=${estimated_cost:.4f}"
                )
            else:
                logger.info(f"[Gemini Response] api_time={api_time:.1f}s (no usage metadata)")

            total_time = time.time() - start_time
            logger.info(f"[Gemini] Total request time: {total_time:.1f}s")

            # Extract text from response
            response_text = response.text if hasattr(response, "text") else ""
            if not response_text:
                logger.warning("[Gemini] Empty response text received")
                raise AIProviderError(
                    "Nie udało się odczytać rozwiązania. Spróbuj ponownie."
                )

            # Use shared parsing utility with etap-specific scoring
            return parse_ai_response(response_text, provider_name="Gemini", etap=etap)

        except AIProviderError:
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
                raise AIProviderError(
                    "Przepraszamy, coś poszło nie tak. Spróbuj ponownie za chwilę."
                )
        finally:
            await self._cleanup_files(uploaded_files, skip_cached=not self._disable_file_cache)

    async def analyze_solution_stream(
        self,
        task_pdf_path: Path,
        solution_pdf_path: Optional[Path],
        image_paths: list[Path],
        task_number: int,
        etap: str = "etap2",
        on_thinking: Optional[Callable[[str], Any]] = None,
        on_feedback: Optional[Callable[[str], Any]] = None,
        on_upload_complete: Optional[Callable[[], Any]] = None,
    ) -> SubmissionResult:
        """
        Analyze a student's solution with streaming response.

        Calls on_thinking and on_feedback callbacks as chunks arrive.

        Args:
            task_pdf_path: Path to the task PDF
            solution_pdf_path: Path to the official solution PDF (for reference)
            image_paths: Paths to uploaded images of student's solution
            task_number: The task number (1-7 for etap1, 1-5 for etap2/etap3)
            etap: The competition stage ("etap1", "etap2", or "etap3")
            on_thinking: Callback for thinking text chunks
            on_feedback: Callback for feedback text chunks
            on_upload_complete: Callback when file upload is complete (before AI analysis)

        Returns:
            SubmissionResult with score and feedback
        """
        uploaded_files = []
        start_time = time.time()

        # Log request metadata
        image_sizes = [p.stat().st_size for p in image_paths if p.exists()]
        total_image_size_kb = sum(image_sizes) / 1024
        logger.info(
            f"[Gemini Stream Request] model={self._model_name}, etap={etap}, "
            f"task={task_number}, images={len(image_paths)}, "
            f"total_image_size={total_image_size_kb:.1f}KB"
        )

        try:
            # Upload files
            uploaded_files, has_solution_pdf = await self._upload_files(
                task_pdf_path, solution_pdf_path, image_paths
            )

            # Build content (pass image_paths for Gemini 3 per-part resolution)
            prompt_text = self._load_prompt(etap)
            content_parts = self._build_content_parts(
                prompt_text, uploaded_files, task_number, has_solution_pdf, len(image_paths),
                image_paths=image_paths,
            )

            upload_time = time.time() - start_time
            logger.info(f"[Gemini] Files uploaded in {upload_time:.1f}s, starting stream...")

            # Notify caller that upload is complete
            if on_upload_complete:
                if asyncio.iscoroutinefunction(on_upload_complete):
                    await on_upload_complete()
                else:
                    on_upload_complete()

            # Configure thinking mode based on model version
            # Gemini 3.x uses thinking_level, Gemini 2.x uses thinking_budget
            if self._is_gemini_3:
                # Gemini 3: use thinking_level (cannot disable thinking)
                thinking_config = types.ThinkingConfig(
                    include_thoughts=True,
                    thinking_level=settings.gemini_thinking_level,  # "low" or "high"
                )
            else:
                # Gemini 2.5: use thinking_budget to enable thinking
                thinking_config = types.ThinkingConfig(
                    include_thoughts=True,
                    thinking_budget=8192,  # Enable thinking with reasonable budget
                )

            # Use global media_resolution for PDFs (per-part resolution handles images for Gemini 3)
            media_resolution = self._get_media_resolution()
            logger.debug(
                f"[Gemini Stream] Using thinking config: {thinking_config}, "
                f"media_resolution: {settings.gemini_media_resolution}"
            )

            config = types.GenerateContentConfig(
                thinking_config=thinking_config,
                response_mime_type="application/json",
                response_json_schema=RESPONSE_JSON_SCHEMA,
                media_resolution=media_resolution,
            )

            # Stream the response with timeout
            api_start_time = time.time()
            thinking_text = ""
            feedback_text = ""
            timeout = self.get_timeout()
            usage_metadata = None  # Will be populated from final chunk

            # Use thread-safe queue and event for cross-thread communication
            chunk_queue: queue.Queue = queue.Queue()
            stream_done_event = threading.Event()
            stream_error: Optional[Exception] = None
            stream_started = threading.Event()

            def stream_to_queue():
                """Run streaming in thread and push chunks to queue."""
                nonlocal stream_error
                try:
                    logger.debug("[Gemini Stream] Thread: Calling generate_content_stream...")
                    response_stream = self._client.models.generate_content_stream(
                        model=self._model_name,
                        contents=content_parts,
                        config=config,
                    )
                    logger.debug("[Gemini Stream] Thread: Got response_stream iterator")
                    stream_started.set()

                    chunk_count = 0
                    for chunk in response_stream:
                        chunk_count += 1
                        if chunk_count == 1:
                            logger.debug("[Gemini Stream] Thread: First chunk received from API")
                        chunk_queue.put(chunk)

                    logger.debug(f"[Gemini Stream] Thread: Stream complete, {chunk_count} chunks received")
                except Exception as e:
                    logger.error(f"[Gemini Stream] Thread error: {type(e).__name__}: {e}")
                    stream_error = e
                    stream_started.set()  # Unblock main thread if waiting
                finally:
                    stream_done_event.set()

            # Start streaming in background thread
            logger.debug("[Gemini Stream] Starting background thread for streaming")
            executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
            stream_future = executor.submit(stream_to_queue)

            # Process chunks with simple polling
            chunks_processed = 0
            start_wait = time.time()
            last_chunk_time = start_wait
            last_log_time = start_wait

            try:
                logger.debug("[Gemini Stream] Starting chunk processing loop")
                while True:
                    elapsed = time.time() - start_wait
                    since_last_chunk = time.time() - last_chunk_time

                    # Check for timeout
                    if elapsed > timeout:
                        logger.error(
                            f"[Gemini Stream] TIMEOUT - elapsed={elapsed:.1f}s, "
                            f"timeout={timeout}s, chunks_processed={chunks_processed}, "
                            f"since_last_chunk={since_last_chunk:.1f}s, "
                            f"stream_done={stream_done_event.is_set()}, "
                            f"stream_started={stream_started.is_set()}"
                        )
                        raise AIProviderError(
                            "Analiza trwa zbyt długo. Spróbuj ponownie za chwilę."
                        )

                    # Log progress every 30 seconds for stuck detection
                    if time.time() - last_log_time > 30:
                        logger.debug(
                            f"[Gemini Stream] Progress - elapsed={elapsed:.1f}s, "
                            f"chunks={chunks_processed}, since_last_chunk={since_last_chunk:.1f}s, "
                            f"thinking_len={len(thinking_text)}, feedback_len={len(feedback_text)}"
                        )
                        last_log_time = time.time()

                    # Check for stream error
                    if stream_error:
                        logger.error(f"[Gemini Stream] Stream error detected: {stream_error}")
                        raise stream_error

                    # Try to get a chunk (non-blocking)
                    try:
                        chunk = chunk_queue.get_nowait()
                        chunks_processed += 1
                        last_chunk_time = time.time()

                        # Log first chunk
                        if chunks_processed == 1:
                            logger.debug(f"[Gemini Stream] Processing first chunk (waited {elapsed:.1f}s)")

                        # Capture usage metadata (typically in final chunk)
                        if hasattr(chunk, "usage_metadata") and chunk.usage_metadata:
                            usage_metadata = chunk.usage_metadata

                        # Process the chunk
                        if hasattr(chunk, "candidates") and chunk.candidates:
                            for candidate in chunk.candidates:
                                if hasattr(candidate, "content") and candidate.content:
                                    for part in candidate.content.parts:
                                        text = getattr(part, "text", "") or ""
                                        if not text:
                                            continue

                                        # Check if this is a thought part
                                        is_thought = getattr(part, "thought", False)

                                        if is_thought:
                                            thinking_text += text
                                            if on_thinking:
                                                if asyncio.iscoroutinefunction(on_thinking):
                                                    await on_thinking(text)
                                                else:
                                                    on_thinking(text)
                                        else:
                                            feedback_text += text
                                            if on_feedback:
                                                if asyncio.iscoroutinefunction(on_feedback):
                                                    await on_feedback(text)
                                                else:
                                                    on_feedback(text)

                    except queue.Empty:
                        # No chunk available - check if stream is done
                        if stream_done_event.is_set() and chunk_queue.empty():
                            logger.debug(f"[Gemini Stream] Stream done, processed {chunks_processed} chunks")
                            break
                        # Wait a bit before polling again
                        await asyncio.sleep(0.05)

            finally:
                # Clean up executor
                logger.debug("[Gemini Stream] Cleaning up executor thread")
                try:
                    stream_future.result(timeout=5)
                except Exception as e:
                    logger.warning(f"[Gemini Stream] Error waiting for stream thread: {e}")
                executor.shutdown(wait=False)

            api_time = time.time() - api_start_time
            total_time = time.time() - start_time

            # Log response with usage stats
            if usage_metadata:
                input_tokens, output_tokens, thoughts_tokens = self._read_usage(
                    usage_metadata
                )
                estimated_cost = self._calculate_cost(
                    input_tokens, output_tokens, thoughts_tokens
                )
                logger.info(
                    f"[Gemini Stream Response] api_time={api_time:.1f}s, "
                    f"total_time={total_time:.1f}s, "
                    f"input_tokens={input_tokens:,}, output_tokens={output_tokens:,}, "
                    f"thoughts_tokens={thoughts_tokens:,}, "
                    f"estimated_cost=${estimated_cost:.4f}, "
                    f"thinking_chars={len(thinking_text)}, feedback_chars={len(feedback_text)}"
                )
            else:
                logger.info(
                    f"[Gemini Stream Response] api_time={api_time:.1f}s, "
                    f"total_time={total_time:.1f}s, "
                    f"thinking_chars={len(thinking_text)}, feedback_chars={len(feedback_text)} "
                    f"(no usage metadata)"
                )

            if not feedback_text:
                logger.warning("[Gemini] Empty feedback text from stream")
                raise AIProviderError(
                    "Nie udało się odczytać rozwiązania. Spróbuj ponownie."
                )

            # Parse the response
            result = parse_ai_response(feedback_text, provider_name="Gemini", etap=etap)

            # Add thinking to scoring_meta
            if result.scoring_meta is None:
                result.scoring_meta = {}
            result.scoring_meta["thinking"] = thinking_text
            result.scoring_meta["api_time"] = api_time
            result.scoring_meta["total_time"] = total_time

            return result

        except AIProviderError:
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
                raise AIProviderError(
                    "Przepraszamy, coś poszło nie tak. Spróbuj ponownie za chwilę."
                )
        finally:
            await self._cleanup_files(uploaded_files, skip_cached=not self._disable_file_cache)

    def _get_file_hash(self, file_path: Path) -> str:
        """Compute MD5 hash of file for cache validation."""
        hasher = hashlib.md5()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                hasher.update(chunk)
        return hasher.hexdigest()

    async def _check_cached_file(self, file_path: Path):
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
            gemini_file = await asyncio.to_thread(
                self._client.files.get,
                name=cached.gemini_name,
            )
            logger.info(f"[Gemini Cache] HIT for {file_path.name}")
            return gemini_file
        except Exception as e:
            logger.debug(f"[Gemini Cache] File gone from Gemini: {file_path.name} ({e})")
            del _file_cache[cache_key]
            return None

    async def _upload_file(self, file_path: Path, use_cache: bool = True):
        """
        Upload a file to Gemini File API with optional caching.

        Args:
            file_path: Path to the file to upload
            use_cache: Whether to use caching (default True, disable for user uploads)

        Returns:
            Gemini File object reference
        """
        file_name = file_path.name
        file_size_kb = file_path.stat().st_size // 1024 if file_path.exists() else 0

        # Check cache first for static files (PDFs)
        if use_cache:
            cached_file = await self._check_cached_file(file_path)
            if cached_file:
                return cached_file

        # Upload to Gemini using new SDK
        upload_start = time.time()
        logger.debug(f"[Gemini Upload] Uploading {file_name} ({file_size_kb}KB)...")
        try:
            gemini_file = await asyncio.to_thread(
                self._client.files.upload,
                file=str(file_path),
            )
            upload_time = time.time() - upload_start
            logger.debug(f"[Gemini Upload] {file_name} uploaded in {upload_time:.1f}s -> {gemini_file.name}")
        except Exception as e:
            upload_time = time.time() - upload_start
            logger.error(f"[Gemini Upload] {file_name} FAILED after {upload_time:.1f}s: {type(e).__name__}: {e}")
            raise

        # Cache the reference for static files
        if use_cache:
            _file_cache[str(file_path)] = CachedFile(
                gemini_name=gemini_file.name,
                file_hash=self._get_file_hash(file_path),
                cached_at=time.time(),
            )
            logger.info(f"[Gemini Cache] STORED {file_name} -> {gemini_file.name}")

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
            file_name = getattr(file, "name", None)
            if not file_name:
                continue
            if file_name in cached_names:
                logger.debug(f"[Gemini Cleanup] Skipping cached file: {file_name}")
                continue
            try:
                await asyncio.to_thread(
                    self._client.files.delete,
                    name=file_name,
                )
                logger.debug(f"[Gemini Cleanup] Deleted: {file_name}")
            except Exception:
                # Log but don't fail if cleanup fails
                pass
