"""Re-score past submissions with an alternative model and report cost.

Reuses the production providers (GeminiProvider / AnthropicProvider) through
analyze_solution_stream, so prompts, request building, parsing and thinking
config match exactly what prod does. Only the provider/model differs. Token
usage and estimated cost come from the result's scoring_meta, the same figures
prod stores.

Usage:
    GEMINI_API_KEY=... ./venv/bin/python scripts/rescore_eval.py \
        submissions.json out.json --model gemini-3.8-flash
    ANTHROPIC_API_KEY=... ANTHROPIC_PROCESSOR_APPROVED=true \
        ./venv/bin/python scripts/rescore_eval.py \
        submissions.json out.json --provider anthropic --model claude-haiku-5-5

The Anthropic arm sends student photos to Anthropic. It refuses to run unless
ANTHROPIC_PROCESSOR_APPROVED is true - see docs/model-ab-playbook.md.
"""

import argparse
import asyncio
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.ai.factory import build_provider  # noqa: E402
from app.ai.models_catalog import get_model, provider_approved  # noqa: E402
from app.config import settings  # noqa: E402
from app.storage import get_task_pdf_path, get_solution_pdf_path  # noqa: E402

USAGE_KEYS = ("input_tokens", "output_tokens", "thoughts_tokens",
              "cache_read_tokens", "cache_write_tokens")


def make_provider(provider: str, model: str):
    """The prod provider class for (provider, model).

    Gemini is built directly so any model id works (candidates are usually not
    in the admin catalog yet). Claude goes through the factory and must be a
    catalog model, otherwise the cost estimate would silently be 0.
    """
    if provider == "gemini":
        from app.ai.providers.gemini import GeminiProvider
        return GeminiProvider(model)
    if not provider_approved(provider):
        sys.exit(f"{provider} is not approved as a data processor "
                 f"(ANTHROPIC_PROCESSOR_APPROVED=false). The A/B sends student photos "
                 f"to the provider; get the sign-off first, see docs/model-ab-playbook.md.")
    if get_model(provider, model) is None:
        sys.exit(f"{provider}/{model} is not in app/ai/models_catalog.py CATALOG "
                 f"(no pricing). Add it there first.")
    return build_provider(provider, model)


def usage_from_meta(meta: dict) -> dict:
    """Token counts from scoring_meta, in the shape ab_compare.py reads.

    {} when the meta carries no token counts at all, so the row is reported
    as unpriced instead of costing $0.
    """
    usage = {k: meta.get(k, 0) or 0 for k in USAGE_KEYS}
    if not any(usage.values()):
        return {}
    usage["total_tokens"] = sum(usage.values())
    return usage


async def main(args):
    subs = json.loads(Path(args.submissions).read_text())
    provider = make_provider(args.provider, args.model)
    print(f"Provider {args.provider}, model {args.model}", flush=True)

    results = []
    for i, s in enumerate(subs, 1):
        year, etap, num = s["year"], s["etap"], int(s["task_number"])
        images = [settings.uploads_dir / p for p in s.get("images") or []]
        missing = [p for p in images if not p.exists()]
        if missing:
            print(f"[{i}/{len(subs)}] {s['id']}: SKIP, missing {missing}", flush=True)
            continue

        t0 = time.time()
        base = {"id": s["id"], "provider": args.provider, "model": args.model,
                "year": year, "etap": etap, "task_number": num,
                "prod_score": s.get("score"), "prod_issue_type": s.get("issue_type")}
        try:
            res = await provider.analyze_solution_stream(
                task_pdf_path=get_task_pdf_path(year, etap),
                solution_pdf_path=get_solution_pdf_path(year, etap),
                image_paths=images,
                task_number=num,
                etap=etap,
                on_thinking=None,
                solution_text=s.get("solution_text"),
            )
            meta = res.scoring_meta or {}
            row = {
                **base,
                "new_score": res.score,
                "new_issue_type": res.issue_type.value,
                "new_abuse_score": res.abuse_score,
                "new_feedback": res.feedback,
                "elapsed_s": round(time.time() - t0, 1),
                "usage": usage_from_meta(meta),
            }
            # No usage reported -> no estimate either (an estimate of 0 would read as free)
            row["estimated_cost"] = meta.get("estimated_cost") if row["usage"] else None
            if meta.get("served_by"):
                row["served_by"] = meta["served_by"]
        except Exception as e:  # keep going; one failure shouldn't kill the run
            row = {**base, "error": str(e)}

        results.append(row)
        print(f"[{i}/{len(subs)}] {s['id']} {year}/{etap}/z{num}: "
              f"prod={s.get('score')} new={row.get('new_score', 'ERR')} "
              f"({row.get('elapsed_s', '?')}s, {row.get('usage', {})}, "
              f"${row.get('estimated_cost')})", flush=True)
        Path(args.out).write_text(json.dumps(results, ensure_ascii=False, indent=2))

    print(f"\nWrote {len(results)} results to {args.out}")


def parse_args(argv=None):
    ap = argparse.ArgumentParser(description="Re-score sample submissions with one provider/model.")
    ap.add_argument("submissions", help="sample.json from scripts/ab_fetch_prod_sample.sh")
    ap.add_argument("out", help="result JSON to write (rewritten after every submission)")
    ap.add_argument("--provider", choices=("gemini", "anthropic"), default="gemini")
    ap.add_argument("--model", help="model id (default: GEMINI_MODEL for gemini; required for anthropic)")
    args = ap.parse_args(argv)
    if args.model is None:
        if args.provider != "gemini":
            ap.error("--model is required for --provider anthropic")
        args.model = settings.gemini_model
    return args


if __name__ == "__main__":
    asyncio.run(main(parse_args()))
