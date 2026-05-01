"""Shared juror runtime — FastAPI app + anet register + Claude /vote endpoint.

Each juror flavor (economic / legal / fairness) reuses this runner with a
domain-specific system prompt.
"""

from __future__ import annotations

import os
import threading
from typing import Optional

import uvicorn
from anthropic import Anthropic
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


def run_juror(
    *,
    category: str,
    system_prompt: str,
    port: int,
    per_call: int,
) -> None:
    name = f"{category}-juror"
    app = FastAPI(title=name)
    client = Anthropic()
    model = os.environ.get("CLAUDE_MODEL", "claude-sonnet-4-6")
    max_tokens = int(os.environ.get("CLAUDE_MAX_TOKENS", "512"))

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
            "model": model,
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
            msg = client.messages.create(
                model=model,
                max_tokens=max_tokens,
                system=system_prompt,
                messages=[{"role": "user", "content": _build_user_message(case)}],
            )
            text = "".join(
                block.text for block in msg.content if getattr(block, "type", None) == "text"
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
