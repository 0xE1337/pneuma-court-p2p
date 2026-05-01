#!/usr/bin/env bash
# One-shot demo: 4 daemons + court + 3 jurors + run a test case.
#
# Pre-flight required:
#   bash scripts/install.sh                    # installs anet daemon
#   python -m venv .venv && source .venv/bin/activate
#   pip install -e .
#   cp .env.example .env                       # then fill in real keys
#
# Usage:
#   bash scripts/demo.sh                       # uses examples/case-economic-dispute.json
#   bash scripts/demo.sh path/to/your-case.json

set -euo pipefail
cd "$(dirname "$0")/.."

if [[ ! -f .env ]]; then
  echo "✗ .env missing. Run: cp .env.example .env  (then fill in keys)" >&2
  exit 2
fi

set -a; . ./.env; set +a

if ! command -v anet >/dev/null 2>&1; then
  echo "✗ anet not installed. Run: bash scripts/install.sh" >&2
  exit 2
fi

PYBIN="${PYBIN:-python}"
"$PYBIN" -c "import anet, web3, anthropic, fastapi" 2>/dev/null || {
  echo "✗ Python deps missing. Activate venv and run: pip install -e ." >&2
  exit 2
}

LOG=demo-output
mkdir -p "$LOG"
PIDS=()

cleanup() {
  echo
  echo "▸ stopping services and daemons …"
  for pid in "${PIDS[@]:-}"; do
    kill "$pid" 2>/dev/null || true
  done
  bash scripts/four-node.sh stop || true
}
trap cleanup EXIT INT TERM

echo "═══════════════════════════════════════════════════════════════════════"
echo "  pneuma-court-p2p — one-shot demo"
echo "═══════════════════════════════════════════════════════════════════════"

echo
echo "▸ [1/5] starting 4 anet daemons …"
bash scripts/four-node.sh start
sleep 2

echo
echo "▸ [2/5] starting court on daemon-1 …"
ANET_BASE_URL=http://127.0.0.1:13921 \
  COURT_PORT=8088 \
  court-main >"$LOG/court.log" 2>&1 &
PIDS+=($!)

echo "▸ [3/5] starting economic-juror on daemon-2 …"
ANET_BASE_URL=http://127.0.0.1:13922 \
  ECONOMIC_JUROR_PORT=9101 \
  court-juror economic >"$LOG/economic.log" 2>&1 &
PIDS+=($!)

echo "▸ [4/5] starting legal-juror + fairness-juror on daemon-3 …"
ANET_BASE_URL=http://127.0.0.1:13923 \
  LEGAL_JUROR_PORT=9102 \
  court-juror legal >"$LOG/legal.log" 2>&1 &
PIDS+=($!)

ANET_BASE_URL=http://127.0.0.1:13923 \
  FAIRNESS_JUROR_PORT=9103 \
  court-juror fairness >"$LOG/fairness.log" 2>&1 &
PIDS+=($!)

echo
echo "▸ [5/5] waiting for ANS gossip + service registration (10s) …"
sleep 10

echo
echo "▸ submitting test case from daemon-4 …"
echo "─────────────────────────────────────────────────────────────────────────"
ANET_BASE_URL=http://127.0.0.1:13924 \
  "$PYBIN" examples/run_case.py "$@"

echo
echo "▸ logs: $LOG/{court,economic,legal,fairness}.log"
echo "▸ press Ctrl+C to stop daemons and exit."
wait
