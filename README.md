# Pneuma Court — Multi-Juror Dispute Resolution as P2P Service

> **A P2P dispute-resolution service for Agent Network. Multiple AI jurors
> discover each other on anet ANS, deliberate independently via Claude, and
> reach a majority verdict — settled entirely in 🐚 Shell credits. No
> blockchain wallet required.**

`#AgentNetwork` · 南客松 S2 P2P Service Gateway 赞助赛道

---

## What this is

A working P2P service that turns "dispute resolution" into a multi-agent process:

1. **Court Agent** receives a dispute (caseId + evidence + category) over anet
2. **Discovers** N juror agents in the mesh by skill — `economic-juror`, `legal-juror`, `fairness-juror`, etc.
3. **Calls each juror** in parallel; each juror is a Claude-powered agent with a domain-specific prompt
4. **Aggregates verdicts** via majority vote
5. **Returns the ruling** to the caller — full verdict + per-juror reasoning, all settled in 🐚 Shell

```
caller (any anet node)
    │  anet svc call pneuma-court --body '{"caseId": 7, "category": "economic", ...}'
    ▼
┌─ pneuma-court (this repo) ─────────────────────────────────────┐
│  ① svc.discover(skill=f"{category}-juror")  →  N peers         │
│  ② parallel anet calls →  each juror returns {verdict, reason} │
│  ③ majority vote                                                │
│  ④ return {verdict, jurors[], tx_hash?}                        │
│     · default: settled in 🐚 Shell, no wallet needed            │
│     · opt-in: on-chain proof (see "On-chain bonus" below)       │
└─────────────────────────────────────────────────────────────────┘
```

---

## ⚡ 5-minute walkthrough

```bash
# 1 — Install anet daemon (one line)
curl -fsSL https://agentnetwork.org.cn/install.sh | sh
anet --version

# 2 — Clone + install this project
git clone https://github.com/0xE/pneuma-court-p2p
cd pneuma-court-p2p
python -m venv .venv && source .venv/bin/activate
pip install -e .

# 3 — Configure
cp .env.example .env
# Fill in: ANTHROPIC_API_KEY, ARC_RPC_URL, COURT_FINALIZER_PRIVATE_KEY

# 4 — One-shot demo: spawn 4 daemons + main court + 3 jurors + run a test case
bash scripts/demo.sh

# Expected output:
#   ✓ daemon-1..4 alive
#   ✓ pneuma-court registered on ANS (skill=dispute-court, cost=20🐚/call)
#   ✓ economic-juror registered (skill=economic-juror, cost=5🐚/call)
#   ✓ legal-juror registered    (skill=legal-juror,    cost=5🐚/call)
#   ✓ fairness-juror registered (skill=fairness-juror, cost=5🐚/call)
#   ▸ test case sent: caseId=7 category=economic
#   ▸ economic-juror votes: PLAINTIFF (reasoning: ...)
#   ▸ legal-juror    votes: DEFENDANT (reasoning: ...)
#   ▸ fairness-juror votes: PLAINTIFF (reasoning: ...)
#   ▸ majority verdict: PLAINTIFF
#   ▸ finalize tx: 0xabc...   (https://explorer.arc-testnet.example/tx/0xabc...)
#   ✓ DEMO PASSED in 47s
```

---

## How it uses anet

| anet capability | How we use it |
|---|---|
| `anet svc register` | Court + each juror registers a service with a skill tag and cost model |
| `anet svc discover --skill` | Court discovers jurors at runtime — no hard-coded peer IDs |
| `cost_model.per_call` | Caller pays court 20🐚, court pays each juror 5🐚, anet wallet handles settlement |
| `X-Agent-DID` header | We log which DID asked for the verdict (audit trail) |
| `svc_call_log` | Every call across 4 daemons writes audit rows; full chain reconstructable |

This is `examples/03-multi-agent-pipeline/` from the anet starter kit, repurposed for adversarial multi-perspective evaluation. **The default deliberation path runs entirely inside anet — no blockchain involved.**

---

## On-chain bonus (opt-in)

The default path is anet-only. If a caller wants a **portable, cross-network
proof** of the verdict (e.g. they're going to cite this ruling on a different
platform), they can opt in:

```jsonc
// case payload — extra fields
{
  "caseId": 7,
  "category": "economic",
  "evidence": "...",
  "want_onchain_proof": true,            // ← opt-in flag
  "beneficiary_address": "0xabc..."      // ← who the attestation is for
}
```

When this flag is set AND the court operator has enabled on-chain support
(`COURT_ENABLE_ONCHAIN=1` in `.env`), the court additionally writes the
verdict to the [`PneumaCourt`](docs/onchain-bonus.md) contract on Arc Testnet.

**Gas economics**:
- **Caller does NOT need an EVM wallet.** Settlement is in 🐚 Shell.
- Gas is paid by the **court operator's** wallet (`COURT_FINALIZER_PRIVATE_KEY`).
- The court recovers cost by charging more 🐚 Shell for proof-included calls
  (e.g. 50🐚 instead of 20🐚 — fully at the operator's discretion).

If on-chain fails (RPC down, wallet underfunded), the verdict is still
returned over anet — the off-chain ruling is the source of truth, the
on-chain write is a **portable receipt** of it.

See [docs/onchain-bonus.md](docs/onchain-bonus.md) for setup details and the
contract address on Arc Testnet.

---

## Why P2P (and not a centralized backend)?

Three reasons that make centralized impossible, not just inconvenient:

1. **Juror independence.** A single backend running all 3 jurors collapses the multi-perspective premise. Real independence requires separate processes, separate API keys, separate operators.
2. **Open marketplace of expertise.** Anyone with a Claude API key and a domain prompt can register a `<category>-juror` service. The court discovers them at runtime — the set of available expertise grows organically.
3. **On-chain accountability.** Each juror call writes an `svc_call_log` row in their own daemon. Combined with the on-chain finalize, you get a fully auditable ruling — who voted, when, for how much, with the verdict cryptographically anchored.

---

## Architecture

See [docs/architecture.md](docs/architecture.md) for the full diagram.

```
                              ┌─ daemon-1 (you)
                              │   pneuma-court main service
                              │
                              ├─ daemon-2 (you)
caller's anet node ──────────▶│   economic-juror
                              │
                              ├─ daemon-3 (you)
                              │   legal-juror
                              │
                              ├─ daemon-4 (you)
                              │   fairness-juror
                              │
                              └─ daemon-N (anyone)
                                  third-party jurors found via ANS discover
```

---

## Project layout

```
pneuma-court-p2p/
├── README.md                 ← you are here
├── LICENSE                   ← MIT
├── pyproject.toml            ← anet, fastapi, web3, anthropic
├── .env.example
├── abi/
│   └── PneumaCourt.json      ← contract ABI (read + finalize)
├── src/court_agent/
│   ├── main.py               ← uvicorn entry: court FastAPI service
│   ├── proxy.py              ← /proxy/dispute → discover + parallel call
│   ├── chain.py              ← web3.py: read getDispute / send finalize
│   ├── verdict.py            ← majority vote algorithm
│   └── jurors/
│       ├── cli.py            ← `court-juror economic` etc.
│       ├── economic.py       ← Claude prompt: economic-dispute expert
│       ├── legal.py          ← Claude prompt: legal expert
│       └── fairness.py       ← Claude prompt: fairness arbiter
├── scripts/
│   ├── install.sh            ← curl install anet
│   ├── four-node.sh          ← spawn 4 anet daemons
│   └── demo.sh               ← one-command demo
├── docs/
│   ├── architecture.md
│   └── pneuma-court-on-arc.md
└── examples/
    └── case-economic-dispute.json
```

---

## Status

✅ **Sprint 1 (functional code committed)** · 5/1
- [x] Repo bootstrapped, license, pyproject, ABI imported (50 entries)
- [x] `main.py` court FastAPI app + anet svc register
- [x] `jurors/{economic,legal,fairness}.py` + Claude system prompts
- [x] `jurors/_runner.py` shared juror runtime + `cli.py` entrypoint
- [x] `proxy.py` discover + parallel fan-out + aggregate
- [x] `chain.py` web3.py vote() + finalize() flow
- [x] `verdict.py` majority-vote + robust JSON-response parser
- [x] `scripts/four-node.sh` 4-daemon orchestration
- [x] `scripts/demo.sh` one-shot full demo
- [x] `examples/run_case.py` caller stub
- [x] **Self-tests: 17/17 pass** (verdict logic + JSON parser + ABI sanity)
- [ ] End-to-end run on real anet daemon (Sprint 2)
- [ ] On-chain finalize verified on Arc Testnet (Sprint 2)
- [ ] `docs/demo.mp4` 90s video (Sprint 2)

Submission: `2026-05-03` · Tag: `#AgentNetwork`

---

## License

MIT — see [LICENSE](LICENSE).
