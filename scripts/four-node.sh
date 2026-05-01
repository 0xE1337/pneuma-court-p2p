#!/usr/bin/env bash
# Spawn five anet daemons on the same laptop, all bootstrapped off daemon-1
# so they form a single mesh. Adapted from anet starter kit
# examples/03-multi-agent-pipeline/scripts/four-node.sh, expanded to 5 daemons
# because anet svc discover dedupes by peer_id — each juror needs its own
# daemon to be discoverable as a distinct panel member.
#
# Layout for pneuma-court:
#   /tmp/anet-p2p-court-u1   API=:13921  P2P=:14021    pneuma-court (main)
#   /tmp/anet-p2p-court-u2   API=:13922  P2P=:14022    economic-juror
#   /tmp/anet-p2p-court-u3   API=:13923  P2P=:14023    legal-juror
#   /tmp/anet-p2p-court-u4   API=:13924  P2P=:14024    fairness-juror
#   /tmp/anet-p2p-court-u5   API=:13925  P2P=:14025    caller (run_case.py)

set -euo pipefail
ANET="${ANET:-anet}"

API=(13921 13922 13923 13924 13925)
P2P=(14021 14022 14023 14024 14025)
HOMES=(
  /tmp/anet-p2p-court-u1
  /tmp/anet-p2p-court-u2
  /tmp/anet-p2p-court-u3
  /tmp/anet-p2p-court-u4
  /tmp/anet-p2p-court-u5
)

green() { printf "\033[32m✓\033[0m %s\n" "$*"; }
red()   { printf "\033[31m✗\033[0m %s\n" "$*"; }

write_config() {
  local dir="$1" api="$2" p2p="$3" boot_csv="$4"
  mkdir -p "$dir/.anet"
  cat > "$dir/.anet/config.json" <<EOF
{
  "listen_addrs": ["/ip4/127.0.0.1/tcp/$p2p"],
  "bootstrap_peers": [$boot_csv],
  "api_port": $api,
  "relay_enabled": false,
  "topics_auto_join": ["/anet/ans", "/anet/credits"],
  "bt_dht": {"enabled": false},
  "overlay": {"enabled": false}
}
EOF
}

api_alive() { curl -sf --noproxy '*' -m 1 "http://127.0.0.1:$1/api/status" >/dev/null 2>&1; }

wait_alive() {
  for _ in $(seq 1 60); do
    api_alive "$1" && return 0
    sleep 1
  done
  return 1
}

cmd_start() {
  command -v "$ANET" >/dev/null || { red "anet not on PATH (set ANET=…)"; exit 1; }

  for d in "${HOMES[@]}"; do rm -rf "$d"; mkdir -p "$d"; done
  for p in "${API[@]}" "${P2P[@]}"; do
    lsof -ti tcp:"$p" 2>/dev/null | xargs -r kill -9 2>/dev/null || true
  done

  write_config "${HOMES[0]}" "${API[0]}" "${P2P[0]}" ""
  HOME="${HOMES[0]}" "$ANET" daemon > "${HOMES[0]}/daemon.log" 2>&1 &
  wait_alive "${API[0]}" || { red "daemon-1 failed"; tail "${HOMES[0]}/daemon.log"; exit 1; }
  PEER1=$(curl -sf --noproxy '*' "http://127.0.0.1:${API[0]}/api/status" \
    | python3 -c "import sys,json;print(json.load(sys.stdin)['peer_id'])")
  green "u1 alive  PEER=$PEER1  (court)"

  for i in 1 2 3 4; do
    BOOT="\"/ip4/127.0.0.1/tcp/${P2P[0]}/p2p/$PEER1\""
    write_config "${HOMES[$i]}" "${API[$i]}" "${P2P[$i]}" "$BOOT"
    HOME="${HOMES[$i]}" "$ANET" daemon > "${HOMES[$i]}/daemon.log" 2>&1 &
    wait_alive "${API[$i]}" || { red "daemon-$((i+1)) failed"; tail "${HOMES[$i]}/daemon.log"; exit 1; }
    case "$i" in
      1) green "u2 alive on :${API[$i]}  (economic-juror)" ;;
      2) green "u3 alive on :${API[$i]}  (legal-juror)" ;;
      3) green "u4 alive on :${API[$i]}  (fairness-juror)" ;;
      4) green "u5 alive on :${API[$i]}  (caller)" ;;
    esac
  done
}

cmd_stop() {
  pkill -f "anet daemon" 2>/dev/null || true
  green "all anet daemons stopped"
}

cmd_status() {
  for i in "${!API[@]}"; do
    if api_alive "${API[$i]}"; then
      green "daemon-$((i+1)) alive on :${API[$i]}"
    else
      red "daemon-$((i+1)) not responding on :${API[$i]}"
    fi
  done
}

cmd_clean() {
  cmd_stop
  for d in "${HOMES[@]}"; do rm -rf "$d"; done
  green "all home dirs removed"
}

case "${1:-start}" in
  start)  cmd_start ;;
  stop)   cmd_stop ;;
  status) cmd_status ;;
  clean)  cmd_clean ;;
  *)
    echo "usage: $0 {start|stop|status|clean}" >&2
    exit 2
    ;;
esac
