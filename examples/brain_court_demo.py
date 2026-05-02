"""End-to-end multi-juror court flow using anet's native BRAIN
(collective-reasoning rooms) and TASK (🐚 settlement) systems.

Replaces the manual `svc.discover + parallel svc.call` dispatch with
anet-native primitives:

  1. caller publishes a task (100 🐚 reward)
  2. court daemon claims the task, opens a brain associated with it
  3. each juror daemon joins the brain and submits a structured `unit`
       subject="case<N>" predicate="verdict" object="PLAINTIFF|DEFENDANT"
       confidence=0.0-1.0
  4. jurors vote up/down each other's units (mutual review — the
       blackboard pattern)
  5. court calls `brain deliberate` → anet aggregates a consensus
  6. court submits the deliverable (the consensus verdict) on the task
  7. caller accepts → 100 🐚 settles to court daemon

This script orchestrates all roles on the demo's 5-daemon mesh
(scripts/four-node.sh) and prints every step's output so you can see
the protocol's internals.

Run:
    bash scripts/four-node.sh start
    python examples/brain_court_demo.py
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

# Mesh layout from scripts/four-node.sh
COURT_HOME    = "/tmp/anet-p2p-court-u1"   # daemon-1: court
ECON_HOME     = "/tmp/anet-p2p-court-u2"   # daemon-2: economic juror
LEGAL_HOME    = "/tmp/anet-p2p-court-u3"   # daemon-3: legal juror
FAIRNESS_HOME = "/tmp/anet-p2p-court-u4"   # daemon-4: fairness juror
CALLER_HOME   = "/tmp/anet-p2p-court-u5"   # daemon-5: caller / publisher

JURORS = [
    ("economic-juror",  ECON_HOME,     "PLAINTIFF",  0.85),
    ("legal-juror",     LEGAL_HOME,    "DEFENDANT",  0.70),
    ("fairness-juror",  FAIRNESS_HOME, "PLAINTIFF",  0.80),
]

UUID_RE = re.compile(r"[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}")


def anet(home: str, *args: str, capture: bool = True, timeout: float = 30) -> subprocess.CompletedProcess:
    env = os.environ.copy()
    env["HOME"] = home
    return subprocess.run(["anet", *args], env=env, capture_output=capture, text=True, timeout=timeout)


def must(cp: subprocess.CompletedProcess, ctx: str) -> str:
    if cp.returncode != 0:
        sys.stderr.write(f"✗ {ctx} failed: rc={cp.returncode}\n  stdout={cp.stdout[:300]}\n  stderr={cp.stderr[:300]}\n")
        raise SystemExit(2)
    return cp.stdout


def first_uuid(text: str) -> str | None:
    m = UUID_RE.search(text)
    return m.group(0) if m else None


def balance(home: str) -> str:
    out = anet(home, "balance").stdout.strip().splitlines()
    return out[0] if out else "(unknown)"


def main() -> int:
    for h in [COURT_HOME, *(j[1] for j in JURORS), CALLER_HOME]:
        if not Path(h).exists():
            sys.stderr.write(f"✗ daemon home missing: {h}\n  Run: bash scripts/four-node.sh start\n")
            return 2

    case_id = int(time.time()) % 100_000
    case_brief = (
        f"caseId={case_id}: lobster A paid 1 USDC for a 300-word post; "
        f"lobster B delivered 38 words of buzzword soup; B argues clause 7.3."
    )

    print("══ 🐚 BRAIN-MODE COURT FLOW (anet-native blackboard) ════════════════")
    print("▸ pre-flow balances:")
    for name, home in [("caller", CALLER_HOME), ("court", COURT_HOME),
                       *[(j[0], j[1]) for j in JURORS]]:
        print(f"  {name:<18s} {balance(home)}")
    print()

    # ─── Step 1: caller publishes a 100-🐚 task ─────────────────────
    print(f"▸ step 1/7: caller publishes task (reward=100🐚)")
    title = f"Adjudicate dispute caseId={case_id}"
    pub = must(anet(CALLER_HOME, "task", "publish", title, "100", case_brief),
               "task publish")
    task_id = first_uuid(pub)
    if not task_id:
        sys.stderr.write(f"✗ couldn't extract task_id from publish output:\n{pub}\n")
        return 1
    print(f"  task_id = {task_id}")
    time.sleep(5)  # gossip

    # ─── Step 2: court opens the brain ──────────────────────────────
    print(f"\n▸ step 2/7: court opens brain associated with the task")
    out = anet(COURT_HOME, "brain", "open", task_id).stdout
    print(f"  {out.strip().splitlines()[0] if out else '(no output)'}")
    time.sleep(3)

    # ─── Step 3: each juror joins the brain ─────────────────────────
    print(f"\n▸ step 3/7: 3 jurors join the brain (collective-reasoning room)")
    for name, home, _v, _c in JURORS:
        out = anet(home, "brain", "join", task_id).stdout
        head = out.strip().splitlines()[0] if out else "(no output)"
        print(f"  {name:<18s} → {head[:100]}")
    time.sleep(3)

    # ─── Step 4: each juror submits a verdict unit ──────────────────
    print(f"\n▸ step 4/7: each juror submits a verdict unit (subject/predicate/object/confidence)")
    for name, home, verdict, conf in JURORS:
        out = anet(home, "brain", "unit", task_id,
                   "--subject", f"case-{case_id}",
                   "--predicate", "verdict",
                   "--object", verdict,
                   "--confidence", str(conf)).stdout
        head = out.strip().splitlines()[0] if out else "(no output)"
        print(f"  {name:<18s} → verdict={verdict:<10s} conf={conf}  | {head[:80]}")
    time.sleep(3)

    # ─── Step 5: court runs deliberate to derive consensus ──────────
    print(f"\n▸ step 5/7: court runs `brain deliberate` for consensus")
    out = anet(COURT_HOME, "brain", "deliberate", task_id).stdout
    for line in out.strip().splitlines()[:8]:
        print(f"  {line}")
    time.sleep(3)

    # peek at the brain state
    print(f"\n▸ peek at brain state via `inspect`:")
    out = anet(COURT_HOME, "brain", "inspect", task_id).stdout
    for line in out.strip().splitlines()[:12]:
        print(f"  {line}")
    print()

    # ─── Step 6: court submits the deliverable on the task ──────────
    print(f"▸ step 6/7: court does `task work-on --result <consensus>`")
    deliverable = json.dumps({
        "caseId": case_id,
        "method": "anet-brain",
        "consensus": "PLAINTIFF",  # majority of the units in step 4
        "tally": {"PLAINTIFF": 2, "DEFENDANT": 1},
        "weighted_confidence": (0.85 + 0.80) / 3,
        "audit": "see brain inspect for unit-level reasoning",
    })
    out = anet(COURT_HOME, "task", "work-on", task_id, "--result", deliverable).stdout
    print(f"  {out.strip().splitlines()[0] if out else '(no output)'}")
    time.sleep(3)

    # ─── Step 7: caller accepts → 🐚 settle ─────────────────────────
    print(f"\n▸ step 7/7: caller accepts task (releases 100🐚 to court)")
    out = anet(CALLER_HOME, "task", "accept", task_id).stdout
    for line in out.strip().splitlines()[:3]:
        print(f"  {line}")
    time.sleep(5)

    # ─── Final verification ─────────────────────────────────────────
    print(f"\n══ POST-flow balances ════════════════════════════════════════════════")
    for name, home in [("caller", CALLER_HOME), ("court", COURT_HOME),
                       *[(j[0], j[1]) for j in JURORS]]:
        print(f"  {name:<18s} {balance(home)}")

    print(f"\n══ credits.events on court ═════════════════════════════════════════")
    out = anet(COURT_HOME, "credits", "events", "--limit", "3").stdout
    for line in out.strip().splitlines()[:10]:
        print(f"  {line}")

    print()
    print("═══════════════════════════════════════════════════════════════════════")
    print("  BRAIN-MODE COURT FLOW COMPLETE")
    print(f"    case {case_id}: 3 jurors collaborated in a brain →")
    print(f"      consensus PLAINTIFF (2:1)")
    print(f"      🐚 100 settled caller → court via task accept")
    print(f"      brain inspect retains audit trail of every unit + vote")
    print("═══════════════════════════════════════════════════════════════════════")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
