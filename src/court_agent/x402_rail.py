"""Pneuma x402 Rail — EIP-3009 USDC payment relay for Agent Network.

This is the **central-bank** layer of Pneuma's public-infrastructure stack:
agents pay other agents in **real USDC** (not 🐚 Shell credits) for service
calls, using the Coinbase x402 protocol with EIP-3009
`transferWithAuthorization` on Arc Testnet.

Protocol shape:

    1. Provider tells caller: "send me <value> USDC to <address> via x402"
    2. Caller signs an EIP-712 TransferWithAuthorization (off-chain)
    3. Caller POSTs the signed authorization to this rail
    4. Rail verifies signature → submits on-chain → forwards request to
       provider with X-Payment-Tx header → returns provider's response
    5. Provider sees the on-chain tx and trusts the call

Key properties:
    * **Anyone-can-submit**: EIP-3009 lets any party broadcast the signed
      authorization. The rail acts as a gas relayer — the actual money
      moves caller → provider, not caller → rail → provider.
    * **No escrow**: this is per-call settlement; for SLA / slash /
      dispute use the CourtEscrow contract instead.
    * **anet-discoverable**: registered on global ANS as
      `pneuma-x402-rail` so any agent on the network can find it.

This pairs with the parent project's **escrow-based** x402 (used inside
the SkillRegistry where SLA timeout matters). Together they cover both
modes of agent-to-agent payment:

    | Use case                      | Pattern              | Where      |
    |-------------------------------|----------------------|------------|
    | Per-call micropayment         | EIP-3009 (this file) | court-p2p  |
    | Stake-and-slash with SLA      | escrow-based x402    | main proto |

Endpoints:
    GET  /health
    GET  /meta
    POST /quote       — build EIP-712 typed-data the caller should sign
    POST /pay         — verify sig + submit on-chain (no forward)
    POST /pay-and-call — verify sig + submit + forward request to target
"""

from __future__ import annotations

import json
import os
import secrets
import threading
import time
from typing import Any, Optional

import httpx
import uvicorn
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from court_agent._register import register_until_ready

NAME = "pneuma-x402-rail"
PORT = int(os.environ.get("X402_RAIL_PORT", "9205"))
PER_CALL = int(os.environ.get("X402_RAIL_COST_PER_CALL", "2"))

CHAIN_ID = int(os.environ.get("ARC_CHAIN_ID", "5042002"))
USDC_ADDR = os.environ.get(
    "USDC_ADDRESS", "0x3600000000000000000000000000000000000000"
)
RPC_URL = os.environ.get("ARC_RPC_URL", "https://rpc.testnet.arc.network")
EXPLORER = os.environ.get("ARC_EXPLORER", "https://testnet.arcscan.app")

USDC_TYPED_DATA_NAME = "USDC"
USDC_TYPED_DATA_VERSION = "2"

USDC_ABI = [
    {
        "inputs": [
            {"name": "from", "type": "address"},
            {"name": "to", "type": "address"},
            {"name": "value", "type": "uint256"},
            {"name": "validAfter", "type": "uint256"},
            {"name": "validBefore", "type": "uint256"},
            {"name": "nonce", "type": "bytes32"},
            {"name": "v", "type": "uint8"},
            {"name": "r", "type": "bytes32"},
            {"name": "s", "type": "bytes32"},
        ],
        "name": "transferWithAuthorization",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function",
    },
    {
        "inputs": [{"name": "account", "type": "address"}],
        "name": "balanceOf",
        "outputs": [{"name": "", "type": "uint256"}],
        "stateMutability": "view",
        "type": "function",
    },
    {
        "inputs": [{"name": "authorizer", "type": "address"}, {"name": "nonce", "type": "bytes32"}],
        "name": "authorizationState",
        "outputs": [{"name": "", "type": "bool"}],
        "stateMutability": "view",
        "type": "function",
    },
]


# ─── EIP-712 typed-data ────────────────────────────────────────────────


def build_typed_data(
    *,
    from_addr: str,
    to: str,
    value: int,
    valid_after: int,
    valid_before: int,
    nonce_hex: str,
) -> dict[str, Any]:
    """Build the EIP-712 TransferWithAuthorization typed-data payload."""
    if not nonce_hex.startswith("0x"):
        nonce_hex = "0x" + nonce_hex
    return {
        "types": {
            "EIP712Domain": [
                {"name": "name", "type": "string"},
                {"name": "version", "type": "string"},
                {"name": "chainId", "type": "uint256"},
                {"name": "verifyingContract", "type": "address"},
            ],
            "TransferWithAuthorization": [
                {"name": "from", "type": "address"},
                {"name": "to", "type": "address"},
                {"name": "value", "type": "uint256"},
                {"name": "validAfter", "type": "uint256"},
                {"name": "validBefore", "type": "uint256"},
                {"name": "nonce", "type": "bytes32"},
            ],
        },
        "primaryType": "TransferWithAuthorization",
        "domain": {
            "name": USDC_TYPED_DATA_NAME,
            "version": USDC_TYPED_DATA_VERSION,
            "chainId": CHAIN_ID,
            "verifyingContract": USDC_ADDR,
        },
        "message": {
            "from": from_addr,
            "to": to,
            "value": value,
            "validAfter": valid_after,
            "validBefore": valid_before,
            "nonce": nonce_hex,
        },
    }


def recover_signer(typed_data: dict[str, Any], signature_hex: str) -> str:
    from eth_account import Account
    from eth_account.messages import encode_typed_data

    msg = encode_typed_data(full_message=typed_data)
    return Account.recover_message(msg, signature=signature_hex)


# ─── On-chain settle ───────────────────────────────────────────────────


def _w3():
    from web3 import Web3

    return Web3(Web3.HTTPProvider(RPC_URL, request_kwargs={"timeout": 15}))


def _relayer_account():
    from eth_account import Account

    pk = os.environ.get("X402_RAIL_PRIVATE_KEY") or os.environ.get(
        "COURT_FINALIZER_PRIVATE_KEY"
    )
    if not pk:
        raise RuntimeError(
            "no relayer key — set X402_RAIL_PRIVATE_KEY or COURT_FINALIZER_PRIVATE_KEY"
        )
    if pk.startswith("0x"):
        pk = pk[2:]
    return Account.from_key(pk)


def submit_transfer_with_authorization(
    *,
    from_addr: str,
    to: str,
    value: int,
    valid_after: int,
    valid_before: int,
    nonce_hex: str,
    signature_hex: str,
) -> tuple[str, int]:
    """Submit the signed authorization on-chain. Returns (tx_hash_hex, status)."""
    from web3 import Web3

    sig_clean = signature_hex.removeprefix("0x")
    sig_bytes = bytes.fromhex(sig_clean)
    if len(sig_bytes) != 65:
        raise ValueError(f"signature must be 65 bytes, got {len(sig_bytes)}")
    r = sig_bytes[:32]
    s = sig_bytes[32:64]
    v = sig_bytes[64]

    nonce_clean = nonce_hex.removeprefix("0x")
    nonce_bytes = bytes.fromhex(nonce_clean)
    if len(nonce_bytes) != 32:
        raise ValueError(f"nonce must be 32 bytes, got {len(nonce_bytes)}")

    w3 = _w3()
    relayer = _relayer_account()
    usdc = w3.eth.contract(address=Web3.to_checksum_address(USDC_ADDR), abi=USDC_ABI)

    fn = usdc.functions.transferWithAuthorization(
        Web3.to_checksum_address(from_addr),
        Web3.to_checksum_address(to),
        int(value),
        int(valid_after),
        int(valid_before),
        nonce_bytes,
        v,
        r,
        s,
    )

    tx_nonce = w3.eth.get_transaction_count(relayer.address)
    tx = fn.build_transaction(
        {
            "from": relayer.address,
            "nonce": tx_nonce,
            "gas": 250_000,
            "gasPrice": w3.eth.gas_price,
        }
    )
    signed = relayer.sign_transaction(tx)
    h = w3.eth.send_raw_transaction(signed.raw_transaction)
    receipt = w3.eth.wait_for_transaction_receipt(h, timeout=60)
    return ("0x" + h.hex().removeprefix("0x"), int(receipt.status))


def usdc_balance(addr: str) -> int:
    from web3 import Web3

    w3 = _w3()
    usdc = w3.eth.contract(address=Web3.to_checksum_address(USDC_ADDR), abi=USDC_ABI)
    return int(usdc.functions.balanceOf(Web3.to_checksum_address(addr)).call())


# ─── Pydantic schemas ──────────────────────────────────────────────────


class TransferAuth(BaseModel):
    """Signed EIP-3009 TransferWithAuthorization payload."""

    model_config = ConfigDict(populate_by_name=True)

    from_addr: str = Field(alias="from")
    to: str
    value: str
    valid_after: int = Field(alias="validAfter")
    valid_before: int = Field(alias="validBefore")
    nonce: str
    signature: str


class QuoteRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    from_addr: str = Field(alias="from")
    to: str
    value: str
    ttl_sec: int = 300


class PayRequest(BaseModel):
    transferAuth: TransferAuth
    target: Optional[str] = None
    method: str = "POST"
    body: Optional[dict[str, Any]] = None
    headers: dict[str, str] = Field(default_factory=dict)


# ─── FastAPI app ───────────────────────────────────────────────────────


def _build_app() -> FastAPI:
    app = FastAPI(title=NAME)

    @app.get("/health")
    def health() -> dict[str, object]:
        return {"ok": True, "agent": NAME}

    @app.get("/meta")
    def meta() -> dict[str, object]:
        return {
            "name": NAME,
            "version": "0.1.0",
            "skill": "x402",
            "scheme": "x402-eip3009",
            "description": (
                "Pneuma x402 Rail — agents pay agents real USDC via Coinbase "
                "x402 + EIP-3009. Public-infrastructure central-bank layer."
            ),
            "asset": USDC_ADDR,
            "chainId": CHAIN_ID,
            "explorerToken": f"{EXPLORER}/address/{USDC_ADDR}",
            "endpoints": {
                "POST /quote": "build EIP-712 typed-data to sign",
                "POST /pay": "verify sig + on-chain settle (no forward)",
                "POST /pay-and-call": "verify sig + settle + forward to target URL",
            },
            "pairsWithEscrowMode": (
                "this rail is per-call; for SLA/slash use CourtEscrow"
            ),
        }

    @app.post("/quote")
    def quote(req: QuoteRequest) -> dict[str, object]:
        now = int(time.time())
        nonce_hex = "0x" + secrets.token_hex(32)
        td = build_typed_data(
            from_addr=req.from_addr,
            to=req.to,
            value=int(req.value),
            valid_after=now - 60,
            valid_before=now + req.ttl_sec,
            nonce_hex=nonce_hex,
        )
        return {
            "typedData": td,
            "validAfter": now - 60,
            "validBefore": now + req.ttl_sec,
            "nonce": nonce_hex,
            "instructions": (
                "Sign typedData with the FROM wallet using EIP-712 "
                "(eth_account.messages.encode_typed_data + Account.sign_message), "
                "then POST {transferAuth: {from, to, value, validAfter, validBefore, "
                "nonce, signature}, target?, body?} to /pay or /pay-and-call."
            ),
        }

    @app.post("/pay")
    def pay(req: PayRequest) -> dict[str, object]:
        return _settle_and_maybe_forward(req, do_forward=False)

    @app.post("/pay-and-call")
    def pay_and_call(req: PayRequest) -> dict[str, object]:
        if not req.target:
            raise HTTPException(400, "target URL is required for /pay-and-call")
        return _settle_and_maybe_forward(req, do_forward=True)

    return app


def _settle_and_maybe_forward(
    req: PayRequest, *, do_forward: bool
) -> dict[str, object]:
    ta = req.transferAuth

    td = build_typed_data(
        from_addr=ta.from_addr,
        to=ta.to,
        value=int(ta.value),
        valid_after=ta.valid_after,
        valid_before=ta.valid_before,
        nonce_hex=ta.nonce,
    )

    try:
        recovered = recover_signer(td, ta.signature)
    except Exception as e:
        raise HTTPException(400, f"signature recover failed: {e}") from e

    if recovered.lower() != ta.from_addr.lower():
        raise HTTPException(
            403, f"signer mismatch: recovered {recovered} != from {ta.from_addr}"
        )

    now = int(time.time())
    if now < ta.valid_after:
        raise HTTPException(400, f"authorization not yet valid (validAfter={ta.valid_after}, now={now})")
    if now > ta.valid_before:
        raise HTTPException(400, f"authorization expired (validBefore={ta.valid_before}, now={now})")

    try:
        tx_hash, status = submit_transfer_with_authorization(
            from_addr=ta.from_addr,
            to=ta.to,
            value=int(ta.value),
            valid_after=ta.valid_after,
            valid_before=ta.valid_before,
            nonce_hex=ta.nonce,
            signature_hex=ta.signature,
        )
    except Exception as e:
        raise HTTPException(500, f"on-chain settle failed: {e}") from e

    if status != 1:
        raise HTTPException(500, f"on-chain tx reverted: {tx_hash}")

    settle_result = {
        "paid": True,
        "txHash": tx_hash,
        "explorer": f"{EXPLORER}/tx/{tx_hash}",
        "from": ta.from_addr,
        "to": ta.to,
        "valueUSDCMicros": ta.value,
    }

    if not do_forward or not req.target:
        return settle_result

    forwarded_headers = {
        **req.headers,
        "X-Payment-Tx": tx_hash,
        "X-Payment-Asset": USDC_ADDR,
        "X-Payment-Value": ta.value,
        "X-Payment-Scheme": "x402-eip3009",
    }
    try:
        with httpx.Client(timeout=30.0) as client:
            method = req.method.upper()
            if method == "GET":
                r = client.get(req.target, headers=forwarded_headers)
            else:
                r = client.request(
                    method, req.target, json=req.body, headers=forwarded_headers
                )
            try:
                target_body: Any = r.json()
            except Exception:
                target_body = {"raw": r.text[:1000]}
            return {
                **settle_result,
                "target": req.target,
                "targetStatus": r.status_code,
                "targetBody": target_body,
            }
    except Exception as e:
        return {
            **settle_result,
            "forwardError": str(e),
            "note": "payment succeeded but forward to target failed; tx is final on-chain",
        }


# ─── CLI ───────────────────────────────────────────────────────────────


def cli() -> None:
    app = _build_app()

    if not os.environ.get("X402_RAIL_NO_REGISTER"):
        threading.Thread(
            target=register_until_ready,
            kwargs=dict(
                name=NAME,
                port=PORT,
                paths=["/health", "/meta", "/quote", "/pay", "/pay-and-call"],
                tags=[
                    "x402",
                    "payment-rail",
                    "usdc",
                    "arc-testnet",
                    "real-money",
                    "eip3009",
                    "central-bank",
                ],
                description=(
                    "EIP-3009 USDC payment relay — agents pay agents REAL USDC "
                    "(not 🐚 Shell) via the Coinbase x402 protocol on Arc Testnet"
                ),
                per_call=PER_CALL,
            ),
            daemon=True,
        ).start()

    uvicorn.run(app, host="0.0.0.0", port=PORT, log_level="warning")


if __name__ == "__main__":
    cli()
