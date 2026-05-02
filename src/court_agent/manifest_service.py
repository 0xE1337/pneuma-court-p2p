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
    },

    "shell_flow": {
        "model": "anet TASK system (publish/work-on/accept settles 🐚 between daemons)",
        "verified_demo": "examples/shell_flow_via_task.py",
        "live_observation": "publisher 5000 → 4895 (-105) ; worker 5000 → 5100 (+100)",
        "audit_event": "credits.events: reward.task_complete 100",
    },

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
