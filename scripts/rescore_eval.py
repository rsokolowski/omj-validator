"""Re-score past submissions with an alternative Gemini model and report cost.

Reuses the production GeminiProvider so prompts, file uploads, media resolution
and thinking config match exactly what prod does. Only the model differs.

Usage:
    GEMINI_API_KEY=... GEMINI_MODEL=gemini-3.6-flash \
        ./venv/bin/python scripts/rescore_eval.py submissions.json out.json
"""

import asyncio
import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.ai.providers.gemini import GeminiProvider  # noqa: E402
from app.storage import get_task_pdf_path, get_solution_pdf_path  # noqa: E402
from app.config import settings  # noqa: E402


def _usage(resp):
    """Pull token counts off a GenerateContentResponse, tolerating missing fields."""
    um = getattr(resp, "usage_metadata", None)
    if not um:
        return {}
    return {
        "input_tokens": getattr(um, "prompt_token_count", 0) or 0,
        "output_tokens": getattr(um, "candidates_token_count", 0) or 0,
        "thoughts_tokens": getattr(um, "thoughts_token_count", 0) or 0,
        "total_tokens": getattr(um, "total_token_count", 0) or 0,
    }


async def main(subs_path: str, out_path: str):
    subs = json.loads(Path(subs_path).read_text())
    provider = GeminiProvider()

    # Wrap generate_content so we can record real token usage per call.
    captured = []
    real_generate = provider._client.models.generate_content

    def recording_generate(*args, **kwargs):
        resp = real_generate(*args, **kwargs)
        captured.append(_usage(resp))
        return resp

    provider._client.models.generate_content = recording_generate

    results = []
    for i, s in enumerate(subs, 1):
        year, etap, num = s["year"], s["etap"], int(s["task_number"])
        images = [settings.uploads_dir / p for p in s["images"]]
        missing = [p for p in images if not p.exists()]
        if missing:
            print(f"[{i}/{len(subs)}] {s['id']}: SKIP, missing {missing}", flush=True)
            continue

        captured.clear()
        t0 = time.time()
        try:
            res = await provider.analyze_solution(
                task_pdf_path=get_task_pdf_path(year, etap),
                solution_pdf_path=get_solution_pdf_path(year, etap),
                image_paths=images,
                task_number=num,
                etap=etap,
            )
            row = {
                "id": s["id"],
                "year": year, "etap": etap, "task_number": num,
                "prod_score": s["score"],
                "prod_issue_type": s["issue_type"],
                "new_score": res.score,
                "new_issue_type": res.issue_type.value,
                "new_abuse_score": res.abuse_score,
                "new_feedback": res.feedback,
                "elapsed_s": round(time.time() - t0, 1),
                "usage": captured[-1] if captured else {},
            }
        except Exception as e:  # keep going; one failure shouldn't kill the run
            row = {"id": s["id"], "year": year, "etap": etap,
                   "task_number": num, "prod_score": s["score"], "error": str(e)}

        results.append(row)
        print(f"[{i}/{len(subs)}] {s['id']} {year}/{etap}/z{num}: "
              f"prod={s['score']} new={row.get('new_score', 'ERR')} "
              f"({row.get('elapsed_s', '?')}s, {row.get('usage', {})})", flush=True)
        Path(out_path).write_text(json.dumps(results, ensure_ascii=False, indent=2))

    print(f"\nWrote {len(results)} results to {out_path}")


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1], sys.argv[2]))
