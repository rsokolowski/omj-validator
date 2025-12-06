"""Shared response parsing utilities for AI providers."""

import json
import re

from ..models import SubmissionResult


# Valid OMJ scores
VALID_OMJ_SCORES = {0, 2, 5, 6}


def normalize_omj_score(score: int) -> int:
    """
    Normalize any score to valid OMJ scores (0, 2, 5, 6).

    Args:
        score: Raw score from AI provider

    Returns:
        Normalized score matching OMJ criteria
    """
    if score in VALID_OMJ_SCORES:
        return score
    if score <= 1:
        return 0
    elif score <= 3:
        return 2
    elif score <= 5:
        return 5
    else:
        return 6


def parse_ai_response(response_text: str, provider_name: str = "") -> SubmissionResult:
    """
    Parse AI response to extract score and feedback.

    This shared function handles JSON extraction from AI responses,
    supporting both {"score": X, "feedback": Y} and {"feedback": Y, "score": X}
    formats embedded in text.

    Args:
        response_text: Raw text response from AI provider
        provider_name: Optional provider name for error messages (e.g., "Gemini")

    Returns:
        SubmissionResult with score and feedback
    """
    try:
        # Try to find JSON in the response (score first)
        json_match = re.search(
            r'\{[^{}]*"score"[^{}]*"feedback"[^{}]*\}', response_text, re.DOTALL
        )
        if not json_match:
            # Try alternative pattern (feedback first)
            json_match = re.search(
                r'\{[^{}]*"feedback"[^{}]*"score"[^{}]*\}', response_text, re.DOTALL
            )

        if json_match:
            result_json = json.loads(json_match.group())
            score = int(result_json.get("score", 0))
            feedback = result_json.get("feedback", "Brak informacji zwrotnej.")

            # Normalize to valid OMJ score
            score = normalize_omj_score(score)

            return SubmissionResult(score=score, feedback=feedback)

        # Fallback: couldn't find JSON
        provider_suffix = f" {provider_name}" if provider_name else ""
        return SubmissionResult(
            score=0,
            feedback=f"Nie udało się przetworzyć odpowiedzi{provider_suffix}. Spróbuj ponownie.",
        )

    except json.JSONDecodeError:
        provider_suffix = f" {provider_name}" if provider_name else ""
        return SubmissionResult(
            score=0,
            feedback=f"Błąd parsowania odpowiedzi{provider_suffix}. Spróbuj ponownie.",
        )
    except Exception as e:
        provider_suffix = f" {provider_name}" if provider_name else ""
        return SubmissionResult(
            score=0,
            feedback=f"Błąd przetwarzania{provider_suffix}: {str(e)}",
        )
