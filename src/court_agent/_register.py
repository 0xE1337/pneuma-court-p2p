"""anet svc register helper — adapted from anet starter kit examples/03."""

from __future__ import annotations

import os
import sys
import time
from typing import Optional

import httpx

from court_agent._anet_client import SvcAPIError, SvcClient


def register_until_ready(
    *,
    name: str,
    port: int,
    paths: list[str],
    tags: list[str],
    description: str,
    per_call: int = 0,
    base_url: Optional[str] = None,
    health_path: str = "/health",
    meta_path: str = "/meta",
) -> None:
    """Wait for the local FastAPI to come up, then register on anet ANS.

    Mirrors `register_until_ready` from anet's official multi-agent example so
    that this project's services look identical to evaluators familiar with the
    starter kit.
    """
    base_url = base_url or os.environ.get("ANET_BASE_URL", "http://127.0.0.1:13921")

    for _ in range(30):
        try:
            r = httpx.get(f"http://127.0.0.1:{port}{health_path}", timeout=1.0)
            if r.status_code == 200:
                break
        except httpx.HTTPError:
            pass
        time.sleep(0.5)
    else:
        print(f"[{name}] backend on :{port} never came up", file=sys.stderr)
        raise SystemExit(1)

    with SvcClient(base_url=base_url) as svc:
        try:
            svc.unregister(name)
        except Exception:  # noqa: BLE001 — unregister is best-effort cleanup
            pass

        try:
            resp = svc.register(
                name=name,
                endpoint=f"http://127.0.0.1:{port}",
                paths=paths,
                modes=["rr"],
                per_call=per_call if per_call > 0 else None,
                free=per_call <= 0,
                tags=tags,
                description=description,
                health_check=health_path,
                meta_path=meta_path,
            )
        except SvcAPIError as e:
            print(f"[{name}] register failed: {e}", file=sys.stderr)
            raise

    ans = (resp.get("ans") or {})
    print(
        f"[{name}] ✓ registered (per_call={per_call}, ans.published={ans.get('published')})",
        file=sys.stderr,
    )
