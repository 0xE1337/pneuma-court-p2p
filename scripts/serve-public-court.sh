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
  echo "▸ registering pneuma-court on global ANS …"
  HOME="$PUB_HOME" .venv/bin/python <<'PY'
import os, sys
os.environ['ANET_HOME'] = os.environ['HOME']
sys.path.insert(0, 'src')
from court_agent._anet_client import SvcClient

with SvcClient() as svc:
    for name, skill_tag in [
        ('pneuma-court',     'dispute-court'),
        ('economic-juror',   'economic-juror'),
        ('legal-juror',      'legal-juror'),
        ('fairness-juror',   'fairness-juror'),
    ]:
        try:
            resp = svc.register(
                name=name,
                endpoint='http://127.0.0.1:8088',  # placeholder; clients won't actually call
                paths=['/health'],
                modes=['rr'],
                per_call=20 if name == 'pneuma-court' else 5,
                tags=[skill_tag, 'court-juror', 'pneuma-court-p2p', 'public'],
                description=f'pneuma-court-p2p {name} (public listing — see github.com/0xE1337/pneuma-court-p2p)',
                health_check='/health',
            )
            pub = (resp.get('ans') or {}).get('published')
            print(f'  ✓ {name} registered  ans.published={pub}')
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
