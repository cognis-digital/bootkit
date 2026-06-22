"""bootkit MCP server — stdio JSON-RPC 2.0. Standard library only.

    {"command": "python", "args": ["-m", "bootkit", "mcp"]}
"""

from __future__ import annotations

import json
import os
import sys
from typing import Any, Dict, Optional

from bootkit import TOOL_NAME, TOOL_VERSION
from bootkit.core import (
    BootkitError,
    build_carry_bundle,
    build_carry_manifest,
    load_spec,
    plan_bootstrap,
    preflight,
)

PROTOCOL_VERSION = "2024-11-05"

_TOOLS = [
    {
        "name": "plan",
        "description": "Emit the ordered, per-node plan to bootstrap a "
                       "disconnected k3s/RKE2-style cluster from a spec file.",
        "inputSchema": {
            "type": "object",
            "properties": {"spec": {"type": "string"}},
            "required": ["spec"], "additionalProperties": False,
        },
    },
    {
        "name": "preflight",
        "description": "Validate the cluster topology and that referenced "
                       "artifacts exist before carrying anything across the gap.",
        "inputSchema": {
            "type": "object",
            "properties": {"spec": {"type": "string"}},
            "required": ["spec"], "additionalProperties": False,
        },
    },
    {
        "name": "manifest",
        "description": "Build the artifact carry list with sizes and sha256 "
                       "hashes for the air-gap transfer.",
        "inputSchema": {
            "type": "object",
            "properties": {"spec": {"type": "string"}},
            "required": ["spec"], "additionalProperties": False,
        },
    },
    {
        "name": "bundle",
        "description": "Emit one self-contained carry bundle (meta + preflight "
                       "+ manifest + plan + per-node scripts) to take across "
                       "the air-gap.",
        "inputSchema": {
            "type": "object",
            "properties": {"spec": {"type": "string"}},
            "required": ["spec"], "additionalProperties": False,
        },
    },
]


def _result(req_id, result): return {"jsonrpc": "2.0", "id": req_id, "result": result}
def _error(req_id, code, msg): return {"jsonrpc": "2.0", "id": req_id, "error": {"code": code, "message": msg}}


def _call_tool(name: str, args: Dict[str, Any]) -> Dict[str, Any]:
    spec_path = args.get("spec")
    if not isinstance(spec_path, str) or not spec_path:
        raise ValueError("`spec` (string) is required")
    spec = load_spec(spec_path)
    base = os.path.dirname(os.path.abspath(spec_path))
    if name == "plan":
        payload = {"plan": plan_bootstrap(spec)}
        is_error = False
    elif name == "preflight":
        payload = preflight(spec, base_dir=base)
        is_error = not payload["ok"]
    elif name == "manifest":
        payload = build_carry_manifest(spec, base_dir=base)
        is_error = False
    elif name == "bundle":
        payload = build_carry_bundle(spec, base_dir=base)
        is_error = not payload["meta"]["preflight_ok"]
    else:
        raise ValueError(f"unknown tool: {name}")
    return {"content": [{"type": "text", "text": json.dumps(payload, indent=2)}],
            "isError": is_error}


def handle_request(req: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    method = req.get("method")
    req_id = req.get("id")
    params = req.get("params") or {}
    is_notification = "id" not in req
    if method == "initialize":
        res = _result(req_id, {"protocolVersion": PROTOCOL_VERSION,
                               "capabilities": {"tools": {"listChanged": False}},
                               "serverInfo": {"name": TOOL_NAME, "version": TOOL_VERSION}})
        return None if is_notification else res
    if method in ("notifications/initialized", "initialized"):
        return None
    if method == "ping":
        return None if is_notification else _result(req_id, {})
    if method == "tools/list":
        return _result(req_id, {"tools": _TOOLS})
    if method == "tools/call":
        name = params.get("name", "")
        args = params.get("arguments") or {}
        try:
            return _result(req_id, _call_tool(name, args))
        except (ValueError, OSError, BootkitError) as exc:
            return _error(req_id, -32602, str(exc))
        except Exception as exc:  # pragma: no cover
            return _error(req_id, -32603, f"internal error: {exc}")
    if is_notification:
        return None
    return _error(req_id, -32601, f"method not found: {method}")


def run_mcp_server(stdin=None, stdout=None) -> None:
    stdin = stdin or sys.stdin
    stdout = stdout or sys.stdout
    for line in stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
        except json.JSONDecodeError:
            stdout.write(json.dumps(_error(None, -32700, "parse error")) + "\n")
            stdout.flush()
            continue
        response = handle_request(req)
        if response is not None:
            stdout.write(json.dumps(response) + "\n")
            stdout.flush()


if __name__ == "__main__":
    run_mcp_server()
