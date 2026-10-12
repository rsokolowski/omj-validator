"""scripts/rescore_eval.py and scripts/ab_compare.py: approval gate and cost bookkeeping."""

import asyncio
import importlib.util
import json
from pathlib import Path

import pytest

from app.config import settings
from app.models import SubmissionResult

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"


def load(name):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


rescore_eval = load("rescore_eval")
ab_compare = load("ab_compare")


def test_rescore_refuses_anthropic_without_processor_approval(monkeypatch):
    monkeypatch.setattr(settings, "anthropic_api_key", "sk-test-not-a-key")
    monkeypatch.setattr(settings, "anthropic_processor_approved", False)
    built = []
    monkeypatch.setattr(rescore_eval, "build_provider", lambda *a: built.append(a))

    with pytest.raises(SystemExit) as info:
        rescore_eval.make_provider("anthropic", "claude-haiku-5-5")

    assert "ANTHROPIC_PROCESSOR_APPROVED=false" in str(info.value)
    assert built == []


def test_usage_from_meta_without_tokens_is_empty():
    assert rescore_eval.usage_from_meta({}) == {}
    assert rescore_eval.usage_from_meta({"input_tokens": 0, "output_tokens": None}) == {}
    usage = rescore_eval.usage_from_meta({"input_tokens": 10, "output_tokens": 5})
    assert usage["total_tokens"] == 15 and usage["cache_read_tokens"] == 0


class _NoUsageProvider:
    async def analyze_solution_stream(self, **kwargs):
        return SubmissionResult(score=2, feedback="f", scoring_meta={"estimated_cost": 0.0})


def test_rescore_row_without_usage_is_unpriced(monkeypatch, tmp_path):
    subs = tmp_path / "subs.json"
    subs.write_text(json.dumps([{"id": "s1", "year": "2024", "etap": "etap1", "task_number": 1, "score": 2}]))
    out = tmp_path / "out.json"
    monkeypatch.setattr(rescore_eval, "make_provider", lambda provider, model: _NoUsageProvider())
    monkeypatch.setattr(rescore_eval, "get_task_pdf_path", lambda year, etap: tmp_path / "t.pdf")
    monkeypatch.setattr(rescore_eval, "get_solution_pdf_path", lambda year, etap: None)

    asyncio.run(rescore_eval.main(rescore_eval.parse_args([str(subs), str(out), "--model", "gemini-2.5-pro"])))

    [row] = json.loads(out.read_text())
    assert row["usage"] == {} and row["estimated_cost"] is None
    assert ab_compare.cost_usd("gemini-2.5-pro", row) is None  # unpriced, not $0


def test_ab_compare_prices_old_format_row_from_usage():
    """Rows written before rescore_eval recorded provider/estimated_cost: Gemini, priced from usage."""
    row = {"id": "s1", "model": "gemini-2.5-pro", "usage": {"input_tokens": 1_000_000, "output_tokens": 100_000}}

    assert ab_compare.row_provider(row) == "gemini"
    assert ab_compare.cost_usd("gemini-2.5-pro", row) == pytest.approx(1.25 + 1.00)
    assert ab_compare.cost_usd("gemini-unknown", {"usage": row["usage"]}) is None
