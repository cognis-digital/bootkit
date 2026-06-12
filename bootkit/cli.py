"""Command-line interface for bootkit."""

from __future__ import annotations

import argparse
import json
import os
import sys
from typing import List, Optional

from bootkit import TOOL_NAME, TOOL_VERSION
from bootkit.core import (
    BootkitError,
    build_carry_manifest,
    load_spec,
    plan_bootstrap,
    preflight,
)


def _human(n: int) -> str:
    f = float(n)
    for u in ("B", "KB", "MB", "GB", "TB"):
        if f < 1024 or u == "TB":
            return f"{f:.0f}{u}" if u == "B" else f"{f:.1f}{u}"
        f /= 1024
    return f"{f:.1f}TB"


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog=TOOL_NAME,
        description="Air-gapped cluster bootstrap planner — turn a node "
                    "inventory + artifact set into the ordered install plan to "
                    "seed a disconnected k3s/RKE2-style cluster.")
    p.add_argument("--version", action="version",
                   version=f"{TOOL_NAME} {TOOL_VERSION}")
    sub = p.add_subparsers(dest="command")

    pl = sub.add_parser("plan", help="Emit the ordered per-node bootstrap plan.")
    pl.add_argument("spec")
    pl.add_argument("--format", choices=("table", "json"), default="table")

    pf = sub.add_parser("preflight", help="Validate topology + artifact presence.")
    pf.add_argument("spec")
    pf.add_argument("--format", choices=("table", "json"), default="table")

    m = sub.add_parser("manifest", help="Build the artifact carry list (size+sha256).")
    m.add_argument("spec")
    m.add_argument("--format", choices=("table", "json"), default="table")

    rn = sub.add_parser("render", help="Render per-node install scripts.")
    rn.add_argument("spec")
    rn.add_argument("--out-dir", help="Write <node>.sh files here (else print).")

    es = sub.add_parser("estimate", help="Estimate carry size + transfer time.")
    es.add_argument("spec")
    es.add_argument("--mbps", type=float, default=100.0,
                    help="Link speed in Mbit/s (default 100).")
    es.add_argument("--format", choices=("table", "json"), default="table")

    sub.add_parser("mcp", help="Run as an MCP server (stdio JSON-RPC).")
    return p


def _run_plan(a) -> int:
    try:
        spec = load_spec(a.spec)
        steps = plan_bootstrap(spec)
    except (OSError, BootkitError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    if a.format == "json":
        print(json.dumps({"plan": steps}, indent=2))
    else:
        print(f"bootkit plan — {spec.get('name', 'cluster')} "
              f"({spec.get('distro', 'generic')})  {len(steps)} step(s)")
        print("=" * 64)
        phase = None
        for s in steps:
            if s["phase"] != phase:
                phase = s["phase"]
                print(f"-- {phase} --")
            print(f"  [{s['node']}] $ {s['command']}")
    return 0


def _run_preflight(a) -> int:
    base = os.path.dirname(os.path.abspath(a.spec))
    try:
        res = preflight(load_spec(a.spec), base_dir=base)
    except (OSError, BootkitError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    if a.format == "json":
        print(json.dumps(res, indent=2))
    else:
        print("bootkit preflight")
        print("=" * 64)
        print(f"  servers: {res['servers']}   agents: {res['agents']}")
        for p in res["problems"]:
            print(f"  ! {p}")
        print("RESULT: " + ("PASS" if res["ok"] else "FAIL"))
    return 0 if res["ok"] else 1


def _run_manifest(a) -> int:
    base = os.path.dirname(os.path.abspath(a.spec))
    try:
        man = build_carry_manifest(load_spec(a.spec), base_dir=base)
    except (OSError, BootkitError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    if a.format == "json":
        print(json.dumps(man, indent=2))
    else:
        print(f"bootkit carry manifest — {man['cluster']} ({man['distro']})")
        print("=" * 64)
        for art in man["artifacts"]:
            size = _human(art["size"]) if "size" in art else art.get("status", "?")
            sha = art.get("sha256", "")[:14]
            print(f"  {art['type']:<10} {art['name']:<24} {size:>9}  {sha}")
        print("-" * 64)
        print(f"{man['artifact_count']} artifact(s), {_human(man['total_bytes'])} total")
    return 0


def _run_render(a) -> int:
    from bootkit import render_scripts, write_scripts
    try:
        spec = load_spec(a.spec)
        if a.out_dir:
            written = write_scripts(spec, a.out_dir)
            print(f"bootkit render — wrote {len(written)} script(s) to {a.out_dir}")
            for w in written:
                print(f"  {w}")
        else:
            for node, script in render_scripts(spec).items():
                print(f"# ===== {node}.sh =====")
                print(script)
    except (OSError, BootkitError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    return 0


def _run_estimate(a) -> int:
    from bootkit import estimate_transfer
    base = os.path.dirname(os.path.abspath(a.spec))
    try:
        est = estimate_transfer(load_spec(a.spec), base_dir=base, mbps=a.mbps)
    except (OSError, BootkitError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    if a.format == "json":
        print(json.dumps(est, indent=2))
    else:
        print(f"bootkit estimate — {est['cluster']}")
        print("=" * 64)
        print(f"  artifacts : {est['artifact_count']}")
        print(f"  carry size: {_human(est['total_bytes'])}")
        print(f"  link      : {est['link_mbps']} Mbit/s")
        print(f"  transfer  : ~{est['estimated_human']}")
    return 0


def _run_mcp() -> int:
    from bootkit.mcp_server import run_mcp_server
    run_mcp_server()
    return 0


def main(argv: Optional[List[str]] = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    if args.command == "plan":
        return _run_plan(args)
    if args.command == "preflight":
        return _run_preflight(args)
    if args.command == "manifest":
        return _run_manifest(args)
    if args.command == "render":
        return _run_render(args)
    if args.command == "estimate":
        return _run_estimate(args)
    if args.command == "mcp":
        return _run_mcp()
    parser.print_help(sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
