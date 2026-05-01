#!/usr/bin/env bash
# One-time setup: mint a Pneuma Soul NFT for each juror, serially, so the
# panel demos with chain-anchored identities. Caches the result in
# ~/.pneuma-court-souls/ so subsequent court-juror invocations skip the
# mint and reuse the existing Soul.
#
# Run this ONCE before the first demo. Re-running is safe — already-cached
# jurors are skipped without sending a new tx.
#
# Why serial: all 3 jurors share the COURT_FINALIZER_PRIVATE_KEY wallet
# during local demos. If they boot in parallel they race on the wallet
# nonce and 2/3 mints fail. This script avoids that.

set -euo pipefail
cd "$(dirname "$0")/.."

if [[ ! -f .env ]]; then
  echo "✗ .env missing. cp .env.example .env then fill in COURT_FINALIZER_PRIVATE_KEY" >&2
  exit 2
fi
set -a; . ./.env; set +a

if [[ ! -x .venv/bin/python ]]; then
  echo "✗ .venv not set up. Run: python -m venv .venv && source .venv/bin/activate && pip install -e ." >&2
  exit 2
fi

.venv/bin/python <<'PY'
import os, time
from court_agent.chain_pneuma import (
    ensure_juror_soul, total_minted, has_pneuma_config, explorer_url,
)

if not has_pneuma_config():
    print("✗ no Pneuma chain config — set ARC_RPC_URL + COURT_FINALIZER_PRIVATE_KEY in .env")
    raise SystemExit(2)

JURORS = ["economic-juror", "legal-juror", "fairness-juror"]

print(f"▸ Pneuma SoulNFT.totalMinted() at start: {total_minted()}")
print()

for j in JURORS:
    print(f"▸ ensuring Soul for {j} …")
    ident = ensure_juror_soul(j)
    if ident is None:
        print(f"  ✗ failed for {j}")
        continue
    print(f"  ✓ Soul #{ident['tokenId']}  TBA {ident['tba'][:10]}…")
    print(f"     {explorer_url(ident['tokenId'])}")
    # Small inter-mint pause to let nonce settle / RPC catch up
    time.sleep(2)

print()
print(f"▸ Pneuma SoulNFT.totalMinted() at end: {total_minted()}")
print()
print("✓ all 3 juror Souls ready. Run scripts/demo.sh next.")
PY
