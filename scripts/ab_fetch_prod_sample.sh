#!/bin/bash
# Pull a sample of completed submissions (rows + photos) from production for
# an offline model A/B run. See docs/model-ab-playbook.md.
#
# Usage:
#   scripts/ab_fetch_prod_sample.sh --out DIR [--n 10] [--since YYYY-MM-DD]
#   scripts/ab_fetch_prod_sample.sh --out DIR --ids id1,id2,...
#
# Produces:
#   DIR/sample.json           input for scripts/rescore_eval.py
#   DIR/data/uploads/...      student photos, laid out exactly like prod so the
#                             eval can run with DATA_DIR=DIR
#   DIR/prod-gemini.env       prod Gemini settings + API key (chmod 600)
#
# Default sampling is round-robin over (etap, score) buckets, newest first, so a
# small N still covers every score value and every etap. Submissions flagged
# wrong_task/injection are their own bucket.
#
# The sample contains student work (personal data). Keep it in a scratch
# directory outside the repo and delete it when the experiment is written up.

set -euo pipefail

SSH_KEY="${SSH_KEY:-$HOME/.ssh/nuc/id_rsa}"
SSH_HOST="${SSH_HOST:-rsokolowski@192.168.86.68}"
REMOTE_DIR="${REMOTE_DIR:-omj-validator}"

OUT=""; N=10; SINCE=""; IDS=""
while [[ $# -gt 0 ]]; do
    case "$1" in
        --out) OUT="$2"; shift 2 ;;
        --n) N="$2"; shift 2 ;;
        --since) SINCE="$2"; shift 2 ;;
        --ids) IDS="$2"; shift 2 ;;
        -h|--help) sed -n '2,20p' "$0"; exit 0 ;;
        *) echo "Unknown option: $1" >&2; exit 1 ;;
    esac
done
[[ -n "$OUT" ]] || { echo "--out DIR is required" >&2; exit 1; }
OUT=$(realpath -m "$OUT")
case "$OUT" in "$(realpath "$(dirname "$0")/..")"/*)
    echo "--out must be outside the repository (it will hold student photos and the prod API key)" >&2; exit 1 ;;
esac
# These are spliced into SQL that runs against the production database, so
# accept only the exact shapes we expect.
[[ "$N" =~ ^[0-9]+$ ]] || { echo "--n must be a positive integer" >&2; exit 1; }
[[ -z "$SINCE" || "$SINCE" =~ ^[0-9]{4}-[0-9]{2}-[0-9]{2}$ ]] || { echo "--since must be YYYY-MM-DD" >&2; exit 1; }
[[ -z "$IDS" || "$IDS" =~ ^[0-9a-f]{8}(,[0-9a-f]{8})*$ ]] || { echo "--ids must be comma-separated 8-char hex submission ids, no spaces" >&2; exit 1; }
mkdir -p "$OUT/data/uploads"

ssh_cmd() { ssh -i "$SSH_KEY" -o BatchMode=yes "$SSH_HOST" "$@"; }
psql_remote() {
    ssh_cmd "cd $REMOTE_DIR && docker compose --env-file .env.prod -f docker-compose.prod.yml exec -T db psql -U omj -d omj -At"
}

if [[ -n "$IDS" ]]; then
    IN_LIST="'$(echo "$IDS" | sed "s/,/','/g")'"
    WHERE="id in ($IN_LIST)"
    SQL="select json_agg(row_to_json(s)) from (
           select id, year, etap, task_number, score, issue_type, abuse_score,
                  feedback, images, timestamp
           from submissions where status='COMPLETED' and $WHERE
           order by timestamp desc) s;"
else
    SINCE_CLAUSE=""
    [[ -n "$SINCE" ]] && SINCE_CLAUSE="and timestamp >= '$SINCE'"
    SQL="with c as (
           select id, year, etap, task_number, score, issue_type, abuse_score,
                  feedback, images, timestamp,
                  row_number() over (
                    partition by etap,
                      case when issue_type <> 'none' then 'flagged' else score::text end
                    order by timestamp desc) as rn
           from submissions where status='COMPLETED' $SINCE_CLAUSE)
         select json_agg(row_to_json(s)) from (
           select id, year, etap, task_number, score, issue_type, abuse_score,
                  feedback, images, timestamp
           from c order by rn, timestamp desc limit $N) s;"
fi

echo "Querying prod for sample..." >&2
echo "$SQL" | psql_remote > "$OUT/sample.json"
python3 - "$OUT/sample.json" <<'EOF'
import json, sys
p = sys.argv[1]
raw = open(p).read().strip()          # json_agg() of no rows prints an empty line
d = json.loads(raw) if raw else []
json.dump(d, open(p, "w"), ensure_ascii=False, indent=1)
open(p.replace("sample.json", "images.txt"), "w").write("".join(x + "\n" for s in d for x in s["images"]))
print(f"{len(d)} submissions, {sum(len(s['images']) for s in d)} images", file=sys.stderr)
for s in d:
    print(f"  {s['id']} {s['year']}/{s['etap']}/z{s['task_number']} score={s['score']} {s['issue_type']}", file=sys.stderr)
EOF

echo "Copying photos..." >&2
# Exit 23 = some files missing on prod (a purge can leave a COMPLETED row whose
# photos are gone). Keep going; rescore_eval.py skips submissions lacking images.
rsync -a -e "ssh -i '$SSH_KEY' -o BatchMode=yes" --files-from="$OUT/images.txt" \
    "$SSH_HOST:$REMOTE_DIR/data/uploads/" "$OUT/data/uploads/" || [[ $? -eq 23 ]]
python3 - "$OUT" <<'EOF'
import json, os, sys
out = sys.argv[1]
for s in json.load(open(f"{out}/sample.json")):
    missing = [i for i in s["images"] if not os.path.exists(f"{out}/data/uploads/{i}")]
    if missing:
        print(f"  WARNING {s['id']}: {len(missing)} photo(s) missing on prod, will be skipped", file=sys.stderr)
EOF

echo "Fetching prod Gemini settings..." >&2
ssh_cmd "grep -E '^GEMINI_' $REMOTE_DIR/.env.prod" > "$OUT/prod-gemini.env"
chmod 600 "$OUT/prod-gemini.env"

echo "Done. Next: see docs/model-ab-playbook.md, step 3." >&2
