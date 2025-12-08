"""Shared response parsing utilities for AI providers."""

import json
import re

from ..models import SubmissionResult


# Valid OMJ scores by etap
VALID_SCORES_ETAP1 = {0, 1, 3}  # Etap 1: 0, 1, 3 points
VALID_SCORES_ETAP2 = {0, 2, 5, 6}  # Etap 2: 0, 2, 5, 6 points
VALID_SCORES_ETAP3 = {0, 2, 5, 6}  # Etap 3 (finał): 0, 2, 5, 6 points (same as etap2)


def normalize_omj_score(score: int, etap: str = "etap2") -> int:
    """
    Normalize any score to valid OMJ scores for the given etap.

    Etap 1: 0, 1, 3 points
    Etap 2/3: 0, 2, 5, 6 points

    Args:
        score: Raw score from AI provider
        etap: Competition stage ("etap1", "etap2", or "etap3")

    Returns:
        Normalized score matching OMJ criteria for the etap
    """
    if etap == "etap1":
        valid_scores = VALID_SCORES_ETAP1
        if score in valid_scores:
            return score
        # Normalize to etap1 scale (0, 1, 3)
        if score <= 0:
            return 0
        elif score <= 2:
            return 1
        else:
            return 3
    else:
        valid_scores = VALID_SCORES_ETAP2
        if score in valid_scores:
            return score
        # Normalize to etap2 scale (0, 2, 5, 6)
        if score <= 1:
            return 0
        elif score <= 3:
            return 2
        elif score <= 5:
            return 5
        else:
            return 6


def parse_ai_response(
    response_text: str, provider_name: str = "", etap: str = "etap2"
) -> SubmissionResult:
    """
    Parse AI response to extract score and feedback.

    This shared function handles JSON extraction from AI responses,
    supporting both {"score": X, "feedback": Y} and {"feedback": Y, "score": X}
    formats embedded in text.

    Args:
        response_text: Raw text response from AI provider
        provider_name: Optional provider name for error messages (e.g., "Gemini")
        etap: Competition stage for score normalization ("etap1", "etap2", or "etap3")

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

            # Normalize to valid OMJ score for the etap
            score = normalize_omj_score(score, etap)

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
