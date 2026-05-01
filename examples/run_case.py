"""Caller — submits a test case to pneuma-court via anet, prints the result.

Usage:
    ANET_BASE_URL=http://127.0.0.1:13924 python examples/run_case.py [case.json]

Default case file: examples/case-economic-dispute.json
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

from court_agent._anet_client import SvcClient

DEFAULT_CASE = Path(__file__).resolve().parent / "case-content-quality.json"


def find_court(svc: SvcClient, retries: int = 30) -> dict | None:
    for _ in range(retries):
        peers = svc.discover(skill="dispute-court")
        if peers:
            return peers[0]
        time.sleep(1)
    return None


def main() -> int:
    ap = argparse.ArgumentParser(description="Submit a dispute to pneuma-court.")
    ap.add_argument(
        "case_file",
        nargs="?",
        default=str(DEFAULT_CASE),
        help="Path to a case JSON file.",
    )
    args = ap.parse_args()

    case_path = Path(args.case_file)
    if not case_path.exists():
        print(f"✗ case file not found: {case_path}", file=sys.stderr)
        return 2

    case = json.loads(case_path.read_text())
    base_url = os.environ.get("ANET_BASE_URL", "http://127.0.0.1:13924")

    with SvcClient(base_url=base_url) as svc:
        target = find_court(svc)
        if not target:
            print("✗ no pneuma-court peers found in ANS", file=sys.stderr)
            return 1

        peer_id = target["peer_id"]
        svc_name = target["services"][0]["name"]
        print(f"▸ calling {svc_name} on peer {peer_id[:18]}…")
        print(f"  case: caseId={case.get('caseId')} category={case.get('category')}")

        resp = svc.call(peer_id, svc_name, "/dispute", method="POST", body=case)
        result = resp.get("body") or {}

    print()
    print("══ RESULT ═════════════════════════════════════════════════════════════")
    print(f"  caseId:    {result.get('caseId')}")
    print(f"  category:  {result.get('category')}")
    print(f"  verdict:   {result.get('verdict')}")
    print(f"  tx_hash:   {result.get('tx_hash') or '(off-chain only — set ARC_RPC_URL + key to enable)'}")
    if result.get("error"):
        print(f"  error:     {result['error']}")
    print()
    jurors = result.get("jurors", [])

    # Show panel identities first (Pneuma Soul anchoring) — gives the run a
    # cross-mesh-reputation framing before the verdict text appears.
    soul_jurors = [j for j in jurors if j.get("soul")]
    if soul_jurors:
        print("══ PANEL (verified on-chain identities · Pneuma Soul NFT) ═════════════")
        for j in soul_jurors:
            soul = j["soul"]
            tba = soul.get("tba", "?")
            print(f"  ▸ {j.get('juror'):<20s} Soul #{soul['tokenId']}  TBA {tba[:10]}…")
            print(f"     verify on testnet.arcscan.app/token/0x5b51…A959/instance/{soul['tokenId']}")
        print()

    print("══ DELIBERATION ═══════════════════════════════════════════════════════")
    if not jurors:
        print("  (no juror votes recorded)")
    for j in jurors:
        prefix = j.get("juror", "?")
        soul = j.get("soul")
        if soul:
            prefix = f"{j.get('juror')} (Soul #{soul['tokenId']})"
        print(f"  ▸ {prefix}: {j.get('verdict')}")
        reasoning = (j.get("reasoning") or "").replace("\n", " ").strip()
        if reasoning:
            print(f"      ↳ {reasoning[:240]}")
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
