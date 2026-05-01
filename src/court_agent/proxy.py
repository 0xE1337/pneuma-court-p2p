"""Court routing — discover jurors, fan-out in parallel, aggregate, finalize."""

from __future__ import annotations

import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

from court_agent._anet_client import SvcClient
from court_agent.chain import has_chain_config
from court_agent.verdict import majority_vote

ANET_BASE_URL = os.environ.get("ANET_BASE_URL", "http://127.0.0.1:13921")
MIN_JURORS = int(os.environ.get("COURT_MIN_JURORS", "3"))
DISCOVER_RETRIES = int(os.environ.get("COURT_DISCOVER_RETRIES", "5"))


def _find_jurors(svc: SvcClient, category: str) -> list[dict[str, Any]]:
    """Assemble a juror panel for a dispute.

    Strategy — match the user-described story 'court finds a few agents
    relevant to the case':

      1. SPECIALIST PASS: discover `<category>-juror` (e.g. economic-juror).
         If we already have ≥ MIN_JURORS specialists, return them.
      2. GENERALIST TOP-UP: discover any `court-juror` (every juror in this
         project's juror pool registers this catch-all tag), and merge
         unique peers into the panel until we hit MIN_JURORS or run out.

    This means a content-quality dispute, for which there is no
    `content-quality-juror` specialist on the mesh, still convenes a
    real 3-juror panel (economic + legal + fairness) instead of running
    with a single fallback peer.
    """
    panel: list[dict[str, Any]] = []
    seen_peers: set[str] = set()

    def _add(peers: list[dict[str, Any]]) -> None:
        for p in peers:
            pid = p.get("peer_id")
            if pid and pid not in seen_peers:
                panel.append(p)
                seen_peers.add(pid)

    # Single retry loop probes BOTH specialist + generalist on each tick. Bails
    # the moment we have enough jurors to seat a panel — never burns the full
    # retry budget when generalists are already advertised, which keeps total
    # discover latency comfortably inside anet's 30s svc-call client timeout.
    skill = f"{category}-juror"
    for _ in range(DISCOVER_RETRIES):
        _add(svc.discover(skill=skill))                 # specialist
        if len(panel) < MIN_JURORS:
            _add(svc.discover(skill="court-juror"))     # generalist top-up
        if len(panel) >= MIN_JURORS:
            break
        time.sleep(1)

    return panel


def _extract_body(resp: dict[str, Any]) -> dict[str, Any]:
    """anet svc call --json output shape varies between versions.
    Empirically observed:
      (a) raw passthrough:    {"verdict": ..., "reasoning": ..., "agent": ...}
      (b) wrapped:            {"body": {"verdict": ..., ...}, "status": 200}
      (c) double-wrapped raw: {"body": "<json string>"}
    Normalise all three to a single body dict."""
    if not isinstance(resp, dict):
        return {}
    if "verdict" in resp:
        return resp
    body = resp.get("body")
    if isinstance(body, dict):
        return body
    if isinstance(body, str):
        try:
            import json as _json
            parsed = _json.loads(body)
            if isinstance(parsed, dict):
                return parsed
        except Exception:  # noqa: BLE001
            pass
    return {}


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

    body = _extract_body(resp)
    if "verdict" not in body:
        return {
            "juror": name, "peer_id": peer_id,
            "verdict": "ABSTAIN",
            "reasoning": f"unexpected response shape: {resp!r}",
        }

    return {
        "juror": name,
        "peer_id": peer_id,
        "verdict": body["verdict"],
        "reasoning": body.get("reasoning", ""),
        "soul": body.get("soul"),
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

    # v0.1 ships anet-only deliberation. The on-chain write path is held back
    # because PneumaCourt.fileDispute requires msg.sender to be the original
    # SkillRegistry caller (plaintiff) — see src/court_agent/chain.py docstring
    # for the exact invariants and the v0.2 meta-tx plan.
    #
    # Read-only on-chain integration IS verified (chain.has_chain_config /
    # chain.dispute_count / chain.get_dispute) and the result includes a
    # snapshot of the contract state when configured.
    # Cheap config probe — no live RPC inside the request hot path so we
    # don't bust anet's 30s svc-call timeout. Operators who want a live
    # chain snapshot can call court_agent.chain.dispute_count() out-of-band.
    if has_chain_config():
        result["onchain_status"] = (
            "configured (RPC + contract + finalizer wallet); "
            "write path queued for v0.2 — see chain.py docstring"
        )
    else:
        result["onchain_status"] = (
            "court has no on-chain config (ARC_RPC_URL / PNEUMA_COURT_ADDRESS"
            " / COURT_FINALIZER_PRIVATE_KEY) — running anet-only"
        )

    return result
