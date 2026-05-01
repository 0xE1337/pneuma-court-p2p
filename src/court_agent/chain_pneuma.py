"""Pneuma Soul NFT bridge — mint + read juror identities on Arc Testnet.

This module is what makes a juror more than a temporary daemon process. By
holding a Pneuma Soul NFT (ERC-721 + ERC-6551 TBA pair), a juror gains a
persistent on-chain identity that:

  • survives daemon restarts and machine wipes
  • is cryptographically verifiable on testnet.arcscan.app
  • can carry attestations / reputation across any Pneuma-aware mesh
  • can be cited as 'I voted on this verdict' on any future product

The mint path uses SoulNFT.publicMint() which is **permissionless** — any
EVM wallet on Arc Testnet can mint a Soul. That's the key protocol
property: anyone in the wider anet network can spin up a juror and join
the panel; we just happen to ship 3 of them in this repo as the canonical
demo set.

Required env vars (same as chain.py):
  ARC_RPC_URL                  — JSON-RPC endpoint
  COURT_FINALIZER_PRIVATE_KEY  — wallet that mints + owns the Soul

Optional:
  PNEUMA_SOUL_NFT_ADDRESS      — defaults to the deployed Arc Testnet address
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

ABI_PATH = Path(__file__).resolve().parent.parent.parent / "abi" / "SoulNFT.json"

# Default to the parent project's Arc Testnet deployment. Operators can
# override via env if they redeploy.
DEFAULT_SOUL_NFT_ADDRESS = "0x5b516Cdc56910C07C9b34C2d56b31422da97A959"


def _load_abi() -> list[dict[str, Any]]:
    return json.loads(ABI_PATH.read_text())


def _w3():
    from web3 import Web3  # lazy

    rpc = os.environ.get("ARC_RPC_URL")
    if not rpc:
        raise RuntimeError("ARC_RPC_URL not set in env")
    return Web3(Web3.HTTPProvider(rpc, request_kwargs={"timeout": 15}))


def _contract(w3):
    from web3 import Web3  # lazy

    addr = os.environ.get("PNEUMA_SOUL_NFT_ADDRESS", DEFAULT_SOUL_NFT_ADDRESS)
    return w3.eth.contract(address=Web3.to_checksum_address(addr), abi=_load_abi())


def _account():
    from eth_account import Account  # lazy

    pk = os.environ.get("COURT_FINALIZER_PRIVATE_KEY")
    if not pk:
        raise RuntimeError("COURT_FINALIZER_PRIVATE_KEY not set")
    if pk.startswith("0x"):
        pk = pk[2:]
    return Account.from_key(pk)


def has_pneuma_config() -> bool:
    """True iff env is configured for Pneuma Soul interaction."""
    return bool(
        os.environ.get("ARC_RPC_URL")
        and os.environ.get("COURT_FINALIZER_PRIVATE_KEY")
    )


def total_minted() -> int:
    """Read SoulNFT.totalMinted() — sanity check + 'how big is the network'."""
    return int(_contract(_w3()).functions.totalMinted().call())


def get_soul_info(token_id: int) -> dict[str, Any]:
    """Return owner + TBA address for a given Soul token id."""
    w3 = _w3()
    c = _contract(w3)
    return {
        "tokenId": int(token_id),
        "owner": c.functions.ownerOf(token_id).call(),
        "tba": c.functions.tbaOf(token_id).call(),
    }


def mint_soul(agent_name: str, metadata_uri: str = "") -> dict[str, Any]:
    """Mint a fresh Soul NFT for this juror. Returns {tokenId, tba, txHash}.

    Uses SoulNFT.publicMint() which is permissionless — any wallet works.
    The minted Soul is owned by COURT_FINALIZER_PRIVATE_KEY's address.
    """
    w3 = _w3()
    acct = _account()
    contract = _contract(w3)

    tx = contract.functions.publicMint(agent_name, metadata_uri).build_transaction({
        "from": acct.address,
        "nonce": w3.eth.get_transaction_count(acct.address),
        "gas": 600_000,
        "gasPrice": w3.eth.gas_price,
    })
    signed = acct.sign_transaction(tx)
    tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
    receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=60)

    # Decode SoulMinted event for tokenId + tba
    events = contract.events.SoulMinted().process_receipt(receipt)
    if not events:
        # Fall back to totalMinted() — the just-minted id is the post-increment
        token_id = int(contract.functions.totalMinted().call())
        return {
            "tokenId": token_id,
            "tba": contract.functions.tbaOf(token_id).call(),
            "owner": acct.address,
            "txHash": tx_hash.hex(),
            "agentName": agent_name,
        }

    args = events[0]["args"]
    return {
        "tokenId": int(args["tokenId"]),
        "tba": args["tba"],
        "owner": args["owner"],
        "txHash": tx_hash.hex(),
        "agentName": args["agentName"],
    }


# ────────────────────────────────────────────────────────────────────────
# Per-juror Soul identity cache (so a juror mints once and re-uses on
# subsequent boots)
# ────────────────────────────────────────────────────────────────────────

CACHE_DIR = Path(os.environ.get("PNEUMA_SOUL_CACHE_DIR",
                                str(Path.home() / ".pneuma-court-souls")))


def _cache_file(juror_name: str) -> Path:
    return CACHE_DIR / f"{juror_name}.json"


def load_cached_identity(juror_name: str) -> dict[str, Any] | None:
    fp = _cache_file(juror_name)
    if not fp.exists():
        return None
    try:
        return json.loads(fp.read_text())
    except Exception:  # noqa: BLE001
        return None


def save_cached_identity(juror_name: str, identity: dict[str, Any]) -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    _cache_file(juror_name).write_text(json.dumps(identity, indent=2))


def ensure_juror_soul(juror_name: str) -> dict[str, Any] | None:
    """Get-or-mint a Soul for this juror. Returns identity dict or None if
    Pneuma config is missing (graceful fallback to anet-only mode).

    First call mints (~15s incl tx confirm). Subsequent calls hit the local
    cache and return immediately.
    """
    cached = load_cached_identity(juror_name)
    if cached:
        return cached

    if not has_pneuma_config():
        return None

    try:
        identity = mint_soul(
            agent_name=juror_name,
            metadata_uri=f"pneuma-court://{juror_name}",
        )
    except Exception as e:  # noqa: BLE001
        # Don't crash juror boot on chain errors — surface and continue anet-only
        print(f"[chain_pneuma] mint failed for {juror_name}: {e}", flush=True)
        return None

    save_cached_identity(juror_name, identity)
    return identity


def explorer_url(token_id: int) -> str:
    addr = os.environ.get("PNEUMA_SOUL_NFT_ADDRESS", DEFAULT_SOUL_NFT_ADDRESS)
    base = os.environ.get("ARC_EXPLORER", "https://testnet.arcscan.app")
    return f"{base}/token/{addr}/instance/{token_id}"
