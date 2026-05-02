"""Pneuma Soul mint service — exposed as an anet svc on ANS.

Lets any external anet agent call us over the mesh to mint a Soul NFT
for themselves. The mint itself is a permissionless on-chain action
(SoulNFT.publicMint), but the operator wallet pays gas — so this is
effectively a sponsored-mint relay: the caller just supplies a name
and we pay the few cents of testnet USDC gas to put a Soul on chain
for them.

Endpoint:
    POST /mint
        body: {"agentName": str, "metadataURI": str (optional)}
        returns: {tokenId, tba, owner, txHash, explorerUrl}

Health:
    GET /health → {ok: true}
    GET /meta   → service metadata
"""

from __future__ import annotations

import os
import threading
from typing import Optional

import uvicorn
from fastapi import FastAPI, Header, Request
from fastapi.responses import JSONResponse

from court_agent._register import register_until_ready
from court_agent.chain_pneuma import (
    ensure_juror_soul,
    explorer_url,
    has_pneuma_config,
    mint_soul,
    total_minted,
)

NAME = "pneuma-soul-mint"
PORT = int(os.environ.get("SOUL_MINT_PORT", "9201"))
PER_CALL = int(os.environ.get("SOUL_MINT_COST_PER_CALL", "10"))


def cli() -> None:
    app = FastAPI(title=NAME)

    @app.get("/health")
    def health() -> dict[str, object]:
        return {"ok": True, "agent": NAME}

    @app.get("/meta")
    def meta() -> dict[str, object]:
        configured = has_pneuma_config()
        info: dict[str, object] = {
            "name": NAME,
            "version": "0.1.0",
            "skill": "soul-mint",
            "description": "Sponsored Pneuma Soul NFT minting on Arc Testnet",
            "configured": configured,
            "contract": os.environ.get(
                "PNEUMA_SOUL_NFT_ADDRESS",
                "0x5b516Cdc56910C07C9b34C2d56b31422da97A959",
            ),
        }
        if configured:
            try:
                info["totalMinted"] = total_minted()
            except Exception:  # noqa: BLE001
                info["totalMinted"] = None
        return info

    @app.post("/mint")
    async def mint(
        req: Request,
        x_agent_did: Optional[str] = Header(default=None, convert_underscores=True),
    ):
        body = await req.json() or {}
        agent_name = str(body.get("agentName") or f"anet-juror-{x_agent_did or 'anon'}")[:64]
        metadata_uri = str(body.get("metadataURI") or f"pneuma-court://{agent_name}")[:200]

        print(f"[{NAME}] mint request: caller={x_agent_did} agentName={agent_name!r}", flush=True)

        if not has_pneuma_config():
            return JSONResponse(
                {"error": "service not configured (ARC_RPC_URL / COURT_FINALIZER_PRIVATE_KEY missing)"},
                status_code=503,
            )

        try:
            # ensure_juror_soul handles cache-or-mint; for external requests we
            # always mint fresh (they own their identity, not cached under our key)
            ident = mint_soul(agent_name=agent_name, metadata_uri=metadata_uri)
        except Exception as e:  # noqa: BLE001
            print(f"[{NAME}] mint failed: {e}", flush=True)
            return JSONResponse({"error": f"mint failed: {e}"}, status_code=500)

        ident["explorerUrl"] = explorer_url(ident["tokenId"])
        print(f"[{NAME}]   ↳ minted Soul #{ident['tokenId']}  → {ident['explorerUrl']}", flush=True)
        return JSONResponse(ident)

    threading.Thread(
        target=lambda: register_until_ready(
            name=NAME,
            port=PORT,
            paths=["/mint", "/health", "/meta"],
            tags=["soul-mint", "identity", "pneuma", "pneuma-court-p2p", "sponsored-mint"],
            description="Sponsored Pneuma Soul NFT minting on Arc Testnet — operator pays gas, caller gets a chain-anchored identity.",
            per_call=PER_CALL,
        ),
        daemon=True,
    ).start()

    uvicorn.run(app, host="127.0.0.1", port=PORT, log_level="warning")


if __name__ == "__main__":
    cli()
