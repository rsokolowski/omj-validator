"""
Skills data module for OMJ Validator.

Loads skills.json at module import time and provides
functions to look up skill information.
"""

import json
import logging
from pathlib import Path
from typing import Optional

from .config import settings
from .models import SkillInfo, SkillCategoryInfo

logger = logging.getLogger(__name__)

# Load skills data once at module import
_skills_data: dict = {"categories": {}, "skills": {}}

def _load_skills_file() -> dict:
    """Load skills.json file."""
    skills_file = settings.base_dir / "data" / "skills.json"

    if not skills_file.exists():
        logger.warning(f"Skills file not found: {skills_file}")
        return {"categories": {}, "skills": {}}

    try:
        with open(skills_file, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError) as e:
        logger.error(f"Failed to load skills file: {e}")
        return {"categories": {}, "skills": {}}

# Load at import time (restart server to pick up changes to skills.json)
_skills_data = _load_skills_file()


def get_skill(skill_id: str) -> Optional[SkillInfo]:
    """Get skill by ID.

    Args:
        skill_id: The skill identifier (e.g., "modular_arithmetic")

    Returns:
        SkillInfo object or None if not found
    """
    skill_data = _skills_data.get("skills", {}).get(skill_id)

    if not skill_data:
        return None

    # skill_data already contains 'id' field from skills.json
    return SkillInfo(**skill_data)


def get_skills_by_ids(skill_ids: list[str]) -> list[SkillInfo]:
    """Get list of skills by their IDs (batch lookup).

    Args:
        skill_ids: List of skill identifiers

    Returns:
        List of SkillInfo objects (missing skills are skipped with warning)
    """
    skills = []
    for skill_id in skill_ids:
        skill = get_skill(skill_id)
        if skill:
            skills.append(skill)
        else:
            logger.warning(f"Skill not found: {skill_id}")
    return skills


def get_skill_category(category_id: str) -> Optional[SkillCategoryInfo]:
    """Get skill category metadata.

    Args:
        category_id: The category identifier (e.g., "number_theory")

    Returns:
        SkillCategoryInfo object or None if not found
    """
    category_data = _skills_data.get("categories", {}).get(category_id)

    if not category_data:
        return None

    return SkillCategoryInfo(id=category_id, **category_data)


def get_all_skills() -> list[SkillInfo]:
    """Get all skills as a list.

    Returns:
        List of all SkillInfo objects
    """
    return [
        SkillInfo(**skill_data)
        for skill_data in _skills_data.get("skills", {}).values()
    ]


def get_skills_by_category(category_id: str) -> list[SkillInfo]:
    """Get all skills in a category.

    Args:
        category_id: The category identifier

    Returns:
        List of SkillInfo objects in that category
    """
    all_skills = get_all_skills()
    return [s for s in all_skills if s.category == category_id]
