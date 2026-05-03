# Public Reachability Fix — Lessons from 5/3 Evaluation

> **Context**: During the 5/3 10:00 hackathon evaluation window, the evaluator
> agent reported "6/6 节点全部 dial 失败" against our cluster (and every other
> Curated Cluster owner — `tech_notes`: "本次抓取所有 owner 节点不可达 (大量
> 绑定到 127.0.0.1:14025/8088)，实际运行需 owner 重启暴露公网 listen").
>
> Root cause: anet 1.1.11 daemon by default announces all local interface
> addrs to ANS gossip — none of which are reachable from the public internet
> when the daemon runs behind home-network NAT.

## Confirmed via 5-node global TCP probe (check-host.net)

```json
host: 108.165.64.29:4001
br2 (Sao Paulo)    → "Connection refused"
ch2 (Zurich)       → "Connection refused"
fr2 (Paris)        → "Connection refused"
ir5 (Isfahan)      → "Connect timeout"
sg1 (Singapore)    → "Connection refused"
```

**Diagnosis**: TCP packets reach our public IP (would otherwise be timeout),
but the home router actively RST-rejects port 4001 inbound — i.e. NAT
forwarding is not configured.

## Fix 1 — Tell anet to ANNOUNCE the public address

Even if the router blocks it, configuring announce_addrs is the right
first step so that **once port forwarding is configured**, ANS gossip
already carries the correct address.

`~/.anet-pneuma-court-public/.anet/config.json`:

```json
{
  "announce_addrs": [
    "/ip4/108.165.64.29/tcp/4001",
    "/ip4/108.165.64.29/udp/4001/quic-v1"
  ]
}
```

Restart daemon after writing. Verify with `anet status` that `listen_addrs`
now shows the public IP. ✅ This was completed during the live debug.

## Fix 2 — Open port 4001 inbound (router or cloud)

**Option A: Home router port forwarding** (5–10 min, free)

1. Log into your router admin (typically http://192.168.1.1 or http://10.0.0.1)
2. Navigate to "Port Forwarding" / "NAT" / "Virtual Server" section
3. Add two rules:
   - External port `4001` TCP → internal IP (the laptop's LAN IP, e.g.
     `10.2.11.217`) port `4001`
   - External port `4001` UDP → same internal IP, port `4001` (for QUIC)
4. Save and reboot router if required

**Option B: Cloud server (most reliable, ~30 min)**

If your ISP is CGNAT (no real public IP) or you can't access the router,
deploy on a cloud VM with a real public IP:

1. Launch a small VM (Hetzner Cloud CX11 ~€4/mo, AWS t4g.nano free tier,
   or Aliyun ECS micro)
2. SSH in and bootstrap:
   ```bash
   curl -fsSL https://agentnetwork.org.cn/install.sh | sh -s -- --user
   git clone https://github.com/0xE1337/pneuma-court-p2p
   cd pneuma-court-p2p
   python3 -m venv .venv && source .venv/bin/activate
   pip install -e .
   cp .env.example .env  # fill in COURT_FINALIZER_PRIVATE_KEY
   bash scripts/serve-public-court.sh start
   ```
3. The cloud VM has a real public IP, so anet's auto-detected listen_addrs
   are already publicly routable — no `announce_addrs` config needed.

## Verification — confirm public dial works

After fix, re-run the 5-node global probe:

```bash
JOB=$(curl -s "https://check-host.net/check-tcp?host=YOUR_IP:4001&max_nodes=5" \
  -H "Accept: application/json")
REQ_ID=$(echo "$JOB" | python3 -c "import json,sys; print(json.load(sys.stdin)['request_id'])")
sleep 10
curl -s "https://check-host.net/check-result/$REQ_ID" \
  -H "Accept: application/json" | python3 -m json.tool
```

Expected: at least 3/5 nodes return `["1.234"]` (latency in seconds), not
`{"error": "Connection refused"}`.

## Lesson — pre-flight test must include a real cross-internet probe

Our 5/2 23:00 pre-flight ran a probe daemon on the same MacBook. libp2p
succeeded via `/ip4/127.0.0.1/tcp/4001` because that's a local loopback —
this gave a **false positive** for cross-internet reachability.

**For future hackathons**: pre-flight reachability MUST come from a node
outside the local LAN (cloud VM, mobile hotspot, friend's laptop). Same-
machine probes only validate the application layer, not the transport
layer.
