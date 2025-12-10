"""Gemini API provider implementation using google-genai SDK."""

import asyncio
import concurrent.futures
import hashlib
import logging
import queue
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import AsyncIterator, Optional, Callable, Any

from ...config import settings
from ...models import SubmissionResult
from ..parsing import parse_ai_response
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
GEMINI_PRICING = {
    # Gemini 3 series
    "gemini-3-pro-preview": {"input": 2.00, "output": 12.00},
    # Gemini 2.5 series
    "gemini-2.5-pro": {"input": 1.25, "output": 10.00},
    "gemini-2.5-flash": {"input": 0.30, "output": 2.50},
    "gemini-2.5-flash-lite": {"input": 0.10, "output": 0.40},
    # Legacy models
    "gemini-2.0-flash": {"input": 0.10, "output": 0.40},
    # Default fallback (gemini-2.5-flash-lite pricing)
    "default": {"input": 0.10, "output": 0.40},
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
        if settings.gemini_api_base_url:
            http_options = types.HttpOptions(base_url=settings.gemini_api_base_url)
            self._client = genai.Client(
                api_key=settings.gemini_api_key,
                http_options=http_options,
            )
            logger.info(f"[Gemini] Using custom API endpoint: {settings.gemini_api_base_url}")
        else:
            self._client = genai.Client(api_key=settings.gemini_api_key)

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

    def _build_content_parts(
        self,
        prompt_text: str,
        uploaded_files: list,
        task_number: int,
        has_solution_pdf: bool,
        num_images: int,
    ) -> list:
        """Build content parts list for API request."""
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

        # Student images
        full_prompt += "### Rozwiązanie ucznia:\n"
        for i in range(num_images):
            full_prompt += f"Zdjęcie {i + 1}:\n"
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

        # Task PDF (cached)
        logger.debug(f"[Gemini Upload] Queueing task PDF: {task_pdf_path}")
        upload_tasks.append(self._upload_file(task_pdf_path, use_cache=True))
        upload_labels.append(("task_pdf", task_pdf_path.name))

        # Solution PDF if exists (cached)
        has_solution_pdf = solution_pdf_path and solution_pdf_path.exists()
        if has_solution_pdf:
            logger.debug(f"[Gemini Upload] Queueing solution PDF: {solution_pdf_path}")
            upload_tasks.append(self._upload_file(solution_pdf_path, use_cache=True))
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

            # Build content
            prompt_text = self._load_prompt(etap)
            content_parts = self._build_content_parts(
                prompt_text, uploaded_files, task_number, has_solution_pdf, len(image_paths)
            )

            upload_time = time.time() - start_time
            logger.info(f"[Gemini] Files uploaded in {upload_time:.1f}s, sending to API...")

            # Generate response with timeout
            api_start_time = time.time()

            # Configure thinking mode based on model version
            # Gemini 3.x uses thinking_level, Gemini 2.x uses thinking_budget
            is_gemini_3 = "gemini-3" in self._model_name.lower()

            if is_gemini_3:
                thinking_config = types.ThinkingConfig(
                    include_thoughts=True,
                    thinking_level="high",
                )
            else:
                thinking_config = types.ThinkingConfig(
                    include_thoughts=True,
                    thinking_budget=8192,
                )

            config = types.GenerateContentConfig(
                thinking_config=thinking_config,
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
            input_tokens = 0
            output_tokens = 0
            if hasattr(response, "usage_metadata") and response.usage_metadata:
                input_tokens = getattr(response.usage_metadata, "prompt_token_count", 0) or 0
                output_tokens = getattr(response.usage_metadata, "candidates_token_count", 0) or 0
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
            await self._cleanup_files(uploaded_files)

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

            # Build content
            prompt_text = self._load_prompt(etap)
            content_parts = self._build_content_parts(
                prompt_text, uploaded_files, task_number, has_solution_pdf, len(image_paths)
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
            is_gemini_3 = "gemini-3" in self._model_name.lower()

            if is_gemini_3:
                # Gemini 3: use thinking_level (cannot disable thinking)
                thinking_config = types.ThinkingConfig(
                    include_thoughts=True,
                    thinking_level="high",  # "low" or "high"
                )
            else:
                # Gemini 2.5: use thinking_budget to enable thinking
                thinking_config = types.ThinkingConfig(
                    include_thoughts=True,
                    thinking_budget=8192,  # Enable thinking with reasonable budget
                )

            config = types.GenerateContentConfig(
                thinking_config=thinking_config,
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
            input_tokens = 0
            output_tokens = 0
            if usage_metadata:
                input_tokens = getattr(usage_metadata, "prompt_token_count", 0) or 0
                output_tokens = getattr(usage_metadata, "candidates_token_count", 0) or 0
                estimated_cost = self._calculate_cost(input_tokens, output_tokens)
                logger.info(
                    f"[Gemini Stream Response] api_time={api_time:.1f}s, "
                    f"total_time={total_time:.1f}s, "
                    f"input_tokens={input_tokens:,}, output_tokens={output_tokens:,}, "
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
            await self._cleanup_files(uploaded_files)

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
