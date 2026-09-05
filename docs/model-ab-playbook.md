# Playbook: A/B testing a new scoring model

Use this whenever Google ships a new Gemini model and the question is "should
prod switch?". The whole thing takes about an hour of wall clock for a
10-submission sample, most of it waiting on the API and reading photos.

The short version:

1. Pull a stratified sample of real submissions from prod (rows + photos).
2. Rescore the sample with the current prod model AND the candidate, using the
   prod prompt, prod Gemini settings and the prod-pinned SDK, so the only
   variable is the model name.
3. Grade the sample yourself against the official solution PDFs before you
   look at either model's output. This is the ground truth. The prod score
   stored in the database is not - it came from whatever model was deployed
   at the time, and the scoring prompt has changed since.
4. Run the comparison report, read the feedback text, decide.
5. Delete the sample. It is student work.

Everything below assumes you run from the repo root with the venv present
(`./venv/bin/pip install -r requirements.txt`).

## Tooling

| Script | Purpose |
|---|---|
| `scripts/ab_fetch_prod_sample.sh` | SSH to the NUC, pick submissions, copy rows + photos + prod Gemini env to a local dir |
| `scripts/rescore_eval.py` | Re-run `GeminiProvider.analyze_solution` on the sample with one model, record score, feedback, latency, real token usage |
| `scripts/ab_compare.py` | Merge result files from several models (and your human review) into a markdown report with agreement, cost and latency |

## Step 1 - sample

```bash
EVAL=/tmp/omj-ab-$(date +%Y%m%d)      # outside the repo, it holds personal data
scripts/ab_fetch_prod_sample.sh --out $EVAL --n 10 --since 2026-08-17
```

The default picker is round-robin over `(etap, score)` buckets, newest first,
with flagged submissions (`wrong_task`, `injection`) as their own bucket. That
is what makes a sample of 10 useful: it will contain every score value on
both ladders (0/1/3 for etap1, 0/2/5/6 for etap2 and etap3) plus one
wrong-task case, rather than ten recent 5s. Pass `--ids a,b,c` to hand-pick.

`--since` should be the date of the last prompt or model change so the stored
prod scores are at least comparable. That date is in `git log` for
`prompts/` and `app/config.py`.

Check the printed list. If a bucket you care about is missing (etap3 is rare),
add ids by hand with a second `--ids` run into a different directory and merge
the `sample.json` files.

## Step 2 - rescore with both models

The SDK version matters. Prod pins `google-genai` in `requirements.txt`
because per-part media resolution depends on it. Make sure the venv matches
(`./venv/bin/pip install -r requirements.txt`) or the images are sent at a
different resolution than prod and the comparison is not apples to apples.
`rescore_eval.py` logs the effective resolution at startup; read that line.

```bash
set -a; . $EVAL/prod-gemini.env; set +a     # API key + thinking level + resolution from prod
export DATA_DIR=$EVAL GEMINI_DEBUG_LOGS=false # DATA_DIR makes uploads_dir = $EVAL/data/uploads

for M in gemini-3.7-flash gemini-3.8-flash; do
  GEMINI_MODEL=$M ./venv/bin/python scripts/rescore_eval.py \
      $EVAL/sample.json $EVAL/results_$M.json > $EVAL/run_$M.log 2>&1 &
done
wait
```

Run the current prod model too, not just the candidate. Scores are noisy from
run to run and the stored prod score may predate the current prompt, so the
fair baseline is "prod model, today, same prompt". For the same reason, if the
budget allows, run each model twice - the second pass tells you how much of
the A/B difference is just noise. Ten submissions cost well under a dollar per
pass at flash pricing.

If a model is missing from `GEMINI_PRICING` in `app/ai/providers/gemini.py`
the log says so. Add it (from https://ai.google.dev/gemini-api/docs/pricing)
before running the report, otherwise the cost column is wrong.

## Step 3 - grade the sample yourself

Do this before reading model output, or you will anchor on it.

For each submission open the task PDF and the official solution PDF
(`tasks/{year}/{etap}/`, the `*r.pdf` file is the solutions) and the photos
under `$EVAL/data/uploads/`. Write a JSON file:

```json
{
  "ffa34843": {"score": 1, "note": "sign error after the expansion; case analysis reasons about the wrong equation"},
  "808cf67b": {"score": 0, "note": "photo is task 2, submitted under task 3 - wrong_task is correct"}
}
```

Scoring reminders, from the official scoring sheets:

- etap1: 3 for a complete solution, 1 for significant progress, 0 otherwise.
- etap2 / etap3: 6 complete, 5 complete with a minor gap, 2 significant
  partial progress, 0 otherwise.
- An answer without justification is 0 even if correct.
- A proof that hinges on a false step is 0 or partial, never full marks,
  however close the final line looks.
- Note in the `note` field when you would accept the adjacent score too;
  it matters when reading the agreement table.

## Step 4 - report and decide

```bash
./venv/bin/python scripts/ab_compare.py $EVAL/report.md \
    --result gemini-3.7-flash=$EVAL/results_gemini-3.7-flash.json \
    --result gemini-3.8-flash=$EVAL/results_gemini-3.8-flash.json \
    --human $EVAL/human_review.json
```

The report has four parts. Read them in this order:

1. **Agreement with human review.** Exact matches, matches within one rung of
   the OMJ ladder, and whether a model errs high (over) or low (under).
   Over-scoring is the worse failure for this product: it tells a student a
   broken proof is fine.
2. **Feedback side by side.** Scores can agree while the feedback is wrong.
   Check that each model names the actual gap (the one in your note), does
   not hallucinate a step the student never wrote, and does not leak the
   official solution. This is where most differences between models show up.
3. **Cost and latency.** Thinking tokens dominate cost at `thinking_level=high`.
   Watch the max latency against `GEMINI_TIMEOUT` in prod (`.env.prod`);
   a model that occasionally thinks for 100 s is one that will time out for
   real users on a bad day.
4. **Scores table.** The raw numbers, with the stored prod score for context.

Switch when the candidate is at least as accurate on the human ground truth,
its feedback is not worse on the side-by-side read, and its p50 / max latency
and cost per submission are acceptable. Do not switch on a score-agreement
tie if the cost or latency is materially worse; there is no benefit to pay
for.

Ten submissions cannot distinguish two models that differ by one grade on one
submission. If the report is close, either grow the sample (30 is a
reasonable next step, `--n 30`) or run a second pass of each model before
concluding anything.

## Step 5 - ship or shelve

To switch prod: change `GEMINI_MODEL` in `.env.prod` on the NUC, add the
pricing entry if you have not yet, and restart via `./deploy.sh`. Also update
the default in `app/config.py`, `.env.example` and `.env.prod.example` so the
next fresh install matches.

Either way, record the outcome in a commit message or a short note in this
directory (`docs/model-ab-YYYY-MM-DD.md`): sample ids, both models' agreement
numbers, cost, and the decision. Then:

```bash
rm -rf $EVAL
```

The sample directory holds student photos and the prod API key. Do not leave
it around and never commit it.

## Past experiments

| Date | Baseline | Candidate | Sample | Outcome |
|---|---|---|---|---|
| 2026-07-31 | gemini-3.1-pro-preview | gemini-3.6-flash | ad hoc | led to the flash switch (see `scripts/rescore_eval.py` history) |
| 2026-09-05 | gemini-3.7-flash | gemini-3.8-flash | 10, stratified | see `docs/model-ab-2026-09-05.md` |
