#!/usr/bin/env bash
# Watchdog: every 60s, check the 8 backend health endpoints. If any is
# dead, auto-respawn that one service. Keeps the public-mesh stack
# resilient against transient crashes / OOM kills / RPC blips.
#
# Run in background:
#   nohup bash scripts/keepalive-public-services.sh > /tmp/keepalive.log 2>&1 &
#   disown
#
# Stop:
#   pkill -f keepalive-public-services

set -uo pipefail
cd "$(dirname "$0")/.."

PUB_HOME="${PUB_HOME:-$HOME/.anet-pneuma-court-public}"
LOG_DIR="$PUB_HOME/logs"
mkdir -p "$LOG_DIR"

if [[ ! -f .env ]]; then
  echo "✗ .env missing." >&2
  exit 2
fi
set -a; . ./.env; set +a

# Same service table as serve-public-court.sh
SERVICES=(
  "court-main          8088 court-main           "
  "economic-juror      9101 court-juror          JUROR_MOCK_MODE=1@economic"
  "legal-juror         9102 court-juror          JUROR_MOCK_MODE=1@legal"
  "fairness-juror      9103 court-juror          JUROR_MOCK_MODE=1@fairness"
  "soul-mint           9201 court-soul-svc       "
  "escrow              9202 court-escrow-svc     "
  "manifest            9203 court-manifest-svc   "
  "x402-rail           9205 court-x402-rail      "
)

respawn_if_dead() {
  local name="$1" port="$2" cli="$3" extra="$4"
  local code
  code=$(curl -s -o /dev/null -w "%{http_code}" --max-time 2 "http://127.0.0.1:$port/health" 2>&1 || echo "000")
  if [[ "$code" == "200" ]]; then
    return 0
  fi

  echo "$(date -Iseconds) ✗ $name :$port code=$code — respawning"
  local logfile="$LOG_DIR/$name.log"
  if [[ -n "$extra" ]]; then
    local env_part="${extra%@*}"
    local cli_arg="${extra#*@}"
    env "$env_part" ANET_HOME="$PUB_HOME" HOME="$PUB_HOME" \
      nohup .venv/bin/$cli "$cli_arg" >> "$logfile" 2>&1 &
  else
    env ANET_HOME="$PUB_HOME" HOME="$PUB_HOME" \
      nohup .venv/bin/$cli >> "$logfile" 2>&1 &
  fi
  disown
}

check_anet_daemon() {
  if ! pgrep -f "anet daemon" | grep -v shell-snapshots >/dev/null 2>&1; then
    echo "$(date -Iseconds) ✗ anet daemon DOWN — respawning"
    HOME="$PUB_HOME" nohup anet daemon >> "$PUB_HOME/daemon.log" 2>&1 &
    disown
    sleep 8
  fi
}

echo "$(date -Iseconds) ▸ keepalive starting (60s interval)"
while true; do
  check_anet_daemon
  for entry in "${SERVICES[@]}"; do
    name=$(echo "$entry" | awk '{print $1}')
    port=$(echo "$entry" | awk '{print $2}')
    cli=$(echo "$entry" | awk '{print $3}')
    extra=$(echo "$entry" | awk '{print $4}')
    respawn_if_dead "$name" "$port" "$cli" "$extra"
  done
  sleep 60
done
