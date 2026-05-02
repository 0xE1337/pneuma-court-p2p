"""End-to-end x402 real-money demo on Arc Testnet.

Demonstrates Pneuma's central-bank layer in action:
   Agent A pays Agent B **real USDC** (not 🐚 Shell) via the x402-rail.

Flow:
   1. Use COURT_FINALIZER_PRIVATE_KEY as Alice (caller / payer)
   2. Generate Bob (provider / payee) ephemerally
   3. Read Alice's & Bob's USDC balance on Arc
   4. Alice signs an EIP-712 TransferWithAuthorization for 0.01 USDC → Bob
   5. POST signed auth to local x402-rail (http://127.0.0.1:9205/pay)
   6. Rail verifies sig + submits on-chain → Bob receives 0.01 USDC
   7. Verify by re-reading Bob's balance (proves real money moved)

Pre-req:
    bash scripts/four-node.sh start              # local mesh
    .venv/bin/court-x402-rail &                  # x402 rail on :9205
    # OR for the smoke test only (no anet register):
    X402_RAIL_NO_REGISTER=1 .venv/bin/court-x402-rail &
"""

from __future__ import annotations

import json
import os
import secrets
import sys
import time
from pathlib import Path

import httpx

# Load .env so COURT_FINALIZER_PRIVATE_KEY etc. are available
try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass

from court_agent.x402_rail import (
    USDC_ADDR,
    USDC_TYPED_DATA_NAME,
    USDC_TYPED_DATA_VERSION,
    build_typed_data,
    usdc_balance,
)

CHAIN_ID = int(os.environ.get("ARC_CHAIN_ID", "5042002"))
RAIL_URL = os.environ.get("X402_RAIL_URL", "http://127.0.0.1:9205")
EXPLORER = os.environ.get("ARC_EXPLORER", "https://testnet.arcscan.app")

PAY_AMOUNT_MICROS = int(os.environ.get("DEMO_PAY_USDC_MICROS", "10000"))  # 0.01 USDC


def fmt_usdc(micros: int) -> str:
    return f"{micros / 1_000_000:.6f} USDC"


def main() -> int:
    from eth_account import Account
    from eth_account.messages import encode_typed_data

    pk = os.environ.get("COURT_FINALIZER_PRIVATE_KEY")
    if not pk:
        print("✗ COURT_FINALIZER_PRIVATE_KEY not set in env", file=sys.stderr)
        return 2

    if pk.startswith("0x"):
        pk_clean = pk[2:]
    else:
        pk_clean = pk

    alice = Account.from_key(pk_clean)
    bob = Account.create()

    print("══ 🐚→💵 PNEUMA x402 RAIL DEMO ═══════════════════════════════════════")
    print()
    print("▸ Roles:")
    print(f"  Alice (payer)    {alice.address}")
    print(f"  Bob   (payee)    {bob.address}  (ephemeral, never funded)")
    print(f"  Asset            USDC @ {USDC_ADDR}")
    print(f"  Amount           {fmt_usdc(PAY_AMOUNT_MICROS)}")
    print(f"  Chain            Arc Testnet ({CHAIN_ID})")
    print()

    print("▸ pre-flow balances:")
    try:
        alice_pre = usdc_balance(alice.address)
        bob_pre = usdc_balance(bob.address)
    except Exception as e:
        print(f"  ✗ balance read failed: {e}", file=sys.stderr)
        return 1
    print(f"  Alice = {fmt_usdc(alice_pre)}")
    print(f"  Bob   = {fmt_usdc(bob_pre)}")
    if alice_pre < PAY_AMOUNT_MICROS:
        print(
            f"  ✗ Alice has insufficient USDC ({fmt_usdc(alice_pre)} < {fmt_usdc(PAY_AMOUNT_MICROS)})"
        )
        print("    Top up: https://faucet.circle.com/")
        return 1
    print()

    # ─── Step 1: Build typed-data ──────────────────────────────────
    now = int(time.time())
    valid_after = now - 60
    valid_before = now + 600
    nonce_hex = "0x" + secrets.token_hex(32)

    print("▸ step 1/4: Alice builds EIP-712 TransferWithAuthorization")
    typed = build_typed_data(
        from_addr=alice.address,
        to=bob.address,
        value=PAY_AMOUNT_MICROS,
        valid_after=valid_after,
        valid_before=valid_before,
        nonce_hex=nonce_hex,
    )
    print(f"  domain.name     = {typed['domain']['name']}")
    print(f"  domain.version  = {typed['domain']['version']}")
    print(f"  domain.chainId  = {typed['domain']['chainId']}")
    print(f"  domain.contract = {typed['domain']['verifyingContract']}")
    print(f"  message.from    = {typed['message']['from']}")
    print(f"  message.to      = {typed['message']['to']}")
    print(f"  message.value   = {typed['message']['value']} (micros)")
    print(f"  message.nonce   = {nonce_hex[:18]}...")
    print()

    # ─── Step 2: Alice signs ────────────────────────────────────────
    print("▸ step 2/4: Alice signs (off-chain, no gas)")
    msg = encode_typed_data(full_message=typed)
    signed = alice.sign_message(msg)
    sig_hex = (
        "0x" + signed.signature.hex().removeprefix("0x")
        if hasattr(signed, "signature")
        else signed["signature"].hex()
    )
    print(f"  signature = {sig_hex[:20]}...{sig_hex[-10:]}")
    print()

    # ─── Step 3: POST to rail ───────────────────────────────────────
    print(f"▸ step 3/4: Alice POSTs to x402-rail at {RAIL_URL}/pay")
    payload = {
        "transferAuth": {
            "from": alice.address,
            "to": bob.address,
            "value": str(PAY_AMOUNT_MICROS),
            "validAfter": valid_after,
            "validBefore": valid_before,
            "nonce": nonce_hex,
            "signature": sig_hex,
        }
    }
    try:
        with httpx.Client(timeout=120.0) as client:
            r = client.post(f"{RAIL_URL}/pay", json=payload)
    except Exception as e:
        print(f"  ✗ rail unreachable at {RAIL_URL}: {e}", file=sys.stderr)
        print("    Start it: .venv/bin/court-x402-rail")
        return 1

    if r.status_code != 200:
        print(f"  ✗ rail returned {r.status_code}: {r.text[:300]}")
        return 1

    result = r.json()
    print(f"  ✓ rail accepted. tx hash = {result['txHash']}")
    print(f"  arcscan  = {result['explorer']}")
    print()

    # ─── Step 4: verify by re-reading Bob's balance ─────────────────
    print("▸ step 4/4: verify on-chain (re-read Bob's balance)")
    bob_post = usdc_balance(bob.address)
    delta = bob_post - bob_pre
    print(f"  Bob before  = {fmt_usdc(bob_pre)}")
    print(f"  Bob after   = {fmt_usdc(bob_post)}")
    print(f"  delta       = +{fmt_usdc(delta)}")
    print()

    if delta == PAY_AMOUNT_MICROS:
        print("══ ✓ REAL USDC MOVED — x402 rail end-to-end verified ═══════════════")
        print(
            f"   Alice paid Bob {fmt_usdc(PAY_AMOUNT_MICROS)} via off-chain signature"
        )
        print(f"   Tx: {result['explorer']}")
        print()
        print("   ▸ Why this matters:")
        print("     - Bob's wallet is brand new, never funded — yet got paid")
        print("     - Alice never sent a tx — only signed off-chain (no gas)")
        print("     - x402-rail (relayer) submitted the signed authorization")
        print("     - Settlement is FINAL on Arc Testnet (real money, not 🐚)")
        return 0
    else:
        print(f"✗ delta mismatch: expected +{PAY_AMOUNT_MICROS} got {delta}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
