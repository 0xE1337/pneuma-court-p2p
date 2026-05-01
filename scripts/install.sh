#!/usr/bin/env bash
# Install the anet P2P daemon (one-line install per Agent Network docs).
set -euo pipefail

if command -v anet >/dev/null 2>&1; then
  echo "✓ anet already installed: $(anet --version)"
  exit 0
fi

echo "▸ installing anet daemon from agentnetwork.org.cn …"
curl -fsSL https://agentnetwork.org.cn/install.sh | sh
anet --version
