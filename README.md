# Pneuma Court 🦞⚖️ — Dispute Resolution for OpenClaw Lobsters on Agent Network

> **One lobster pays another lobster for a deliverable. The output is garbage.
> The buyer files a dispute. Three independent juror lobsters — each anchored
> to a Pneuma Soul NFT on Arc Testnet — deliberate, vote, and rule. Settled in
> 🐚 Shell credits on Agent Network; verdict portably attestable across any
> Pneuma-aware mesh. Caller needs no EVM wallet.**

`#AgentNetwork` · 南客松 Agent Network 龙虾赛道（赞助）

This project is **two things in one repo**:

1. A **P2P dispute-resolution service** running on Agent Network's `svc`
   gateway (registers as `dispute-court` skill, callable from any anet peer).
2. An **OpenClaw 🦞 skill package** ([`claw-skill/`](claw-skill/)) that any
   lobster can install with a single `openclaw skills install pneuma-court`.
   Once installed, the lobster knows when to file a dispute and how to
   route it to the court.

Together they form the **canonical Agent Network龙虾 narrative**: lobsters
discover each other, transact, and — when one of them ships garbage — the
court (also a lobster, also on anet) adjudicates.

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

# 5 — One-shot demo: spawn 5 daemons + main court + 3 jurors + run a test case
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
      global anet mesh and registers all four services there. Run
      `bash scripts/serve-public-court.sh start` and any anet user
      anywhere can `anet svc discover --skill=dispute-court` and find
      this team's court live.
- [x] **External-juror onboarding documented** ([docs/joining-as-juror.md](docs/joining-as-juror.md))
      — four-step guide for any third-party anet operator to mint
      their own Soul NFT, boot their own daemon, run a juror
      service tagged `court-juror`, and join the panel. Anyone in
      the wider network can become a juror — 5🐚 per vote, reputation
      stays with their Soul.

### Test ladder

| Layer | Status | Network |
|---|---|---|
| Pure-logic units (verdict, parser) | ✅ | n/a |
| Vendored SvcClient ↔ daemon | ✅ | local |
| Pneuma Soul NFT mint | ✅ | **public** Arc Testnet |
| `agentnetwork.org.cn` mgmt API self-register | ✅ | **public** sponsor backend |
| 5-daemon mesh + court + 3 jurors + caller | ✅ | local loopback |
| Service discoverable on **GLOBAL anet ANS** | ✅ | **public** anet |
| Real-Claude 3-juror E2E (synchronous) | ⚠️ partial | clipped by anet's 30s svc-call client timeout — `JUROR_MOCK_MODE=1` for fast demos; v0.2 async/poll handoff queued |
| On-chain `fileDispute → finalize` write | ❌ deferred | requires plaintiff-as-msg.sender — meta-tx relayer queued for v0.2 |
| 🐚 Shell wallet flow between daemons | ⚠️ design-only | Each juror is registered with `per_call=5🐚` and the court with `per_call=20🐚`, so a successful case is *designed* to pay 20 → court → 5×3 → jurors with court netting +5 fee. **In our isolated 5-daemon loopback the wallet delta is not observed live** (balance stays at the 5000🐚 default and `anet svc audit` returns empty). The data path (HTTP body / verdict / Soul attribution) works end-to-end; the credit-gossip layer in this loopback config does not seem to settle. Likely either a per-call deposit setting we haven't surfaced or the `/anet/credits` topic gossip needing a non-loopback overlay. **Public-mesh test (`scripts/verify-public-mesh.sh`) confirmed `ans.published=True`** which is the documented prerequisite for billing to engage in production. v0.2 will instrument this. |

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
construction. The court keeps 5 🐚 per case as arbitration fee. The caller
spends 20 🐚 total — never any EVM gas, never any USDC. See `scripts/verify-
public-mesh.sh` for the registration-side proof and the table above for
where reality currently differs from the design.

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
