"""Thin Python wrapper around the `anet` CLI's svc subcommand.

The official anet Python SDK referenced in the starter kit
(`from anet.svc import SvcClient`) is not published on PyPI as of
2026-05-01 — `pip install anet` resolves to an unrelated 0.0.1 package.
This module reimplements the SvcClient surface used by the starter kit's
examples/03-multi-agent-pipeline so this project's code can stay
identical in shape to the official examples.

Implementation strategy: shell out to `anet svc <subcmd> --json` and
parse the JSON output. Each daemon is selected by setting HOME — the
CLI then reads `$HOME/.anet/config.json` for the api_port. To target
a specific daemon, set ANET_HOME in the environment before importing
or before instantiating SvcClient.
"""

from __future__ import annotations

import json
import os
import subprocess
from typing import Any, Optional


class SvcAPIError(RuntimeError):
    """Raised when an `anet svc` subcommand exits non-zero or returns
    unparseable output. Mirrors the exception surface from anet's
    official starter-kit SDK."""


def _run(args: list[str], *, env: dict[str, str] | None = None,
         timeout: float = 30.0) -> dict[str, Any] | list[Any]:
    """Invoke `anet svc …` with --json, return the parsed payload."""
    cmd = ["anet", "svc", *args, "--json"]
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            env=env or os.environ.copy(),
        )
    except FileNotFoundError as e:
        raise SvcAPIError(f"`anet` not on PATH: {e}") from e
    except subprocess.TimeoutExpired as e:
        raise SvcAPIError(f"`anet svc {' '.join(args)}` timed out") from e

    if proc.returncode != 0:
        raise SvcAPIError(
            f"`anet svc {' '.join(args)}` failed (exit {proc.returncode}): "
            f"{proc.stderr.strip() or proc.stdout.strip()}"
        )

    out = proc.stdout.strip()
    if not out:
        return {}
    try:
        return json.loads(out)
    except json.JSONDecodeError as e:
        raise SvcAPIError(f"non-JSON output from anet svc: {out[:200]}") from e


class SvcClient:
    """Drop-in replacement for anet starter-kit's SvcClient — subprocess-backed.

    Usage matches the starter kit pattern exactly:

        with SvcClient(base_url="http://127.0.0.1:13921") as svc:
            svc.register(name=..., endpoint=..., ...)
            peers = svc.discover(skill="economic-juror")
            resp = svc.call(peer["peer_id"], peer["services"][0]["name"],
                            "/vote", method="POST", body={...})
    """

    def __init__(self, base_url: Optional[str] = None,
                 anet_home: Optional[str] = None) -> None:
        # base_url is accepted for API parity with the starter-kit SvcClient.
        # The CLI itself routes via HOME-based config rather than a URL, so
        # base_url is informational here. Set ANET_HOME or anet_home to point
        # at a specific daemon's data dir.
        self.base_url = base_url
        self._env = os.environ.copy()
        home = anet_home or os.environ.get("ANET_HOME")
        if home:
            self._env["HOME"] = home

    def __enter__(self) -> "SvcClient":
        return self

    def __exit__(self, *_exc: object) -> None:
        return None

    # ──────────────────────────────────────────────────────────────────
    # Lifecycle
    # ──────────────────────────────────────────────────────────────────

    def register(
        self,
        *,
        name: str,
        endpoint: str,
        paths: list[str],
        modes: list[str] = ("rr",),
        per_call: int | None = None,
        free: bool = False,
        per_kb: int | None = None,
        per_minute: int | None = None,
        tags: list[str] | None = None,
        description: str | None = None,
        version: str | None = None,
        health_check: str | None = None,
        meta_path: str | None = None,
        transport: str = "http",
    ) -> dict[str, Any]:
        args: list[str] = [
            "register",
            "--name", name,
            "--endpoint", endpoint,
            "--transport", transport,
            "--paths", ",".join(paths),
            "--modes", ",".join(modes),
        ]
        if free:
            args.append("--free")
        elif per_call is not None:
            args += ["--per-call", str(per_call)]
        if per_kb is not None:
            args += ["--per-kb", str(per_kb)]
        if per_minute is not None:
            args += ["--per-minute", str(per_minute)]
        if tags:
            args += ["--tags", ",".join(tags)]
        if description:
            args += ["--description", description]
        if version:
            args += ["--version", version]
        if health_check:
            args += ["--health-check", health_check]
        # Note: anet CLI does not expose --meta-path; the daemon discovers
        # /meta by convention. We accept it as a kwarg for SDK parity.

        result = _run(args, env=self._env)
        return result if isinstance(result, dict) else {"raw": result}

    def unregister(self, name: str) -> dict[str, Any]:
        result = _run(["unregister", name], env=self._env)
        return result if isinstance(result, dict) else {"raw": result}

    # ──────────────────────────────────────────────────────────────────
    # Discovery
    # ──────────────────────────────────────────────────────────────────

    def discover(self, *, skill: str, limit: int = 50) -> list[dict[str, Any]]:
        result = _run(
            ["discover", "--skill", skill, "--limit", str(limit)],
            env=self._env,
        )
        if isinstance(result, list):
            return result
        if isinstance(result, dict):
            # Some anet versions wrap the list under {"peers": [...]}; tolerate both.
            for key in ("peers", "results", "services"):
                if key in result and isinstance(result[key], list):
                    return result[key]
        return []

    # ──────────────────────────────────────────────────────────────────
    # Calling remote services
    # ──────────────────────────────────────────────────────────────────

    def call(
        self,
        peer_id: str,
        name: str,
        path: str,
        *,
        method: str = "POST",
        body: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        timeout: float = 60.0,
    ) -> dict[str, Any]:
        args: list[str] = ["call", peer_id, name, path, "--method", method]
        if headers:
            for k, v in headers.items():
                args += ["--header", f"{k}={v}"]
        if body is not None:
            # Pipe JSON body via stdin to avoid shell-quoting hazards.
            payload = json.dumps(body)
            cmd = ["anet", "svc", *args, "--body-stdin", "--json"]
            try:
                proc = subprocess.run(
                    cmd,
                    input=payload,
                    capture_output=True,
                    text=True,
                    timeout=timeout,
                    env=self._env,
                )
            except FileNotFoundError as e:
                raise SvcAPIError(f"`anet` not on PATH: {e}") from e
            if proc.returncode != 0:
                raise SvcAPIError(
                    f"`anet svc call` failed (exit {proc.returncode}): "
                    f"{proc.stderr.strip() or proc.stdout.strip()}"
                )
            out = proc.stdout.strip()
            try:
                return json.loads(out) if out else {}
            except json.JSONDecodeError as e:
                raise SvcAPIError(f"non-JSON output: {out[:200]}") from e

        result = _run(args, env=self._env, timeout=timeout)
        return result if isinstance(result, dict) else {"body": result}

    # ──────────────────────────────────────────────────────────────────
    # Audit / introspection
    # ──────────────────────────────────────────────────────────────────

    def list(self) -> list[dict[str, Any]]:
        result = _run(["list"], env=self._env)
        if isinstance(result, list):
            return result
        if isinstance(result, dict):
            for key in ("services", "registrations"):
                if key in result and isinstance(result[key], list):
                    return result[key]
        return []
