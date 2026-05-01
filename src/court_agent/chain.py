"""Arc Testnet bridge — read PneumaCourt state + send finalize tx.

Sprint 0 placeholder.

Required env:
    ARC_RPC_URL
    PNEUMA_COURT_ADDRESS
    COURT_FINALIZER_PRIVATE_KEY  (must have JUROR_ROLE on the contract)

API:
    get_dispute(dispute_id: int) -> dict
        — calls PneumaCourt.getDispute(disputeId), returns parsed struct

    finalize_dispute(call_id: int, verdict: str) -> str
        — sends PneumaCourt.finalize(disputeId, verdict) tx
        — returns tx hash; reverts if caller lacks role
"""

from __future__ import annotations

# import json
# import os
# from pathlib import Path
# from web3 import Web3
# from eth_account import Account

# ABI_PATH = Path(__file__).resolve().parent.parent.parent / "abi" / "PneumaCourt.json"
# (Sprint 1 will load ABI + build contract handle)
