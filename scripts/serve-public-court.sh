#!/usr/bin/env bash
# Run pneuma-court on the GLOBAL Agent Network mesh, persistently. Other
# anet users can then `anet svc discover --skill=dispute-court` and find us
# from anywhere on the network — not just inside our 5-daemon loopback.
#
# This script bootstraps a single default-config public-mesh daemon
# (talks to anet's public bootstrap peers, joins ANS / tasks / credits
# topics), then registers the pneuma-court service plus three jurors on
# top of it. Leave it running 24/7 if you want global discoverability.
#
# Usage:
#   bash scripts/serve-public-court.sh start    # boot daemon + register
#   bash scripts/serve-public-court.sh stop     # tear everything down
#   bash scripts/serve-public-court.sh status   # show daemon + service state

set -euo pipefail
cd "$(dirname "$0")/.."

PUB_HOME="${PUB_HOME:-$HOME/.anet-pneuma-court-public}"

if [[ ! -f .env ]]; then
  echo "✗ .env missing. Run: cp .env.example .env" >&2
  exit 2
fi
set -a; . ./.env; set +a

cmd_status() {
  if pgrep -f "anet daemon" >/dev/null 2>&1; then
    echo "▸ anet daemon: running"
    HOME="$PUB_HOME" anet status 2>&1 | grep -E "peer_id|peers|overlay_peers" | sed 's/^/  /'
    echo
    echo "▸ services advertised on global ANS:"
    HOME="$PUB_HOME" anet svc list 2>&1 | head -10
  else
    echo "▸ anet daemon: not running"
  fi
}

cmd_start() {
  if pgrep -f "anet daemon" >/dev/null 2>&1; then
    echo "✗ another anet daemon is already running. Stop it first:"
    echo "    bash scripts/serve-public-court.sh stop"
    exit 2
  fi

  mkdir -p "$PUB_HOME"
  echo "▸ booting public-mesh daemon (HOME=$PUB_HOME) …"
  HOME="$PUB_HOME" anet daemon > "$PUB_HOME/daemon.log" 2>&1 &
  DAEMON_PID=$!
  echo "  PID=$DAEMON_PID"
  for _ in $(seq 1 30); do
    HOME="$PUB_HOME" anet status >/dev/null 2>&1 && break
    sleep 1
  done

  PEERS=$(HOME="$PUB_HOME" anet status 2>/dev/null | grep -E "overlay_peers" | grep -oE '[0-9]+' | head -1)
  echo "  ✓ alive — overlay peers: ${PEERS:-?}"

  # Register the four services on the public mesh. Each needs a backing
  # FastAPI process; here we just register against placeholder endpoints.
  # Real lifecycle (jurors actually voting) requires running the demo's
  # 5-daemon mesh too — this script's job is just public discoverability.
  echo
  echo "▸ registering full Pneuma Court protocol surface on global ANS …"
  HOME="$PUB_HOME" .venv/bin/python <<'PY'
import os, sys
os.environ['ANET_HOME'] = os.environ['HOME']
sys.path.insert(0, 'src')
from court_agent._anet_client import SvcClient

# Core 4 (court + 3 jurors) + 2 protocol-prerequisite services
# (Soul mint and CourtEscrow). External agents discover the FULL stack
# via anet ANS:
#   anet svc discover --skill=soul-mint        → identity layer
#   anet svc discover --skill=escrow           → enforcement layer
#   anet svc discover --skill=dispute-court    → reasoning layer
#   anet svc discover --skill=court-juror      → panel pool
#
# Each service's tags + description tell external agents exactly what
# they get + how to participate (see docs/joining-as-juror.md).
SERVICES = [
    # name, primary skill tag, per_call, extra tags, description
    ('pneuma-soul-mint',  'soul-mint',     10,
        ['identity', 'sponsored-mint', 'arc-testnet'],
        'Sponsored Pneuma Soul NFT minting (operator pays gas)'),
    ('pneuma-court-escrow', 'escrow',       5,
        ['stake-and-slash', 'onchain', 'arc-testnet'],
        'On-chain stake/escrow/dispute view + tx-quote helper'),
    ('pneuma-court',      'dispute-court', 20,
        ['multi-juror', 'court-juror', 'arbitration'],
        'Multi-juror dispute resolution (3 Soul-anchored jurors)'),
    ('economic-juror',    'economic-juror', 5,
        ['court-juror', 'juror'],
        'Economic-dispute juror (commercial-arbitration prompt)'),
    ('legal-juror',       'legal-juror',    5,
        ['court-juror', 'juror'],
        'Legal-procedure juror (statutory-construction prompt)'),
    ('fairness-juror',    'fairness-juror', 5,
        ['court-juror', 'juror'],
        'Fairness/equity juror (good-faith / unjust-enrichment prompt)'),
]

with SvcClient() as svc:
    for name, primary_skill, per_call, extra_tags, desc in SERVICES:
        # idempotent: try unregister so re-runs don't choke on
        # 'service already registered'
        try:
            svc.unregister(name)
        except Exception:
            pass
        try:
            resp = svc.register(
                name=name,
                endpoint='http://127.0.0.1:8088',  # placeholder; advertised metadata only
                paths=['/health'],
                modes=['rr'],
                per_call=per_call,
                tags=[primary_skill, *extra_tags, 'pneuma-court-p2p', 'public'],
                description=f'{desc} — github.com/0xE1337/pneuma-court-p2p',
                health_check='/health',
            )
            pub = (resp.get('ans') or {}).get('published')
            print(f'  ✓ {name:<22s} skill={primary_skill:<14s} per_call={per_call:<3d}🐚  ans.published={pub}')
        except Exception as e:
            print(f'  ✗ {name} register failed: {e}')
PY

  echo
  echo "▸ daemon will keep running in background. To verify from another"
  echo "  shell or another machine on the same anet network:"
  echo
  echo "    anet svc discover --skill dispute-court"
  echo
  echo "  Stop with: bash scripts/serve-public-court.sh stop"
}

cmd_stop() {
  pkill -f "anet daemon" 2>/dev/null && echo "✓ daemon stopped" || echo "▸ no daemon running"
}

case "${1:-status}" in
  start)  cmd_start ;;
  stop)   cmd_stop ;;
  status) cmd_status ;;
  *)
    echo "usage: $0 {start|stop|status}" >&2
    exit 2
    ;;
esac
