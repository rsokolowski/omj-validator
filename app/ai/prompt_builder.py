"""Prompt construction for AI providers with abuse detection.

This module provides a clean API for building complete prompts by combining:
- Base prompt (role and language instructions)
- Etap-specific scoring criteria
- Abuse detection instructions and JSON format

Usage:
    from app.ai.prompt_builder import build_prompt

    prompt = build_prompt("etap2")  # Returns complete prompt for etap2
"""

import logging
from functools import lru_cache
from pathlib import Path

from ..config import settings

logger = logging.getLogger(__name__)

# Prompt file names
BASE_PROMPT_FILE = "gemini_prompt_base.txt"
ABUSE_PROMPT_FILE = "gemini_prompt_abuse.txt"
SCORING_PROMPT_FILES = {
    "etap1": "gemini_prompt_scoring_etap1.txt",
    "etap2": "gemini_prompt_scoring_etap2.txt",
    "etap3": "gemini_prompt_scoring_etap3.txt",
}


@lru_cache(maxsize=10)
def _load_prompt_file(file_path: Path) -> str:
    """Load a prompt file with caching.

    Args:
        file_path: Absolute path to the prompt file

    Returns:
        Contents of the prompt file

    Raises:
        FileNotFoundError: If the file doesn't exist
    """
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return f.read().strip()
    except FileNotFoundError:
        logger.error(f"Prompt file not found: {file_path}")
        raise
    except Exception as e:
        logger.error(f"Error loading prompt file {file_path}: {e}")
        raise


def build_prompt(etap: str = "etap2") -> str:
    """
    Build complete prompt for given etap with abuse detection.

    The prompt is assembled from three components:
    1. Base instructions (role, language)
    2. Etap-specific scoring criteria
    3. Abuse detection instructions and JSON format

    Args:
        etap: Competition stage ("etap1", "etap2", or "etap3")

    Returns:
        Complete prompt text ready for AI provider

    Raises:
        ValueError: If etap is not valid
        FileNotFoundError: If any prompt file is missing
    """
    if etap not in SCORING_PROMPT_FILES:
        logger.warning(f"Unknown etap '{etap}', defaulting to etap2")
        etap = "etap2"

    prompts_dir = settings.prompts_dir

    # Load components
    base = _load_prompt_file(prompts_dir / BASE_PROMPT_FILE)
    scoring = _load_prompt_file(prompts_dir / SCORING_PROMPT_FILES[etap])
    abuse = _load_prompt_file(prompts_dir / ABUSE_PROMPT_FILE)

    # Combine in order: base → scoring → abuse (includes JSON format)
    return f"{base}\n\n{scoring}\n\n{abuse}"


def validate_prompts() -> list[str]:
    """
    Validate all prompt files exist and are readable.

    Useful for startup checks or health endpoints.

    Returns:
        List of error messages (empty if all valid)
    """
    errors = []
    prompts_dir = settings.prompts_dir

    # Check base prompt
    base_path = prompts_dir / BASE_PROMPT_FILE
    if not base_path.exists():
        errors.append(f"Base prompt not found: {base_path}")
    elif not base_path.is_file():
        errors.append(f"Base prompt is not a file: {base_path}")

    # Check abuse prompt
    abuse_path = prompts_dir / ABUSE_PROMPT_FILE
    if not abuse_path.exists():
        errors.append(f"Abuse prompt not found: {abuse_path}")
    elif not abuse_path.is_file():
        errors.append(f"Abuse prompt is not a file: {abuse_path}")

    # Check scoring prompts for all etaps
    for etap, filename in SCORING_PROMPT_FILES.items():
        scoring_path = prompts_dir / filename
        if not scoring_path.exists():
            errors.append(f"Scoring prompt for {etap} not found: {scoring_path}")
        elif not scoring_path.is_file():
            errors.append(f"Scoring prompt for {etap} is not a file: {scoring_path}")

    return errors


def clear_cache() -> None:
    """Clear the prompt file cache.

    Useful for testing or after prompt file updates.
    """
    _load_prompt_file.cache_clear()
