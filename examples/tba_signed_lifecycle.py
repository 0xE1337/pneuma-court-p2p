"""ERC-6551 TBA-routed CourtEscrow lifecycle on Arc Testnet.

Demonstrates the **fully integrated** Pneuma stack: caller is an agent's
ERC-6551 TBA (Token-Bound Account) bound to a Soul NFT. The Soul-owner
EOA signs `TBA.execute(...)` so CourtEscrow sees the TBA address as
msg.sender — fileDispute works **without any meta-tx relayer**.

This closes the loop on the parent project's identity-and-authority
unification. The Soul (ERC-721) is the identity; the TBA (ERC-6551) is
the on-chain actor; together they make the agent a first-class on-chain
citizen.

Lifecycle (all on Arc Testnet):

    0. mint a fresh Soul → derive caller's TBA
    1. operator funds caller's TBA with USDC
    2. provider stakes 5 USDC (provider == operator EOA, direct sign)
    3. caller TBA approves CourtEscrow (via TBA.execute)
    4. caller TBA escrows 1 USDC (via TBA.execute)
         ↳ on-chain c.caller = TBA address (NOT operator EOA)
    5. caller TBA files dispute (via TBA.execute)
         ↳ msg.sender = TBA == c.caller ✓ — non-custodial
    6. court resolves (operator EOA, plaintiffWins=True)
         ↳ caller TBA receives 1.50 USDC (1.00 refund + 0.50 slash)

Compare to `examples/escrow_lifecycle.py` which takes the convenience
shortcut of having the operator EOA sign every step. This file shows
the production-correct flow where caller and provider are different
on-chain actors and the caller is an agent (not a human).
"""

from __future__ import annotations

import os
import sys
import time

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from court_agent.chain_pneuma import _account, _w3, mint_soul
from court_agent.escrow import _escrow
from court_agent.tba import tba_execute

CHAIN_ID = int(os.environ.get("ARC_CHAIN_ID", "5042002"))
USDC_ADDR = os.environ.get("USDC_ADDRESS", "0x3600000000000000000000000000000000000000")
EXPLORER = os.environ.get("ARC_EXPLORER", "https://testnet.arcscan.app")

USDC_ABI = [
    {
        "inputs": [{"name": "to", "type": "address"}, {"name": "amount", "type": "uint256"}],
        "name": "transfer",
        "outputs": [{"type": "bool"}],
        "stateMutability": "nonpayable",
        "type": "function",
    },
    {
        "inputs": [{"name": "spender", "type": "address"}, {"name": "amount", "type": "uint256"}],
        "name": "approve",
        "outputs": [{"type": "bool"}],
        "stateMutability": "nonpayable",
        "type": "function",
    },
    {
        "inputs": [{"name": "account", "type": "address"}],
        "name": "balanceOf",
        "outputs": [{"type": "uint256"}],
        "stateMutability": "view",
        "type": "function",
    },
]

STAKE_MICROS = 5_000_000     # 5 USDC
ESCROW_MICROS = 1_000_000    # 1 USDC
TBA_FUND_MICROS = 1_500_000  # 1.5 USDC (escrow + small buffer)


def fmt(micros: int) -> str:
    return f"{micros / 1_000_000:.6f} USDC"


def _send_direct(w3, account, fn, gas: int = 400_000) -> tuple[str, dict]:
    nonce = w3.eth.get_transaction_count(account.address)
    tx = fn.build_transaction(
        {
            "from": account.address,
            "nonce": nonce,
            "gas": gas,
            "gasPrice": w3.eth.gas_price,
        }
    )
    signed = account.sign_transaction(tx)
    h = w3.eth.send_raw_transaction(signed.raw_transaction)
    receipt = w3.eth.wait_for_transaction_receipt(h, timeout=90)
    return ("0x" + h.hex().removeprefix("0x"), receipt)


def main() -> int:
    from web3 import Web3

    w3 = _w3()
    operator = _account()
    escrow_addr = Web3.to_checksum_address(
        os.environ.get("COURT_ESCROW_ADDRESS", "0x72E945cD718E6A5b36C34896343a436D3e7dd8d0")
    )

    usdc = w3.eth.contract(address=Web3.to_checksum_address(USDC_ADDR), abi=USDC_ABI)
    escrow = _escrow(w3)

    print("══ 🪪→⚖️  TBA-ROUTED COURTESCROW LIFECYCLE ══════════════════════════")
    print()
    print("▸ pre-flow setup:")
    print(f"  operator EOA          {operator.address}")
    print(f"  CourtEscrow           {escrow_addr}")
    print(f"  USDC                  {USDC_ADDR}")
    print()

    # ─── Step 0: Mint Soul → derive TBA ──────────────────────────────
    print("▸ step 0: mint Soul NFT (ERC-721) → derive caller TBA (ERC-6551)")
    soul = mint_soul(
        agent_name=f"court-p2p-caller-{int(time.time())}",
        metadata_uri="pneuma-court://tba-lifecycle-demo",
    )
    caller_tba = Web3.to_checksum_address(soul["tba"])
    soul_mint_tx = soul["txHash"] if soul["txHash"].startswith("0x") else "0x" + soul["txHash"]
    print(f"  Soul tokenId          {soul['tokenId']}")
    print(f"  caller TBA            {caller_tba}")
    print(f"  mint tx               {EXPLORER}/tx/{soul_mint_tx}")
    print()

    op_pre = int(usdc.functions.balanceOf(operator.address).call())
    tba_pre = int(usdc.functions.balanceOf(caller_tba).call())
    print(f"  operator USDC pre     {fmt(op_pre)}")
    print(f"  caller TBA USDC pre   {fmt(tba_pre)}")
    print()

    # ─── Step 1: fund TBA ────────────────────────────────────────────
    print("▸ step 1: operator funds caller TBA with USDC")
    h1, _ = _send_direct(w3, operator, usdc.functions.transfer(caller_tba, TBA_FUND_MICROS))
    print(f"  USDC.transfer → TBA   {h1[:18]}…")
    print()

    # ─── Step 2: provider stakes ─────────────────────────────────────
    print("▸ step 2: provider (= operator EOA, direct sign) stakes 5 USDC")
    h2a, _ = _send_direct(w3, operator, usdc.functions.approve(escrow_addr, STAKE_MICROS))
    print(f"  USDC.approve(Escrow)  {h2a[:18]}…")
    h2b, _ = _send_direct(w3, operator, escrow.functions.stake(STAKE_MICROS))
    print(f"  CourtEscrow.stake     {h2b[:18]}…")
    print()

    # ─── Step 3: TBA approves CourtEscrow (via TBA.execute) ──────────
    print("▸ step 3: caller TBA approves CourtEscrow (via TBA.execute) — TBA is msg.sender")
    approve_data = usdc.encode_abi(abi_element_identifier="approve", args=[escrow_addr, ESCROW_MICROS])
    h3, status3 = tba_execute(w3, operator, caller_tba, USDC_ADDR, 0, approve_data)
    if status3 != 1:
        print(f"  ✗ TBA approve reverted: {h3}")
        return 1
    print(f"  TBA.execute → approve {h3[:18]}…")
    print()

    # ─── Step 4: TBA escrows (via TBA.execute) ───────────────────────
    print("▸ step 4: caller TBA escrows 1 USDC (via TBA.execute) — c.caller = TBA")
    escrow_call_data = escrow.encode_abi(
        abi_element_identifier="escrowCall", args=[operator.address, ESCROW_MICROS]
    )
    h4, status4 = tba_execute(w3, operator, caller_tba, escrow_addr, 0, escrow_call_data)
    if status4 != 1:
        print(f"  ✗ TBA escrow reverted: {h4}")
        return 1
    print(f"  TBA.execute → escrow  {h4[:18]}…")

    # decode CallEscrowed
    receipt4 = w3.eth.get_transaction_receipt(h4)
    call_id = None
    for log in receipt4["logs"]:
        try:
            evt = escrow.events.CallEscrowed().process_log(log)
            call_id = int(evt["args"]["callId"])
            break
        except Exception:
            continue
    if call_id is None:
        print("  ⚠ couldn't decode CallEscrowed — falling back to callCount()")
        call_id = int(escrow.functions.callCount().call())
    print(f"  callId                {call_id}")

    call = escrow.functions.getCall(call_id).call()
    c_caller_onchain = Web3.to_checksum_address(call[1])
    is_match = c_caller_onchain.lower() == caller_tba.lower()
    print(f"  c.caller on-chain     {c_caller_onchain}")
    print(f"  matches TBA?          {'✓ YES — TBA is the on-chain caller' if is_match else '✗ MISMATCH'}")
    if not is_match:
        return 1
    print()

    # ─── Step 5: TBA files dispute (via TBA.execute) ─────────────────
    print("▸ step 5: caller TBA files dispute (via TBA.execute) — NON-CUSTODIAL")
    evidence_hash = bytes.fromhex("dead" * 16)  # 32 bytes placeholder
    file_dispute_data = escrow.encode_abi(
        abi_element_identifier="fileDispute", args=[call_id, evidence_hash]
    )
    h5, status5 = tba_execute(w3, operator, caller_tba, escrow_addr, 0, file_dispute_data)
    if status5 != 1:
        print(f"  ✗ TBA fileDispute reverted: {h5}")
        return 1
    print(f"  TBA.execute → dispute {h5[:18]}…")

    receipt5 = w3.eth.get_transaction_receipt(h5)
    case_id = None
    for log in receipt5["logs"]:
        try:
            evt = escrow.events.DisputeFiled().process_log(log)
            case_id = int(evt["args"]["caseId"])
            break
        except Exception:
            continue
    if case_id is None:
        print("  ⚠ couldn't decode DisputeFiled — falling back to caseCount()")
        case_id = int(escrow.functions.caseCount().call())
    print(f"  caseId                {case_id}")
    print()

    # ─── Step 6: court resolves (plaintiff wins) ─────────────────────
    print("▸ step 6: court resolves dispute (plaintiff wins) — operator EOA direct")
    h6, _ = _send_direct(w3, operator, escrow.functions.resolveDispute(case_id, True))
    print(f"  resolveDispute(plaintiff=True)   {h6[:18]}…")
    print()

    # ─── Verify ──────────────────────────────────────────────────────
    print("══ POST-FLOW VERIFICATION ══════════════════════════════════════════")
    op_post = int(usdc.functions.balanceOf(operator.address).call())
    tba_post = int(usdc.functions.balanceOf(caller_tba).call())
    delta = tba_post - tba_pre
    print(f"  operator USDC  post   {fmt(op_post)}")
    print(f"  caller TBA USDC post  {fmt(tba_post)}")
    print(f"  TBA delta             +{fmt(delta)}  (expected: 2.000000 = 1.50 funded - 1.00 escrowed + 1.00 refund + 0.50 slash)")
    print()

    case = escrow.functions.getCase(case_id).call()
    outcome_int = int(case[3])
    outcome_str = ["Pending", "PlaintiffWins", "DefendantWins"][outcome_int]
    print(f"  case[{case_id}].outcome      {outcome_str}")
    print()

    print("══ ✓ TBA-ROUTED LIFECYCLE COMPLETE ════════════════════════════════")
    print()
    print("   The agent's ERC-6551 TBA acted as the on-chain caller throughout.")
    print("   No meta-tx relayer needed — the Soul-bound TBA *is* the wallet.")
    print()
    print("   Tx trail:")
    print(f"     0. Soul mint            {EXPLORER}/tx/{soul_mint_tx}")
    print(f"     1. fund TBA             {EXPLORER}/tx/{h1}")
    print(f"     2a. provider approve    {EXPLORER}/tx/{h2a}")
    print(f"     2b. provider stake      {EXPLORER}/tx/{h2b}")
    print(f"     3. TBA approve  →       {EXPLORER}/tx/{h3}")
    print(f"     4. TBA escrowCall →     {EXPLORER}/tx/{h4}  (c.caller = TBA)")
    print(f"     5. TBA fileDispute →    {EXPLORER}/tx/{h5}  (msg.sender = TBA)")
    print(f"     6. court resolve →      {EXPLORER}/tx/{h6}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
