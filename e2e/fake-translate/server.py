"""
Fake Google Cloud Translation API Server for E2E Testing.

Mimics the Google Cloud Translation API v2 (Basic) REST endpoint.
Provides deterministic translations for known status phrases used in the application.

Endpoints implemented:
- POST /language/translate/v2
- GET /health
"""

import logging
import os
from typing import Optional

from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Fake Translation API v2", version="1.0.0")


# ============================================================================
# Translation Dictionary
# ============================================================================

# Known status message translations (English -> Polish)
# These match the headings extracted from Gemini's thinking output
#
# NOTE: This is a module-level mutable dict. In a multi-worker setup, mutations
# via /config/add-translation would not be shared between workers. This is
# acceptable for e2e testing which uses a single uvicorn worker.
TRANSLATIONS = {
    # AI thinking headings (from fake-gemini THINKING_TEMPLATE)
    "Understanding the Problem": "Rozumienie problemu",
    "Analyzing the Student's Solution": "Analiza rozwiązania ucznia",
    "Checking Mathematical Correctness": "Sprawdzanie poprawności matematycznej",
    "Evaluating Completeness": "Ocena kompletności",
    "Determining the Score": "Wyznaczanie wyniku",
    # Additional common headings that might appear
    "Reading the Problem": "Czytanie zadania",
    "Examining the Solution": "Badanie rozwiązania",
    "Verifying Calculations": "Weryfikacja obliczeń",
    "Checking for Errors": "Szukanie błędów",
    "Final Assessment": "Końcowa ocena",
    "Scoring": "Punktacja",
    "Summary": "Podsumowanie",
    # Pass-through for already Polish messages
    "Przesyłam pliki...": "Przesyłam pliki...",
    "Analizuję rozwiązanie...": "Analizuję rozwiązanie...",
    "Finalizowanie...": "Finalizowanie...",
}


# ============================================================================
# Endpoints
# ============================================================================


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "healthy", "service": "fake-translate-v2"}


@app.post("/language/translate/v2")
async def translate_text(request: Request):
    """
    Translate text from source language to target language.

    Mimics: POST https://translation.googleapis.com/language/translate/v2

    Request body:
    {
        "q": "text to translate",
        "source": "en",
        "target": "pl",
        "format": "text"
    }

    Response format (v2 style):
    {
        "data": {
            "translations": [
                {"translatedText": "translated text"}
            ]
        }
    }
    """
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(400, {"error": {"message": "Invalid JSON body"}})

    # Support both single string and list of strings
    q = body.get("q")
    if q is None:
        raise HTTPException(
            400, {"error": {"message": "'q' field is required"}}
        )

    # Normalize to list
    texts = [q] if isinstance(q, str) else q
    source_lang = body.get("source", "en")
    target_lang = body.get("target", "pl")

    logger.info(
        f"Translating {len(texts)} text(s): {source_lang} -> {target_lang}"
    )

    # Translate each text
    translations = []
    for text in texts:
        # Use dictionary lookup for known phrases
        if text in TRANSLATIONS:
            translated = TRANSLATIONS[text]
            logger.debug(f"  Known phrase: '{text}' -> '{translated}'")
        else:
            # For unknown text, return original (simulates fallback behavior)
            translated = text
            logger.debug(f"  Unknown phrase (passthrough): '{text}'")

        translations.append({"translatedText": translated})

    # Return v2 response format
    return {
        "data": {
            "translations": translations
        }
    }


# ============================================================================
# Configuration Endpoint (for test control)
# ============================================================================


@app.post("/config/add-translation")
async def add_translation(request: Request):
    """
    Add a custom translation for testing.

    Body: {"source": "English text", "target": "Polish text"}
    """
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(400, {"error": {"message": "Invalid JSON body"}})

    source = body.get("source")
    target = body.get("target")

    if not source or not target:
        raise HTTPException(
            400, {"error": {"message": "Both 'source' and 'target' are required"}}
        )

    TRANSLATIONS[source] = target
    logger.info(f"Added translation: '{source}' -> '{target}'")

    return {"status": "ok", "translations_count": len(TRANSLATIONS)}


@app.get("/config/translations")
async def get_translations():
    """Get all registered translations (for debugging)."""
    return {"translations": TRANSLATIONS}


# ============================================================================
# Main
# ============================================================================

if __name__ == "__main__":
    import uvicorn

    port = int(os.environ.get("PORT", "8081"))
    logger.info(f"Starting Fake Translation API v2 server on port {port}")
    uvicorn.run(app, host="0.0.0.0", port=port)
