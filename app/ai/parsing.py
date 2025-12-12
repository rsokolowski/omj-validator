"""Shared response parsing utilities for AI providers."""

import json
import logging
import re
from typing import Optional

from ..models import SubmissionResult, IssueType

logger = logging.getLogger(__name__)

# Valid OMJ scores by etap
VALID_SCORES_ETAP1 = {0, 1, 3}  # Etap 1: 0, 1, 3 points
VALID_SCORES_ETAP2 = {0, 2, 5, 6}  # Etap 2: 0, 2, 5, 6 points
VALID_SCORES_ETAP3 = {0, 2, 5, 6}  # Etap 3 (finał): 0, 2, 5, 6 points (same as etap2)

# User-friendly feedback for detected issues
WRONG_TASK_FEEDBACK = (
    "Uwaga: Przesłane rozwiązanie prawdopodobnie nie dotyczy tego zadania. "
    "Sprawdź numer zadania i prześlij poprawne rozwiązanie."
)

# Bland feedback for injection attempts (don't reveal detection)
INJECTION_FEEDBACK = (
    "Nie udało się przeanalizować rozwiązania. "
    "Upewnij się, że zdjęcia zawierają wyraźne rozwiązanie zadania matematycznego."
)


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


def _extract_json_from_text(text: str) -> Optional[dict]:
    """
    Extract JSON object from AI response text.

    Uses multiple strategies to find valid JSON:
    1. Direct parse (for clean JSON-only responses)
    2. Markdown code block extraction (```json ... ```)
    3. Find JSON object with balanced braces containing "score"
    4. Fallback regex patterns

    Args:
        text: Raw AI response text

    Returns:
        Parsed JSON dict, or None if no valid JSON found
    """
    text_stripped = text.strip()

    # Strategy 1: Try direct JSON parse (for clean responses)
    if text_stripped.startswith("{"):
        try:
            return json.loads(text_stripped)
        except json.JSONDecodeError:
            pass

    # Strategy 2: Extract from markdown code blocks
    # Handles: ```json {...} ``` or ``` {...} ```
    code_block_patterns = [
        r'```json\s*(\{[\s\S]*?\})\s*```',  # ```json {...} ```
        r'```\s*(\{[\s\S]*?\})\s*```',       # ``` {...} ```
    ]
    for pattern in code_block_patterns:
        match = re.search(pattern, text)
        if match:
            try:
                return json.loads(match.group(1))
            except json.JSONDecodeError:
                continue

    # Strategy 3: Find balanced JSON object containing "score"
    # This handles nested objects like {"score": 5, "feedback": "text with {braces}"}
    def find_balanced_json(s: str) -> Optional[str]:
        """Find a balanced JSON object starting from first { and containing 'score'."""
        start_idx = s.find('{')
        while start_idx != -1:
            depth = 0
            in_string = False
            escape_next = False
            end_idx = start_idx

            for i in range(start_idx, len(s)):
                char = s[i]

                if escape_next:
                    escape_next = False
                    continue

                if char == '\\' and in_string:
                    escape_next = True
                    continue

                if char == '"' and not escape_next:
                    in_string = not in_string
                    continue

                if not in_string:
                    if char == '{':
                        depth += 1
                    elif char == '}':
                        depth -= 1
                        if depth == 0:
                            end_idx = i
                            candidate = s[start_idx:end_idx + 1]
                            # Check for "score" as a key (followed by colon)
                            if '"score"' in candidate and '"score":' in candidate.replace(' ', '').replace('\n', ''):
                                return candidate
                            break

            # Try next { if this one didn't work
            next_start = s.find('{', start_idx + 1)
            if next_start == -1:
                break
            start_idx = next_start

        return None

    balanced_json = find_balanced_json(text)
    if balanced_json:
        try:
            return json.loads(balanced_json)
        except json.JSONDecodeError:
            pass

    # Strategy 4: Simple regex fallback for flat JSON (no nested braces)
    patterns = [
        r'\{[^{}]*"score"\s*:\s*\d+[^{}]*\}',
    ]

    for pattern in patterns:
        match = re.search(pattern, text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                continue

    # Log a snippet of the response for debugging
    logger.debug(f"Failed to extract JSON from response (first 500 chars): {text[:500]}")

    return None


def parse_ai_response(
    response_text: str, provider_name: str = "", etap: str = "etap2"
) -> SubmissionResult:
    """
    Parse AI response to extract score, feedback, and abuse detection.

    This shared function handles JSON extraction from AI responses,
    supporting the extended format with abuse detection fields.

    Expected JSON format:
    {
        "score": <int>,
        "feedback": "<string>",
        "issue_type": "none"|"wrong_task"|"injection",  # Optional
        "abuse_score": <int 0-100>  # Optional
    }

    Args:
        response_text: Raw text response from AI provider
        provider_name: Optional provider name for error messages (e.g., "Gemini")
        etap: Competition stage for score normalization ("etap1", "etap2", or "etap3")

    Returns:
        SubmissionResult with score, feedback, and abuse detection fields
    """
    try:
        result_json = _extract_json_from_text(response_text)

        if not result_json:
            # Log more details for debugging
            response_preview = response_text[:500] if len(response_text) > 500 else response_text
            logger.warning(
                f"No JSON found in {provider_name} response. "
                f"Response length: {len(response_text)}, "
                f"Preview: {response_preview!r}"
            )
            provider_suffix = f" {provider_name}" if provider_name else ""
            return SubmissionResult(
                score=0,
                feedback=f"Nie udało się przetworzyć odpowiedzi{provider_suffix}. Spróbuj ponownie.",
                issue_type=IssueType.NONE,
                abuse_score=0,
            )

        # Extract basic fields
        score = int(result_json.get("score", 0))
        feedback = result_json.get("feedback", "Brak informacji zwrotnej.")

        # Parse abuse detection fields (optional, defaults for backward compatibility)
        issue_type_str = result_json.get("issue_type", "none")
        try:
            abuse_score = int(result_json.get("abuse_score", 0) or 0)
        except (ValueError, TypeError):
            logger.warning(f"Invalid abuse_score value, defaulting to 0")
            abuse_score = 0

        # Validate and convert issue_type
        try:
            issue_type = IssueType(issue_type_str)
        except ValueError:
            logger.warning(f"Invalid issue_type '{issue_type_str}', defaulting to none")
            issue_type = IssueType.NONE

        # Clamp abuse_score to 0-100
        abuse_score = max(0, min(100, abuse_score))

        # Handle detected issues with appropriate feedback
        if issue_type == IssueType.WRONG_TASK:
            # Helpful feedback for wrong task (honest mistake)
            feedback = WRONG_TASK_FEEDBACK
            score = 0
            logger.info(f"Wrong task detected (confidence: {abuse_score}%)")

        elif issue_type == IssueType.INJECTION:
            # Bland feedback for injection (don't reveal detection)
            feedback = INJECTION_FEEDBACK
            score = 0
            logger.warning(f"Injection attempt detected (confidence: {abuse_score}%)")

        else:
            # Normal submission - normalize score to valid OMJ values
            score = normalize_omj_score(score, etap)

        return SubmissionResult(
            score=score,
            feedback=feedback,
            issue_type=issue_type,
            abuse_score=abuse_score,
        )

    except json.JSONDecodeError as e:
        logger.error(f"JSON decode error in {provider_name} response: {e}")
        provider_suffix = f" {provider_name}" if provider_name else ""
        return SubmissionResult(
            score=0,
            feedback=f"Błąd parsowania odpowiedzi{provider_suffix}. Spróbuj ponownie.",
            issue_type=IssueType.NONE,
            abuse_score=0,
        )
    except Exception as e:
        logger.error(f"Unexpected error parsing {provider_name} response: {e}")
        provider_suffix = f" {provider_name}" if provider_name else ""
        return SubmissionResult(
            score=0,
            feedback=f"Błąd przetwarzania{provider_suffix}: {str(e)}",
            issue_type=IssueType.NONE,
            abuse_score=0,
        )
