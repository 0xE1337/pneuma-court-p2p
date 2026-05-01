"""Juror CLI — `court-juror economic`, `court-juror legal`, etc.

Sprint 0 placeholder. Sprint 1 implementation:

    1. parse argv[1] → category in {economic, legal, fairness}
    2. import the matching prompt module
    3. start FastAPI on $JUROR_PORT (default 9001 + offset)
    4. anet svc register
         name=f"{category}-juror"
         skills=[f"{category}-juror"]
         cost=per_call=$JUROR_COST_PER_CALL
    5. POST /vote receives {case_payload, X-Agent-DID}
       calls Claude with domain prompt
       returns {verdict: PLAINTIFF|DEFENDANT|ABSTAIN, reasoning: str}
"""

from __future__ import annotations

import sys


def cli() -> None:
    if len(sys.argv) < 2:
        print("usage: court-juror {economic|legal|fairness}", file=sys.stderr)
        sys.exit(2)
    print(f"[juror:{sys.argv[1]}] Sprint 0 skeleton", file=sys.stderr)
    sys.exit(0)


if __name__ == "__main__":
    cli()
