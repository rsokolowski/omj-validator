"""Shared scoring constants and helpers."""


def get_max_score(etap: str) -> int:
    """Get max score for an etap (3 for etap1, 6 for etap2/3)."""
    return 3 if etap == "etap1" else 6
