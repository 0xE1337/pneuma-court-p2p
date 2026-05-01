"""Pneuma Court main service — FastAPI app + anet svc registration.

Sprint 0 placeholder. Full implementation lands in Sprint 1.

Pseudocode:

    1. boot FastAPI on COURT_HOST:COURT_PORT
    2. anet svc register
         name=pneuma-court
         skills=[dispute-court, multi-juror, onchain-finalize]
         modes=[server-stream]
         cost=per_call=COURT_COST_PER_CALL
         backend=http://COURT_HOST:COURT_PORT/proxy/dispute
    3. POST /proxy/dispute streams SSE — see proxy.py
    4. SIGINT → anet svc unregister + shutdown
"""

from __future__ import annotations

import os
import sys


def cli() -> None:
    """Console entry registered in pyproject.toml as `court-main`."""
    print("[court-main] Sprint 0 skeleton — full impl in Sprint 1", file=sys.stderr)
    print(f"[court-main] would register on anet at {os.environ.get('COURT_HOST', '127.0.0.1')}:{os.environ.get('COURT_PORT', '8088')}", file=sys.stderr)
    sys.exit(0)


if __name__ == "__main__":
    cli()
