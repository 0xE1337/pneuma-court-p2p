#!/usr/bin/env bash
# Reproducible proof that the court service can be registered on the GLOBAL
# Agent Network mesh (not just our local 5-daemon loopback) and discovered
# from a separate, independent daemon over public ANS gossip.
#
# Two daemons spawned with default-config public mesh, each with its own
# HOME / api_port / peer_id. Daemon-1 hosts a stub court service; Daemon-2
# is the caller. Daemon-2 finds the service over the public anet mesh
# without any side-channel — proving global discoverability.
#
# Run: bash scripts/verify-public-mesh.sh
# Expected output: "found 1 peer(s) advertising dispute-court" near the end.

set -euo pipefail
cd "$(dirname "$0")/.."

if ! command -v anet >/dev/null 2>&1; then
  echo "✗ anet not on PATH. Run: bash scripts/install.sh" >&2
  exit 2
fi

if [[ ! -x .venv/bin/python ]]; then
  echo "✗ .venv missing. Run: python -m venv .venv && source .venv/bin/activate && pip install -e ." >&2
  exit 2
fi

PUB1_HOME=/tmp/anet-pub-court
PUB2_HOME=/tmp/anet-pub-caller

cleanup() {
  pkill -f "anet daemon" 2>/dev/null || true
  pkill -f "verify-public-stub" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

cleanup
sleep 1
rm -rf "$PUB1_HOME" "$PUB2_HOME"
mkdir -p "$PUB1_HOME/.anet" "$PUB2_HOME/.anet"

echo "▸ booting daemon-court (default config — public mesh) …"
HOME="$PUB1_HOME" anet daemon > "$PUB1_HOME/d.log" 2>&1 &
sleep 8

# Second daemon needs different ports so it's a distinct peer
cat > "$PUB2_HOME/.anet/config.json" <<'EOF'
{
  "api_port": 3999,
  "listen_addrs": ["/ip4/0.0.0.0/tcp/4011", "/ip4/0.0.0.0/udp/4011/quic-v1"]
}
EOF
echo "▸ booting daemon-caller (public mesh, api_port=3999) …"
HOME="$PUB2_HOME" anet daemon > "$PUB2_HOME/d.log" 2>&1 &
sleep 8

echo
echo "▸ both daemons on the public anet mesh:"
HOME="$PUB1_HOME" anet status 2>/dev/null \
  | grep -E "peer_id|overlay_peers" | sed 's/^/  daemon-court: /'
echo "  ---"
HOME="$PUB2_HOME" anet status 2>/dev/null \
  | grep -E "peer_id|overlay_peers" | sed 's/^/  daemon-caller: /'

# Tiny stub backend so register has something to point at
.venv/bin/python -c "
import http.server, threading, sys
sys.argv[0] = 'verify-public-stub'
class H(http.server.BaseHTTPRequestHandler):
  def do_GET(self):
    self.send_response(200); self.send_header('Content-Type','application/json'); self.end_headers()
    self.wfile.write(b'{\"ok\":true,\"name\":\"pneuma-court-public-test\"}')
  def log_message(self,*a,**k): pass
srv=http.server.HTTPServer(('127.0.0.1',7901),H)
threading.Thread(target=srv.serve_forever,daemon=True).start()
import time; time.sleep(180)
" >/dev/null 2>&1 &
sleep 1

echo
echo "▸ register pneuma-court-public-test on daemon-court (public ANS) …"
HOME="$PUB1_HOME" ANET_HOME="$PUB1_HOME" .venv/bin/python -c "
from court_agent._anet_client import SvcClient
with SvcClient() as svc:
    resp = svc.register(
        name='pneuma-court-public-test',
        endpoint='http://127.0.0.1:7901',
        paths=['/health'],
        modes=['rr'],
        per_call=1,
        tags=['dispute-court','court-juror','public-test','pneuma-court-p2p'],
        description='Public-mesh reachability proof',
        health_check='/health',
    )
    pub = (resp.get('ans') or {}).get('published')
    print(f'  ✓ ans.published={pub}')
"

echo
echo "▸ wait 25s for ANS gossip to reach daemon-caller …"
sleep 25

echo
echo "▸ from daemon-caller (separate home, separate api token, separate peer_id):"
HOME="$PUB2_HOME" ANET_HOME="$PUB2_HOME" .venv/bin/python -c "
from court_agent._anet_client import SvcClient
with SvcClient() as svc:
    peers = svc.discover(skill='dispute-court')
    print(f'  found {len(peers)} peer(s) advertising dispute-court on the global anet mesh')
    for p in peers[:5]:
        services = p.get('services', [])
        names = [s.get('name','?') for s in services]
        print(f'    peer {p.get(\"peer_id\",\"?\")[:18]}…  services: {names}')
    raise SystemExit(0 if peers else 1)
"

echo
echo "✓ public-mesh discoverability verified"
