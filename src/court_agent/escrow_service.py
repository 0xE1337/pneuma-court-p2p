"""CourtEscrow service — exposes the on-chain enforcement surface as an
anet svc that other agents can discover and query/observe.

WRITE operations (stake / escrowCall / fileDispute) require the *caller's*
own EVM wallet — we cannot sign on their behalf without compromising the
non-custodial invariant. So this service publishes an INSTRUCTION
endpoint that returns the exact tx data they should sign + the contract
address + the chain id.

READ operations are fully served (callers don't need any wallet to see
state).

Endpoints:
    GET /health
    GET /meta
    POST /quote              — return tx-build payload for stake / escrow / fileDispute
    GET  /call/{call_id}     — read on-chain state of a call
    GET  /case/{case_id}     — read on-chain state of a case
    GET  /provider/{address} — read provider's stake / locked / available

Resolve (court-only) is NOT exposed — the court daemon's own
`court_agent.proxy.deliberate` invokes `escrow.resolve_dispute_onchain`
internally, signed by COURT_FINALIZER_PRIVATE_KEY.
"""

from __future__ import annotations

import os
import threading
from typing import Optional

import uvicorn
from fastapi import FastAPI, Header, Request
from fastapi.responses import JSONResponse

from court_agent._register import register_until_ready
from court_agent.escrow import (
    explorer_addr,
    get_call,
    get_case,
    get_provider_stake,
)

NAME = "pneuma-court-escrow"
PORT = int(os.environ.get("ESCROW_SVC_PORT", "9202"))
PER_CALL = int(os.environ.get("ESCROW_SVC_COST_PER_CALL", "5"))

CHAIN_ID = int(os.environ.get("ARC_CHAIN_ID", "5042002"))
ESCROW_ADDR = os.environ.get(
    "COURT_ESCROW_ADDRESS",
    "0x72E945cD718E6A5b36C34896343a436D3e7dd8d0",
)


def cli() -> None:
    app = FastAPI(title=NAME)

    @app.get("/health")
    def health() -> dict[str, object]:
        return {"ok": True, "agent": NAME}

    @app.get("/meta")
    def meta() -> dict[str, object]:
        return {
            "name": NAME,
            "version": "0.1.0",
            "skill": "escrow",
            "description": "On-chain stake/escrow/dispute/slash for Pneuma Court",
            "contract": ESCROW_ADDR,
            "explorer": explorer_addr(ESCROW_ADDR),
            "chainId": CHAIN_ID,
            "endpoints": {
                "GET /call/{id}":     "read on-chain call state",
                "GET /case/{id}":     "read on-chain case state",
                "GET /provider/{addr}": "read provider stake/locked/available",
                "POST /quote":        "build a tx the caller signs themselves",
            },
        }

    @app.get("/call/{call_id}")
    def call_view(call_id: int):
        try:
            return JSONResponse(get_call(call_id))
        except Exception as e:  # noqa: BLE001
            return JSONResponse({"error": str(e)}, status_code=404)

    @app.get("/case/{case_id}")
    def case_view(case_id: int):
        try:
            return JSONResponse(get_case(case_id))
        except Exception as e:  # noqa: BLE001
            return JSONResponse({"error": str(e)}, status_code=404)

    @app.get("/provider/{address}")
    def provider_view(address: str):
        try:
            return JSONResponse(get_provider_stake(address))
        except Exception as e:  # noqa: BLE001
            return JSONResponse({"error": str(e)}, status_code=400)

    @app.post("/quote")
    async def quote(
        req: Request,
        x_agent_did: Optional[str] = Header(default=None, convert_underscores=True),
    ):
        # Body shape: {"action": "stake"|"escrow"|"file_dispute",
        #              "args": {...}}
        # Returns the JSON-RPC tx-build hint the caller can sign + send.
        body = await req.json() or {}
        action = str(body.get("action", "")).lower()
        args = body.get("args") or {}

        if action == "stake":
            return JSONResponse({
                "to": ESCROW_ADDR,
                "function": "stake(uint256)",
                "args": [args.get("amount")],
                "chainId": CHAIN_ID,
                "note": (
                    "Caller must `IERC20.approve(escrow, amount)` on the "
                    "USDC contract first, then send this tx from their own wallet."
                ),
            })

        if action == "escrow":
            return JSONResponse({
                "to": ESCROW_ADDR,
                "function": "escrowCall(address,uint256)",
                "args": [args.get("provider"), args.get("amount")],
                "chainId": CHAIN_ID,
                "note": (
                    "Caller must `IERC20.approve(escrow, amount)` first, "
                    "then send this tx from their own wallet. callId is "
                    "emitted in the CallEscrowed event."
                ),
            })

        if action == "file_dispute":
            return JSONResponse({
                "to": ESCROW_ADDR,
                "function": "fileDispute(uint256,bytes32)",
                "args": [args.get("callId"), args.get("evidenceHash")],
                "chainId": CHAIN_ID,
                "note": (
                    "Plaintiff invariant: msg.sender must equal the original "
                    "caller of this callId. Caller signs themselves."
                ),
            })

        return JSONResponse({"error": "unknown action; use stake|escrow|file_dispute"}, status_code=400)

    threading.Thread(
        target=lambda: register_until_ready(
            name=NAME,
            port=PORT,
            paths=["/quote", "/call/{id}", "/case/{id}", "/provider/{addr}", "/health", "/meta"],
            tags=["escrow", "stake-and-slash", "pneuma-court-p2p", "onchain"],
            description=f"On-chain stake/escrow/dispute for Pneuma Court (CourtEscrow @ {ESCROW_ADDR})",
            per_call=PER_CALL,
        ),
        daemon=True,
    ).start()

    uvicorn.run(app, host="127.0.0.1", port=PORT, log_level="warning")


if __name__ == "__main__":
    cli()
