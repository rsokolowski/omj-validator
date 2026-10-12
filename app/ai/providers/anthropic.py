"""Anthropic (Claude) provider on the official ``anthropic`` SDK.

Prompt parity with Gemini: every request is ONE user message whose blocks carry
exactly the text of ``app/ai/requests.py`` in Gemini's order - no ``system``
prompt split (the design spec suggested one; an A/B between providers must
compare models, not prompt layouts). OMJ grading, for example, sends:
grading text, task PDF, official solution PDF (if any), photos, the typed
solution block (if any), the closing line.

Request options (claude-api skill reference, anthropic 1.13.0):
- structured output: ``output_config={"format": {"type": "json_schema",
  "schema": ...}, "effort": ...}``; the API requires ``additionalProperties:
  false`` on every object, so the shared schemas are sent as strict copies;
- thinking: adaptive (the only mode on Claude Opus 5.5); grading asks for
  ``display: "summarized"`` so thinking text can be streamed to the student;
- refusals: ``stop_reason == "refusal"``. Opus 5.5 / Sonnet 5.5 opt into the
  server-side fallback (``fallbacks="default"`` + beta
  ``server-side-fallback-2026-07-01``); Haiku 5.5 has none.

Never logs student content: sizes, counts, tokens, timings and request ids only.
"""

import asyncio
import base64
import inspect
import io
import json
import logging
import time
from pathlib import Path
from typing import Any, Callable, Optional

import anthropic
from PIL import Image, ImageOps

from ...config import settings
from ...models import (
    LinkResult,
    PrivateExtractionResult,
    PrivateTaskMeta,
    RefineResult,
    SubmissionResult,
    SuggestResult,
)
from ...skills import get_all_skills
from .. import requests as ai_requests
from ..factory import (
    UNAVAILABLE_AUTH,
    UNAVAILABLE_CONNECTION_LOST,
    UNAVAILABLE_INTERNAL,
    UNAVAILABLE_NETWORK,
    UNAVAILABLE_NOT_FOUND,
    UNAVAILABLE_RATE_LIMIT,
    UNAVAILABLE_SERVER,
    UNAVAILABLE_TIMEOUT,
    AIContentBlockedError,
    AIProviderError,
    AIUnavailableError,
)
from ..messages import (
    AUX_UNREADABLE_MESSAGE,
    GENERIC_MESSAGE,
    OVERLOADED_MESSAGE,
    TECHNICAL_MESSAGE,
    TIMEOUT_MESSAGE,
    UNREADABLE_MESSAGE,
)
from ..models_catalog import estimate_cost, get_model
from ..parsing import parse_ai_response
from ..pattern_parsing import (
    PATTERN_LINK_SCHEMA,
    PATTERN_REFINE_SCHEMA,
    PATTERN_SUGGEST_SCHEMA,
    parse_link_response,
    parse_refine_response,
    parse_suggest_response,
)
from ..private_parsing import (
    EXTRACTION_SCHEMA,
    META_SCHEMA,
    parse_extraction_response,
    parse_meta_response,
)
from ..prompt_builder import CLOSING_LINE, build_prompt, solution_text_block
from ..schemas import RESPONSE_JSON_SCHEMA

logger = logging.getLogger(__name__)

GRADING_MAX_TOKENS = 64000  # thinking counts toward it; grading always streams
AUX_MAX_TOKENS = 16000
PING_TIMEOUT_SECONDS = 30
# The ping goes through the grading request builder (beta path + fallbacks,
# adaptive thinking with summarized display, strict JSON schema) so a shape the
# API rejects fails the admin switch instead of the first student's grading.
# Room for some thinking at low effort; hitting max_tokens still counts as success.
PING_MAX_TOKENS = 2048
PING_EFFORT = "low"
PING_PROMPT = 'Odpowiedz obiektem JSON {"ok": true}.'
PING_SCHEMA = {
    "type": "object",
    "properties": {"ok": {"type": "boolean"}},
    "required": ["ok"],
    "additionalProperties": False,
}

# Server-side refusal fallback ("default" scalar form needs exactly this header).
# Not for Haiku 5.5: it has no server-side fallback.
FALLBACK_BETA = "server-side-fallback-2026-07-01"
FALLBACK_MODELS = frozenset({"claude-opus-5-5", "claude-sonnet-5-5"})

# Messages API per-image limits: 5 MB on the base64-encoded form (the SDK's
# DEFAULT_MAX_IMAGE_BASE64_BYTES in anthropic/lib/tools/agent_toolset.py) and
# 8000 px per side (vision docs). Only an image over a limit is re-encoded,
# in memory, to a JPEG of at most DOWNSCALE_LONG_SIDE px on the long side.
MAX_IMAGE_BASE64_BYTES = 5 * 1024 * 1024
MAX_IMAGE_SIDE_PX = 8000
DOWNSCALE_LONG_SIDE_PX = 2000
DOWNSCALE_JPEG_QUALITY = 85

# Whole-request cap: the Messages API rejects a body over 32 MB (413
# request_too_large; the SDK keeps raw PDFs at 20 MB so their base64 stays
# under it). PDFs + photos (base64) + text are kept under a safer budget by
# re-encoding all photos smaller, step by step, before giving up.
REQUEST_BUDGET_BYTES = 24 * 1024 * 1024
REQUEST_SHRINK_STEPS = ((1600, 80), (1200, 80))  # (long side px, JPEG quality)

_IMAGE_MEDIA_TYPES = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
}

BLOCKED_MESSAGE = (
    "Nie udało się przetworzyć rozwiązania. Upewnij się, że zawiera tylko treść zadania lub rozwiązanie."
)
TOO_LARGE_MESSAGE = "Przesłane zdjęcia są zbyt duże. Spróbuj wysłać mniej zdjęć."


def _strict(schema: Any) -> Any:
    """Deep copy of a JSON schema with ``additionalProperties: False`` on every object.

    The shared dicts are also sent by Gemini, so they are never mutated.
    """
    if isinstance(schema, dict):
        out = {key: _strict(value) for key, value in schema.items()}
        if out.get("type") == "object":
            out["additionalProperties"] = False
        return out
    if isinstance(schema, list):
        return [_strict(value) for value in schema]
    return schema


GRADING_SCHEMA = _strict(RESPONSE_JSON_SCHEMA)
EXTRACTION_SCHEMA_STRICT = _strict(EXTRACTION_SCHEMA)
META_SCHEMA_STRICT = _strict(META_SCHEMA)
REFINE_SCHEMA_STRICT = _strict(PATTERN_REFINE_SCHEMA)
SUGGEST_SCHEMA_STRICT = _strict(PATTERN_SUGGEST_SCHEMA)
LINK_SCHEMA_STRICT = _strict(PATTERN_LINK_SCHEMA)


# ------------------------------------------------------------------ blocks


def _text_block(text: str) -> dict:
    return {"type": "text", "text": text}


def _b64(data: bytes) -> str:
    return base64.standard_b64encode(data).decode("ascii")


def _b64_size(raw_size: int) -> int:
    return 4 * ((raw_size + 2) // 3)


def _pdf_block(path: Path) -> dict:
    return {
        "type": "document",
        "source": {"type": "base64", "media_type": "application/pdf", "data": _b64(path.read_bytes())},
    }


def _over_limits(data: bytes) -> bool:
    if _b64_size(len(data)) > MAX_IMAGE_BASE64_BYTES:
        return True
    with Image.open(io.BytesIO(data)) as img:
        return max(img.size) > MAX_IMAGE_SIDE_PX


def _to_jpeg(
    data: bytes, long_side: int = DOWNSCALE_LONG_SIDE_PX, quality: int = DOWNSCALE_JPEG_QUALITY
) -> bytes:
    """Re-encode in memory: upright, flattened on white, long side <= long_side, <= 5 MB base64."""
    with Image.open(io.BytesIO(data)) as opened:
        img = ImageOps.exif_transpose(opened)
        if img.mode in ("RGBA", "LA") or (img.mode == "P" and "transparency" in img.info):
            rgba = img.convert("RGBA")
            flat = Image.new("RGB", rgba.size, "white")
            flat.paste(rgba, mask=rgba.getchannel("A"))
            img = flat
        else:
            img = img.convert("RGB")
    while True:
        scaled = img.copy()
        scaled.thumbnail((long_side, long_side), Image.Resampling.LANCZOS)
        buffer = io.BytesIO()
        scaled.save(buffer, "JPEG", quality=quality)
        out = buffer.getvalue()
        if _b64_size(len(out)) <= MAX_IMAGE_BASE64_BYTES or long_side <= 256:
            return out
        long_side = int(long_side * 0.8)


def _image_block(path: Path, shrink: Optional[tuple[int, int]] = None) -> dict:
    """A photo as a base64 image block; re-encoded only when over the API limits.

    ``shrink`` = (long side, quality) forces a re-encode (request size budget).
    """
    data = path.read_bytes()
    media_type = _IMAGE_MEDIA_TYPES.get(path.suffix.lower())
    if shrink is not None or media_type is None or _over_limits(data):
        original = len(data)
        data, media_type = _to_jpeg(data, *(shrink or ())), "image/jpeg"
        logger.info(f"[Claude] Image re-encoded in memory: {original // 1024}KB -> {len(data) // 1024}KB")
    return {"type": "image", "source": {"type": "base64", "media_type": media_type, "data": _b64(data)}}


def _block_size(block: dict) -> int:
    """Approximate bytes a block adds to the request body."""
    if "source" in block:
        return len(block["source"]["data"])
    return len(block.get("text", "").encode("utf-8"))


def _photo_blocks(image_paths: list[Path], other_bytes: int) -> list[dict]:
    """Photo blocks that, with ``other_bytes`` of the rest of the request, fit REQUEST_BUDGET_BYTES."""
    blocks = [_image_block(path) for path in image_paths]
    for shrink in (None, *REQUEST_SHRINK_STEPS):
        if shrink is not None:
            blocks = [_image_block(path, shrink) for path in image_paths]
        total = other_bytes + sum(_block_size(b) for b in blocks)
        if total <= REQUEST_BUDGET_BYTES:
            return blocks
        logger.info(
            f"[Claude] Request {total // 1024}KB over budget {REQUEST_BUDGET_BYTES // 1024}KB "
            f"at shrink={shrink}, photos={len(image_paths)}"
        )
    raise AIProviderError(TOO_LARGE_MESSAGE)


def _final_text(final: Any) -> str:
    """Concatenated text blocks (thinking and fallback markers are skipped)."""
    return "".join(
        getattr(block, "text", "") or ""
        for block in (getattr(final, "content", None) or [])
        if getattr(block, "type", None) == "text"
    )


def _is_json_object(text: str) -> bool:
    try:
        return isinstance(json.loads(text), dict)
    except (TypeError, ValueError):
        return False


async def _notify(callback: Optional[Callable], *args) -> None:
    """Call a sync or async callback."""
    if callback is None:
        return
    result = callback(*args)
    if inspect.isawaitable(result):
        await result


def _status_text(error: Exception) -> str:
    """'429 rate_limit_error' / '503 Service Unavailable' for an HTTP error, else the class name.

    Status code and status text only - never the response body.
    """
    status = getattr(error, "status_code", None)
    if status is None:
        return type(error).__name__
    response = getattr(error, "response", None)
    text = getattr(error, "type", None) or getattr(response, "reason_phrase", "") or ""
    return f"{status} {text}".strip()


def classify_unavailable(error: Exception) -> Optional[AIUnavailableError]:
    """An AIUnavailableError when ``error`` means Claude could not serve at all, else None.

    Same fail-closed rule as Gemini (see gemini.classify_unavailable): 401/403,
    404, 429, 502/503/504/529, a connection never established and a 400 about
    the account's credit balance fail a request over; timeouts, 500 and a
    connection dropped mid-request (which the request's own content can
    cause) are classified for the breaker only. Anything else returns None.
    """
    name = type(error).__name__
    status = getattr(error, "status_code", None)
    if isinstance(error, (asyncio.TimeoutError, TimeoutError, anthropic.APITimeoutError)):
        kind, message = UNAVAILABLE_TIMEOUT, TIMEOUT_MESSAGE
    elif isinstance(error, (anthropic.AuthenticationError, anthropic.PermissionDeniedError)):
        kind, message = UNAVAILABLE_AUTH, TECHNICAL_MESSAGE
    elif isinstance(error, anthropic.BadRequestError) and str(getattr(error, "message", "")).lower().startswith(
        "your credit balance is too low"
    ):
        kind, message = UNAVAILABLE_AUTH, TECHNICAL_MESSAGE
    elif isinstance(error, anthropic.NotFoundError):
        kind, message = UNAVAILABLE_NOT_FOUND, GENERIC_MESSAGE
    elif isinstance(error, anthropic.RateLimitError):
        kind, message = UNAVAILABLE_RATE_LIMIT, OVERLOADED_MESSAGE
    elif isinstance(error, anthropic.APIConnectionError):
        # The SDK wraps the transport error; only a failed connect proves the content played no part
        never_connected = type(error.__cause__).__name__ in ("ConnectError", "ConnectTimeout")
        kind = UNAVAILABLE_NETWORK if never_connected else UNAVAILABLE_CONNECTION_LOST
        message = OVERLOADED_MESSAGE
    elif isinstance(error, anthropic.APIStatusError) and status in (502, 503, 504, 529):
        kind, message = UNAVAILABLE_SERVER, OVERLOADED_MESSAGE
    elif isinstance(error, anthropic.APIStatusError) and (status or 0) >= 500:
        kind, message = UNAVAILABLE_INTERNAL, OVERLOADED_MESSAGE
    else:
        return None
    return AIUnavailableError(message, kind=kind, status=status, error_class=name)


def _image_bytes_kb(image_paths: list[Path]) -> float:
    return sum(p.stat().st_size for p in image_paths if p.exists()) / 1024


class AnthropicProvider:
    """AI provider using the Anthropic Messages API (Claude)."""

    provider_name = "anthropic"

    def __init__(self, model: str):
        if not settings.anthropic_api_key:
            raise ValueError("ANTHROPIC_API_KEY is required. Set it in your .env file.")
        self._model_name = model
        self._fallbacks = model in FALLBACK_MODELS
        # The overall wall-clock limit is anthropic_timeout, enforced by
        # asyncio.wait_for around each call (same semantics as Gemini's
        # gemini_timeout). The SDK timeout below is per HTTP request, so its
        # retries (default 2: connection errors, 408/409/429/5xx) only fit in
        # when a failure is fast; a slow one runs into the wall-clock limit.
        self._client = anthropic.AsyncAnthropic(
            api_key=settings.anthropic_api_key,
            base_url=settings.anthropic_api_base_url or None,
            timeout=settings.anthropic_timeout,
        )
        logger.info(
            f"[Claude] Initialized with model={model}, effort={settings.anthropic_effort}, "
            f"effort_aux={settings.anthropic_effort_aux}, fallbacks={'default' if self._fallbacks else 'none'}"
            + (f", base_url={settings.anthropic_api_base_url}" if settings.anthropic_api_base_url else "")
        )

    @property
    def model_name(self) -> str:
        return self._model_name

    def get_timeout(self) -> int:
        return settings.anthropic_timeout

    # ------------------------------------------------------------ plumbing

    def _messages(self):
        """The SDK resource: beta (for the fallback parameter) or plain messages."""
        return self._client.beta.messages if self._fallbacks else self._client.messages

    def _request(
        self, content: list, schema: dict, effort: str, *, grading: bool, max_tokens: Optional[int] = None
    ) -> dict:
        thinking: dict = {"type": "adaptive"}
        if grading:
            thinking["display"] = "summarized"  # default is "omitted" (empty thinking text)
        kwargs: dict = {
            "model": self._model_name,
            "max_tokens": max_tokens or (GRADING_MAX_TOKENS if grading else AUX_MAX_TOKENS),
            "messages": [{"role": "user", "content": content}],
            "thinking": thinking,
            "output_config": {"format": {"type": "json_schema", "schema": schema}, "effort": effort},
        }
        if self._fallbacks:
            kwargs["betas"] = [FALLBACK_BETA]
            kwargs["fallbacks"] = "default"
        return kwargs

    async def _stream(
        self,
        kwargs: dict,
        on_thinking: Optional[Callable] = None,
        on_feedback: Optional[Callable] = None,
    ) -> tuple[str, Any, float, Optional[str]]:
        """Stream one request. Returns (thinking_text, final_message, api_time, request_id)."""
        thinking: list[str] = []
        request_id: list[Optional[str]] = [None]

        async def consume():
            async with self._messages().stream(**kwargs) as stream:
                request_id[0] = getattr(stream, "request_id", None)
                async for event in stream:
                    if getattr(event, "type", None) != "content_block_delta":
                        continue  # raw deltas only; the SDK's helper events repeat them
                    delta = event.delta
                    if delta.type == "thinking_delta":
                        thinking.append(delta.thinking)
                        await _notify(on_thinking, delta.thinking)
                    elif delta.type == "text_delta":
                        await _notify(on_feedback, delta.text)
                return await stream.get_final_message()

        api_start = time.time()
        # Wall-clock limit for the whole stream, SDK retries included (see __init__)
        final = await asyncio.wait_for(consume(), timeout=self.get_timeout())
        return "".join(thinking), final, time.time() - api_start, request_id[0]

    def _checked_text(self, final: Any, request_id: Optional[str], *, grading: bool) -> str:
        """The response text, or the error a refusal / truncated answer maps to."""
        stop_reason = getattr(final, "stop_reason", None)
        if stop_reason == "refusal":
            category = getattr(getattr(final, "stop_details", None), "category", None)
            logger.warning(
                f"[Claude] Refusal model={self._model_name} category={category} request_id={request_id}"
            )
            raise AIContentBlockedError(BLOCKED_MESSAGE)
        text = _final_text(final)
        if (stop_reason == "max_tokens" and not _is_json_object(text)) or not text.strip():
            # An empty aux answer must not read as "no problem found" / "no manipulation"
            logger.warning(
                f"[Claude] Unusable response stop_reason={stop_reason} chars={len(text)} request_id={request_id}"
            )
            raise AIProviderError(UNREADABLE_MESSAGE if grading else AUX_UNREADABLE_MESSAGE)
        return text

    def _usage_meta(self, final: Any, started: float) -> dict:
        """Model, tokens, cost and timing - never content.

        Thinking is billed inside output_tokens, hence thoughts_tokens=0.
        Top-level usage covers the attempt that produced the answer; with a
        server-side fallback that is the fallback model (named in served_by).
        A fallback ran when usage.iterations has a "fallback_message" entry
        (shared/model-migration.md, "Reading the response"); the top-level
        model then names the model that served the answer.
        """
        usage = getattr(final, "usage", None)
        input_tokens = getattr(usage, "input_tokens", 0) or 0
        output_tokens = getattr(usage, "output_tokens", 0) or 0
        cache_read = getattr(usage, "cache_read_input_tokens", 0) or 0
        cache_write = getattr(usage, "cache_creation_input_tokens", 0) or 0
        iterations = getattr(usage, "iterations", None) or []
        served_by = (
            getattr(final, "model", None)
            if any(getattr(entry, "type", None) == "fallback_message" for entry in iterations)
            else None
        )
        # Top-level usage is the serving model's: price it at that model's rates when known
        priced_as = served_by if served_by and get_model("anthropic", served_by) else self._model_name
        meta = {
            "provider": "anthropic",
            "model": self._model_name,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "cache_read_tokens": cache_read,
            "cache_write_tokens": cache_write,
            "thoughts_tokens": 0,
            "estimated_cost": round(
                estimate_cost(
                    "anthropic", priced_as, input_tokens, output_tokens,
                    cache_read_tokens=cache_read, cache_write_tokens=cache_write,
                ),
                6,
            ),
            "api_time": round(time.time() - started, 2),
        }
        if served_by is not None:
            meta["served_by"] = served_by
        return meta

    def _friendly_error(self, error: Exception, label: str, started: float) -> AIProviderError:
        """Map an SDK/transport error to a Polish message fit for a child; log type/status/request id."""
        elapsed = time.time() - started
        status = getattr(error, "status_code", None)
        request_id = getattr(error, "request_id", None)
        detail = ""
        if isinstance(error, (anthropic.BadRequestError, anthropic.NotFoundError, anthropic.UnprocessableEntityError)):
            # API validation text (request structure, not student content) - needed to debug a 400
            detail = f" detail={str(getattr(error, 'message', ''))[:300]!r}"
        logger.error(
            f"[{label}] {type(error).__name__} status={status} request_id={request_id} "
            f"model={self._model_name} after {elapsed:.1f}s{detail}"
        )
        unavailable = classify_unavailable(error)
        if unavailable is not None:
            return unavailable
        return AIProviderError(GENERIC_MESSAGE)

    # ---------------------------------------------------------------- ping

    async def ping(self) -> None:
        """One small call in the grading request shape, proving key + model + request
        options work (admin switch). Any stop_reason counts as success. Raises AIProviderError."""
        kwargs = self._request(
            [_text_block(PING_PROMPT)], PING_SCHEMA, PING_EFFORT, grading=True, max_tokens=PING_MAX_TOKENS
        )
        started = time.time()
        try:
            final = await asyncio.wait_for(self._messages().create(**kwargs), timeout=PING_TIMEOUT_SECONDS)
        except Exception as e:
            self._friendly_error(e, "Claude ping", started)  # logs type/status/request id/400 detail
            raise AIProviderError(f"Model {self._model_name} nie odpowiada: {_status_text(e)}")
        usage = getattr(final, "usage", None)
        logger.info(
            f"[Claude ping] model={self._model_name} stop_reason={getattr(final, 'stop_reason', None)} "
            f"input_tokens={getattr(usage, 'input_tokens', None)} output_tokens={getattr(usage, 'output_tokens', None)} "
            f"served_by={getattr(final, 'model', None)} after {time.time() - started:.1f}s"
        )

    # ---------------------------------------------------------- OMJ grading

    def _omj_content(
        self,
        prompt_text: str,
        task_pdf_path: Path,
        solution_pdf_path: Optional[Path],
        image_paths: list[Path],
        task_number: int,
        solution_text: Optional[str],
    ) -> list:
        """Blocks in Gemini's order.

        No prompt-cache breakpoint: the prefix starts with per-task grading
        text, so a cache entry would rarely be hit while every miss would pay
        the 1.25x cache-write rate on the PDFs.
        """
        head = [
            _text_block(
                ai_requests.omj_grading_text(
                    prompt_text, task_number, solution_pdf_path is not None, len(image_paths), bool(solution_text)
                )
            ),
            _pdf_block(task_pdf_path),
        ]
        if solution_pdf_path is not None:
            head.append(_pdf_block(solution_pdf_path))
        tail = [_text_block(solution_text_block(solution_text))] if solution_text else []
        tail.append(_text_block(CLOSING_LINE))
        photos = _photo_blocks(image_paths, sum(_block_size(b) for b in head + tail))
        return head + photos + tail

    async def analyze_solution(
        self,
        task_pdf_path: Path,
        solution_pdf_path: Optional[Path],
        image_paths: list[Path],
        task_number: int,
        etap: str = "etap2",
        solution_text: Optional[str] = None,
    ) -> SubmissionResult:
        """Grade an OMJ solution. Streams under the hood (64k max_tokens needs streaming)."""
        return await self.analyze_solution_stream(
            task_pdf_path, solution_pdf_path, image_paths, task_number, etap, solution_text=solution_text
        )

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
        solution_text: Optional[str] = None,
    ) -> SubmissionResult:
        """Grade an OMJ solution, streaming thinking/feedback text through the callbacks."""
        start_time = time.time()
        logger.info(
            f"[Claude Stream Request] model={self._model_name}, etap={etap}, "
            f"task={task_number}, images={len(image_paths)}, "
            f"text_chars={len(solution_text or '')}, "
            f"total_image_size={_image_bytes_kb(image_paths):.1f}KB"
        )
        try:
            has_solution_pdf = bool(solution_pdf_path and solution_pdf_path.exists())
            content = await asyncio.to_thread(
                self._omj_content,
                build_prompt(etap),
                task_pdf_path,
                solution_pdf_path if has_solution_pdf else None,
                image_paths,
                task_number,
                solution_text,
            )
            # No upload step: the request is about to be sent
            await _notify(on_upload_complete)

            return await self._grade(content, etap, "Claude Stream Response", on_thinking, on_feedback, start_time)
        except AIProviderError:
            raise
        except Exception as e:
            raise self._friendly_error(e, "Claude Stream", start_time)

    async def _grade(
        self,
        content: list,
        etap: str,
        label: str,
        on_thinking: Optional[Callable[[str], Any]],
        on_feedback: Optional[Callable[[str], Any]],
        start_time: float,
    ) -> SubmissionResult:
        """Stream one grading request and turn it into a SubmissionResult with scoring_meta."""
        kwargs = self._request(content, GRADING_SCHEMA, settings.anthropic_effort, grading=True)
        thinking, final, api_time, request_id = await self._stream(kwargs, on_thinking, on_feedback)
        text = self._checked_text(final, request_id, grading=True)
        result = parse_ai_response(text, provider_name="Claude", etap=etap)
        result.scoring_meta = {
            **(result.scoring_meta or {}),
            **self._usage_meta(final, start_time),
            "thinking": thinking,
            "api_time": api_time,
            "total_time": time.time() - start_time,
        }
        self._log_response(label, result.scoring_meta, final, request_id, thinking, text)
        return result

    def _log_response(self, label: str, meta: dict, final: Any, request_id, thinking: str, text: str) -> None:
        logger.info(
            f"[{label}] api_time={meta['api_time']:.1f}s, total_time={meta.get('total_time', 0):.1f}s, "
            f"input_tokens={meta['input_tokens']:,}, output_tokens={meta['output_tokens']:,}, "
            f"cache_read={meta['cache_read_tokens']:,}, cache_write={meta['cache_write_tokens']:,}, "
            f"estimated_cost=${meta['estimated_cost']:.4f}, stop_reason={getattr(final, 'stop_reason', None)}, "
            f"thinking_chars={len(thinking)}, feedback_chars={len(text)}, "
            f"served_by={meta.get('served_by', self._model_name)}, request_id={request_id}"
        )

    # ------------------------------------------------------ private grading

    def _private_content(
        self, task_title: str, task_content: str, image_paths: list[Path], solution_text: Optional[str]
    ) -> list:
        head = _text_block(
            ai_requests.private_grading_text(task_title, task_content, len(image_paths), bool(solution_text))
        )
        labels = [_text_block(ai_requests.photo_label(index)) for index in range(1, len(image_paths) + 1)]
        tail = [_text_block(solution_text_block(solution_text))] if solution_text else []
        tail.append(_text_block(CLOSING_LINE))
        photos = _photo_blocks(image_paths, sum(_block_size(b) for b in [head, *labels, *tail]))
        blocks = [head]
        for label, photo in zip(labels, photos):
            blocks += [label, photo]
        return blocks + tail

    async def analyze_private_solution_stream(
        self,
        task_title: str,
        task_content: str,
        image_paths: list[Path],
        on_thinking: Optional[Callable[[str], Any]] = None,
        on_upload_complete: Optional[Callable[[], Any]] = None,
        solution_text: Optional[str] = None,
    ) -> SubmissionResult:
        """Grade a solution to a private task - no PDF, no official solution."""
        start_time = time.time()
        logger.info(
            f"[Claude Private Stream] model={self._model_name}, images={len(image_paths)}, "
            f"text_chars={len(solution_text or '')}, "
            f"total_image_size={_image_bytes_kb(image_paths):.1f}KB"
        )
        try:
            content = await asyncio.to_thread(
                self._private_content, task_title, task_content, image_paths, solution_text
            )
            await _notify(on_upload_complete)

            # Private tasks are graded on the etap2 ladder (0, 2, 5, 6)
            return await self._grade(
                content, "etap2", "Claude Private Stream Response", on_thinking, None, start_time
            )
        except AIProviderError:
            raise
        except Exception as e:
            raise self._friendly_error(e, "Claude Private Stream", start_time)

    # ------------------------------------------------- aux (non-streaming)

    async def _create_json(self, content: list, schema: dict, label: str) -> tuple[str, dict]:
        """One non-streaming, schema-constrained call. Returns (text, usage meta)."""
        kwargs = self._request(content, schema, settings.anthropic_effort_aux, grading=False)
        started = time.time()
        try:
            final = await asyncio.wait_for(self._messages().create(**kwargs), timeout=self.get_timeout())
        except Exception as e:
            raise self._friendly_error(e, label, started)
        request_id = getattr(final, "_request_id", None)
        text = self._checked_text(final, request_id, grading=False)
        meta = self._usage_meta(final, started)
        logger.info(
            f"[{label}] api_time={meta['api_time']}s, "
            f"input_tokens={meta['input_tokens']:,}, output_tokens={meta['output_tokens']:,}, "
            f"cache_read={meta['cache_read_tokens']:,}, estimated_cost=${meta['estimated_cost']:.4f}, "
            f"stop_reason={getattr(final, 'stop_reason', None)}, request_id={request_id}"
        )
        return text, meta

    async def extract_private_tasks(self, image_paths: list[Path]) -> PrivateExtractionResult:
        """Read every problem statement off photos of a page."""
        started = time.time()
        try:
            instruction = _text_block(ai_requests.extract_text())
            images = await asyncio.to_thread(_photo_blocks, image_paths, _block_size(instruction))
        except AIProviderError:
            raise
        except Exception as e:
            raise self._friendly_error(e, "Claude Extract", started)
        content = [instruction, *images]
        text, meta = await self._create_json(content, EXTRACTION_SCHEMA_STRICT, "Claude Extract")
        result = parse_extraction_response(text)
        result.meta = meta
        return result

    async def generate_private_task_meta(self, title: str, content: str) -> PrivateTaskMeta:
        """Hints, category and difficulty for a task statement (text only)."""
        text, meta = await self._create_json(
            [_text_block(ai_requests.meta_text(title, content))], META_SCHEMA_STRICT, "Claude Meta"
        )
        result = parse_meta_response(text)
        result.meta = meta
        return result

    async def refine_pattern(
        self,
        draft: dict,
        source_text: Optional[str],
        history: list[dict],
        current: dict,
        candidates: list[dict],
    ) -> RefineResult:
        """One turn of the refine conversation: a reply, 2-3 versions, verdict, questions."""
        skills = get_all_skills()
        prompt = ai_requests.refine_text(draft, source_text, history, current, candidates, skills)
        text, meta = await self._create_json([_text_block(prompt)], REFINE_SCHEMA_STRICT, "Claude Refine")
        result = parse_refine_response(text, {s.id for s in skills}, {c["task_key"] for c in candidates})
        result.meta = meta
        return result

    async def suggest_patterns(self, task_text: str, feedback: str, draft: Optional[str]) -> SuggestResult:
        """1-3 patterns worth remembering from a graded solution."""
        prompt = ai_requests.suggest_text(task_text, feedback, draft)
        text, meta = await self._create_json([_text_block(prompt)], SUGGEST_SCHEMA_STRICT, "Claude Suggest")
        result = parse_suggest_response(text)
        result.meta = meta
        return result

    async def link_pattern_tasks(self, pattern: dict, candidates: list[dict]) -> LinkResult:
        """Up to 5 of the server's candidate OMJ tasks that exercise the pattern."""
        prompt = ai_requests.link_text(pattern, candidates)
        text, meta = await self._create_json([_text_block(prompt)], LINK_SCHEMA_STRICT, "Claude Link")
        result = parse_link_response(text, {c["task_key"] for c in candidates})
        result.meta = meta
        return result
