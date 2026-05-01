"""Shared juror runtime — FastAPI app + anet register + Claude /vote endpoint.

Each juror flavor (economic / legal / fairness) reuses this runner with a
domain-specific system prompt.

NOTE on the model: jurors do NOT call the Anthropic API directly. They spawn
the local `claude` CLI in non-interactive mode (`claude -p`), which reuses
whatever auth Claude Code is already configured with (OAuth keychain, etc.).
This means:
  • No ANTHROPIC_API_KEY environment variable required
  • No per-token billing — the operator pays via their existing Claude
    Code subscription
  • Each juror's reasoning is produced by the same local Claude install
    that the operator is already using interactively

The trade-off is ~5–10s of CLI startup per call. For a 3-juror court that
fans out in parallel, total deliberation latency stays under 15s.
"""

from __future__ import annotations

import os
import subprocess
import threading
from typing import Optional

import uvicorn
from fastapi import FastAPI, Header, Request
from fastapi.responses import JSONResponse

from court_agent._register import register_until_ready
from court_agent.verdict import parse_juror_response


def _build_user_message(case: dict) -> str:
    case_id = case.get("caseId", "(unknown)")
    evidence = case.get("evidence", "(no evidence supplied)")
    claims = case.get("claims") or {}
    return f"""Case ID: {case_id}

Evidence:
{evidence}

Plaintiff's claim: {claims.get('plaintiff', '(not provided)')}
Defendant's claim: {claims.get('defendant', '(not provided)')}

Return a strict JSON object with exactly these keys:
  {{"verdict": "PLAINTIFF" | "DEFENDANT" | "ABSTAIN", "reasoning": "<= 200 words"}}
Do not include any text outside the JSON object.
"""


def _ask_claude_cli(system_prompt: str, user_msg: str, *, timeout: float = 90.0) -> str:
    """Spawn `claude -p` and pipe the user message via stdin. Return stdout.

    Uses the local Claude Code install's existing auth (OAuth via keychain by
    default). No ANTHROPIC_API_KEY needed.
    """
    cmd = [
        "claude",
        "-p",
        "--append-system-prompt", system_prompt,
    ]
    proc = subprocess.run(
        cmd,
        input=user_msg,
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    if proc.returncode != 0:
        raise RuntimeError(
            f"claude CLI exited {proc.returncode}: "
            f"{(proc.stderr or proc.stdout)[:300]}"
        )
    return proc.stdout


def run_juror(
    *,
    category: str,
    system_prompt: str,
    port: int,
    per_call: int,
) -> None:
    name = f"{category}-juror"
    app = FastAPI(title=name)
    timeout = float(os.environ.get("CLAUDE_CLI_TIMEOUT", "90"))

    @app.get("/health")
    def health() -> dict[str, object]:
        return {"ok": True, "agent": name}

    @app.get("/meta")
    def meta() -> dict[str, object]:
        return {
            "name": name,
            "version": "0.1.0",
            "skill": name,
            "category": category,
            "model": "local-claude-cli",
        }

    @app.post("/vote")
    async def vote(
        req: Request,
        x_agent_did: Optional[str] = Header(default=None, convert_underscores=True),
    ):
        case = await req.json() or {}
        case_id = case.get("caseId")
        print(f"[{name}] caller={x_agent_did} caseId={case_id!r}", flush=True)

        try:
            text = _ask_claude_cli(
                system_prompt,
                _build_user_message(case),
                timeout=timeout,
            )
            verdict, reasoning = parse_juror_response(text)
        except Exception as e:  # noqa: BLE001
            verdict, reasoning = "ABSTAIN", f"juror call failed: {e}"

        print(f"[{name}]   ↳ verdict={verdict}", flush=True)
        return JSONResponse(
            {"verdict": verdict, "reasoning": reasoning, "agent": name}
        )

    threading.Thread(
        target=lambda: register_until_ready(
            name=name,
            port=port,
            paths=["/vote", "/health", "/meta"],
            tags=[name, "juror", "court-p2p"],
            description=f"AI juror specialized in {category} disputes (Claude-powered).",
            per_call=per_call,
        ),
        daemon=True,
    ).start()
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="warning")
