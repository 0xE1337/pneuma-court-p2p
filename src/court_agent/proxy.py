"""Court routing — discover jurors, fan-out in parallel, aggregate, finalize."""

from __future__ import annotations

import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

from anet.svc import SvcClient

from court_agent.chain import finalize_dispute
from court_agent.verdict import majority_vote

ANET_BASE_URL = os.environ.get("ANET_BASE_URL", "http://127.0.0.1:13921")
MIN_JURORS = int(os.environ.get("COURT_MIN_JURORS", "3"))
DISCOVER_RETRIES = int(os.environ.get("COURT_DISCOVER_RETRIES", "10"))


def _find_jurors(svc: SvcClient, category: str) -> list[dict[str, Any]]:
    """Discover jurors by category, with fallback to fairness-juror."""
    skill = f"{category}-juror"
    for _ in range(DISCOVER_RETRIES):
        peers = svc.discover(skill=skill)
        if peers:
            return peers
        time.sleep(1)

    # Fallback: fairness-juror is the universal arbiter — try it if a
    # specialised juror category isn't online.
    if category != "fairness":
        return svc.discover(skill="fairness-juror")
    return []


def _call_juror(svc: SvcClient, peer: dict[str, Any], case: dict[str, Any]) -> dict[str, Any]:
    """Call a juror's /vote endpoint. Wraps failures as ABSTAIN votes so
    one flaky peer doesn't tank the whole deliberation."""
    peer_id = peer["peer_id"]
    name = peer["services"][0]["name"]

    try:
        resp = svc.call(peer_id, name, "/vote", method="POST", body=case)
    except Exception as e:  # noqa: BLE001
        return {
            "juror": name, "peer_id": peer_id,
            "verdict": "ABSTAIN",
            "reasoning": f"call failed: {e}",
        }

    body = resp.get("body") or {}
    if not isinstance(body, dict) or "verdict" not in body:
        return {
            "juror": name, "peer_id": peer_id,
            "verdict": "ABSTAIN",
            "reasoning": f"unexpected response shape: {body!r}",
        }

    return {
        "juror": name,
        "peer_id": peer_id,
        "verdict": body["verdict"],
        "reasoning": body.get("reasoning", ""),
    }


def deliberate(case: dict[str, Any], *, caller_did: str | None) -> dict[str, Any]:
    """Run the full deliberation pipeline.

        case = {
            "caseId": int,
            "category": "economic" | "legal" | "fairness" | ...,
            "evidence": str,
            "claims": {"plaintiff": str, "defendant": str},
        }

    Returns the aggregated result including individual juror votes, the final
    majority verdict, and (best-effort) the on-chain finalize tx hash.
    """
    case_id = case.get("caseId")
    category = case.get("category", "fairness")

    result: dict[str, Any] = {
        "caseId": case_id,
        "category": category,
        "caller": caller_did,
        "jurors": [],
        "verdict": "ABSTAIN",
        "tx_hash": None,
        "error": None,
    }

    with SvcClient(base_url=ANET_BASE_URL) as svc:
        peers = _find_jurors(svc, category)
        if not peers:
            result["error"] = f"no jurors found for category={category!r}"
            return result

        targets = peers[:MIN_JURORS]
        with ThreadPoolExecutor(max_workers=max(1, len(targets))) as ex:
            futures = [ex.submit(_call_juror, svc, p, case) for p in targets]
            votes = [f.result() for f in as_completed(futures)]

        result["jurors"] = votes
        result["verdict"] = majority_vote(v["verdict"] for v in votes)

    # On-chain finalize is OPT-IN, not the default path.
    #
    # Two gating conditions, BOTH must be true to attempt on-chain write:
    #   1. caller explicitly requested it via payload: want_onchain_proof=true
    #   2. court operator hasn't disabled it via env: COURT_ENABLE_ONCHAIN=1
    #
    # gas is paid by the court operator (whoever runs this service), not the
    # caller — anet callers are not assumed to hold an EVM wallet. The court
    # recovers gas cost via higher 🐚 Shell pricing for on-chain-proof requests.
    #
    # This keeps the default path (anet-only, 🐚 Shell settlement) unchanged
    # for the 99% of users who don't need a cross-network proof.
    want_proof = bool(case.get("want_onchain_proof"))
    onchain_enabled = os.environ.get("COURT_ENABLE_ONCHAIN", "0") == "1"

    if not (want_proof and onchain_enabled and case_id is not None):
        result["onchain_skipped_reason"] = (
            "not requested" if not want_proof
            else "court operator disabled on-chain"
            if not onchain_enabled
            else "no caseId"
        )
        return result

    try:
        result["tx_hash"] = finalize_dispute(int(case_id), result["verdict"])
    except Exception as e:  # noqa: BLE001
        # On-chain failure is non-fatal: deliberation result already returns,
        # caller sees the error in the response and can retry or accept the
        # off-chain-only ruling.
        result["error"] = f"on-chain finalize failed: {e}"

    return result
