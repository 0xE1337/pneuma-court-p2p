"""Arc Testnet bridge — read PneumaCourt state.

Required env vars:
    ARC_RPC_URL                    — JSON-RPC endpoint
    PNEUMA_COURT_ADDRESS           — contract address (default in .env.example)
    COURT_FINALIZER_PRIVATE_KEY    — finalizer wallet (gas + future writes)

────────────────────────────────────────────────────────────────────────
WRITE-PATH STATUS — read carefully before enabling on-chain finalize
────────────────────────────────────────────────────────────────────────

PneumaCourt's `fileDispute(callId, evidenceHash, description, jurors[])`
has stricter invariants than a generic on-chain logger:

    1. msg.sender MUST be the plaintiff — i.e. the original `caller`
       address recorded in SkillRegistry.getCall(callId). If our court
       service tries to fileDispute on the caller's behalf, the contract
       reverts with NotPlaintiff.

    2. The call referenced by `callId` MUST be settled (status == 1).
       Unsettled calls go through the timeout-slash path, not the court.

    3. `jurors` MUST be ≥ MIN_JURORS (3) addresses, each holding a Soul
       NFT, none of them the plaintiff or defendant.

These invariants are by design: the court is the parent Pneuma protocol's
on-chain dispute lifecycle, where every party already holds a wallet and
a Soul. Our anet-side multi-juror deliberation is a complementary off-
chain layer — it produces the *reasoning* a Pneuma user can attach to a
real fileDispute call when they later raise one through the parent app.

For the sponsor-track submission window, this module exposes only
read-only on-chain helpers (has_chain_config, get_dispute, disputeCount).
The write path is intentionally not implemented here — wiring it up
requires either:

  (a) a meta-tx / account-abstraction relayer so the court can fileDispute
      on the caller's behalf (v0.2 work), or
  (b) the caller signing fileDispute themselves through the parent Pneuma
      hub UI (already implemented at apps/hub/app/court/new in the parent
      project — out of scope for this repo).
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


def dispute_count() -> int:
    """Read PneumaCourt.disputeCount() — useful as a sanity check that
    RPC + contract address + ABI all align."""
    w3 = _w3()
    return int(_contract(w3).functions.disputeCount().call())


# ────────────────────────────────────────────────────────────────────────
# Write path — intentionally not implemented in v0.1.
#
# See the module docstring for why fileDispute / finalize cannot be safely
# invoked from this service: msg.sender must be the plaintiff (the original
# SkillRegistry caller) and jurors must be N independent Soul holders. A
# single court-operator wallet acting on behalf of an anet caller would
# revert with NotPlaintiff. The proxy gates on this and runs anet-only
# unless a future meta-tx / AA relayer is wired up.
# ────────────────────────────────────────────────────────────────────────


def file_dispute(call_id: int, evidence: str) -> tuple[int, str]:
    raise NotImplementedError(
        "fileDispute requires msg.sender to be the original SkillRegistry "
        "caller (plaintiff) with N Soul-holding jurors. See chain.py "
        "module docstring for the v0.2 meta-tx plan."
    )


def finalize_dispute(dispute_id: int, verdict: str) -> str:
    raise NotImplementedError(
        "finalize requires the dispute to have been filed first via "
        "fileDispute (caller-signed). See chain.py module docstring."
    )
