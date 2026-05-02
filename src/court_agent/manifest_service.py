"""Pneuma Court Protocol manifest — single anet service that returns the
full topology + recommended caller flow as JSON.

Registers as an anet svc with skill `pneuma-court-manifest`. External
agents that find any of our 6 services on ANS can call this one to get
the protocol map without reading the README first.

Endpoints:
    GET /health
    GET /meta
    GET /protocol  ← the answer to "how do these 6 services compose?"
"""

from __future__ import annotations

import os
import threading

import uvicorn
from fastapi import FastAPI
from fastapi.responses import JSONResponse

from court_agent._register import register_until_ready

NAME = "pneuma-court-manifest"
PORT = int(os.environ.get("MANIFEST_PORT", "9203"))
PER_CALL = 0  # free — this is the protocol's directory page


PROTOCOL_DOC = {
    "name": "Pneuma Court Protocol",
    "version": "0.1.0",
    "homepage": "https://github.com/0xE1337/pneuma-court-p2p",
    "tagline": "Multi-juror dispute resolution for AI-to-AI commerce on Agent Network, with on-chain enforcement on Arc Testnet.",

    "layers": [
        {
            "id": "identity",
            "purpose": "Mint a chain-anchored Pneuma Soul NFT. Required for jurors; optional for callers.",
            "service": "pneuma-soul-mint",
            "skill_tag": "soul-mint",
            "ans_query": "anet svc discover --skill=soul-mint",
        },
        {
            "id": "enforcement",
            "purpose": "On-chain stake/escrow/dispute/slash via CourtEscrow.sol on Arc Testnet.",
            "service": "pneuma-court-escrow",
            "skill_tag": "escrow",
            "ans_query": "anet svc discover --skill=escrow",
            "contract": os.environ.get(
                "COURT_ESCROW_ADDRESS",
                "0x72E945cD718E6A5b36C34896343a436D3e7dd8d0",
            ),
            "chain_id": int(os.environ.get("ARC_CHAIN_ID", "5042002")),
        },
        {
            "id": "reasoning",
            "purpose": "Multi-juror deliberation. Court discovers a panel of court-juror peers and aggregates their verdicts.",
            "services": ["pneuma-court", "economic-juror", "legal-juror", "fairness-juror"],
            "skill_tags": ["dispute-court", "economic-juror", "legal-juror", "fairness-juror", "court-juror"],
            "ans_query": "anet svc discover --skill=dispute-court",
        },
        {
            "id": "settlement",
            "purpose": (
                "Central-bank layer: agent-to-agent REAL USDC payments via "
                "Coinbase x402 (EIP-3009 transferWithAuthorization). Pairs "
                "with the escrow layer — escrow for SLA-bound calls, x402 "
                "for per-call micropayments."
            ),
            "service": "pneuma-x402-rail",
            "skill_tag": "x402",
            "ans_query": "anet svc discover --skill=x402",
            "asset": os.environ.get(
                "USDC_ADDRESS",
                "0x3600000000000000000000000000000000000000",
            ),
            "scheme": "x402-eip3009",
            "verified_demo": "examples/x402_real_money_demo.py",
            "demo_tx_example": (
                "Alice signs off-chain → rail submits → Bob (ephemeral wallet) "
                "receives 0.01 USDC. Verified on Arc Testnet."
            ),
        },
    ],

    "caller_flow": [
        {
            "step": 1,
            "actor": "provider (B)",
            "action": "USDC.approve(CourtEscrow, stakeAmount); CourtEscrow.stake(amount)",
            "where": "Arc Testnet (provider signs)",
            "purpose": "Make B's USDC slashable. Without stake, B can't be punished — protocol declines to route disputes against unstaked providers.",
            "skip_if": "B already has providerStake > 0 from a previous setup",
        },
        {
            "step": 2,
            "actor": "caller (A)",
            "action": "USDC.approve(CourtEscrow, escrowAmount); CourtEscrow.escrowCall(B, amount)",
            "where": "Arc Testnet (caller signs)",
            "purpose": "A locks USDC into the escrow + locks an equal-or-lesser slice of B's stake as the slash cap.",
            "returns": "callId (uint256, emitted via CallEscrowed event)",
        },
        {
            "step": 3,
            "actor": "(B does work)",
            "action": "off-protocol — A and B exchange the deliverable however they normally do",
            "where": "anywhere",
            "purpose": "Real work happens here. anet's role is service routing; the actual content delivery is between A and B.",
        },
        {
            "step": 4,
            "actor": "caller (A)",
            "action": "if HAPPY: CourtEscrow.settleCall(callId)  →  escrow flows to B, done",
            "where": "Arc Testnet (caller signs)",
        },
        {
            "step": 5,
            "actor": "caller (A) — UNHAPPY PATH",
            "action": "CourtEscrow.fileDispute(callId, evidenceHash)",
            "where": "Arc Testnet (caller signs — msg.sender invariant)",
            "returns": "caseId (uint256)",
        },
        {
            "step": 6,
            "actor": "caller (A)",
            "action": "anet svc call <peer> pneuma-court /dispute --body '{caseId, callId, category, evidence, claims}'",
            "where": "anet (caller pays cost in 🐚 Shell via task wrapper, see /shell_flow)",
            "purpose": "Hand the case to the multi-juror panel for off-chain reasoning.",
        },
        {
            "step": 7,
            "actor": "court (server-side)",
            "action": "svc.discover(skill='court-juror') → parallel /vote calls → majority_vote",
            "where": "anet (court pays each juror 5🐚)",
            "result": "verdict ∈ {PLAINTIFF, DEFENDANT, ABSTAIN}",
        },
        {
            "step": 8,
            "actor": "court (server-side)",
            "action": "CourtEscrow.resolveDispute(caseId, plaintiffWins)",
            "where": "Arc Testnet (court signs as the trusted aggregator)",
            "purpose": "Trigger on-chain settlement. If plaintiffWins: caller gets refund + 50% of locked stake. Else: provider gets escrow.",
        },
    ],

    "service_dependency_graph": {
        "pneuma-court": {
            "calls_into": ["economic-juror", "legal-juror", "fairness-juror", "court-juror (catch-all)"],
            "writes_to_chain": ["CourtEscrow.resolveDispute"],
        },
        "pneuma-court-escrow": {
            "called_by": ["caller (off-protocol via web3)", "pneuma-court (resolveDispute)"],
            "reads_from_chain": ["CourtEscrow.getCall", "CourtEscrow.getCase", "providerStake/lockedStake"],
        },
        "pneuma-soul-mint": {
            "called_by": ["any agent wanting an on-chain identity"],
            "writes_to_chain": ["SoulNFT.publicMint"],
        },
        "economic-juror / legal-juror / fairness-juror": {
            "called_by": ["pneuma-court (during deliberation)"],
            "reasoning_engine": "local Claude CLI (no Anthropic API key needed)",
        },
        "pneuma-x402-rail": {
            "called_by": ["any agent wanting to pay/receive REAL USDC per call"],
            "writes_to_chain": ["USDC.transferWithAuthorization (EIP-3009)"],
            "scheme": "x402-eip3009",
            "complements": "pneuma-court-escrow (escrow for SLA, rail for per-call)",
        },
    },

    "shell_flow": {
        "model": "anet TASK system (publish/work-on/accept settles 🐚 between daemons)",
        "verified_demo": "examples/shell_flow_via_task.py",
        "live_observation": "publisher 5000 → 4895 (-105) ; worker 5000 → 5100 (+100)",
        "audit_event": "credits.events: reward.task_complete 100",
    },

    # End-to-end verified demos with on-chain / anet evidence. Listed
    # here so any external agent reading /protocol gets machine-readable
    # proof of what runs without needing to clone the repo first.
    "verified_demos": [
        {
            "name": "anet brain — collective-reasoning court",
            "script": "examples/brain_court_demo.py",
            "command": ".venv/bin/python examples/brain_court_demo.py",
            "purpose": "3 jurors join an anet brain room, each posts a structured (case, verdict, confidence) unit; brain deliberate aggregates consensus; caller publishes a 100🐚 task that settles to court.",
            "verified_at": "2026-05-02",
            "evidence": [
                {"type": "anet_brain", "id": "b49ffc17-613a-427a-86ed-1994c01d0415", "members": 4, "units": 3, "consensus": "PLAINTIFF (2:1)"},
                {"type": "shell_settle", "caller_delta": "5000→4895 (-105)", "court_delta": "5000→5100 (+100)"},
                {"type": "credits_event", "row": "reward.task_complete 100"},
            ],
            "anet_primitives_used": ["svc.discover", "task.publish/work-on/accept", "brain.open/join/unit/deliberate"],
        },
        {
            "name": "CourtEscrow — full on-chain enforcement lifecycle",
            "script": "examples/escrow_lifecycle.py",
            "command": ".venv/bin/python examples/escrow_lifecycle.py",
            "purpose": "stake → escrow → fileDispute → resolveDispute(plaintiffWins) end-to-end, verified live on Arc Testnet. 4 transactions on chain.",
            "verified_at": "2026-05-01",
            "evidence": [
                {"type": "onchain_contract", "address": os.environ.get("COURT_ESCROW_ADDRESS", "0x72E945cD718E6A5b36C34896343a436D3e7dd8d0"), "explorer": "https://testnet.arcscan.app/address/0x72E945cD718E6A5b36C34896343a436D3e7dd8d0"},
                {"type": "lifecycle_outcome", "result": "caller +1.50 USDC (escrow refund 1.00 + 50% slash 0.50); provider stake 5.00→4.50; case=PlaintiffWins, call=Resolved"},
                {"type": "tx_count", "count": 4},
            ],
            "anet_primitives_used": [],
            "chain_primitives_used": ["USDC.approve", "CourtEscrow.stake", "CourtEscrow.escrowCall", "CourtEscrow.fileDispute", "CourtEscrow.resolveDispute"],
        },
        {
            "name": "🐚 Shell flow — real settlement via anet TASK",
            "script": "examples/shell_flow_via_task.py",
            "command": ".venv/bin/python examples/shell_flow_via_task.py",
            "purpose": "Demonstrates that 🐚 Shell actually moves between daemons via anet's TASK system (publish/work-on/accept) — NOT via svc.cost_model.per_call which is metadata only.",
            "verified_at": "2026-05-01",
            "evidence": [
                {"type": "shell_settle", "caller_delta": "5000→4895 (-105)", "court_delta": "5000→5100 (+100)"},
                {"type": "credits_event", "row": "reward.task_complete 100 — Task reward for task a49c3edd-…"},
            ],
            "anet_primitives_used": ["task.publish", "task.work-on", "task.accept", "credits.events"],
        },
        {
            "name": "x402 Rail — REAL USDC payment via Coinbase x402 + EIP-3009",
            "script": "examples/x402_real_money_demo.py",
            "command": ".venv/bin/court-x402-rail &  # rail on :9205\n.venv/bin/python examples/x402_real_money_demo.py",
            "purpose": "Brand-new ephemeral wallet (never funded) receives real USDC purely via off-chain signature; the rail acts as gas relayer. Anyone-can-submit EIP-3009 design — caller pays no gas.",
            "verified_at": "2026-05-02",
            "evidence": [
                {"type": "onchain_tx", "tx_hash": "0x14dff7f46b9f03ae2761589df3bfbf9387966d17d115d462760997b5ee386e8c", "explorer": "https://testnet.arcscan.app/tx/0x14dff7f46b9f03ae2761589df3bfbf9387966d17d115d462760997b5ee386e8c"},
                {"type": "balance_delta", "from_addr": "Bob (ephemeral)", "before": "0.000000 USDC", "after": "0.010000 USDC"},
                {"type": "gas_paid_by", "value": "rail relayer (caller signed off-chain only)"},
            ],
            "anet_primitives_used": ["svc.register"],
            "chain_primitives_used": ["USDC.transferWithAuthorization (EIP-3009 / FiatTokenV2)"],
        },
        {
            "name": "ERC-6551 TBA-routed CourtEscrow lifecycle (non-custodial)",
            "script": "examples/tba_signed_lifecycle.py",
            "command": ".venv/bin/python examples/tba_signed_lifecycle.py",
            "purpose": "Closes the loop on the parent project's identity-and-authority unification. Caller is an agent's ERC-6551 Token-Bound Account, bound to a Soul NFT. The Soul-owner EOA signs TBA.execute() → CourtEscrow sees the TBA address as msg.sender. fileDispute works without any meta-tx relayer because the agent's TBA *is* the on-chain wallet.",
            "verified_at": "2026-05-02",
            "evidence": [
                {"type": "soul_id", "tokenId": 14, "tba_address": "0x2Ac66faCEaE863dDC87E34D3039776f59177842D"},
                {"type": "msg_sender_assertion", "claim": "c.caller on-chain == TBA address", "verified_live": True},
                {"type": "case_outcome", "case_id": 2, "outcome": "PlaintiffWins"},
                {"type": "balance_delta", "from_addr": "TBA 0x2Ac66f…7842D", "before": "0.000000 USDC", "after": "2.000000 USDC", "note": "1.50 funded - 1.00 escrowed + 1.00 refund + 0.50 slash payout"},
                {"type": "tx_trail", "soul_mint": "0x72f0cde3927f6c1bfadb3b139176179c011bfb999f80a68904ae19ad149285f0", "tba_escrow": "0x9bc27c3dee6b67220ebfb478c8c0c05d4f5430dee0dfb0023ca99866da85c559", "tba_dispute": "0x5f66784bede2aac201334f52958bf3efa541cb42e91393c9e8870e35f753e5e1", "court_resolve": "0xa66dbe8567c5736c1683980ec4b1a7f42497a92b8c4af74a63bdde58aff3d7db"},
            ],
            "anet_primitives_used": [],
            "chain_primitives_used": ["SoulNFT.publicMint", "ERC-6551 TBA.execute (operation=CALL)", "CourtEscrow.escrowCall", "CourtEscrow.fileDispute", "CourtEscrow.resolveDispute"],
        },
    ],

    "external_juror_onboarding": "https://github.com/0xE1337/pneuma-court-p2p/blob/main/docs/joining-as-juror.md",
    "openclaw_install": "openclaw skills install pneuma-court",
    "license": "MIT",
}


def cli() -> None:
    app = FastAPI(title=NAME)

    @app.get("/health")
    def health() -> dict[str, object]:
        return {"ok": True, "agent": NAME}

    @app.get("/meta")
    def meta() -> dict[str, object]:
        return {
            "name": NAME,
            "version": PROTOCOL_DOC["version"],
            "skill": "pneuma-court-manifest",
            "purpose": "Returns the full Pneuma Court protocol topology + caller flow as JSON",
            "endpoint_to_call": "/protocol",
        }

    @app.get("/protocol")
    def protocol():
        return JSONResponse(PROTOCOL_DOC)

    threading.Thread(
        target=lambda: register_until_ready(
            name=NAME,
            port=PORT,
            paths=["/protocol", "/health", "/meta"],
            tags=["pneuma-court-manifest", "protocol-doc", "pneuma-court-p2p", "public"],
            description="Protocol manifest — returns the full Pneuma Court service topology + caller flow",
            per_call=PER_CALL,
        ),
        daemon=True,
    ).start()

    uvicorn.run(app, host="127.0.0.1", port=PORT, log_level="warning")


if __name__ == "__main__":
    cli()
