"""Arc Testnet bridge — read PneumaCourt state and finalize verdicts on-chain.

Required env vars:
    ARC_RPC_URL                    — JSON-RPC endpoint
    PNEUMA_COURT_ADDRESS           — contract address (default in .env.example)
    COURT_FINALIZER_PRIVATE_KEY    — wallet with JUROR_ROLE on PneumaCourt

Workflow per dispute (off-chain mesh deliberation already produced a verdict):
    1. vote(disputeId, code)       — finalizer casts a single aggregated vote
    2. finalize(disputeId)         — closes the case, slash/refund triggers fire
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

# NOTE: web3 and eth_account are imported lazily inside the functions that
# actually need them. This keeps has_chain_config() and the module itself
# importable in environments where the chain deps aren't installed (e.g.
# CI running pure-logic tests, or anet-only deployments where the operator
# never plans to wire on-chain).

ABI_PATH = Path(__file__).resolve().parent.parent.parent / "abi" / "PneumaCourt.json"

# Mirrors the Solidity Verdict enum in PneumaCourt.sol:
#   enum Verdict { NONE, PLAINTIFF, DEFENDANT, ABSTAIN }
_VERDICT_CODE: dict[str, int] = {
    "NONE": 0,
    "PLAINTIFF": 1,
    "DEFENDANT": 2,
    "ABSTAIN": 3,
}


def _load_abi() -> list[dict[str, Any]]:
    return json.loads(ABI_PATH.read_text())


def _w3():
    from web3 import Web3  # lazy: only needed when chain ops actually run

    rpc = os.environ.get("ARC_RPC_URL")
    if not rpc:
        raise RuntimeError("ARC_RPC_URL not set in env")
    return Web3(Web3.HTTPProvider(rpc, request_kwargs={"timeout": 15}))


def _contract(w3):
    from web3 import Web3  # lazy

    addr = os.environ.get("PNEUMA_COURT_ADDRESS")
    if not addr:
        raise RuntimeError("PNEUMA_COURT_ADDRESS not set in env")
    return w3.eth.contract(address=Web3.to_checksum_address(addr), abi=_load_abi())


def _finalizer_account():
    from eth_account import Account  # lazy

    pk = os.environ.get("COURT_FINALIZER_PRIVATE_KEY")
    if not pk:
        raise RuntimeError("COURT_FINALIZER_PRIVATE_KEY not set")
    if pk.startswith("0x"):
        pk = pk[2:]
    return Account.from_key(pk)


def has_chain_config() -> bool:
    """True iff this court has the env config to write on-chain.

    Used by the proxy to decide on-chain vs anet-only at deliberation time.
    Missing any one of these three vars → automatic fallback to anet-only.
    """
    return all(
        os.environ.get(k)
        for k in ("ARC_RPC_URL", "PNEUMA_COURT_ADDRESS", "COURT_FINALIZER_PRIVATE_KEY")
    )


def get_dispute(dispute_id: int) -> dict[str, Any]:
    """Read PneumaCourt.getDispute(disputeId). Returns the raw struct tuple
    plus a `raw` echo so callers can inspect; field decoding is left to the
    caller because the struct shape is part of the contract version."""
    w3 = _w3()
    raw = _contract(w3).functions.getDispute(dispute_id).call()
    return {"raw": raw}


def file_dispute(call_id: int, evidence: str) -> tuple[int, str]:
    """Open a dispute on-chain. Court operator pays gas — caller needs no wallet.

    Returns (dispute_id, tx_hash). Raises if the receipt has no DisputeFiled
    event or if the wallet/RPC is misconfigured.
    """
    w3 = _w3()
    acct = _finalizer_account()
    contract = _contract(w3)

    tx = contract.functions.fileDispute(call_id, evidence).build_transaction({
        "from": acct.address,
        "nonce": w3.eth.get_transaction_count(acct.address),
        "gas": 300_000,
        "gasPrice": w3.eth.gas_price,
    })
    signed = acct.sign_transaction(tx)
    tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
    receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=60)

    # Decode DisputeFiled event to extract the dispute id assigned by the contract.
    try:
        events = contract.events.DisputeFiled().process_receipt(receipt)
    except Exception:  # noqa: BLE001 — fall back to manual log parsing below
        events = []

    if events:
        dispute_id = int(events[0]["args"]["disputeId"])
    else:
        # Fallback: many implementations also expose disputeCount() — read it
        # back as the just-assigned id (count is post-incremented).
        dispute_id = int(contract.functions.disputeCount().call())
        if dispute_id == 0:
            raise RuntimeError(
                f"fileDispute receipt parsed no event and disputeCount=0 "
                f"(tx={tx_hash.hex()})"
            )

    return dispute_id, tx_hash.hex()


def finalize_dispute(dispute_id: int, verdict: str) -> str:
    """Cast aggregated vote + finalize. Returns the finalize tx hash (hex)."""
    code = _VERDICT_CODE.get(verdict)
    if code is None or verdict == "NONE":
        raise ValueError(f"Invalid verdict for on-chain submission: {verdict!r}")

    w3 = _w3()
    acct = _finalizer_account()
    contract = _contract(w3)

    # Best-effort: skip vote() if finalizer has already voted (lets the demo
    # be re-runnable on the same disputeId without revert).
    already_voted = False
    try:
        already_voted = contract.functions.hasVoted(dispute_id, acct.address).call()
    except Exception:  # noqa: BLE001 — view fallback, ignore
        pass

    nonce = w3.eth.get_transaction_count(acct.address)
    gas_price = w3.eth.gas_price

    if not already_voted:
        vote_tx = contract.functions.vote(dispute_id, code).build_transaction({
            "from": acct.address,
            "nonce": nonce,
            "gas": 200_000,
            "gasPrice": gas_price,
        })
        signed_vote = acct.sign_transaction(vote_tx)
        vote_hash = w3.eth.send_raw_transaction(signed_vote.raw_transaction)
        w3.eth.wait_for_transaction_receipt(vote_hash, timeout=60)
        nonce += 1

    fin_tx = contract.functions.finalize(dispute_id).build_transaction({
        "from": acct.address,
        "nonce": nonce,
        "gas": 250_000,
        "gasPrice": gas_price,
    })
    signed_fin = acct.sign_transaction(fin_tx)
    fin_hash = w3.eth.send_raw_transaction(signed_fin.raw_transaction)
    w3.eth.wait_for_transaction_receipt(fin_hash, timeout=60)

    return fin_hash.hex()
