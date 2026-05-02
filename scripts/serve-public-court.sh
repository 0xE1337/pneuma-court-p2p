#!/usr/bin/env bash
# Boot the full Pneuma Court 8-service stack on the GLOBAL Agent Network
# mesh. Other anet users can `anet svc discover --skill=<tag>` and find
# us from anywhere on the network.
#
# What this script does:
#   1. Boot a single default-config public-mesh daemon (joins ANS / tasks
#      / credits / brain topics)
#   2. Spawn 8 FastAPI backends locally:
#        court-main          :8088
#        economic-juror      :9101    (JUROR_MOCK_MODE=1, anet 30s timeout)
#        legal-juror         :9102    (JUROR_MOCK_MODE=1)
#        fairness-juror      :9103    (JUROR_MOCK_MODE=1)
#        soul-mint           :9201
#        escrow              :9202
#        manifest            :9203
#        x402-rail           :9205
#   3. Each backend self-registers on the public daemon's ANS with its
#      OWN endpoint (no :8088 placeholder)
#   4. Health-check all 8 ports
#
# Usage:
#   bash scripts/serve-public-court.sh start    # boot daemon + 8 backends + register
#   bash scripts/serve-public-court.sh stop     # kill daemon + all 8 backends
#   bash scripts/serve-public-court.sh status   # show daemon + ANS state
#   bash scripts/serve-public-court.sh health   # health-check all 8 ports
#   bash scripts/serve-public-court.sh logs <svc>   # tail one service log

set -euo pipefail
cd "$(dirname "$0")/.."

PUB_HOME="${PUB_HOME:-$HOME/.anet-pneuma-court-public}"
LOG_DIR="$PUB_HOME/logs"

if [[ ! -f .env ]]; then
  echo "✗ .env missing. Run: cp .env.example .env" >&2
  exit 2
fi
set -a; . ./.env; set +a

# (svc-name port cli-bin extra-env)
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

cmd_status() {
  if pgrep -f "anet daemon" | grep -v shell-snapshots >/dev/null 2>&1; then
    echo "▸ anet daemon: running"
    HOME="$PUB_HOME" anet status 2>&1 | grep -E "peer_id|peers|overlay_peers" | sed 's/^/  /'
    echo
    echo "▸ services advertised on global ANS:"
    HOME="$PUB_HOME" anet svc list 2>&1 | head -12
  else
    echo "▸ anet daemon: not running"
  fi
  echo
  cmd_health
}

cmd_health() {
  echo "▸ backend health (8 ports):"
  local all_ok=1
  for entry in "${SERVICES[@]}"; do
    local name port
    name=$(echo "$entry" | awk '{print $1}')
    port=$(echo "$entry" | awk '{print $2}')
    local code
    code=$(curl -s -o /dev/null -w "%{http_code}" --max-time 2 "http://127.0.0.1:$port/health" 2>&1 || echo "000")
    if [[ "$code" == "200" ]]; then
      printf "  \033[32m✓\033[0m  %-20s :%-5s = %s\n" "$name" "$port" "$code"
    else
      printf "  \033[31m✗\033[0m  %-20s :%-5s = %s\n" "$name" "$port" "$code"
      all_ok=0
    fi
  done
  if [[ $all_ok -eq 1 ]]; then
    echo
    echo "  ✓ all 8 backends healthy"
  fi
}

_spawn_backend() {
  local name="$1" port="$2" cli="$3" extra="$4"
  # Already running on this port? Skip.
  if curl -s -o /dev/null --max-time 1 "http://127.0.0.1:$port/health" 2>&1; then
    echo "  ▸ $name already up on :$port (skipping)"
    return 0
  fi

  local logfile="$LOG_DIR/$name.log"
  if [[ -n "$extra" ]]; then
    # Format: "VAR=val@arg" — set env var + pass arg to cli
    local env_part="${extra%@*}"
    local cli_arg="${extra#*@}"
    env "$env_part" ANET_HOME="$PUB_HOME" HOME="$PUB_HOME" \
      nohup .venv/bin/$cli "$cli_arg" > "$logfile" 2>&1 &
  else
    env ANET_HOME="$PUB_HOME" HOME="$PUB_HOME" \
      nohup .venv/bin/$cli > "$logfile" 2>&1 &
  fi
  disown
  echo "  ▸ spawned $name on :$port (log: $logfile)"
}

cmd_start() {
  if pgrep -f "anet daemon" | grep -v shell-snapshots >/dev/null 2>&1; then
    echo "▸ anet daemon already running — skipping daemon boot"
  else
    mkdir -p "$PUB_HOME"
    mkdir -p "$LOG_DIR"
    echo "▸ booting public-mesh daemon (HOME=$PUB_HOME) …"
    HOME="$PUB_HOME" anet daemon > "$PUB_HOME/daemon.log" 2>&1 &
    DAEMON_PID=$!
    echo "  PID=$DAEMON_PID"
    for _ in $(seq 1 30); do
      HOME="$PUB_HOME" anet status >/dev/null 2>&1 && break
      sleep 1
    done

    PEERS=$(HOME="$PUB_HOME" anet status 2>/dev/null | grep -E "overlay_peers" | grep -oE '[0-9]+' | head -1)
    echo "  ✓ daemon alive — overlay peers: ${PEERS:-?}"
  fi

  mkdir -p "$LOG_DIR"
  echo
  echo "▸ spawning 8 backends (each self-registers on ANS with its own endpoint) …"
  for entry in "${SERVICES[@]}"; do
    local name port cli extra
    name=$(echo "$entry" | awk '{print $1}')
    port=$(echo "$entry" | awk '{print $2}')
    cli=$(echo "$entry" | awk '{print $3}')
    extra=$(echo "$entry" | awk '{print $4}')
    _spawn_backend "$name" "$port" "$cli" "$extra"
  done

  echo
  echo "▸ waiting 22s for backends to boot + self-register …"
  sleep 22

  echo
  cmd_health

  echo
  echo "▸ services on ANS (with their actual endpoints):"
  HOME="$PUB_HOME" anet svc list 2>&1 | head -12

  echo
  echo "▸ verify from another shell or another machine on anet:"
  echo "    anet svc discover --skill dispute-court"
  echo "    anet svc discover --skill x402"
  echo "    anet svc discover --skill pneuma-court-manifest"
  echo
  echo "  Stop everything: bash scripts/serve-public-court.sh stop"
}

cmd_stop() {
  echo "▸ stopping backends …"
  for cli in court-main court-juror court-soul-svc court-escrow-svc court-manifest-svc court-x402-rail; do
    for pid in $(pgrep -f ".venv/bin/$cli" 2>/dev/null); do
      if ! ps -p $pid -o command= 2>/dev/null | grep -q shell-snapshots; then
        kill $pid 2>/dev/null && echo "  killed $cli pid=$pid" || true
      fi
    done
  done
  echo
  echo "▸ stopping anet daemon …"
  pkill -f "anet daemon" 2>/dev/null && echo "  ✓ daemon stopped" || echo "  (no daemon running)"
}

cmd_logs() {
  local svc="${1:-}"
  if [[ -z "$svc" ]]; then
    echo "Available logs in $LOG_DIR:"
    ls -1 "$LOG_DIR" 2>/dev/null | sed 's/^/  /'
    echo
    echo "Usage: bash scripts/serve-public-court.sh logs <svc>"
    echo "  e.g. logs court-main, logs x402-rail"
    return 0
  fi
  tail -50 "$LOG_DIR/$svc.log"
}

case "${1:-status}" in
  start)  cmd_start ;;
  stop)   cmd_stop ;;
  status) cmd_status ;;
  health) cmd_health ;;
  logs)   shift; cmd_logs "$@" ;;
  *)
    echo "usage: $0 {start|stop|status|health|logs}" >&2
    exit 2
    ;;
esac
