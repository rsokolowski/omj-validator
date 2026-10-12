"""Compare rescore_eval.py result files from several models and write a report.

Usage:
    ./venv/bin/python scripts/ab_compare.py OUT.md \
        --result gemini-3.8-flash=results_gemini-3.8-flash.json \
        --result claude-haiku-5-5=results_claude-haiku-5-5.json \
        [--human human_review.json]

Each arm is labelled provider/LABEL in the report; the provider is read from
the result rows ("gemini" for files written before rows carried a provider).
A LABEL that already contains "/" is used as is.

The optional human review file is a JSON object keyed by submission id:
    {"ffa34843": {"score": 1, "note": "sign error after the expansion"}, ...}
It is the ground truth the report measures every model against. Without it
the report still shows the scores side by side, cost and latency, but no
accuracy numbers - the prod score is NOT ground truth (it came from whatever
model was deployed at the time).

Cost, for both providers, is the row's estimated_cost (what the provider put
in scoring_meta, the figure prod stores) when present. Rows without it (result
files written before rows carried a cost) are priced from their usage with
app.ai.models_catalog.estimate_cost - Gemini through GEMINI_PRICING (promo
pricing and long-context tiers applied the same way prod logs them), Claude at
the catalog rates including cache reads/writes. A row with no usage, or for a
model missing from both tables, is reported as unpriced, never as $0.
"""

import argparse
import json
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.ai.parsing import score_ladder  # noqa: E402
from app.ai.models_catalog import estimate_cost, get_model  # noqa: E402
from app.ai.providers.gemini import GEMINI_PRICING  # noqa: E402


def row_provider(row: dict) -> str:
    return row.get("provider") or "gemini"


def pricing_model(label: str, row: dict) -> str | None:
    """Model to price a row at: the name rescore_eval.py recorded, else the CLI
    label. None when the pricing tables have no entry, so the report shows a
    gap rather than a silently wrong fallback rate."""
    model = row.get("model") or label
    if row_provider(row) == "gemini":
        return model if model in GEMINI_PRICING else None
    return model if get_model(row_provider(row), model) else None


def cost_usd(label: str, row: dict) -> float | None:
    """Same estimate prod logs. None when the model or the usage is unknown."""
    model = pricing_model(label, row)
    if model is None:
        return None  # a stored estimate for an unpriced model used fallback rates
    if row.get("estimated_cost") is not None:
        return row["estimated_cost"]
    usage = row.get("usage")
    if not usage:
        return None
    return estimate_cost(row_provider(row), model, usage.get("input_tokens", 0),
                         usage.get("output_tokens", 0), usage.get("thoughts_tokens", 0),
                         usage.get("cache_read_tokens", 0), usage.get("cache_write_tokens", 0))


def arm_label(label: str, result_rows: list) -> str:
    """provider/label, the provider taken from the file's rows."""
    if "/" in label:
        return label
    provider = row_provider(result_rows[0]) if result_rows else "gemini"
    return f"{provider}/{label}"


def fmt(x, nd=2):
    return "-" if x is None else f"{x:.{nd}f}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("out")
    ap.add_argument("--result", action="append", required=True,
                    metavar="LABEL=FILE")
    ap.add_argument("--human", help="JSON of {id: {score, note}}")
    args = ap.parse_args()

    models = []
    rows = {}  # id -> {model: row}
    for spec in args.result:
        label, path = spec.split("=", 1)
        result_rows = json.loads(Path(path).read_text())
        model = arm_label(label, result_rows)
        if model in models:
            sys.exit(f"duplicate arm {model}: give each --result a distinct label")
        models.append(model)
        for r in result_rows:
            r.setdefault("_label", label)
            rows.setdefault(r["id"], {})[model] = r
    human = json.loads(Path(args.human).read_text()) if args.human else {}
    for hid in set(human) - set(rows):
        print(f"WARNING: human review id {hid} matches no result row, ignored", file=sys.stderr)
    for hid, h in human.items():
        if hid not in rows or h.get("score") is None:
            continue
        etap = next(iter(rows[hid].values()))["etap"]
        try:
            h["score"] = int(h["score"])
        except (TypeError, ValueError):
            sys.exit(f"human review {hid}: score {h['score']!r} is not an integer")
        if h["score"] not in score_ladder(etap):
            sys.exit(f"human review {hid}: score {h['score']} is not valid for {etap} "
                     f"(allowed {score_ladder(etap)})")

    ids = sorted(rows, key=lambda i: (
        next(iter(rows[i].values()))["etap"],
        next(iter(rows[i].values()))["year"],
        next(iter(rows[i].values()))["task_number"]))

    lines = [f"# Model A/B report: {' vs '.join(models)}", ""]

    # Per-submission score table
    hdr = ["id", "task", "prod"] + models + (["human"] if human else [])
    lines += ["## Scores", "", "| " + " | ".join(hdr) + " |",
              "|" + "---|" * len(hdr)]
    for i in ids:
        any_row = next(iter(rows[i].values()))
        cells = [i, f"{any_row['year']}/{any_row['etap']}/z{any_row['task_number']}",
                 str(any_row.get("prod_score"))]
        for m in models:
            r = rows[i].get(m)
            if not r:
                cells.append("missing")
            elif "error" in r:
                cells.append("ERR")
            else:
                s = str(r["new_score"])
                if r.get("new_issue_type") not in (None, "none"):
                    s += f" ({r['new_issue_type']})"
                cells.append(s)
        if human:
            h = human.get(i, {})
            cells.append(str(h.get("score", "?")))
        lines.append("| " + " | ".join(cells) + " |")
    lines.append("")

    # Accuracy vs human
    if human:
        lines += ["## Agreement with human review", "",
                  "| model | exact | within 1 step | MAE | over | under |",
                  "|---|---|---|---|---|---|"]
        for m in models:
            pairs = [(rows[i][m]["new_score"], human[i]["score"])
                     for i in ids if m in rows[i] and "new_score" in rows[i][m]
                     and i in human and human[i].get("score") is not None]
            if not pairs:
                continue
            n = len(pairs)
            exact = sum(a == b for a, b in pairs)
            mae = sum(abs(a - b) for a, b in pairs) / n
            over = sum(a > b for a, b in pairs)
            under = sum(a < b for a, b in pairs)
            # "within 1 step" on the OMJ ladder for that etap
            def step(etap_row, s):
                ladder = score_ladder(etap_row["etap"])
                return ladder.index(s) if s in ladder else -99
            within = sum(abs(step(rows[i][m], rows[i][m]["new_score"])
                             - step(rows[i][m], human[i]["score"])) <= 1
                         for i in ids if m in rows[i] and "new_score" in rows[i][m]
                         and i in human and human[i].get("score") is not None)
            lines.append(f"| {m} | {exact}/{n} | {within}/{n} | {mae:.2f} | {over} | {under} |")
        lines.append("")

    # Cost / latency
    lines += ["## Cost and latency (per submission)", "",
              "| model | calls | median s | max s | median thoughts tok | max thoughts tok | mean cost USD | total cost USD |",
              "|---|---|---|---|---|---|---|---|"]
    for m in models:
        rs = [rows[i][m] for i in ids if m in rows[i] and "usage" in rows[i][m]]
        if not rs:
            continue
        el = [r["elapsed_s"] for r in rs]
        th = [r["usage"].get("thoughts_tokens", 0) for r in rs]
        costs = [cost_usd(r["_label"], r) for r in rs]
        unpriced = sum(c is None for c in costs)
        costs = [c for c in costs if c is not None]
        if unpriced:
            print(f"WARNING: {m}: {unpriced} call(s) not priced (model missing from "
                  f"GEMINI_PRICING / models_catalog or no usage metadata)", file=sys.stderr)
        lines.append(
            f"| {m} | {len(rs)} | {statistics.median(el):.1f} | {max(el):.1f} | "
            f"{int(statistics.median(th))} | {max(th)} | "
            f"{fmt(statistics.mean(costs) if costs else None, 4)} | "
            f"{fmt(sum(costs) if costs else None, 3)} |")
    errs = [(i, m) for i in ids for m in models if m in rows[i] and "error" in rows[i][m]]
    if errs:
        lines += ["", "Errors: " + ", ".join(f"{i}/{m}" for i, m in errs)]
    lines.append("")

    # Feedback side by side for manual validation
    lines += ["## Feedback side by side", ""]
    for i in ids:
        any_row = next(iter(rows[i].values()))
        lines.append(f"### {i} - {any_row['year']}/{any_row['etap']}/z{any_row['task_number']} "
                     f"(prod {any_row.get('prod_score')})")
        if i in human:
            lines.append(f"**Human:** {human[i].get('score')} - {human[i].get('note', '')}")
            lines.append("")
        for m in models:
            r = rows[i].get(m)
            if not r:
                continue
            if "error" in r:
                lines += [f"**{m}:** ERROR {r['error']}", ""]
                continue
            lines += [f"**{m}:** score {r['new_score']}, issue {r.get('new_issue_type')}, "
                      f"abuse {r.get('new_abuse_score')}, {r['elapsed_s']}s, "
                      f"thoughts {r['usage'].get('thoughts_tokens', 0)}", "",
                      "> " + (r.get("new_feedback") or "").replace("\n", "\n> "), ""]
    Path(args.out).write_text("\n".join(lines))
    print(f"Wrote {args.out}")


if __name__ == "__main__":
    main()
