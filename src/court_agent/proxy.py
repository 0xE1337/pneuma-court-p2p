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

    if case_id is None or os.environ.get("COURT_SKIP_ONCHAIN") == "1":
        return result

    try:
        result["tx_hash"] = finalize_dispute(int(case_id), result["verdict"])
    except Exception as e:  # noqa: BLE001
        # Demo continues even if RPC is flaky — surfaces error in result.
        result["error"] = f"on-chain finalize failed: {e}"

    return result
