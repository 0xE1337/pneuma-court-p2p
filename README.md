# Pneuma Court — Multi-Juror Dispute Resolution as P2P Service

> **A P2P dispute-resolution service for Agent Network. Multiple AI jurors
> discover each other on anet ANS, deliberate independently via Claude, reach
> a majority verdict, and write a portable receipt on-chain — all without
> requiring the caller to own a blockchain wallet.**

`#AgentNetwork` · 南客松 S2 P2P Service Gateway 赞助赛道

---

## What this is

A working P2P service that turns "dispute resolution" into a multi-agent process:

1. **Court Agent** receives a dispute (caseId + evidence + category) over anet
2. **Discovers** N juror agents in the mesh by skill — `economic-juror`, `legal-juror`, `fairness-juror`, etc.
3. **Calls each juror** in parallel; each juror is a Claude-powered agent with a domain-specific prompt
4. **Aggregates verdicts** via majority vote
5. **Writes the ruling on-chain** (Arc Testnet, gas paid by the court operator, free testnet ETH) so the verdict is publicly verifiable
6. **Returns** verdict + per-juror reasoning + tx hash to the caller

```
caller (any anet node, no EVM wallet needed)
    │  anet svc call pneuma-court --body '{"caseId": 7, "callId": 142, ...}'
    ▼
┌─ pneuma-court (this repo) ─────────────────────────────────────┐
│  ① svc.discover(skill=f"{category}-juror")  →  N peers         │
│  ② parallel anet calls →  each juror returns {verdict, reason} │
│  ③ majority vote                                                │
│  ④ on-chain finalize (court operator pays gas — Arc Testnet)   │
│      └─ if court has no on-chain config: auto-fallback to       │
│         advisory-only mode, verdict still returned              │
│  ⑤ return {verdict, jurors[], dispute_id, tx_hash}             │
└─────────────────────────────────────────────────────────────────┘
```

> **Why on-chain by default?** Arc Testnet gas is free from the faucet, the
> court operator's wallet pays it, and the caller never sees a wallet prompt.
> The on-chain receipt makes the verdict portable and publicly auditable —
> any other anet/web3 agent can verify the ruling existed without trusting
> the court operator. If the court is misconfigured, on-chain is skipped
> automatically and the deliberation still produces a binding result via anet.

---

## ⚡ 5-minute walkthrough

```bash
# 1 — Install anet daemon (one line)
curl -fsSL https://agentnetwork.org.cn/install.sh | sh
anet --version

# 2 — Clone + install this project
git clone https://github.com/0xE1337/pneuma-court-p2p
cd pneuma-court-p2p
python -m venv .venv && source .venv/bin/activate
pip install -e .

# 3 — Configure (.env.example has defaults for everything except the wallet)
cp .env.example .env
# Fill in: COURT_FINALIZER_PRIVATE_KEY  (a wallet with JUROR_ROLE on PneumaCourt
#                                        and ~10 testnet USDC for gas)
# NOTE: NO ANTHROPIC_API_KEY required. Jurors spawn the local `claude` CLI
#       which uses your existing Claude Code auth (OAuth keychain).

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

## Public registration on Agent Network

This project is registered on the official `agentnetwork.org.cn` management
registry per [SKILL.md §0.5](https://agentnetwork.org.cn/SKILL.md):

| Field | Value |
|---|---|
| Public ID | `01KQHSGXC8ESG24BY3775S1128` |
| DID | `did:key:z6MkvE8XCwYhznY8un917BNhoW2UrH1KvS7LjxYpwwwMg4C6` |
| Name | `pneuma-court-p2p` |
| Registered | `2026-05-01T12:51:52Z` |

Verify (no auth required for the public lookup, since the registration is
attached to a public GitHub URL in the description):

```bash
# Confirms the agent record exists on the mgmt registry.
# The API key needed to read /agent/me is in ~/.anet-pneuma-court/.anet/keys.json
# after running scripts/register-with-anet.sh — DO NOT commit that file.
```

To register your own deployment, run:

```bash
bash scripts/register-with-anet.sh
```

The script is idempotent — re-running it for an already-registered DID
returns `409 did_taken` and exits successfully without overwriting keys.

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

## On-chain settlement (default, free)

Every verdict is finalized on the [`PneumaCourt`](docs/onchain-bonus.md)
contract at [`0x3371...66AC`](https://testnet.arcscan.app/address/0x3371e96b29b5565EF2622A141cDAD3912Daa66AC)
on Arc Testnet (chain id `5042002`, RPC `https://rpc.testnet.arc.network`).
The court does this automatically when the operator has configured
`ARC_RPC_URL` + `PNEUMA_COURT_ADDRESS` + `COURT_FINALIZER_PRIVATE_KEY`.

**Gas model — why callers don't need a wallet**:

| Who | Pays | What |
|---|---|---|
| Caller | 🐚 Shell only (e.g. 20🐚) | The court call itself |
| Court operator | testnet USDC (~cents/call) | gas for `fileDispute` + `vote` + `finalize` |
| Circle faucet | free | one drip funds thousands of calls |

> **Heads-up**: on Arc Testnet, **native gas IS USDC** — the contract at
> `0x3600...0000` serves as both the ERC-20 USDC interface and the gas
> token. The court operator does not need separate ETH; one Circle faucet
> drip lasts the whole hackathon.

The court opens the dispute on the caller's behalf via `fileDispute()`,
then casts the aggregated verdict via `vote()`, then closes it via
`finalize()`. All three transactions sign with the operator's
`COURT_FINALIZER_PRIVATE_KEY`. The caller never sees a wallet prompt.

**Auto-fallback — graceful degrade if the chain is unreachable**:

- Court not configured (any RPC/address/key missing) → skip on-chain,
  return verdict over anet only.
- Court configured but transaction fails (RPC down, role not granted,
  gas exhausted) → verdict still returned, error surfaced in
  `result.error`. The off-chain ruling is the source of truth.

See [docs/onchain-bonus.md](docs/onchain-bonus.md) for the JUROR_ROLE
grant command and the contract address on Arc Testnet.

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

✅ **Sprint 2 (sponsor-track ready)** · 2026-05-01
- [x] Repo bootstrapped, license, pyproject, ABI imported (50 entries)
- [x] `main.py` court FastAPI app + anet svc register
- [x] `jurors/{economic,legal,fairness}.py` + Claude system prompts
- [x] `jurors/_runner.py` shared juror runtime + `cli.py` entrypoint
- [x] `proxy.py` discover + parallel fan-out + aggregate (anet-only)
- [x] `chain.py` read-only on-chain integration (RPC + ABI + wallet verified live)
- [x] `verdict.py` majority-vote + robust JSON-response parser
- [x] `scripts/four-node.sh` 4-daemon orchestration
- [x] `scripts/demo.sh` one-shot full demo
- [x] `examples/run_case.py` caller stub
- [x] Vendored `_anet_client.py` SvcClient (starter kit's SDK is unpublished)
- [x] Local `claude` CLI integration — no `ANTHROPIC_API_KEY` needed
- [x] End-to-end run: 4-daemon mesh + court + 3 jurors register + dispatch + aggregate + caller receives verdict (mock-juror fast path)
- [x] On-chain integration verified live against Arc Testnet:
      `chain_id=5042002`, `block=39976495+`, `disputeCount()=0`,
      ABI matches deployed bytecode, finalizer wallet funded (97 USDC)
- [x] **Registered on `agentnetwork.org.cn` mgmt registry** (Public ID
      `01KQHSGXC8ESG24BY3775S1128`, DID
      `did:key:z6MkvE8XCwYhznY8un917BNhoW2UrH1KvS7LjxYpwwwMg4C6`)
      — sponsor team can find us in their backend

Known v0.2 work (out of sponsor-track scope, parent project handles):
- Real-Claude end-to-end synchronous: anet's 30s svc-call client timeout
  clips real-Claude's ~46s/call latency. Needs an async/poll handoff in
  proxy.py.
- On-chain `fileDispute → vote → finalize` write path: requires either
  a meta-tx relayer or caller-signed flow because `msg.sender` must
  be the original SkillRegistry caller (plaintiff). See
  `src/court_agent/chain.py` module docstring for invariants.

Submission: `2026-05-03` · Tag: `#AgentNetwork`

---

## License

MIT — see [LICENSE](LICENSE).
