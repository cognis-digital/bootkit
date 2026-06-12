"""Core engine for bootkit — air-gapped cluster bootstrap planner.

bootkit takes a declarative *bootstrap spec* — a node inventory (servers +
agents) plus the artifacts that must be present (the distro install tarball,
images, a registry seed, optional manifests) — and produces the ordered,
per-node plan to stand up a disconnected Kubernetes cluster (k3s / RKE2-style).

It also assembles a manifest of the artifacts to carry across the air-gap and
verifies that everything the plan references is actually present, so you find a
missing tarball on the connected side, not at 2 a.m. in the SCIF.

What bootkit produces:

  * plan       — ordered steps: stage artifacts -> start first server (init) ->
                 join remaining servers -> join agents -> seed registry ->
                 apply manifests
  * manifest   — the artifact set with sizes + sha256 (a carry list)
  * preflight  — checks that referenced artifact files exist and the topology is
                 sane (odd server count for HA, unique node names/IPs)

bootkit never touches a real machine; it emits the commands and the carry list.
This is original Cognis Digital work; it shares no code, names, or branding with
any distro or air-gap tool.
"""

from __future__ import annotations

import hashlib
import json
import os
from typing import Any, Dict, List, Optional, Tuple

TOOL_NAME = "bootkit"
TOOL_VERSION = "0.1.0"

SUPPORTED_DISTROS = ("k3s", "rke2", "generic")


class BootkitError(Exception):
    """User-facing bootstrap-spec error."""


# --------------------------------------------------------------------------- #
# YAML subset
# --------------------------------------------------------------------------- #

def _coerce(text: str) -> Any:
    s = text.strip()
    if s in ("", "~", "null"):
        return None
    if s in ("true", "false"):
        return s == "true"
    if len(s) >= 2 and s[0] == s[-1] and s[0] in "\"'":
        return s[1:-1]
    if len(s) >= 2 and s[0] == "[" and s[-1] == "]":
        inner = s[1:-1].strip()
        return [] if not inner else [_coerce(p) for p in inner.split(",")]
    try:
        return int(s)
    except ValueError:
        pass
    try:
        return float(s)
    except ValueError:
        pass
    return s


def parse_yaml_subset(text: str) -> Any:
    lines = text.replace("\t", "  ").splitlines()
    toks: List[Tuple[int, str]] = []
    for raw in lines:
        out, sgl, dbl = [], False, False
        for i, ch in enumerate(raw):
            if ch == "'" and not dbl:
                sgl = not sgl
            elif ch == '"' and not sgl:
                dbl = not dbl
            elif ch == "#" and not sgl and not dbl and (i == 0 or raw[i-1] in " \t"):
                break
            out.append(ch)
        line = "".join(out).rstrip()
        if not line.strip() or line.strip() == "---":
            continue
        indent = len(line) - len(line.lstrip(" "))
        toks.append((indent, line.strip()))
    if not toks:
        return {}
    pos = [0]

    def kv(s):
        i = s.find(":")
        if i == -1:
            return s, ""
        k, v = s[:i].strip(), s[i+1:].strip()
        if len(k) >= 2 and k[0] == k[-1] and k[0] in "\"'":
            k = k[1:-1]
        return k, v

    def parse_block(indent):
        if pos[0] >= len(toks):
            return None
        _c, content = toks[pos[0]]
        return parse_list(indent) if content.startswith("- ") else parse_map(indent)

    def parse_list(indent):
        items = []
        while pos[0] < len(toks):
            cur, content = toks[pos[0]]
            if cur != indent or not content.startswith("- "):
                break
            inner = content[2:].strip()
            pos[0] += 1
            if ":" in inner and not (inner.find(":")+1 < len(inner)
                                     and inner[inner.find(":")+1] != " "):
                k, v = kv(inner)
                obj = {k: (_coerce(v) if v else _child(indent + 2))}
                obj.update(cont_map(indent + 2))
                items.append(obj)
            elif inner == "":
                items.append(_child(indent + 2))
            else:
                items.append(_coerce(inner))
        return items

    def cont_map(indent):
        obj = {}
        while pos[0] < len(toks):
            cur, content = toks[pos[0]]
            if cur != indent or content.startswith("- "):
                break
            k, v = kv(content)
            pos[0] += 1
            obj[k] = _coerce(v) if v else _child(indent + 2)
        return obj

    def parse_map(indent):
        obj = {}
        while pos[0] < len(toks):
            cur, content = toks[pos[0]]
            if cur != indent or content.startswith("- "):
                break
            k, v = kv(content)
            pos[0] += 1
            obj[k] = _coerce(v) if v else _child(indent + 1)
        return obj

    def _child(min_indent):
        if pos[0] >= len(toks):
            return None
        cur, content = toks[pos[0]]
        if cur < min_indent:
            return None
        return parse_list(cur) if content.startswith("- ") else parse_map(cur)

    result = parse_block(0)
    return result if result is not None else {}


def load_spec(path: str) -> Dict[str, Any]:
    if not os.path.isfile(path):
        raise BootkitError(f"bootstrap spec not found: {path}")
    with open(path, "r", encoding="utf-8") as fh:
        text = fh.read()
    ext = os.path.splitext(path)[1].lower()
    try:
        data = json.loads(text) if ext == ".json" else parse_yaml_subset(text)
    except (json.JSONDecodeError, ValueError) as exc:
        raise BootkitError(f"could not parse {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise BootkitError("spec root must be a mapping")
    return data


# --------------------------------------------------------------------------- #
# Preflight
# --------------------------------------------------------------------------- #

def preflight(spec: Dict[str, Any], base_dir: str = ".") -> Dict[str, Any]:
    """Validate topology + that referenced artifact files exist."""
    problems: List[str] = []
    distro = spec.get("distro", "generic")
    if distro not in SUPPORTED_DISTROS:
        problems.append(f"unsupported distro: {distro} (use {SUPPORTED_DISTROS})")

    nodes = spec.get("nodes", []) or []
    servers = [n for n in nodes if n.get("role") == "server"]
    agents = [n for n in nodes if n.get("role") == "agent"]
    if not servers:
        problems.append("no server nodes declared (need at least one)")
    if len(servers) % 2 == 0 and len(servers) > 1:
        problems.append(f"even server count ({len(servers)}) — HA etcd quorum "
                        "needs an odd number")
    names = [n.get("name") for n in nodes]
    if len(names) != len(set(names)):
        problems.append("duplicate node names")
    ips = [n.get("ip") for n in nodes if n.get("ip")]
    if len(ips) != len(set(ips)):
        problems.append("duplicate node IPs")

    missing_artifacts: List[str] = []
    for art in spec.get("artifacts", []) or []:
        p = art.get("path")
        if p:
            full = p if os.path.isabs(p) else os.path.join(base_dir, p)
            if not os.path.exists(full):
                missing_artifacts.append(p)
    if missing_artifacts:
        problems.append(f"{len(missing_artifacts)} artifact file(s) missing")

    return {"ok": not problems, "problems": problems,
            "servers": len(servers), "agents": len(agents),
            "missing_artifacts": missing_artifacts}


# --------------------------------------------------------------------------- #
# Artifact manifest (carry list)
# --------------------------------------------------------------------------- #

def _sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def build_carry_manifest(spec: Dict[str, Any], base_dir: str = ".") -> Dict[str, Any]:
    """List the artifacts to carry across the gap with size + sha256."""
    items = []
    total = 0
    for art in spec.get("artifacts", []) or []:
        p = art.get("path")
        entry = {"name": art.get("name") or (os.path.basename(p) if p else "?"),
                 "type": art.get("type", "file"), "path": p}
        if p:
            full = p if os.path.isabs(p) else os.path.join(base_dir, p)
            if os.path.isfile(full):
                entry["size"] = os.path.getsize(full)
                entry["sha256"] = _sha256_file(full)
                total += entry["size"]
            else:
                entry["status"] = "missing"
        items.append(entry)
    return {"cluster": spec.get("name", "cluster"),
            "distro": spec.get("distro", "generic"),
            "artifact_count": len(items), "total_bytes": total,
            "artifacts": items}


# --------------------------------------------------------------------------- #
# Plan
# --------------------------------------------------------------------------- #

def plan_bootstrap(spec: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Compute the ordered, per-node bootstrap step plan."""
    distro = spec.get("distro", "generic")
    nodes = spec.get("nodes", []) or []
    servers = [n for n in nodes if n.get("role") == "server"]
    agents = [n for n in nodes if n.get("role") == "agent"]
    if not servers:
        raise BootkitError("no server nodes to bootstrap")

    token = spec.get("token", "${CLUSTER_TOKEN}")
    init = servers[0]
    init_ip = init.get("ip", "<init-ip>")
    steps: List[Dict[str, Any]] = []

    # 1. Stage artifacts on every node.
    for n in nodes:
        steps.append({"phase": "stage", "node": n.get("name"),
                      "command": f"bootkit-stage {n.get('name')} "
                                 f"--from ./carry --to /var/lib/{distro}/agent/images"})

    # 2. Init the first server.
    steps.append({"phase": "init-server", "node": init.get("name"),
                  "command": _install_cmd(distro, "server", init_ip=None,
                                          token=token, first=True)})

    # 3. Join remaining servers.
    for s in servers[1:]:
        steps.append({"phase": "join-server", "node": s.get("name"),
                      "command": _install_cmd(distro, "server", init_ip=init_ip,
                                              token=token, first=False)})

    # 4. Join agents.
    for a in agents:
        steps.append({"phase": "join-agent", "node": a.get("name"),
                      "command": _install_cmd(distro, "agent", init_ip=init_ip,
                                              token=token, first=False)})

    # 5. Seed the registry (if a registry seed artifact exists).
    if any(art.get("type") == "registry" for art in spec.get("artifacts", []) or []):
        steps.append({"phase": "seed-registry", "node": init.get("name"),
                      "command": "bootkit-seed-registry ./carry/registry "
                                 f"--to {spec.get('registry', 'localhost:5000')}"})

    # 6. Apply bootstrap manifests.
    for m in spec.get("manifests", []) or []:
        steps.append({"phase": "apply", "node": init.get("name"),
                      "command": f"kubectl apply -f {m}"})

    return steps


def _install_cmd(distro: str, role: str, init_ip: Optional[str],
                 token: str, first: bool) -> str:
    if distro == "k3s":
        if role == "server" and first:
            return f"INSTALL_K3S_SKIP_DOWNLOAD=true k3s server --cluster-init --token {token}"
        if role == "server":
            return (f"INSTALL_K3S_SKIP_DOWNLOAD=true k3s server "
                    f"--server https://{init_ip}:6443 --token {token}")
        return (f"INSTALL_K3S_SKIP_DOWNLOAD=true k3s agent "
                f"--server https://{init_ip}:6443 --token {token}")
    if distro == "rke2":
        if role == "server" and first:
            return f"rke2 server  # config: token={token}, cluster-init"
        if role == "server":
            return f"rke2 server  # config: server=https://{init_ip}:9345, token={token}"
        return f"rke2 agent   # config: server=https://{init_ip}:9345, token={token}"
    # generic
    target = "control-plane (init)" if first else f"join via {init_ip}"
    return f"bootkit-install --distro generic --role {role} --{target.split()[0]}"


# --------------------------------------------------------------------------- #
# AI hook (opt-in, default OFF)
# --------------------------------------------------------------------------- #

def review_topology(spec: Dict[str, Any]) -> Dict[str, Any]:
    out = {"nodes": len(spec.get("nodes", []) or []), "notes": "",
           "_ai": "disabled — set COGNIS_AI_BACKEND to enable"}
    backend = _load_ai_backend()
    if backend is None or not backend.is_enabled() or not backend.health():
        return out
    try:
        out["notes"] = backend._chat(
            "Review this air-gapped Kubernetes bootstrap topology for HA and "
            "resilience risks in two sentences.", json.dumps(spec)) or ""
        out["_ai"] = "reviewed by local fleet"
    except Exception:
        pass
    return out


def _load_ai_backend():
    import importlib.util
    here = os.path.dirname(os.path.abspath(__file__))
    cand = os.path.abspath(os.path.join(here, "..", "..", "..", "_shared",
                                        "cognis_ai_backend.py"))
    if os.path.isfile(cand):
        try:
            spec = importlib.util.spec_from_file_location("cognis_ai_backend", cand)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)  # type: ignore[union-attr]
            return mod.CognisAIBackend()
        except Exception:
            return None
    return None
