#!/usr/bin/env bash
# Register this team's anet identity (DID) on the public agentnetwork.org.cn
# management registry. Idempotent — reruns return 409 did_taken, which is fine.
#
# What this does:
#   1. Boots a public-mesh anet daemon under $HOME/.anet-pneuma-court (so it
#      doesn't clash with the demo's isolated 4-daemon mesh in /tmp).
#   2. Reads our DID via `anet whoami`.
#   3. POSTs to https://agentnetwork.org.cn/api/mgmt/agents/self-register
#      with our DID, project name, and GitHub URL.
#   4. Saves the returned agent_api_key + human_api_key to
#      ~/.anet-pneuma-court/.anet/keys.json (chmod 600).
#   5. Verifies the registration via /api/mgmt/agent/me.
#
# Re-run safety: if the DID is already registered, the API returns 409
# (did_taken) and this script exits successfully without overwriting keys.

set -euo pipefail
PUB_HOME="${PUB_HOME:-$HOME/.anet-pneuma-court}"

if ! command -v anet >/dev/null 2>&1; then
  echo "✗ anet not on PATH. Install: bash scripts/install.sh" >&2
  exit 2
fi

mkdir -p "$PUB_HOME"
HOME="$PUB_HOME" anet daemon > "$PUB_HOME/daemon.log" 2>&1 &
DAEMON_PID=$!
trap 'kill "$DAEMON_PID" 2>/dev/null || true' EXIT INT TERM

echo "▸ booting public-mesh daemon (PID=$DAEMON_PID, HOME=$PUB_HOME)…"
for _ in $(seq 1 30); do
  HOME="$PUB_HOME" anet status >/dev/null 2>&1 && break
  sleep 1
done

DID=$(HOME="$PUB_HOME" anet whoami --json 2>/dev/null \
  | python3 -c 'import sys,json;print(json.load(sys.stdin).get("did",""))')
[[ -n "$DID" ]] || { echo "✗ no DID from anet whoami"; exit 1; }
echo "  ✓ DID: $DID"

echo "▸ self-registering on https://agentnetwork.org.cn/api/mgmt/agents/self-register …"
RESPONSE=$(curl -fsSL -X POST \
  https://agentnetwork.org.cn/api/mgmt/agents/self-register \
  -H 'content-type: application/json' \
  -d "{
    \"did\":\"$DID\",
    \"name\":\"pneuma-court-p2p\",
    \"description\":\"Multi-juror dispute resolution as a P2P service. South Hackathon Agent Network sponsor track. https://github.com/0xE1337/pneuma-court-p2p\"
  }" 2>&1) || true

if echo "$RESPONSE" | grep -q "agent_api_key"; then
  KEYS_FILE="$PUB_HOME/.anet/keys.json"
  echo "$RESPONSE" > "$KEYS_FILE"
  chmod 600 "$KEYS_FILE"
  echo "  ✓ keys saved to $KEYS_FILE (chmod 600)"
elif echo "$RESPONSE" | grep -qiE "did_taken|409"; then
  echo "  ✓ DID already registered (idempotent — fine)"
else
  echo "  ⚠ unexpected response:"
  echo "$RESPONSE"
fi

KEYS_FILE="$PUB_HOME/.anet/keys.json"
if [[ -f "$KEYS_FILE" ]]; then
  AGENT_KEY=$(python3 -c "import json;print(json.load(open('$KEYS_FILE'))['agent_api_key'])")
  echo "▸ verifying via /api/mgmt/agent/me …"
  curl -fsSL -H "authorization: Bearer $AGENT_KEY" \
    https://agentnetwork.org.cn/api/mgmt/agent/me 2>&1 \
    | python3 -m json.tool 2>/dev/null | head -20
fi
