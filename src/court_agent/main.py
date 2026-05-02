"""Pneuma Court main service — FastAPI app + anet svc registration."""

from __future__ import annotations

import os
import threading
from typing import Optional

import uvicorn
from fastapi import FastAPI, Header, Request
from fastapi.responses import JSONResponse

from court_agent._register import register_until_ready
from court_agent.proxy import deliberate

NAME = "pneuma-court"
PORT = int(os.environ.get("COURT_PORT", "8088"))
PER_CALL = int(os.environ.get("COURT_COST_PER_CALL", "20"))

app = FastAPI(title=NAME)


@app.get("/health")
def health() -> dict[str, object]:
    return {"ok": True, "agent": NAME}


@app.get("/meta")
def meta() -> dict[str, object]:
    return {
        "name": NAME,
        "version": "0.1.0",
        "skill": "dispute-court",
        "description": (
            "Multi-juror dispute resolution. Court convenes 3 Soul-anchored "
            "jurors via anet brain (collective reasoning), aggregates the "
            "consensus verdict, and signs CourtEscrow.resolveDispute on "
            "Arc Testnet for unhappy-path enforcement."
        ),
        "calls_into": ["economic-juror", "legal-juror", "fairness-juror", "court-juror (catch-all)"],
        "writes_onchain": "CourtEscrow @ Arc Testnet (0x72E945cD718E6A5b36C34896343a436D3e7dd8d0)",
        "endpoints": {
            "POST /dispute": "submit a dispute body {caseId, callId, category, evidence, claims}; returns {verdict, jurors[], tx_hash, brain_audit_url}",
            "GET /health":   "liveness probe",
            "GET /meta":     "this introspection payload",
        },
        "complementary_services": [
            "pneuma-court-manifest (start here for full topology)",
            "pneuma-court-escrow (read on-chain state + tx-quote)",
            "pneuma-x402-rail (per-call USDC payments via x402)",
            "pneuma-soul-mint (mint a Soul + TBA wallet)",
        ],
    }


@app.post("/dispute")
async def dispute(
    req: Request,
    x_agent_did: Optional[str] = Header(default=None, convert_underscores=True),
):
    body = await req.json()
    case_id = (body or {}).get("caseId")
    print(f"[court] caller={x_agent_did} caseId={case_id!r}", flush=True)
    result = deliberate(body or {}, caller_did=x_agent_did)
    print(
        f"[court]   ↳ verdict={result['verdict']}"
        f" jurors={len(result['jurors'])}"
        f" tx={result.get('tx_hash')}",
        flush=True,
    )
    return JSONResponse(result)


def cli() -> None:
    threading.Thread(
        target=lambda: register_until_ready(
            name=NAME,
            port=PORT,
            paths=["/dispute", "/health", "/meta"],
            tags=["dispute-court", "multi-juror", "onchain-finalize", "court-p2p"],
            description=(
                "Multi-juror dispute resolution. Discovers domain-specific juror "
                "agents on anet, aggregates verdicts via majority vote, finalizes "
                "the ruling on Arc Testnet via the PneumaCourt contract."
            ),
            per_call=PER_CALL,
        ),
        daemon=True,
    ).start()
    uvicorn.run(app, host="127.0.0.1", port=PORT, log_level="warning")


if __name__ == "__main__":
    cli()
