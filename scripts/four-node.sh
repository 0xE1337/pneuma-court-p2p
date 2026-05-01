#!/usr/bin/env bash
# Spawn 4 anet daemons on isolated $HOME prefixes — adapted from
# anet starter kit examples/03-multi-agent-pipeline/scripts/four-node.sh.
# Sprint 0 placeholder.

set -euo pipefail

ACTION="${1:-start}"
BASE_PORT="${BASE_PORT:-13921}"

case "$ACTION" in
  start)
    for i in 1 2 3 4; do
      port=$((BASE_PORT + i - 1))
      home="/tmp/anet-p2p-court-u${i}"
      mkdir -p "$home"
      HOME="$home" anet daemon --port "$port" >"$home/daemon.log" 2>&1 &
      echo "✓ daemon-${i} started on :${port} (HOME=$home)"
    done
    ;;
  stop)
    pkill -f "anet daemon" || true
    echo "✓ daemons stopped"
    ;;
  status)
    pgrep -fa "anet daemon" || echo "no daemons running"
    ;;
  *)
    echo "usage: $0 {start|stop|status}" >&2
    exit 2
    ;;
esac
