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

from anet.svc import SvcClient

DEFAULT_CASE = Path(__file__).resolve().parent / "case-economic-dispute.json"


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
    print("══ JUROR VOTES ═══════════════════════════════════════════════════════")
    jurors = result.get("jurors", [])
    if not jurors:
        print("  (no juror votes recorded)")
    for j in jurors:
        print(f"  ▸ {j.get('juror')}: {j.get('verdict')}")
        reasoning = (j.get("reasoning") or "").replace("\n", " ").strip()
        if reasoning:
            print(f"      ↳ {reasoning[:240]}")
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
