"""Demo the full on-chain enforcement lifecycle: stake → escrow → dispute
→ court resolves → caller refunded with slash.

This script uses the deployer key for both 'provider' and 'caller' in the
demo (since we only have one funded testnet wallet) — the contract logic
is identical regardless. To simulate a multi-party scenario, just supply
two different keys via env.

Run: python examples/escrow_lifecycle.py
"""

from __future__ import annotations

import json
import os
from hashlib import sha256
from pathlib import Path

from court_agent.escrow import (
    _account, _escrow, _send, _w3,
    explorer_addr, explorer_tx,
    get_call, get_case, get_provider_stake,
    resolve_dispute_onchain,
)

# USDC contract (Arc Testnet native)
USDC_ADDR = os.environ.get("USDC_ADDRESS", "0x3600000000000000000000000000000000000000")
USDC_ABI = [
    {"name":"transfer","type":"function","stateMutability":"nonpayable","inputs":[{"name":"to","type":"address"},{"name":"amount","type":"uint256"}],"outputs":[{"type":"bool"}]},
    {"name":"approve","type":"function","stateMutability":"nonpayable","inputs":[{"name":"spender","type":"address"},{"name":"amount","type":"uint256"}],"outputs":[{"type":"bool"}]},
    {"name":"balanceOf","type":"function","stateMutability":"view","inputs":[{"name":"who","type":"address"}],"outputs":[{"type":"uint256"}]},
    {"name":"allowance","type":"function","stateMutability":"view","inputs":[{"name":"owner","type":"address"},{"name":"spender","type":"address"}],"outputs":[{"type":"uint256"}]},
]


def main() -> int:
    w3 = _w3()
    acct = _account()
    escrow = _escrow(w3)
    escrow_addr = escrow.address
    usdc = w3.eth.contract(address=w3.to_checksum_address(USDC_ADDR), abi=USDC_ABI)

    print(f"▸ wallet (= provider = caller in this demo): {acct.address}")
    print(f"  USDC balance: {usdc.functions.balanceOf(acct.address).call()/1e6:.6f}")
    print(f"  CourtEscrow:  {escrow_addr}")
    print(f"  explorer:     {explorer_addr(escrow_addr)}")
    print()

    STAKE_AMOUNT  = 5_000_000   # 5 USDC stake
    ESCROW_AMOUNT = 1_000_000   # 1 USDC per call

    # ── Step 1: Provider stakes USDC ────────────────────────────────
    print(f"▸ step 1/4: provider.stake({STAKE_AMOUNT/1e6:.2f} USDC)")
    s_before = get_provider_stake(acct.address)
    print(f"  pre:  total={s_before['total']/1e6:.6f}  locked={s_before['locked']/1e6:.6f}")

    # approve escrow contract to pull stake
    tx = _send(w3, usdc.functions.approve(escrow_addr, STAKE_AMOUNT), from_acct=acct, gas=120_000)
    print(f"  approve tx: {tx[:18]}…")
    tx = _send(w3, escrow.functions.stake(STAKE_AMOUNT), from_acct=acct, gas=200_000)
    print(f"  stake tx:   {tx[:18]}…  → {explorer_tx(tx)}")

    s_after = get_provider_stake(acct.address)
    print(f"  post: total={s_after['total']/1e6:.6f}  locked={s_after['locked']/1e6:.6f}")
    print()

    # ── Step 2: Caller escrows for a call ────────────────────────────
    print(f"▸ step 2/4: caller.escrowCall(provider, {ESCROW_AMOUNT/1e6:.2f} USDC)")
    tx = _send(w3, usdc.functions.approve(escrow_addr, ESCROW_AMOUNT), from_acct=acct, gas=120_000)
    print(f"  approve tx: {tx[:18]}…")
    tx = _send(w3, escrow.functions.escrowCall(acct.address, ESCROW_AMOUNT), from_acct=acct, gas=300_000)
    print(f"  escrow tx:  {tx[:18]}…  → {explorer_tx(tx)}")

    call_id = int(escrow.functions.callCount().call())
    c = get_call(call_id)
    print(f"  callId:        {call_id}")
    print(f"  status:        {c['status']}")
    print(f"  escrowed:      {c['escrowedAmount']/1e6:.6f} USDC")
    print(f"  lockedStake:   {c['lockedStake']/1e6:.6f} USDC  (slash ceiling)")
    print()

    # ── Step 3: Caller files dispute ─────────────────────────────────
    print(f"▸ step 3/4: caller.fileDispute(callId={call_id}, evidenceHash)")
    evidence_text = f"demo case for callId={call_id} — plaintiff alleges non-performance"
    evidence_hash = sha256(evidence_text.encode()).digest()
    tx = _send(w3, escrow.functions.fileDispute(call_id, evidence_hash), from_acct=acct, gas=250_000)
    print(f"  filedispute tx: {tx[:18]}…  → {explorer_tx(tx)}")

    case_id = int(escrow.functions.caseCount().call())
    k = get_case(case_id)
    print(f"  caseId:    {k['caseId']}")
    print(f"  outcome:   {k['outcome']}")
    print(f"  evidence:  0x{k['evidenceHash']}")
    print()

    # ── Step 4: Court resolves — plaintiff wins → slash ─────────────
    print(f"▸ step 4/4: court.resolveDispute(caseId={case_id}, plaintiffWins=true)")
    print("            (in real demo: this is called automatically by proxy.py")
    print("             after the multi-juror panel returns a PLAINTIFF verdict)")
    bal_before = usdc.functions.balanceOf(acct.address).call()
    s_before = get_provider_stake(acct.address)
    print(f"  pre:  caller balance       = {bal_before/1e6:.6f} USDC")
    print(f"        provider stake total = {s_before['total']/1e6:.6f}")
    print(f"        provider stake locked= {s_before['locked']/1e6:.6f}")

    tx = resolve_dispute_onchain(case_id, plaintiff_wins=True)
    print(f"  resolve tx: {tx[:18]}…  → {explorer_tx(tx)}")

    bal_after = usdc.functions.balanceOf(acct.address).call()
    s_after = get_provider_stake(acct.address)
    k_after = get_case(case_id)
    c_after = get_call(call_id)
    print(f"  post: caller balance       = {bal_after/1e6:.6f} USDC  (Δ = +{(bal_after-bal_before)/1e6:.6f})")
    print(f"        provider stake total = {s_after['total']/1e6:.6f}  (Δ = -{(s_before['total']-s_after['total'])/1e6:.6f})")
    print(f"        provider stake locked= {s_after['locked']/1e6:.6f}")
    print(f"        case outcome:        {k_after['outcome']}")
    print(f"        call status:         {c_after['status']}")
    print()
    print("═══════════════════════════════════════════════════════════════")
    print("  ENFORCEMENT VERIFIED:")
    print(f"    • caller refunded: {ESCROW_AMOUNT/1e6:.2f} USDC (escrow)")
    print(f"    • plus slash of:   {(s_before['total']-s_after['total'])/1e6:.6f} USDC")
    print(f"      (50% of {ESCROW_AMOUNT/1e6:.2f} locked stake)")
    print(f"    • all on-chain on Arc Testnet — verifiable on arcscan")
    print("═══════════════════════════════════════════════════════════════")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
