# Architecture

## Service-of-services on anet, finalized on Arc Testnet

```mermaid
sequenceDiagram
    participant C as Caller (any anet node)
    participant Court as pneuma-court (daemon-1)
    participant JE as economic-juror (daemon-2)
    participant JL as legal-juror (daemon-3)
    participant JF as fairness-juror (daemon-4)
    participant ARC as Arc Testnet<br/>PneumaCourt @ 0x3371...

    C->>Court: anet svc call pneuma-court<br/>{caseId, category, evidence}
    Note over Court: cost: 20 🐚

    Court->>Court: svc.discover(skill="economic-juror")<br/>→ peers list

    par parallel juror calls
        Court->>JE: svc.call /vote {case}
        JE-->>Court: {verdict: PLAINTIFF, reasoning}
        Note over JE: cost: 5 🐚
    and
        Court->>JL: svc.call /vote {case}
        JL-->>Court: {verdict: DEFENDANT, reasoning}
        Note over JL: cost: 5 🐚
    and
        Court->>JF: svc.call /vote {case}
        JF-->>Court: {verdict: PLAINTIFF, reasoning}
        Note over JF: cost: 5 🐚
    end

    Court->>Court: majority_vote([PL, DEF, PL]) → PLAINTIFF
    Court->>ARC: PneumaCourt.finalize(disputeId, PLAINTIFF)
    ARC-->>Court: tx_hash 0xabc...
    Court-->>C: SSE stream:<br/>juror votes + final + tx_hash
```

## Why each layer exists

### Layer 1 — anet P2P mesh

- Service discovery without hard-coded peer IDs
- Per-call billing in 🐚 Shell credits, settled cross-daemon by anet wallet
- Audit trail per node via `svc_call_log`

### Layer 2 — Court orchestration

- Translates "dispute category" → list of relevant juror skills
- Parallel fan-out + result aggregation
- Streams partial results as SSE so the caller sees deliberation in real time

### Layer 3 — Juror agents

- Each is an independent anet service with a domain-specific Claude prompt
- Stateless — every call gets a fresh reasoning pass
- Independent registration means anyone in the world can stand up a `<x>-juror` and the court will discover it

### Layer 4 — On-chain finalize

- Off-chain mesh deliberation produces a verdict
- Verdict is committed to `PneumaCourt.finalize()` on Arc Testnet
- Result: cryptographically verifiable, censorship-resistant ruling

## Why this architecture rules out centralized backends

A single backend running all 3 jurors:
- Shares state → biases compound across jurors
- One API key → one operator can silently rewrite verdicts
- No `svc_call_log` audit per juror → no independent accountability

A P2P mesh:
- Each juror's daemon owns its audit log; rewriting requires N-party collusion
- Anyone can register a competing juror with the same skill tag
- The court's discover/aggregate logic is the only thing that needs to be trusted, and it's open-source in this repo
