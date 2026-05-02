"""ERC-6551 Token-Bound Account helper — route on-chain writes through
a Soul's TBA so `msg.sender` of the inner call becomes the TBA address.

Why this exists:
  CourtEscrow (and most well-designed escrow contracts) check
  `msg.sender == c.caller` to gate sensitive ops like `fileDispute`. If
  we want the *agent's TBA* — not the operator EOA — to be the legal
  caller, the operator must call `TBA.execute(...)` which forwards the
  inner call with the TBA itself as msg.sender.

  This closes the loop on the parent project's ERC-6551 design: a Soul
  isn't just an identity badge, the TBA derived from it is the agent's
  actual on-chain wallet — capable of holding funds and signing actions
  through its owner EOA.

The TBA implementation deployed on Arc Testnet is `SoulAccount`, a
custom variant of the ERC-6551 account standard. It uses the standard
v3 `execute(address,uint256,bytes,uint8)` selector with `operation=0`
meaning a regular CALL.
"""

from __future__ import annotations

from typing import Any


# Standard ERC-6551 v3 + minimal owner getter.
TBA_EXECUTE_ABI: list[dict[str, Any]] = [
    {
        "inputs": [
            {"name": "to", "type": "address"},
            {"name": "value", "type": "uint256"},
            {"name": "data", "type": "bytes"},
            {"name": "operation", "type": "uint8"},
        ],
        "name": "execute",
        "outputs": [{"name": "", "type": "bytes"}],
        "stateMutability": "payable",
        "type": "function",
    },
    {
        "inputs": [],
        "name": "owner",
        "outputs": [{"name": "", "type": "address"}],
        "stateMutability": "view",
        "type": "function",
    },
    {
        "inputs": [],
        "name": "token",
        "outputs": [
            {"name": "chainId", "type": "uint256"},
            {"name": "tokenContract", "type": "address"},
            {"name": "tokenId", "type": "uint256"},
        ],
        "stateMutability": "view",
        "type": "function",
    },
]


def tba_execute(
    w3,
    signer_account,
    tba_address: str,
    target: str,
    value: int,
    calldata: bytes | str,
    *,
    gas: int = 400_000,
) -> tuple[str, int]:
    """Operator EOA signs `TBA.execute(target, value, calldata, op=0)`.

    The inner call lands on `target` with `msg.sender = tba_address`.

    Args:
        w3:               web3.Web3 instance
        signer_account:   eth_account.Account who is the Soul-owner EOA
        tba_address:      the TBA address (ERC-6551 account)
        target:           contract to call from the TBA's perspective
        value:            wei to send (usually 0 for ERC-20 / dispute flows)
        calldata:         encoded function data (bytes or 0x-prefixed hex)
        gas:              gas limit for the outer execute() tx

    Returns:
        (outer_tx_hash_hex, status)  status=1 if mined ok
    """
    from web3 import Web3

    if isinstance(calldata, str):
        calldata = bytes.fromhex(calldata.removeprefix("0x"))

    tba = w3.eth.contract(
        address=Web3.to_checksum_address(tba_address), abi=TBA_EXECUTE_ABI
    )
    fn = tba.functions.execute(
        Web3.to_checksum_address(target),
        int(value),
        calldata,
        0,  # operation = CALL
    )

    nonce = w3.eth.get_transaction_count(signer_account.address)
    tx = fn.build_transaction(
        {
            "from": signer_account.address,
            "nonce": nonce,
            "gas": gas,
            "gasPrice": w3.eth.gas_price,
        }
    )
    signed = signer_account.sign_transaction(tx)
    h = w3.eth.send_raw_transaction(signed.raw_transaction)
    receipt = w3.eth.wait_for_transaction_receipt(h, timeout=90)
    return ("0x" + h.hex().removeprefix("0x"), int(receipt.status))


def tba_owner(w3, tba_address: str) -> str:
    """Return the EOA that owns the Soul that owns this TBA."""
    from web3 import Web3

    tba = w3.eth.contract(
        address=Web3.to_checksum_address(tba_address), abi=TBA_EXECUTE_ABI
    )
    return tba.functions.owner().call()
