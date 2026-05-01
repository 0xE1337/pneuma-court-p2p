#!/usr/bin/env bash
# One-shot demo: spawn 4 anet daemons + main court + 3 jurors + run a test case.
# Sprint 0 placeholder — fully wires up in Sprint 2.

set -euo pipefail

cd "$(dirname "$0")/.."

if ! command -v anet >/dev/null 2>&1; then
  echo "✗ anet daemon not installed. Run: bash scripts/install.sh" >&2
  exit 2
fi

if [[ ! -f .env ]]; then
  echo "✗ .env missing. Run: cp .env.example .env  (then fill in keys)" >&2
  exit 2
fi

echo "▸ Sprint 0 — skeleton present, demo lights up in Sprint 2."
echo "  Today's check: ./.venv/bin/python -c 'import anet, web3, anthropic'"
echo "  Tomorrow:       bash scripts/four-node.sh start"
echo "                  court-main &"
echo "                  court-juror economic &"
echo "                  court-juror legal &"
echo "                  court-juror fairness &"
echo "                  python examples/run_case.py examples/case-economic-dispute.json"
