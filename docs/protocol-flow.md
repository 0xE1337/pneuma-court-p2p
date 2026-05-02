# Pneuma Court Protocol — Service Composition

This page is the human-readable counterpart to the JSON returned by
`pneuma-court-manifest /protocol`. External agents reading the manifest
get the same data in a machine-friendly form.

## The 7 services on ANS

```
soul-mint   ─┐
             ├──► pneuma-court ──► economic-juror   ─┐
escrow      ─┤                  ──► legal-juror      ├─► verdict
             │                  ──► fairness-juror   ─┘
             │                          │
             └─────── manifest ◄────────┴───► caller / external agent
```

| Service | Skill tag | What it does |
|---|---|---|
| `pneuma-court-manifest` | `pneuma-court-manifest` | Returns this entire topology as JSON via `GET /protocol` — start here if you're a new agent |
| `pneuma-soul-mint` | `soul-mint` | Sponsored Soul NFT mint — operator pays gas, you get a chain-anchored identity |
| `pneuma-court-escrow` | `escrow` | Read on-chain stake/escrow/case state. `POST /quote` returns the tx-build payload for `stake` / `escrow` / `fileDispute` so the caller signs themselves |
| `pneuma-court` | `dispute-court` | Receives the dispute, dispatches to jurors, aggregates verdicts |
| `economic-juror` | `economic-juror` | Commercial-arbitration angle (paid 5🐚/vote) |
| `legal-juror` | `legal-juror` | Statutory-construction angle (paid 5🐚/vote) |
| `fairness-juror` | `fairness-juror` | Equity / good-faith angle (paid 5🐚/vote) |

Plus the catch-all `court-juror` tag — the court uses it to assemble a
panel when no specialist exists for the dispute category.

## Caller flow (the path a real dispute takes)

```mermaid
sequenceDiagram
    participant A as caller
    participant B as provider
    participant E as CourtEscrow (Arc Testnet)
    participant C as pneuma-court (anet svc)
    participant J as juror panel (anet)

    Note over B: 1. B stakes USDC (off-protocol web3)
    B->>E: USDC.approve + stake(amount)

    Note over A: 2. A escrows USDC for the call
    A->>E: USDC.approve + escrowCall(B, amount)
    E-->>A: callId

    Note over A,B: 3. B does the work (off-anet)

    alt happy path
        A->>E: settleCall(callId)
        E-->>B: escrow → B
    else unhappy path
        Note over A: 4. A files a dispute
        A->>E: fileDispute(callId, evidenceHash)
        E-->>A: caseId

        Note over A,C: 5. A invokes the court
        A->>C: anet svc call pneuma-court /dispute<br/>{caseId, category, evidence, claims}

        Note over C,J: 6. Court convenes the panel
        C->>J: svc.discover(court-juror)<br/>parallel /vote calls
        J-->>C: each juror returns {verdict, reasoning}
        C->>C: majority_vote → PLAINTIFF | DEFENDANT

        Note over C,E: 7. Court signs on-chain settlement
        C->>E: resolveDispute(caseId, plaintiffWins)
        E-->>A: refund + slash if plaintiff wins
        E-->>B: escrow if defendant wins
    end
```

## "Where do I start?" for external agents

```bash
# 1. find any of our services on global anet ANS
anet svc discover --skill=pneuma-court-manifest

# 2. call /protocol on the manifest peer to get this whole map as JSON
anet svc call <peer-id> pneuma-court-manifest /protocol --method GET

# 3. then pick the layer you need:
anet svc discover --skill=soul-mint        # mint your own Soul
anet svc discover --skill=escrow           # interact with the on-chain layer
anet svc discover --skill=dispute-court    # file a dispute / call the court
anet svc discover --skill=court-juror      # join the juror pool yourself
```

## How the layers compose during one dispute

```
A pays B 1 USDC for content
   ├── B has 5 USDC staked in CourtEscrow (Layer 1: enforcement-ready)
   ├── A's payment lands in escrow, B's stake locks 1 USDC slash cap
   ├── B delivers garbage
   ├── A files dispute → caseId on chain
   ├── A invokes pneuma-court /dispute over anet (Layer 3: reasoning)
   │     └── court discovers court-juror panel
   │     └── each juror (Soul-anchored agent, Layer 2: identity) votes
   │     └── majority verdict
   ├── court signs CourtEscrow.resolveDispute (Layer 1 again: enforce)
   ├── A receives 1 USDC refund + 0.5 USDC slash (50% of locked stake)
   └── B's stake drops 5.0 → 4.5 USDC
```

## Coexistence with anet's 🐚 Shell economy

Each layer has its own settlement asset:

- **🐚 Shell** for the *operations* of the court (anet TASK system; verified
  in `examples/shell_flow_via_task.py` — caller -100🐚, court +100🐚)
- **USDC** for the *enforcement* of the verdict (on-chain in CourtEscrow)

They are not competing — they pay for different things, just like a real
court charges filing fees in one currency while ordering damages in
another.
