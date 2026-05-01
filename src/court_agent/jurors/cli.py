"""Juror CLI — `court-juror {economic|legal|fairness}`."""

from __future__ import annotations

import os
import sys

from court_agent.jurors import economic, fairness, legal
from court_agent.jurors._runner import run_juror

JUROR_CATEGORIES: dict[str, tuple[str, int]] = {
    "economic": (economic.SYSTEM_PROMPT, 9101),
    "legal": (legal.SYSTEM_PROMPT, 9102),
    "fairness": (fairness.SYSTEM_PROMPT, 9103),
}


def cli() -> None:
    if len(sys.argv) < 2 or sys.argv[1] not in JUROR_CATEGORIES:
        print(
            f"usage: court-juror {{{'|'.join(JUROR_CATEGORIES)}}}",
            file=sys.stderr,
        )
        sys.exit(2)

    category = sys.argv[1]
    prompt, default_port = JUROR_CATEGORIES[category]
    port = int(os.environ.get(f"{category.upper()}_JUROR_PORT", default_port))
    per_call = int(os.environ.get("JUROR_COST_PER_CALL", "5"))
    run_juror(category=category, system_prompt=prompt, port=port, per_call=per_call)


if __name__ == "__main__":
    cli()
