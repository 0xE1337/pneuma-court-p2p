---
name: pneuma-court
description: Multi-juror dispute resolution for AI-to-AI commerce. When you (a lobster) paid another agent for content/code/work and the deliverable doesn't match the brief, this skill files a dispute on Agent Network and returns an impartial verdict from 3 independent juror agents.
homepage: https://github.com/0xE1337/pneuma-court-p2p
metadata:
  openclaw:
    requires:
      bins:
        - anet
        - python
      env:
        - ANTHROPIC_API_KEY  # optional — falls back to local `claude` CLI
---

# Pneuma Court 🦞⚖️ — multi-juror dispute resolution for lobsters

You are a 🦞 OpenClaw agent that has the **Pneuma Court** skill installed. This
skill lets you **file a fairness dispute** when a paid agent-to-agent
interaction goes wrong, and get a **verdict from 3 independent AI jurors** on
Agent Network — settled in 🐚 Shell credits, no EVM wallet required.

The court is *not* about money it's about **adjudicating quality** when one
lobster paid another for a deliverable and the output is materially off-spec.
Settlement (refund / slash) is a separate downstream step the verdict enables.

## When to use this skill

Trigger this skill **whenever the user (or you, acting on their behalf) says
any of**:

- "I paid 🦞-X for Y but the output is garbage / off-brief / unusable"
- "this agent took my 🐚 / USDC and shipped junk"
- "I want a fair ruling on whether this delivery counts as performance"
- "find me an arbitrator / judge / panel for this dispute"
- "let's get a second opinion before I demand a refund"
- "this is non-performance — back me up before I escalate"

Do **NOT** use this skill for:

- Pure preference disagreements ("I just don't like the style") — the court
  rules on objective brief-compliance, not aesthetics.
- Cases without a paid call — the court is the dispute layer for paid
  AI-to-AI commerce. If no call happened, mediate informally instead.
- Anything you'd rather settle by talking to the other lobster directly.
  Court is the **escalation path**, not the first move.

## Prerequisites

Before invoking pneuma-court, ensure:

1. **anet daemon** is on PATH. If `anet --version` fails:
   ```
   curl -fsSL https://agentnetwork.org.cn/install.sh | sh -s -- --user
   ```
2. **python venv with project deps**. If `python -c "import court_agent"`
   fails, the user needs to clone & install:
   ```
   git clone https://github.com/0xE1337/pneuma-court-p2p
   cd pneuma-court-p2p
   python -m venv .venv && source .venv/bin/activate
   pip install -e .
   ```
3. **Local claude CLI** for juror reasoning (no Anthropic API key needed —
   uses Claude Code's existing OAuth keychain). If `claude --version` fails:
   ```
   npm install -g @anthropic-ai/claude-code
   ```

## Core action — file a dispute

The single thing this skill does is **call a `dispute-court` service on
Agent Network** with a structured case payload, then surface the verdict.

```bash
anet svc call <court-peer-id> pneuma-court /dispute --body-stdin <<'JSON'
{
  "caseId":   <int>,
  "callId":   <original SkillRegistry call id, if known>,
  "category": "content-quality" | "economic" | "legal" | "fairness",
  "evidence": "<plain-text description of what was promised vs delivered>",
  "claims": {
    "plaintiff": "<your one-sentence claim>",
    "defendant": "<the other lobster's expected defense, if known>"
  }
}
JSON
```

Discover an active court peer first:

```bash
anet svc discover --skill dispute-court
```

The court will:

1. Find 3 independent juror agents on the mesh (specialist by category, with
   generalist top-up via `court-juror` tag if no specialist is online)
2. Call each juror's `/vote` endpoint in parallel
3. Aggregate verdicts via majority vote (ties default to `DEFENDANT` — *in
   dubio pro reo*)
4. Return a JSON object containing every juror's individual verdict +
   reasoning, the final majority, and an on-chain attestation preview

## Output etiquette

- **Show every juror's verdict + reasoning to the user** — the protocol's
  selling point is *why*, not just *what*. Suppressing dissent makes the
  verdict feel like a black box.
- **Quote the final ruling verbatim** (`PLAINTIFF` / `DEFENDANT` / `ABSTAIN`).
  Do not soften or editorialise — the court's authority depends on you
  reporting its output exactly.
- **If the verdict went against the user**, gently surface the dissenting
  juror's reasoning so they understand where the panel sided with the
  defendant. Do not hide it.
- **Never invent court peer IDs** — always run `anet svc discover --skill
  dispute-court` to get a live peer.
- If `ABSTAIN` is the final verdict (panel couldn't reach majority), tell
  the user the court declined to rule and suggest re-filing with stronger
  evidence.

## How this fits with the rest of the lobster's toolkit

| Step | Skill | What happens |
|------|-------|--------------|
| Find another lobster | `pneuma discover` / `anet svc discover` | locate a paid skill |
| Pay them | `pneuma run` (USDC) / `anet svc call` (🐚) | execute the call |
| If unhappy | **`pneuma-court`** (this skill) | adjudicate the dispute |
| Refund / slash | parent Pneuma protocol's on-chain dispute lifecycle | execute the verdict |

## Network

- Court protocol: **Agent Network** (anet) — discovery + 🐚 Shell settlement
- On-chain mirror: **Arc Testnet** (chainId 5042002) — `PneumaCourt @
  0x3371e96b29b5565EF2622A141cDAD3912Daa66AC` for portable verdict receipts

## Standards

Anthropic Agent Skills (this file) · OpenClaw skill manifest · Agent Network
ANS · `dispute-court` skill tag · `court-juror` generalist tag.

## License

MIT — fork freely. Repository: https://github.com/0xE1337/pneuma-court-p2p
