"""CourtEscrow on Arc Testnet — independent stake/slash enforcement.

This is the on-chain enforcement layer for Pneuma Court. Stand-alone:
no dependency on the parent Pneuma Protocol's SkillRegistry. The
contract is deployed at COURT_ESCROW_ADDRESS in .env.

Roles:
    deployer  — set at construction; can re-bind the court authority
    court     — only address that can call resolveDispute()
    provider  — anyone who stakes USDC via stake(amount)
    caller    — anyone who escrows USDC via escrowCall(provider, amount)

Lifecycle for a single call:

    1. provider.stake(N USDC)           [providers do this once, ahead of time]
    2. caller.escrowCall(provider, M)   [locks min(M, provider.available_stake)]
    3a. caller.settleCall(callId)       [happy path → escrow transfers to provider]
    3b. caller.fileDispute(callId, h)   [dispute path]
    4. court.resolveDispute(caseId, p)  [court signs after off-chain verdict]
       if plaintiffWins:
           caller += escrow + slash(50% of locked stake)
       else:
           provider += escrow, stake unlocks, no slash

Functions used by court_agent.proxy:
    file_dispute_and_resolve(call_id, evidence, plaintiff_wins) — full path
    open_call(provider, amount)         — set up a fresh demo call
    get_call(call_id) / get_case(...)   — read-only state probes
    explorer_url(tx_hash)               — return arcscan link
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

ABI_PATH = Path(__file__).resolve().parent.parent.parent / "abi" / "CourtEscrow.json"


def _has_escrow_config() -> bool:
    return bool(
        os.environ.get("ARC_RPC_URL")
        and os.environ.get("COURT_ESCROW_ADDRESS")
        and os.environ.get("COURT_FINALIZER_PRIVATE_KEY")
    )


def _w3():
    from web3 import Web3
    rpc = os.environ.get("ARC_RPC_URL")
    if not rpc:
        raise RuntimeError("ARC_RPC_URL not set in env")
    return Web3(Web3.HTTPProvider(rpc, request_kwargs={"timeout": 15}))


def _escrow(w3):
    from web3 import Web3
    addr = os.environ.get("COURT_ESCROW_ADDRESS")
    if not addr:
        raise RuntimeError("COURT_ESCROW_ADDRESS not set in env")
    abi = json.loads(ABI_PATH.read_text())
    return w3.eth.contract(address=Web3.to_checksum_address(addr), abi=abi)


def _account():
    from eth_account import Account
    pk = os.environ.get("COURT_FINALIZER_PRIVATE_KEY")
    if not pk:
        raise RuntimeError("COURT_FINALIZER_PRIVATE_KEY not set")
    if pk.startswith("0x"):
        pk = pk[2:]
    return Account.from_key(pk)


def _send(w3, contract_fn, *, from_acct, gas: int = 300_000) -> str:
    """Build, sign, send, wait — return tx hash hex."""
    nonce = w3.eth.get_transaction_count(from_acct.address)
    tx = contract_fn.build_transaction({
        "from": from_acct.address,
        "nonce": nonce,
        "gas": gas,
        "gasPrice": w3.eth.gas_price,
    })
    signed = from_acct.sign_transaction(tx)
    h = w3.eth.send_raw_transaction(signed.raw_transaction)
    w3.eth.wait_for_transaction_receipt(h, timeout=60)
    return h.hex()


# ────────────────────────────────────────────────────────────────────────
# View functions
# ────────────────────────────────────────────────────────────────────────


def get_call(call_id: int) -> dict[str, Any]:
    w3 = _w3()
    raw = _escrow(w3).functions.getCall(call_id).call()
    return {
        "callId": int(raw[0]),
        "caller": raw[1],
        "provider": raw[2],
        "escrowedAmount": int(raw[3]),
        "lockedStake": int(raw[4]),
        "status": ["Empty", "Escrowed", "Settled", "Disputed", "Resolved"][int(raw[5])],
    }


def get_case(case_id: int) -> dict[str, Any]:
    w3 = _w3()
    raw = _escrow(w3).functions.getCase(case_id).call()
    return {
        "caseId": int(raw[0]),
        "callId": int(raw[1]),
        "evidenceHash": raw[2].hex() if isinstance(raw[2], (bytes, bytearray)) else str(raw[2]),
        "outcome": ["Pending", "PlaintiffWins", "DefendantWins"][int(raw[3])],
    }


def get_provider_stake(provider: str) -> dict[str, int]:
    from web3 import Web3
    w3 = _w3()
    e = _escrow(w3)
    p = Web3.to_checksum_address(provider)
    return {
        "total": int(e.functions.providerStake(p).call()),
        "locked": int(e.functions.lockedStake(p).call()),
        "available": int(e.functions.availableStake(p).call()),
    }


def explorer_tx(tx_hash: str) -> str:
    base = os.environ.get("ARC_EXPLORER", "https://testnet.arcscan.app")
    return f"{base}/tx/{tx_hash if tx_hash.startswith('0x') else '0x' + tx_hash}"


def explorer_addr(addr: str) -> str:
    base = os.environ.get("ARC_EXPLORER", "https://testnet.arcscan.app")
    return f"{base}/address/{addr}"


# ────────────────────────────────────────────────────────────────────────
# Court-side write — only this server's wallet can call resolve
# ────────────────────────────────────────────────────────────────────────


def resolve_dispute_onchain(case_id: int, plaintiff_wins: bool) -> str:
    """Court signs the resolution — slashes provider stake to caller (or
    releases escrow to provider). Returns the resolve tx hash."""
    w3 = _w3()
    acct = _account()
    fn = _escrow(w3).functions.resolveDispute(case_id, plaintiff_wins)
    return _send(w3, fn, from_acct=acct, gas=400_000)
