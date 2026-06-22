# Demo 09 — One self-contained carry bundle (`bundle`)

## Where this comes from

You are about to cross the gap and want **one** thing to carry alongside the
artifacts: a single JSON that contains the verified manifest, the ordered plan,
and a runnable install script for every node. The `bundle` subcommand emits
exactly that — so the far side needs no copy of bootkit at all.

## Run it

```bash
# Print the bundle:
python -m bootkit bundle demos/09-carry-bundle/bootstrap.yaml

# Or write it to a file (exits non-zero if the embedded preflight fails):
python -m bootkit bundle demos/09-carry-bundle/bootstrap.yaml --out carry-bundle.json
```

## What to expect

A JSON document with five top-level keys:

- `meta` — tool, version, cluster, distro, `node_count` (5), `artifact_count`
  (2), and `preflight_ok` (`true` here).
- `preflight` — the full topology + artifact-presence result.
- `manifest` — the carry list with per-artifact size + sha256.
- `plan` — the ordered, per-node step plan.
- `scripts` — `{ "cp-1": "#!/usr/bin/env bash\n...", ... }`, one per node.

Writing with `--out` prints a one-line summary and **exits 0 only if the
embedded preflight passed** — making `bundle` a drop-in CI gate that also
produces the artifact.

## How to act

Copy `carry-bundle.json` plus the staged artifacts across the gap. On the far
side, extract each node's script with stock tooling, e.g.:

```bash
python -c "import json,sys; print(json.load(open('carry-bundle.json'))['scripts']['cp-1'])" > cp-1.sh
bash cp-1.sh
```
