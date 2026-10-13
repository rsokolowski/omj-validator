# Playbook: A/B testing a new scoring model

Use this whenever Google or Anthropic ships a new model and the question is
"should prod switch?". The whole thing takes about an hour of wall clock for a
10-submission sample, most of it waiting on the API and reading photos.

The short version:

1. Pull a stratified sample of real submissions from prod (rows + photos).
2. Rescore the sample with the current prod model AND the candidate, using the
   prod prompt, prod provider settings and the prod-pinned SDK, so the only
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
| `scripts/rescore_eval.py` | Re-run the prod provider's `analyze_solution_stream` on the sample with one `--provider`/`--model`, record score, feedback, latency, token usage and estimated cost from `scoring_meta` |
| `scripts/ab_compare.py` | Merge result files from several models (and your human review) into a markdown report with agreement, cost and latency; arms are labelled `provider/model` |

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

The scripts build each arm with `build_provider()`, so the app's automatic
failover (`AI_FAILOVER_*`) never applies here: an arm whose provider fails
records the error instead of silently being graded by the backup model. In
prod, a submission graded after a failover carries `scoring_meta["failover"]`
- leave such rows out of a sample meant to measure one model.

```bash
set -a; . $EVAL/prod-gemini.env; set +a     # API key + thinking level + resolution from prod
export DATA_DIR=$EVAL GEMINI_DEBUG_LOGS=false # DATA_DIR makes uploads_dir = $EVAL/data/uploads

for M in gemini-3.7-flash gemini-3.8-flash; do
  ./venv/bin/python scripts/rescore_eval.py --model $M \
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

### Claude arm

Running a Claude model on the sample **sends prod student photos to
Anthropic**. That is the same processing as using Claude in prod, so it needs
the same sign-off first: Anthropic approved as a processor (DPA accepted, RODO
docs updated - see `docs/rodo/`) and `ANTHROPIC_PROCESSOR_APPROVED=true`.
`rescore_eval.py --provider anthropic` refuses to start without it. Do not
flip the flag just to run the A/B.

```bash
export ANTHROPIC_API_KEY=...          # from the Anthropic console, never commit it
export ANTHROPIC_PROCESSOR_APPROVED=true   # only after the sign-off above
# optional, same defaults as prod: ANTHROPIC_EFFORT=high ANTHROPIC_TIMEOUT=180

M=claude-haiku-5-5
./venv/bin/python scripts/rescore_eval.py --provider anthropic --model $M \
    $EVAL/sample.json $EVAL/results_$M.json > $EVAL/run_$M.log 2>&1
```

`--model` must be a Claude model listed in `app/ai/models_catalog.py`
(`CATALOG`); that is where its prices live, and the script refuses unknown
ids rather than reporting a cost of 0. Run it next to the current Gemini prod
model (above) so the report has the baseline.

Cost hint: grading uses `ANTHROPIC_EFFORT` (default `high`) with adaptive
thinking, and Claude bills thinking as output tokens - the report's "thoughts
tok" column is 0 for Claude arms, the thinking is inside the output count and
the cost. Rough order of magnitude, assuming ~15k input and 5-15k output
tokens per submission at catalog prices: about $0.01 per submission with
Haiku 5.5, $0.10-0.20 with Sonnet 5.5, $0.20-0.40 with Opus 5.5. Check the
`$` figure on the first lines of the run log before launching a larger sample.

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

Add `--result claude-haiku-5-5=$EVAL/results_claude-haiku-5-5.json` for a
Claude arm. Each arm shows up as `provider/label`; result files written
before rows carried a provider are read as Gemini. Cost is the
`estimated_cost` each row recorded (the figure prod stores), or for older
files an estimate from the pricing tables.

The report has four parts. Read them in this order:

1. **Agreement with human review.** Exact matches, matches within one rung of
   the OMJ ladder, and whether a model errs high (over) or low (under).
   Over-scoring is the worse failure for this product: it tells a student a
   broken proof is fine.
2. **Feedback side by side.** Scores can agree while the feedback is wrong.
   Check that each model names the actual gap (the one in your note), does
   not hallucinate a step the student never wrote, and does not leak the
   official solution. This is where most differences between models show up.
   Also check the Polish text itself: 3.8-flash once produced corrupted words
   in prod ("Ŵe", "żee" for "że"), see
   the 2026-09-05 report (kept outside the repository).
3. **Cost and latency.** Thinking tokens dominate cost at `thinking_level=high`
   (Gemini) and `ANTHROPIC_EFFORT=high` (Claude).
   Watch the max latency against `GEMINI_TIMEOUT` / `ANTHROPIC_TIMEOUT` in prod (`.env.prod`);
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

To switch prod: pick the model in `/admin/settings` (the choice is stored in
the `app_settings` table and takes effect on the next submission, no restart).
The admin page only lists models from `app/ai/models_catalog.py`, so a new
model needs a catalog entry (and, for Gemini, a `GEMINI_PRICING` entry) and a
deploy first. `GEMINI_MODEL` in `.env.prod` is only the default used when no
choice has been saved; update it, and the default in `app/config.py`,
`.env.example` and `.env.prod.example`, when Gemini's default model changes.
Switching prod to Claude needs the processor sign-off described under
"Claude arm".

**Rollback.** `ANTHROPIC_PROCESSOR_APPROVED=false` in `.env.prod` plus an api
restart forces Gemini (the `GEMINI_MODEL` default) whatever the stored row
says; `/admin/settings` then shows the fallback. Switching back to Gemini in
the UI also works, but only after a successful Gemini ping - while Google
answers 503/429 the switch is refused, so use the env flag.

Either way, record the outcome in a commit message or a short note in this
directory (`docs/model-ab-YYYY-MM-DD.md`): sample ids, both models' agreement
numbers, cost, and the decision. Then:

```bash
rm -rf $EVAL
```

The sample directory holds student photos and the prod API key (and the
result files hold model feedback on student work). Do not leave
it around and never commit it.

## Past experiments

| Date | Baseline | Candidate | Sample | Outcome |
|---|---|---|---|---|
| 2026-07-31 | gemini-3.1-pro-preview | gemini-3.6-flash | ad hoc | led to the flash switch (see `scripts/rescore_eval.py` history) |
| 2026-09-05 | gemini-3.7-flash | gemini-3.8-flash | 10, stratified | report kept outside the repository |
