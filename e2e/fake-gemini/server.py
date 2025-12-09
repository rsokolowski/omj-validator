"""
Fake Gemini API Server for E2E Testing.

Mimics the Google Gemini API (generativelanguage.googleapis.com) endpoints
used by the google-genai SDK. Allows configuring different response scenarios
for comprehensive testing.

Endpoints implemented:
- POST /upload/v1beta/files - Upload file
- GET /v1beta/files/{name} - Get file info
- DELETE /v1beta/files/{name} - Delete file
- POST /v1beta/models/{model}:generateContent - Generate content (non-streaming)
- POST /v1beta/models/{model}:streamGenerateContent - Generate content (streaming)
"""

import asyncio
import json
import logging
import os
import re
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

from fastapi import FastAPI, HTTPException, Request, Query
from fastapi.responses import StreamingResponse, JSONResponse
from pydantic import BaseModel

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Fake Gemini API", version="1.0.0")

# Expected API key for validation (set via environment or use test default)
EXPECTED_API_KEY = os.environ.get("FAKE_GEMINI_API_KEY", "fake-api-key-for-testing")


def validate_api_key(request: Request) -> None:
    """Validate API key from request headers."""
    api_key = request.headers.get("x-goog-api-key")
    if not api_key:
        # Also check query parameter (some SDKs use this)
        api_key = request.query_params.get("key")

    if not api_key:
        raise HTTPException(401, {"error": {"message": "API key is required", "status": "UNAUTHENTICATED"}})

    if api_key != EXPECTED_API_KEY:
        logger.warning(f"Invalid API key: {api_key[:8]}...")
        raise HTTPException(401, {"error": {"message": "Invalid API key", "status": "UNAUTHENTICATED"}})


# ============================================================================
# Configuration - Control test scenarios via environment variables
# ============================================================================

class ScenarioType(str, Enum):
    """Available test scenarios."""
    SUCCESS_SCORE_6 = "success_score_6"  # Perfect score
    SUCCESS_SCORE_5 = "success_score_5"  # Good score
    SUCCESS_SCORE_2 = "success_score_2"  # Partial score
    SUCCESS_SCORE_0 = "success_score_0"  # Zero score
    ERROR_TIMEOUT = "error_timeout"      # Simulate timeout
    ERROR_QUOTA = "error_quota"          # Quota exceeded
    ERROR_SAFETY = "error_safety"        # Safety filter blocked
    ERROR_INVALID_KEY = "error_invalid_key"  # Invalid API key
    SLOW_RESPONSE = "slow_response"      # Slow but successful (for loading state tests)


@dataclass
class ServerConfig:
    """Server configuration loaded from environment."""
    default_scenario: ScenarioType = ScenarioType.SUCCESS_SCORE_6
    response_delay_ms: int = 100  # Base delay for all responses
    slow_response_delay_ms: int = 5000  # Delay for SLOW_RESPONSE scenario
    streaming_chunk_delay_ms: int = 50  # Delay between streaming chunks
    # Task-specific scenarios: task_key -> scenario
    task_scenarios: dict = field(default_factory=dict)

    @classmethod
    def from_env(cls) -> "ServerConfig":
        config = cls()
        config.default_scenario = ScenarioType(
            os.environ.get("FAKE_GEMINI_SCENARIO", "success_score_6")
        )
        config.response_delay_ms = int(
            os.environ.get("FAKE_GEMINI_DELAY_MS", "100")
        )
        config.slow_response_delay_ms = int(
            os.environ.get("FAKE_GEMINI_SLOW_DELAY_MS", "5000")
        )
        config.streaming_chunk_delay_ms = int(
            os.environ.get("FAKE_GEMINI_STREAM_DELAY_MS", "50")
        )
        # Parse task scenarios from JSON env var
        # Format: {"2024_etap2_1": "success_score_0", "2024_etap2_2": "error_timeout"}
        task_scenarios_json = os.environ.get("FAKE_GEMINI_TASK_SCENARIOS", "{}")
        try:
            config.task_scenarios = json.loads(task_scenarios_json)
        except json.JSONDecodeError:
            logger.warning(f"Invalid FAKE_GEMINI_TASK_SCENARIOS: {task_scenarios_json}")
        return config


config = ServerConfig.from_env()


# ============================================================================
# In-memory storage for uploaded files
# ============================================================================

@dataclass
class StoredFile:
    """Stored file metadata."""
    name: str
    display_name: str
    mime_type: str
    size_bytes: int
    create_time: str
    state: str = "ACTIVE"


_files: dict[str, StoredFile] = {}
MAX_STORED_FILES = 100  # Cleanup oldest files when limit is reached


def cleanup_old_files() -> None:
    """Remove oldest files when storage limit is reached."""
    if len(_files) >= MAX_STORED_FILES:
        # Sort by create_time and remove oldest half
        sorted_files = sorted(_files.items(), key=lambda x: x[1].create_time)
        files_to_remove = sorted_files[:len(sorted_files) // 2]
        for file_id, _ in files_to_remove:
            del _files[file_id]
        logger.info(f"Cleaned up {len(files_to_remove)} old files, {len(_files)} remaining")


# ============================================================================
# Response templates
# ============================================================================

FEEDBACK_TEMPLATES = {
    ScenarioType.SUCCESS_SCORE_6: """## Ocena rozwiązania

Rozwiązanie jest **poprawne i kompletne**.

### Mocne strony:
- Prawidłowe zrozumienie treści zadania
- Logiczne i przejrzyste rozumowanie
- Poprawne obliczenia
- Odpowiedź końcowa jest prawidłowa

### Podsumowanie:
Gratulacje! Rozwiązanie zasługuje na maksymalną liczbę punktów.""",

    ScenarioType.SUCCESS_SCORE_5: """## Ocena rozwiązania

Rozwiązanie jest **w większości poprawne**, ale zawiera drobne uchybienia.

### Mocne strony:
- Prawidłowe zrozumienie treści zadania
- Poprawny tok rozumowania

### Do poprawy:
- Brak pełnego uzasadnienia jednego z kroków
- Niewielkie niedoprecyzowanie w końcowej odpowiedzi

### Podsumowanie:
Bardzo dobre rozwiązanie, wymaga jedynie drobnych uzupełnień.""",

    ScenarioType.SUCCESS_SCORE_2: """## Ocena rozwiązania

Rozwiązanie jest **częściowo poprawne**.

### Mocne strony:
- Prawidłowe zrozumienie treści zadania

### Problemy:
- Niepełne rozumowanie - brakuje kluczowych kroków
- Błędy w obliczeniach
- Odpowiedź końcowa jest nieprawidłowa

### Podsumowanie:
Rozwiązanie pokazuje pewne zrozumienie problemu, ale wymaga znacznej poprawy.""",

    ScenarioType.SUCCESS_SCORE_0: """## Ocena rozwiązania

Rozwiązanie jest **niepoprawne**.

### Problemy:
- Błędne zrozumienie treści zadania
- Nieprawidłowe podejście do rozwiązania
- Brak poprawnych obliczeń
- Odpowiedź końcowa jest całkowicie błędna

### Podsumowanie:
Proszę przeczytać treść zadania ponownie i spróbować innego podejścia.""",
}

THINKING_TEMPLATE = """**Understanding the Problem**
Let me carefully read the problem statement and identify the key elements...

**Analyzing the Student's Solution**
I can see the student has attempted to solve this problem. Let me trace through their work...

**Checking Mathematical Correctness**
Now I'll verify each step of the calculation...

**Evaluating Completeness**
Checking if all required parts of the solution are present...

**Determining the Score**
Based on my analysis, I will now assign a score according to the OMJ rubric..."""


def get_response_json(scenario: ScenarioType, task_number: int = 1) -> dict:
    """Generate the JSON response for a given scenario."""
    score_map = {
        ScenarioType.SUCCESS_SCORE_6: 6,
        ScenarioType.SUCCESS_SCORE_5: 5,
        ScenarioType.SUCCESS_SCORE_2: 2,
        ScenarioType.SUCCESS_SCORE_0: 0,
        ScenarioType.SLOW_RESPONSE: 6,
    }

    score = score_map.get(scenario, 6)
    feedback = FEEDBACK_TEMPLATES.get(scenario, FEEDBACK_TEMPLATES[ScenarioType.SUCCESS_SCORE_6])

    return {
        "score": score,
        "feedback": feedback
    }


# ============================================================================
# API Endpoints
# ============================================================================

@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "healthy", "service": "fake-gemini"}


@app.get("/config")
async def get_config():
    """Get current server configuration (for debugging)."""
    return {
        "default_scenario": config.default_scenario.value,
        "response_delay_ms": config.response_delay_ms,
        "slow_response_delay_ms": config.slow_response_delay_ms,
        "streaming_chunk_delay_ms": config.streaming_chunk_delay_ms,
        "task_scenarios": config.task_scenarios,
        "stored_files_count": len(_files),
    }


@app.post("/config/scenario")
async def set_scenario(scenario: str, task_key: Optional[str] = None):
    """
    Set the scenario for responses.

    Args:
        scenario: The scenario type (e.g., "success_score_6", "error_timeout")
        task_key: Optional task key (e.g., "2024_etap2_1") for task-specific scenarios
    """
    try:
        scenario_type = ScenarioType(scenario)
    except ValueError:
        raise HTTPException(400, f"Invalid scenario: {scenario}. Valid: {[s.value for s in ScenarioType]}")

    if task_key:
        config.task_scenarios[task_key] = scenario
        logger.info(f"Set scenario for task {task_key}: {scenario}")
    else:
        config.default_scenario = scenario_type
        logger.info(f"Set default scenario: {scenario}")

    return {"status": "ok", "scenario": scenario, "task_key": task_key}


@app.delete("/config/scenario/{task_key}")
async def clear_task_scenario(task_key: str):
    """Clear a task-specific scenario."""
    if task_key in config.task_scenarios:
        del config.task_scenarios[task_key]
        logger.info(f"Cleared scenario for task {task_key}")
    return {"status": "ok"}


@app.post("/config/reset")
async def reset_config():
    """Reset configuration to defaults."""
    global config
    config = ServerConfig.from_env()
    _files.clear()
    logger.info("Reset configuration to defaults")
    return {"status": "ok"}


# ============================================================================
# Gemini API - Files (Resumable Upload Support)
# ============================================================================

# Pending uploads: upload_id -> metadata
_pending_uploads: dict[str, dict] = {}


def make_file_response(stored_file: StoredFile) -> dict:
    """Create a file response dict with all required fields including uri."""
    return {
        "name": stored_file.name,
        "displayName": stored_file.display_name,
        "mimeType": stored_file.mime_type,
        "sizeBytes": str(stored_file.size_bytes),
        "createTime": stored_file.create_time,
        "state": stored_file.state,
        # URI is required by the google-genai SDK
        "uri": f"https://generativelanguage.googleapis.com/v1beta/{stored_file.name}",
    }


@app.post("/upload/v1beta/files")
async def create_file(request: Request):
    """
    Create a file upload session (resumable upload protocol).

    The google-genai SDK uses a two-phase upload:
    1. POST to /upload/v1beta/files with JSON metadata
       - Response includes X-Goog-Upload-URL header with upload URI
    2. PUT/POST to the upload URI with actual file data

    For uploadType=multipart, the SDK may send both in one request.
    """
    validate_api_key(request)

    content_type = request.headers.get("content-type", "")
    upload_type = request.query_params.get("uploadType", "")
    body = await request.body()

    logger.info(f"Upload request: content-type={content_type}, uploadType={upload_type}, body_size={len(body)}")

    # Check if this is a resumable upload initiation (metadata only)
    if "application/json" in content_type and upload_type == "resumable":
        # Phase 1: Create upload session, return upload URL
        try:
            metadata = json.loads(body.decode("utf-8"))
        except json.JSONDecodeError:
            metadata = {}

        upload_id = uuid.uuid4().hex[:16]
        _pending_uploads[upload_id] = metadata

        # Get the host from the request to build the upload URL
        host = request.headers.get("host", "fake-gemini:8080")
        scheme = "http"  # Always http for internal testing
        upload_url = f"{scheme}://{host}/upload/v1beta/files/{upload_id}"

        logger.info(f"Created resumable upload session: {upload_id}, upload_url={upload_url}")

        # Return response with upload URL in header
        return JSONResponse(
            content={"file": metadata.get("file", {})},
            headers={"X-Goog-Upload-URL": upload_url},
        )

    # Check if this is a multipart upload (metadata + file in one request)
    elif "multipart/related" in content_type:
        return await handle_multipart_upload(request, body, content_type)

    # Direct upload (file content only, metadata in query params)
    elif upload_type == "media":
        return await handle_direct_upload(request, body, content_type)

    # Application/json without resumable - also initiate session
    elif "application/json" in content_type:
        # Some SDK versions might not pass uploadType
        try:
            metadata = json.loads(body.decode("utf-8"))
        except json.JSONDecodeError:
            metadata = {}

        upload_id = uuid.uuid4().hex[:16]
        _pending_uploads[upload_id] = metadata

        host = request.headers.get("host", "fake-gemini:8080")
        upload_url = f"http://{host}/upload/v1beta/files/{upload_id}"

        logger.info(f"Created upload session (no uploadType): {upload_id}")

        return JSONResponse(
            content={"file": metadata.get("file", {})},
            headers={"X-Goog-Upload-URL": upload_url},
        )

    else:
        # Unknown format - try to handle as raw binary
        return await handle_direct_upload(request, body, content_type)


@app.post("/upload/v1beta/files/{upload_id}")
@app.put("/upload/v1beta/files/{upload_id}")
async def complete_upload(upload_id: str, request: Request):
    """
    Complete a resumable upload by receiving the file data.

    Note: We skip API key validation here because:
    1. The upload URL is only obtained after authenticating the initial request
    2. The google-genai SDK may not include the API key header in this request
    3. This mimics Google's signed upload URLs which don't require additional auth
    """
    # Skip API key validation for upload completion - URL is pre-authenticated

    body = await request.body()
    content_type = request.headers.get("content-type", "application/octet-stream")

    logger.info(f"Completing upload {upload_id}: content-type={content_type}, size={len(body)}")

    # Get pending metadata if available
    metadata = _pending_uploads.pop(upload_id, {})
    display_name = metadata.get("file", {}).get("displayName", "unknown")

    file_id = f"files/{uuid.uuid4().hex[:12]}"

    stored_file = StoredFile(
        name=file_id,
        display_name=display_name,
        mime_type=content_type,
        size_bytes=len(body),
        create_time=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    )
    cleanup_old_files()
    _files[file_id] = stored_file

    logger.info(f"Completed upload: {file_id} ({stored_file.display_name}, {stored_file.size_bytes} bytes)")

    await asyncio.sleep(config.response_delay_ms / 1000)

    # Return response with upload status header to indicate completion
    return JSONResponse(
        content={"file": make_file_response(stored_file)},
        headers={"X-Goog-Upload-Status": "final"},
    )


async def handle_multipart_upload(request: Request, body: bytes, content_type: str):
    """Handle multipart/related upload (metadata + file in one request)."""
    # Extract boundary
    boundary = None
    for part in content_type.split(";"):
        part = part.strip()
        if part.startswith("boundary="):
            boundary = part[9:].strip('"\'')
            break

    if not boundary:
        raise HTTPException(400, "Missing boundary in multipart/related request")

    # Parse multipart content
    metadata, file_content, mime_type = parse_multipart_related(body, boundary)
    display_name = metadata.get("file", {}).get("displayName", "unknown")

    file_id = f"files/{uuid.uuid4().hex[:12]}"

    stored_file = StoredFile(
        name=file_id,
        display_name=display_name,
        mime_type=mime_type,
        size_bytes=len(file_content),
        create_time=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    )
    cleanup_old_files()
    _files[file_id] = stored_file

    logger.info(f"Multipart upload: {file_id} ({stored_file.display_name}, {stored_file.size_bytes} bytes)")

    await asyncio.sleep(config.response_delay_ms / 1000)

    return {"file": make_file_response(stored_file)}


async def handle_direct_upload(request: Request, body: bytes, content_type: str):
    """Handle direct file upload (no metadata)."""
    file_id = f"files/{uuid.uuid4().hex[:12]}"

    stored_file = StoredFile(
        name=file_id,
        display_name="unknown",
        mime_type=content_type or "application/octet-stream",
        size_bytes=len(body),
        create_time=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    )
    cleanup_old_files()
    _files[file_id] = stored_file

    logger.info(f"Direct upload: {file_id} ({stored_file.size_bytes} bytes)")

    await asyncio.sleep(config.response_delay_ms / 1000)

    return {"file": make_file_response(stored_file)}


def parse_multipart_related(body: bytes, boundary: str) -> tuple[dict, bytes, str]:
    """
    Parse multipart/related body.

    Returns: (metadata_dict, file_content, mime_type)
    """
    boundary_bytes = boundary.encode() if isinstance(boundary, str) else boundary
    parts = body.split(b"--" + boundary_bytes)

    metadata = {}
    file_content = b""
    mime_type = "application/octet-stream"

    for part in parts:
        if not part or part.strip() in (b"", b"--"):
            continue

        # Split headers and body
        if b"\r\n\r\n" in part:
            headers_section, body_section = part.split(b"\r\n\r\n", 1)
        elif b"\n\n" in part:
            headers_section, body_section = part.split(b"\n\n", 1)
        else:
            continue

        headers_str = headers_section.decode("utf-8", errors="ignore")

        if "application/json" in headers_str.lower():
            try:
                json_body = body_section.rstrip()
                if json_body.endswith(b"--"):
                    json_body = json_body[:-2].rstrip()
                metadata = json.loads(json_body.decode("utf-8"))
            except json.JSONDecodeError:
                pass
        else:
            for line in headers_str.split("\n"):
                if line.lower().startswith("content-type:"):
                    mime_type = line.split(":", 1)[1].strip()
                    break

            file_content = body_section.rstrip()
            if file_content.endswith(b"--"):
                file_content = file_content[:-2].rstrip()

    return metadata, file_content, mime_type


@app.get("/v1beta/files/{file_id}")
async def get_file(request: Request, file_id: str):
    """
    Get file metadata.

    Mimics: GET https://generativelanguage.googleapis.com/v1beta/files/{name}
    """
    validate_api_key(request)
    full_name = f"files/{file_id}"
    if full_name not in _files:
        raise HTTPException(404, f"File not found: {full_name}")

    stored_file = _files[full_name]
    return make_file_response(stored_file)


@app.delete("/v1beta/files/{file_id}")
async def delete_file(request: Request, file_id: str):
    """
    Delete a file.

    Mimics: DELETE https://generativelanguage.googleapis.com/v1beta/files/{name}
    """
    validate_api_key(request)
    full_name = f"files/{file_id}"
    if full_name in _files:
        del _files[full_name]
        logger.info(f"Deleted file: {full_name}")
    return {}


# ============================================================================
# Gemini API - Generate Content
# ============================================================================

def extract_task_info_from_request(request_body: dict) -> tuple[int, str]:
    """
    Extract task number and key from the request contents.

    The prompt usually contains "Zadanie {number}" and task info.
    Returns (task_number, task_key) where task_key is like "2024_etap2_1".
    """
    contents = request_body.get("contents", [])

    # Look for task number in the text content
    task_number = 1
    year = "2024"
    etap = "etap2"

    for content in contents:
        if isinstance(content, str):
            text = content
        elif isinstance(content, dict):
            parts = content.get("parts", [])
            text = " ".join(
                p.get("text", "") if isinstance(p, dict) else str(p)
                for p in parts
            )
        else:
            continue

        # Extract task number
        task_match = re.search(r"Zadanie\s+(\d+)", text)
        if task_match:
            task_number = int(task_match.group(1))

        # Try to extract year/etap from file paths or context
        year_match = re.search(r"(20\d{2})", text)
        if year_match:
            year = year_match.group(1)

        etap_match = re.search(r"(etap[123])", text, re.IGNORECASE)
        if etap_match:
            etap = etap_match.group(1).lower()

    task_key = f"{year}_{etap}_{task_number}"
    return task_number, task_key


def get_scenario_for_request(request_body: dict) -> ScenarioType:
    """Determine which scenario to use based on request content."""
    task_number, task_key = extract_task_info_from_request(request_body)

    # Check for task-specific scenario
    if task_key in config.task_scenarios:
        scenario_str = config.task_scenarios[task_key]
        try:
            return ScenarioType(scenario_str)
        except ValueError:
            pass

    return config.default_scenario


@app.post("/v1beta/models/{model}:generateContent")
async def generate_content(model: str, request: Request):
    """
    Generate content (non-streaming).

    Mimics: POST https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent
    """
    # Validate API key (unless testing invalid key scenario)
    validate_api_key(request)

    body = await request.json()
    scenario = get_scenario_for_request(body)
    task_number, task_key = extract_task_info_from_request(body)

    logger.info(f"generateContent: model={model}, scenario={scenario.value}, task={task_key}")

    # Handle error scenarios
    if scenario == ScenarioType.ERROR_TIMEOUT:
        await asyncio.sleep(120)  # Long delay to trigger client timeout

    if scenario == ScenarioType.ERROR_QUOTA:
        raise HTTPException(429, {"error": {"message": "Quota exceeded", "status": "RESOURCE_EXHAUSTED"}})

    if scenario == ScenarioType.ERROR_SAFETY:
        return {
            "candidates": [{
                "finishReason": "SAFETY",
                "safetyRatings": [{"category": "HARM_CATEGORY_DANGEROUS", "probability": "HIGH"}]
            }]
        }

    if scenario == ScenarioType.ERROR_INVALID_KEY:
        raise HTTPException(401, {"error": {"message": "Invalid API key", "status": "UNAUTHENTICATED"}})

    if scenario == ScenarioType.SLOW_RESPONSE:
        await asyncio.sleep(config.slow_response_delay_ms / 1000)
    else:
        await asyncio.sleep(config.response_delay_ms / 1000)

    # Generate response
    response_json = get_response_json(scenario, task_number)
    response_text = json.dumps(response_json, ensure_ascii=False)

    return {
        "candidates": [{
            "content": {
                "parts": [
                    {"text": THINKING_TEMPLATE, "thought": True},
                    {"text": response_text}
                ],
                "role": "model"
            },
            "finishReason": "STOP"
        }],
        "usageMetadata": {
            "promptTokenCount": 5000,
            "candidatesTokenCount": 500,
            "totalTokenCount": 5500
        }
    }


@app.post("/v1beta/models/{model}:streamGenerateContent")
async def stream_generate_content(
    model: str,
    request: Request,
    alt: str = Query(default="sse"),
):
    """
    Generate content with streaming.

    Mimics: POST https://generativelanguage.googleapis.com/v1beta/models/{model}:streamGenerateContent
    """
    # Validate API key
    validate_api_key(request)

    body = await request.json()
    scenario = get_scenario_for_request(body)
    task_number, task_key = extract_task_info_from_request(body)

    logger.info(f"streamGenerateContent: model={model}, scenario={scenario.value}, task={task_key}")

    # Handle error scenarios
    if scenario == ScenarioType.ERROR_TIMEOUT:
        await asyncio.sleep(120)

    if scenario == ScenarioType.ERROR_QUOTA:
        raise HTTPException(429, {"error": {"message": "Quota exceeded", "status": "RESOURCE_EXHAUSTED"}})

    if scenario == ScenarioType.ERROR_INVALID_KEY:
        raise HTTPException(401, {"error": {"message": "Invalid API key", "status": "UNAUTHENTICATED"}})

    async def generate_chunks():
        chunk_delay = config.streaming_chunk_delay_ms / 1000

        if scenario == ScenarioType.SLOW_RESPONSE:
            await asyncio.sleep(config.slow_response_delay_ms / 1000)

        # Stream thinking in chunks
        thinking_chunks = THINKING_TEMPLATE.split("\n\n")
        for i, chunk in enumerate(thinking_chunks):
            await asyncio.sleep(chunk_delay)
            data = {
                "candidates": [{
                    "content": {
                        "parts": [{"text": chunk + "\n\n", "thought": True}],
                        "role": "model"
                    }
                }]
            }
            yield f"data: {json.dumps(data)}\n\n"

        # Handle safety error after thinking
        if scenario == ScenarioType.ERROR_SAFETY:
            data = {
                "candidates": [{
                    "finishReason": "SAFETY",
                    "safetyRatings": [{"category": "HARM_CATEGORY_DANGEROUS", "probability": "HIGH"}]
                }]
            }
            yield f"data: {json.dumps(data)}\n\n"
            return

        # Stream the response JSON
        response_json = get_response_json(scenario, task_number)
        response_text = json.dumps(response_json, ensure_ascii=False)

        # Split response into smaller chunks for realistic streaming
        chunk_size = 50
        for i in range(0, len(response_text), chunk_size):
            await asyncio.sleep(chunk_delay)
            chunk = response_text[i:i + chunk_size]
            data = {
                "candidates": [{
                    "content": {
                        "parts": [{"text": chunk}],
                        "role": "model"
                    }
                }]
            }
            yield f"data: {json.dumps(data)}\n\n"

        # Final chunk with usage metadata
        await asyncio.sleep(chunk_delay)
        final_data = {
            "candidates": [{
                "content": {
                    "parts": [],
                    "role": "model"
                },
                "finishReason": "STOP"
            }],
            "usageMetadata": {
                "promptTokenCount": 5000,
                "candidatesTokenCount": 500,
                "totalTokenCount": 5500
            }
        }
        yield f"data: {json.dumps(final_data)}\n\n"

    return StreamingResponse(
        generate_chunks(),
        media_type="text/event-stream",
    )


# ============================================================================
# Main
# ============================================================================

if __name__ == "__main__":
    import uvicorn

    port = int(os.environ.get("PORT", "8080"))
    logger.info(f"Starting Fake Gemini API server on port {port}")
    logger.info(f"Default scenario: {config.default_scenario.value}")

    uvicorn.run(app, host="0.0.0.0", port=port)
