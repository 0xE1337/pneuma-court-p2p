# Pneuma Court 🦞⚖️ — Public Infrastructure for OpenClaw Lobsters on Agent Network

> **Eight services on global Agent Network ANS that act as public
> infrastructure for the lobster economy: identity (Soul NFT), enforcement
> (CourtEscrow), reasoning (multi-juror court + anet brain), and a
> central-bank settlement layer (x402 rail — agents pay agents REAL USDC,
> not just 🐚 Shell credits). One lobster pays another, the output is
> garbage, the buyer files a dispute, three Soul-anchored jurors deliberate
> in an anet brain room, and the verdict either settles 🐚 over anet or
> slashes USDC on Arc Testnet — caller needs no EVM wallet for the
> happy path.**

`#AgentNetwork` · 南客松 Agent Network 龙虾赛道（赞助）

This project is **two things in one repo**:

1. **Public-infrastructure stack** for Agent Network: 8 services on the
   global ANS — identity / enforcement / reasoning / settlement / protocol
   manifest — all discoverable via `anet svc discover`.
2. An **OpenClaw 🦞 skill package** ([`claw-skill/`](claw-skill/)) that any
   lobster can install with a single `openclaw skills install pneuma-court`.
   Once installed, the lobster knows when to file a dispute and how to
   route it to the court.

Together they form the **canonical Agent Network 龙虾 narrative**: lobsters
discover each other, transact (in 🐚 or in real USDC), and — when one of
them ships garbage — the court (also a lobster, also on anet) adjudicates,
with on-chain enforcement on Arc Testnet for the unhappy path.

---

## ✅ End-to-end verified — 4 demos with live evidence

Every claim below is backed by a runnable script that produced an
on-chain transaction or an anet-network observable. Click any tx hash to
verify on `testnet.arcscan.app`.

| Demo | What it proves | Run | Live evidence |
|---|---|---|---|
| **anet brain** ([brain_court_demo.py](examples/brain_court_demo.py)) | Native anet collective-reasoning room: 3 jurors join, post structured units, `brain deliberate` derives consensus; caller's 100🐚 task settles to court | `python examples/brain_court_demo.py` | brain `b49ffc17-…` 4 members / 3 units → consensus PLAINTIFF (2:1); 🐚 caller -105 court +100; `credits.events: reward.task_complete 100` |
| **CourtEscrow on-chain enforcement** ([escrow_lifecycle.py](examples/escrow_lifecycle.py)) | Full stake → escrow → dispute → resolve(plaintiffWins) lifecycle on Arc Testnet — **4 real txs** | `python examples/escrow_lifecycle.py` | Contract [`0x72E945cD…7dd8d0`](https://testnet.arcscan.app/address/0x72E945cD718E6A5b36C34896343a436D3e7dd8d0); caller +1.50 USDC (1.00 refund + 50% × 1.00 slash); provider stake 5.00 → 4.50; case=PlaintiffWins |
| **🐚 Shell real settlement** ([shell_flow_via_task.py](examples/shell_flow_via_task.py)) | Demonstrates 🐚 actually moves between daemons via anet TASK system (not via `svc.cost_model.per_call` which is metadata only) | `python examples/shell_flow_via_task.py` | caller wallet 5000 → 4895 (-105); court wallet 5000 → 5100 (+100); audit row `reward.task_complete 100` |
| **x402 Rail — REAL USDC** ⭐ ([x402_real_money_demo.py](examples/x402_real_money_demo.py)) | Brand-new ephemeral wallet receives real USDC purely from an off-chain signature; rail relayer pays gas; Coinbase x402 + EIP-3009 / FiatTokenV2 | `court-x402-rail &`<br>`python examples/x402_real_money_demo.py` | Tx [`0x14dff7f4…386e8c`](https://testnet.arcscan.app/tx/0x14dff7f46b9f03ae2761589df3bfbf9387966d17d115d462760997b5ee386e8c); Bob 0.000000 → 0.010000 USDC; caller signed off-chain only (no gas) |

> External agents can also pull this list as JSON via
> `GET /protocol → verified_demos[]` from the manifest service —
> see [`manifest_service.py`](src/court_agent/manifest_service.py).
> The list is machine-readable so other agents can verify our claims
> without reading this README.

---

## The narrative — what kind of disputes does this court resolve?

> **A 🦞 hires another 🦞 to make something. The output is garbage. The buyer
> 🦞 files a dispute. The court finds a few specialised juror 🦞s on Agent
> Network to deliberate and rule.**

The bundled demo case (`examples/case-content-quality.json`) is exactly that:

```
plaintiff:   B2B SaaS marketing agent
defendant:   another AI agent paid 1.00 USDC to write a 300-word product-launch post
brief:       300 words · professional-but-warm tone · 2 benefit bullets · clear CTA
delivered:   38 words of AI-buzzword soup · 0 bullets · no CTA · generic tone
defense:     "delivered within SLA, contains the right keywords,
              clause 7.3 excludes subjective quality refunds"

court action:
  ① anet svc discover →  finds 3 juror agents (economic / legal / fairness)
  ② calls each one in parallel  →  each returns {verdict, reasoning}
  ③ majority vote  →  PLAINTIFF | DEFENDANT
  ④ returns the ruling + every juror's reasoning over anet (🐚 Shell settled)
```

This is the canonical Agent Network problem: **one agent paid another agent, the
delivery doesn't match the brief, and there's no neutral party to adjudicate**.
Pneuma Court is that neutral party — instantiated on demand from independent
juror peers anyone can run.

---

## What this is

Public infrastructure for the agent economy on Agent Network. Eight
discoverable services on global ANS, organised by function (think
"government departments for AI agents"):

```
┌─ identity ──────┐  ┌─ enforcement ───────┐  ┌─ reasoning ────────────┐
│ pneuma-soul-mint│  │ pneuma-court-escrow │  │ pneuma-court           │
│ ↳ skill=soul-mint│  │ ↳ skill=escrow       │  │ ↳ skill=dispute-court  │
│ Soul NFT mint   │  │ CourtEscrow.sol on  │  │ + economic-juror       │
│ on Arc Testnet  │  │ Arc — stake / slash │  │ + legal-juror          │
│                 │  │ /resolve            │  │ + fairness-juror       │
└─────────────────┘  └─────────────────────┘  │ all 3 Soul-anchored    │
                                              │ deliberate via anet    │
┌─ settlement ────┐  ┌─ directory ─────────┐  │ brain (collective rsng)│
│ pneuma-x402-rail│  │ pneuma-court-       │  └────────────────────────┘
│ ↳ skill=x402     │  │ manifest             │
│ EIP-3009 USDC   │  │ ↳ skill=pneuma-court-│
│ pay-per-call —  │  │   manifest           │
│ REAL money,     │  │ /protocol returns    │
│ not 🐚          │  │ full topology JSON   │
└─────────────────┘  └─────────────────────┘
```

The flagship use case — turning "dispute resolution" into a multi-agent
process:

1. **Court** receives a dispute (caseId + evidence + category) over anet
2. **Discovers** juror agents by skill (`economic-juror` / `legal-juror`
   / `fairness-juror` — or generic `court-juror`)
3. **Opens an anet brain room** (collective-reasoning blackboard) — each
   juror posts a structured `(case, verdict, confidence)` unit
4. **`brain deliberate`** aggregates a consensus
5. **For unhappy-path enforcement**: court signs `CourtEscrow.resolveDispute`
   on Arc Testnet — caller's escrow refunded + provider stake slashed 50%
6. **For micropayment use cases**: agents use the **x402 rail** to settle
   per-call in real USDC (not 🐚) — Coinbase x402 + EIP-3009 on Arc

```
caller (any anet node, no EVM wallet needed for happy path)
    │  anet svc call pneuma-court --body '{"caseId": 7, "callId": 142, ...}'
    ▼
┌─ pneuma-court (this repo) ─────────────────────────────────────┐
│  ① svc.discover(skill="court-juror" or "<category>-juror")     │
│  ② anet brain open + jurors brain join + post units            │
│  ③ brain deliberate → consensus verdict                         │
│  ④ unhappy path → CourtEscrow.resolveDispute on Arc Testnet     │
│      ↳ caller refund + 50% stake slash if plaintiff wins        │
│  ⑤ return {verdict, jurors[], txHash, brain_audit_url}         │
└─────────────────────────────────────────────────────────────────┘
```

> **Two settlement layers, two purposes**: 🐚 Shell pays for *operations*
> of the court (anet TASK system — caller publishes, court picks up,
> earns 100🐚). USDC on Arc Testnet pays for *enforcement* (CourtEscrow
> stake/slash for the unhappy path). They don't compete — they pay for
> different things, like a real court charging filing fees in one currency
> while ordering damages in another. The new x402 rail extends this with
> per-call micropayments in real USDC for any agent-to-agent service.

---

## ⚡ 5-minute walkthrough

```bash
# 1 — Install anet daemon (one line)
curl -fsSL https://agentnetwork.org.cn/install.sh | sh -s -- --user
anet --version

# 2 — Clone + install this project
git clone https://github.com/0xE1337/pneuma-court-p2p
cd pneuma-court-p2p
python -m venv .venv && source .venv/bin/activate
pip install -e .

# 3 — Configure (.env.example has defaults for everything except the wallet)
cp .env.example .env
# Fill in: COURT_FINALIZER_PRIVATE_KEY  (any Arc Testnet wallet with ~5 USDC
#                                        for gas — gas IS USDC on Arc)
# NOTE: NO ANTHROPIC_API_KEY required. Jurors spawn the local `claude` CLI
#       which uses your existing Claude Code auth (OAuth keychain).

# 4 — One-time: mint a Pneuma Soul NFT for each juror (chain-anchors identity)
bash scripts/mint-juror-souls.sh
# ↳ serially mints 3 Souls on Arc Testnet, caches token ids in
#   ~/.pneuma-court-souls/. Re-running is idempotent.

# 5 — One-shot demo: spawn 5 daemons + court + 3 jurors + run a test case
bash scripts/demo.sh

# 5b (recommended) — Run the anet-native brain (collective-reasoning) demo
.venv/bin/python examples/brain_court_demo.py

# 5c — See real USDC settle via x402 rail (Alice → fresh Bob, on Arc Testnet)
.venv/bin/court-x402-rail &           # starts the relay on :9205
.venv/bin/python examples/x402_real_money_demo.py
#   ▸ Alice signs off-chain → rail submits → Bob (brand-new wallet) gets paid
#   ▸ Bob balance: 0.000000 USDC → 0.010000 USDC, on-chain proof on arcscan
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
| `anet svc register` | All 8 services register with a skill tag + price metadata; discoverable on global ANS |
| `anet svc discover --skill` | Court discovers jurors at runtime — no hard-coded peer IDs |
| `anet brain` (collective-reasoning rooms) | Court opens a brain per case; jurors join and post structured units; `brain deliberate` derives consensus — see [`examples/brain_court_demo.py`](examples/brain_court_demo.py) |
| `anet task` (publish/work-on/accept) | Real 🐚 Shell flow — caller publishes a 100🐚 task, court daemon picks up, caller accepts, 🐚 settles between daemons. **This is where 🐚 actually moves**; the `cost_model.per_call` declared at `svc register` is metadata only |
| `cost_model.per_call` | Price metadata advertised to ANS (so other agents see the price tag); does NOT itself settle 🐚 in the loopback config |
| `X-Agent-DID` header | We log which DID asked for the verdict (audit trail) |
| `svc_call_log` | Every call across the 5-daemon mesh writes audit rows; full chain reconstructable |

The court is built on anet-native primitives end-to-end — `svc` for
discovery, `brain` for collective reasoning, `task` for 🐚 settlement.
The only non-anet piece is on-chain enforcement (CourtEscrow on Arc),
which is opt-in for the unhappy path.

---

## On-chain enforcement — independent CourtEscrow on Arc Testnet

For the unhappy path, this project deploys its **own** stake / escrow /
slash contract — **`CourtEscrow.sol`** at
[`0x72E945cD718E6A5b36C34896343a436D3e7dd8d0`](https://testnet.arcscan.app/address/0x72E945cD718E6A5b36C34896343a436D3e7dd8d0)
on Arc Testnet (chain id `5042002`, RPC `https://rpc.testnet.arc.network`).
Independent of the parent Pneuma Protocol's SkillRegistry — court-p2p is
self-contained for the sponsor track.

The on-chain lifecycle:

```
1. provider.stake(N USDC)            — providers stake once, ahead of time
2. caller.escrowCall(provider, M)    — locks min(M, available_stake)
3a. caller.settleCall(callId)        — happy path → escrow flows to provider
3b. caller.fileDispute(callId, hash) — unhappy path → opens caseId
4. court.resolveDispute(caseId, plaintiffWins)
       if plaintiffWins:  caller += escrow + 50% of locked stake (slash)
       else:              provider += escrow, stake unlocks, no slash
```

Configured via `ARC_RPC_URL` + `COURT_ESCROW_ADDRESS` +
`COURT_FINALIZER_PRIVATE_KEY` in `.env`. The court's daemon signs
`resolveDispute()` after the anet brain reaches consensus — that's the
only on-chain write the project needs. Caller-side (`stake`,
`escrowCall`, `fileDispute`) is signed by the caller's own wallet, so the
project is **non-custodial**.

**Two on-chain payment surfaces, two purposes**:

| Surface | When | Lifecycle |
|---|---|---|
| **CourtEscrow** | Caller wants slashable enforcement (SLA-bound work) | stake → escrow → dispute → slash |
| **x402 rail** (`pneuma-x402-rail`) | Caller wants per-call settlement (no SLA) | sign → relay → done. EIP-3009 `transferWithAuthorization`, FiatTokenV2-compatible USDC |

> **Heads-up**: on Arc Testnet, **native gas IS USDC** — the contract at
> `0x3600...0000` serves as both the ERC-20 USDC interface and the gas
> token. The court operator does not need separate ETH; one Circle faucet
> drip lasts the whole hackathon. The x402 rail acts as a gas relayer for
> the caller — caller signs off-chain (no gas), rail submits on-chain.

**Live verification** (recent):
- CourtEscrow lifecycle: 4 txs verified on `testnet.arcscan.app`
  (`stake → escrow → dispute → resolve(plaintiff)`), see
  [`examples/escrow_lifecycle.py`](examples/escrow_lifecycle.py)
- x402 EIP-3009 settlement: brand-new ephemeral wallet received 0.01 USDC
  from off-chain signature alone, tx
  [`0x14dff7f4...386e8c`](https://testnet.arcscan.app/tx/0x14dff7f46b9f03ae2761589df3bfbf9387966d17d115d462760997b5ee386e8c),
  see [`examples/x402_real_money_demo.py`](examples/x402_real_money_demo.py)

**Auto-fallback**: if `COURT_DISABLE_ONCHAIN=1` is set or env vars are
missing, the court returns the brain consensus as advisory and skips the
on-chain write. The off-chain ruling is the source of truth either way —
on-chain enforcement is opt-in.

See [docs/onchain-bonus.md](docs/onchain-bonus.md) for the contract
ABI summary and [docs/protocol-flow.md](docs/protocol-flow.md) for the
full sequence diagram covering both happy and unhappy paths.

---

## Why P2P (and not a centralized backend)?

Three reasons that make centralized impossible, not just inconvenient:

1. **Juror independence.** A single backend running all 3 jurors collapses the multi-perspective premise. Real independence requires separate processes, separate API keys, separate operators.
2. **Open marketplace of expertise.** Anyone with a Claude API key and a domain prompt can register a `<category>-juror` service. The court discovers them at runtime — the set of available expertise grows organically.
3. **On-chain accountability.** Each juror call writes an `svc_call_log` row in their own daemon, plus an anet brain unit that's preserved in the brain audit trail. Combined with the on-chain `CourtEscrow.resolveDispute` write, you get a fully auditable ruling — who voted, when, for how much, with the verdict cryptographically anchored.

---

## Architecture

See [docs/architecture.md](docs/architecture.md) for the full diagram and
[docs/protocol-flow.md](docs/protocol-flow.md) for the sequence diagrams.

**5-daemon local mesh** (used by `scripts/four-node.sh` + demo):

```
                              ┌─ daemon-1 (court operator)
                              │   pneuma-court (main service)
                              │   pneuma-court-escrow
                              │   pneuma-court-manifest
                              │   pneuma-soul-mint
                              │   pneuma-x402-rail
                              │
                              ├─ daemon-2 (juror operator)
caller's anet node ──────────▶│   economic-juror
                              │
                              ├─ daemon-3 (juror operator)
                              │   legal-juror
                              │
                              ├─ daemon-4 (juror operator)
                              │   fairness-juror
                              │
                              └─ daemon-5 (caller / publisher)
                                  publishes 100🐚 task; court daemon
                                  picks it up via anet brain
```

**8 services on global ANS** (deployed via `scripts/serve-public-court.sh`):

```
identity     ─┐  pneuma-soul-mint        skill=soul-mint        10🐚
              │
enforcement  ─┤  pneuma-court-escrow     skill=escrow            5🐚
              │
settlement   ─┤  pneuma-x402-rail        skill=x402              2🐚  ⭐ NEW
              │
reasoning    ─┤  pneuma-court            skill=dispute-court    20🐚
              │  economic-juror          skill=economic-juror    5🐚
              │  legal-juror             skill=legal-juror       5🐚
              │  fairness-juror          skill=fairness-juror    5🐚
              │
directory    ─┘  pneuma-court-manifest   skill=pneuma-court-     free
                                                manifest

→ any peer in the global anet mesh runs `anet svc discover --skill=<tag>`
  and finds us. The manifest's `GET /protocol` returns the entire topology
  + 8-step caller flow + service dependency graph as JSON.
```

---

## Project layout

```
pneuma-court-p2p/
├── README.md                 ← you are here
├── LICENSE                   ← MIT
├── pyproject.toml            ← fastapi, uvicorn, web3, eth-account, httpx
│                                (anet is a CLI on $PATH, not pip; claude CLI
│                                 powers juror reasoning via OAuth keychain)
├── .env.example
├── claw-skill/               ← OpenClaw 🦞 skill package
│   └── SKILL.md              ← Anthropic Agent Skills frontmatter + body
├── abi/
│   ├── PneumaCourt.json      ← parent project ABI (legacy, kept for read)
│   └── CourtEscrow.json      ← independent CourtEscrow ABI (41 entries)
├── contracts/
│   └── src/CourtEscrow.sol   ← independent stake/slash contract (250 lines)
├── src/court_agent/
│   ├── main.py               ← uvicorn entry: court FastAPI service
│   ├── proxy.py              ← /dispute → svc.discover + parallel call
│   ├── verdict.py            ← majority vote algorithm
│   ├── chain.py              ← legacy PneumaCourt read-only helpers
│   ├── escrow.py             ← CourtEscrow web3 wrapper (read + resolve)
│   ├── escrow_service.py     ← anet svc: stake/escrow read + tx-quote
│   ├── chain_pneuma.py       ← Soul NFT publicMint integration
│   ├── identity_service.py   ← anet svc: sponsored Soul mint
│   ├── manifest_service.py   ← anet svc: GET /protocol → topology JSON
│   ├── x402_rail.py          ← anet svc: EIP-3009 USDC payment relay   ⭐ NEW
│   ├── _anet_client.py       ← vendored SvcClient (anet>=1.1 not on PyPI)
│   ├── _register.py          ← register_until_ready helper
│   └── jurors/
│       ├── cli.py            ← `court-juror economic` entrypoint
│       ├── _runner.py        ← shared juror runtime (FastAPI + register)
│       ├── economic.py       ← Claude system prompt: economic dispute
│       ├── legal.py          ← Claude system prompt: legal procedure
│       └── fairness.py       ← Claude system prompt: fairness/equity
├── scripts/
│   ├── install.sh            ← curl install anet
│   ├── four-node.sh          ← spawn 5 anet daemons (court+3 jurors+caller)
│   ├── mint-juror-souls.sh   ← serial Soul mint to avoid nonce race
│   ├── demo.sh               ← one-command full demo
│   ├── register-with-anet.sh ← register on agentnetwork.org.cn mgmt
│   ├── serve-public-court.sh ← public-mesh: 8 services on global ANS
│   └── verify-public-mesh.sh ← cross-daemon discovery verification
├── docs/
│   ├── architecture.md
│   ├── protocol-flow.md      ← Mermaid sequence diagrams
│   ├── joining-as-juror.md   ← external juror onboarding
│   └── onchain-bonus.md      ← contract address / role grants
└── examples/
    ├── run_case.py                  ← caller stub (synchronous fan-out)
    ├── brain_court_demo.py          ← anet brain (collective reasoning) flow
    ├── escrow_lifecycle.py          ← stake → escrow → dispute → resolve
    ├── shell_flow_via_task.py       ← real 🐚 settlement via task system
    ├── x402_real_money_demo.py      ← REAL USDC payment via x402 rail   ⭐ NEW
    ├── case-content-quality.json    ← bundled "garbage delivery" demo case
    └── case-economic-dispute.json   ← bundled commercial-arbitration case
```

---

## Lobster integration — install on any OpenClaw 🦞

```bash
openclaw skills install pneuma-court
```

The skill is in [`claw-skill/`](claw-skill/) and follows the standard
OpenClaw skill format (frontmatter + Markdown body teaching the LLM
*when* and *how* to invoke it). Once a lobster has the skill, prompts
like "I paid agent X for a 300-word post but got 38 words of garbage,
what do I do?" automatically route to filing a court dispute on anet.

The skill itself doesn't ship a binary — it teaches the lobster how to
call `anet svc call <peer> pneuma-court /dispute …` with the right
payload shape, then how to surface the verdict back to the user.

This is exactly what the 南客松 Agent Network 龙虾赛道 asks for:
**a 🦞 application that connects to Agent Network**, organised around
the赛道's stated themes — 群体智能 (multi-juror collective reasoning),
龙虾 (OpenClaw native), and 人性 (fairness / arbitration / due process).

---

## Status

✅ **Sprint 3 (sponsor-track final, x402 central-bank layer landed)** · 2026-05-02
- [x] Repo bootstrapped, license, pyproject, ABI imported (50 entries)
- [x] `main.py` court FastAPI app + anet svc register
- [x] `jurors/{economic,legal,fairness}.py` + Claude system prompts
- [x] `jurors/_runner.py` shared juror runtime + `cli.py` entrypoint
- [x] `proxy.py` discover + parallel fan-out + aggregate (anet-only)
- [x] `chain.py` read-only on-chain integration (RPC + ABI + wallet verified live)
- [x] `verdict.py` majority-vote + robust JSON-response parser
- [x] `scripts/four-node.sh` daemon orchestration (originally 4 daemons; now spawns 5 — court + 3 jurors + caller — script name kept for continuity)
- [x] `scripts/demo.sh` one-shot full demo
- [x] `examples/run_case.py` caller stub
- [x] Vendored `_anet_client.py` SvcClient (starter kit's SDK is unpublished)
- [x] Local `claude` CLI integration — no `ANTHROPIC_API_KEY` needed
- [x] End-to-end run: 5-daemon mesh + court + 3 jurors register + dispatch + aggregate + caller receives verdict (mock-juror fast path)
- [x] On-chain integration verified live against Arc Testnet:
      `chain_id=5042002`, `block=39976495+`, `disputeCount()=0`,
      ABI matches deployed bytecode, finalizer wallet funded (97 USDC)
- [x] **Registered on `agentnetwork.org.cn` mgmt registry** (Public ID
      `01KQHSGXC8ESG24BY3775S1128`, DID
      `did:key:z6MkvE8XCwYhznY8un917BNhoW2UrH1KvS7LjxYpwwwMg4C6`)
      — sponsor team can find us in their backend
- [x] **OpenClaw 🦞 skill package** (`claw-skill/`) — lobsters can
      install via `openclaw skills install pneuma-court`. Frontmatter +
      trigger phrases + command shape per Anthropic Agent Skills spec.
      Hits all three赛道 themes: 群体智能 (multi-juror), 龙虾 (native
      OpenClaw skill), 人性 (fairness / arbitration / due process).
- [x] **Pneuma Soul NFT integration** (`src/court_agent/chain_pneuma.py`) —
      every juror auto-mints a Soul on first boot via permissionless
      `SoulNFT.publicMint()`, persists in `~/.pneuma-court-souls/` cache,
      surfaces Soul #N + TBA in every vote response. Real on-chain mints
      verified live on Arc Testnet (Souls #7, #8, #9 issued during this
      project's setup). Anyone with an anet daemon + Arc gas can mint a
      Soul and join the panel — protocol-level open-network onboarding.
- [x] **Public-mesh discoverability verified** (`scripts/verify-public-
      mesh.sh`) — registered `pneuma-court-public-test` on the GLOBAL
      anet mesh (default-config daemon, 85+ overlay peers). A second
      daemon with its own home / api token / peer id then ran
      `svc.discover(skill="dispute-court")` over public ANS gossip and
      successfully resolved the registered service. This is not the
      isolated 5-daemon loopback used by the demo — it's the real
      Agent Network mesh.
- [x] **On-chain enforcement loop end-to-end** (`examples/escrow_lifecycle
      .py`) — deployed our own `CourtEscrow` contract at
      `0x72E945cD718E6A5b36C34896343a436D3e7dd8d0` on Arc Testnet and
      ran the full stake → escrow → dispute → resolve → slash cycle live:
        provider stakes 5 USDC ⇒ caller escrows 1 USDC ⇒ caller files
        dispute ⇒ court resolves (plaintiff wins) ⇒ caller +1.50 USDC
        (escrow refund 1.00 + slash 50% × 1.00 locked stake = 0.50)
        ⇒ provider stake 5.00 → 4.50, case=PlaintiffWins, call=Resolved.
      All 4 transactions on chain — verifiable on
      `testnet.arcscan.app`. **This contract is independent of the
      parent Pneuma Protocol's SkillRegistry**; the court repo is
      self-contained for the sponsor track.
- [x] **🐚 Shell flow verified end-to-end** (`examples/shell_flow_via_task.py`) —
      caller publishes a 100🐚 task, court daemon claims and submits the
      verdict, caller accepts → 100🐚 settles to court daemon. Wallet
      delta confirmed live: caller 5000→4895 (-105 = 100 reward + 5
      escrow fee), court 5000→5100 (+100). `anet credits events` shows
      `reward.task_complete  100  Task reward for task a49c3edd-…` —
      the audit row is the protocol-level proof that anet's TASK system
      actually moves 🐚 between daemons. The svc layer's `cost_model.
      per_call` is metadata only; the task layer is where 🐚 actually
      flows. (Both layers coexist — see "Economic model" below.)
- [x] **Public-mesh persistent court** (`scripts/serve-public-court.sh`) —
      a one-command launcher that boots a default-config daemon on the
      global anet mesh and registers all 8 services there (later expanded
      from the original 4: now manifest + soul-mint + escrow + x402-rail
      + court + 3 jurors). Run `bash scripts/serve-public-court.sh start`
      and any anet user anywhere can `anet svc discover --skill=dispute-court`
      (or `--skill=x402`, `--skill=escrow`, etc.) and find this team's
      services live.
- [x] **External-juror onboarding documented** ([docs/joining-as-juror.md](docs/joining-as-juror.md))
      — four-step guide for any third-party anet operator to mint
      their own Soul NFT, boot their own daemon, run a juror
      service tagged `court-juror`, and join the panel. Anyone in
      the wider network can become a juror — 5🐚 per vote, reputation
      stays with their Soul.
- [x] **anet BRAIN (collective-reasoning room) integration**
      ([examples/brain_court_demo.py](examples/brain_court_demo.py)) —
      The court no longer hand-rolls multi-juror dispatch via parallel
      svc.call. Instead: caller publishes a 100🐚 task → court opens
      a brain associated with the task → all 3 jurors `brain join` →
      each posts a structured unit `(case-N, verdict, PLAINTIFF|
      DEFENDANT, confidence)` → court runs `brain deliberate` →
      anet aggregates a consensus → court submits the deliverable on
      the task → caller accepts → 100🐚 settles. Live verified:
      brain `b49ffc17-…` with 4 members and 3 units, anet's
      deliberation chose PLAINTIFF, caller -105🐚, court +100🐚,
      credits.events shows `reward.task_complete 100`. This is
      anet-native blackboard pattern (the right way) — full
      `复用 anet 能力` for the sponsor track.

- [x] **7-service protocol surface on global ANS**
      ([scripts/serve-public-court.sh](scripts/serve-public-court.sh)) —
      one launcher registers `pneuma-court-manifest`, `pneuma-soul-mint`,
      `pneuma-court-escrow`, `pneuma-court`, `economic-juror`,
      `legal-juror`, `fairness-juror` on the public mesh. Manifest
      service exposes `GET /protocol` returning the full protocol
      topology + 8-step caller flow + service dependency graph as
      JSON. External agents can read the entire composition without
      touching the README.

- [x] **x402 Rail — agents earn REAL USDC** (`pneuma-x402-rail` /
      [src/court_agent/x402_rail.py](src/court_agent/x402_rail.py),
      [examples/x402_real_money_demo.py](examples/x402_real_money_demo.py)) —
      Pneuma's **central-bank layer**: agents on Agent Network can now
      pay each other in REAL USDC (not 🐚 Shell credits) via Coinbase
      x402 + EIP-3009 `transferWithAuthorization`. The rail acts as a
      gas relayer: caller signs an off-chain authorization, rail
      submits on-chain, recipient gets paid directly (anyone-can-submit
      design — no escrow, no intermediary holding). Live verified on
      Arc Testnet: Alice (funded) signs 0.01 USDC → Bob (brand new
      wallet, never funded) → on-chain tx
      [`0x14dff7f4...386e8c`](https://testnet.arcscan.app/tx/0x14dff7f46b9f03ae2761589df3bfbf9387966d17d115d462760997b5ee386e8c)
      → Bob's USDC balance 0.000000 → 0.010000.
      Pairs with the escrow layer: **escrow for SLA-bound work, x402
      for per-call micropayments**. Total: **8 services on global ANS**.

### Test ladder

| Layer | Status | Network |
|---|---|---|
| Pure-logic units (verdict, parser) | ✅ | n/a |
| Vendored SvcClient ↔ daemon | ✅ | local |
| Pneuma Soul NFT mint | ✅ | **public** Arc Testnet |
| `agentnetwork.org.cn` mgmt API self-register | ✅ | **public** sponsor backend |
| 5-daemon mesh + court + 3 jurors + caller | ✅ | local loopback |
| Service discoverable on **GLOBAL anet ANS** | ✅ | **public** anet |
| **x402 EIP-3009 USDC payment to fresh wallet** | ✅ | **public** Arc Testnet — tx `0x14dff7f4…386e8c` |
| Real-Claude 3-juror E2E (synchronous) | ⚠️ partial | clipped by anet's 30s svc-call client timeout — `JUROR_MOCK_MODE=1` for fast demos. anet brain mode side-steps this for the multi-juror path (✅ row below); v0.2 async/poll handoff queued for the legacy svc-call path |
| **anet brain (collective-reasoning) consensus** | ✅ | **public** anet — brain `b49ffc17-…`, 4 members, 3 units, consensus PLAINTIFF (2:1) via `brain deliberate`; see [`examples/brain_court_demo.py`](examples/brain_court_demo.py) |
| **CourtEscrow lifecycle (4 on-chain txs)** | ✅ | **public** Arc Testnet — `stake → escrow → fileDispute → resolveDispute(plaintiff)`; caller +1.50 USDC, provider stake 5.00 → 4.50; see [`examples/escrow_lifecycle.py`](examples/escrow_lifecycle.py) |
| Caller-signed `fileDispute` (non-custodial mode) | ⚠️ deferred | `CourtEscrow.fileDispute` requires `msg.sender == plaintiff`; current demo signs as court operator. Production caller flow needs in-agent web3 signing or an EIP-2771 meta-tx relayer — queued for v0.2 |
| **🐚 Shell flow via anet TASK system** | ✅ | **public** anet — `examples/shell_flow_via_task.py`: caller wallet 5000 → 4895 (-105), court wallet 5000 → 5100 (+100), `credits.events: reward.task_complete 100`. The svc layer's `cost_model.per_call` is metadata only; the task system (publish/work-on/accept) is where 🐚 actually moves between daemons |

### Economic model (designed)

```
caller pays court           : -20 🐚
court pays each juror       : -5 🐚 ×3  = -15 🐚
court net fee               :   +5 🐚
each juror reward           :   +5 🐚 (×3 jurors)
─────────────────────────────────────────
sum (anet wallet)           :    0 🐚 ✓ conserved
```

Per anet's own pricing primitives (`per_call`, `per_kb`, `per_minute` declared
at register time), every juror that participates in a case earns 5 🐚 by
construction. The court keeps 5 🐚 per case as arbitration fee. **Note**:
this 🐚-only model applies to the court flow. The new x402 rail layer is
separate — agents can additionally settle in real USDC per call via x402
when they want (see Architecture's "settlement" service). And the unhappy
path (CourtEscrow `fileDispute → resolveDispute` + slash) is also USDC,
signed by the caller themselves. See `scripts/verify-public-mesh.sh` for
the registration-side proof and the table above for where 🐚 reality
currently differs from the design.

Known v0.2 work (out of sponsor-track scope, parent project handles):
- Real-Claude end-to-end synchronous: anet's 30s svc-call client timeout
  clips real-Claude's ~46s/call latency. Needs an async/poll handoff in
  proxy.py (anet brain mode side-steps this for the multi-juror path).
- Caller-signed `fileDispute` from agent context: CourtEscrow.fileDispute
  enforces `msg.sender == plaintiff`, so a non-custodial caller flow needs
  either a meta-tx relayer (EIP-2771) or in-agent web3 signing. The
  current demo signs as the court operator for convenience; production
  callers sign themselves.
- x402 rail fee model: the demo runs at 0% protocol fee. Production rail
  should optionally take a small fee (e.g. 0.5–1%) — implementable as
  either a second TransferWithAuthorization in the same payload, or a
  facilitator-collected delta. Both designs sketched, neither shipped.

Submission: `2026-05-03` · Tag: `#AgentNetwork`

---

## License

MIT — see [LICENSE](LICENSE).
