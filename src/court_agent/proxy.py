"""Court routing — receive dispute, discover jurors, fan out, aggregate, stream back.

Sprint 0 placeholder.

Flow:

    POST /proxy/dispute
      body: {"caseId": int, "category": str, "evidence": str, "callId": int}
      header: X-Agent-DID  (anet auto-injected)

      1. peers = svc.discover(skill=f"{category}-juror")      # ≥ 1 peer
      2. for peer in peers[:3] in parallel:
            verdict = svc.call(peer, "/vote", {case_payload})
            yield SSE: {juror: peer.did, verdict, reasoning}
      3. final = majority_vote(verdicts)
      4. tx = chain.finalize_dispute(callId, final)            # see chain.py
      5. yield SSE: {final_verdict, tx_hash}
"""

from __future__ import annotations

# from anet.svc import SvcClient  # Sprint 1
# from .verdict import majority_vote  # Sprint 1
# from .chain import finalize_dispute  # Sprint 1
