# Demo 04 — Preflight catches a broken spec (intentional failure)

## Where this comes from

A spec hand-edited under time pressure. Before walking it into a disconnected
space, you run `preflight` as a CI gate. This spec contains **four** real
mistakes on purpose so you can see each one surface.

## Run it

```bash
python -m bootkit preflight demos/04-preflight-fails/bootstrap.yaml
echo "exit code: $?"

# Machine-readable for a CI pipeline:
python -m bootkit preflight demos/04-preflight-fails/bootstrap.yaml --format json
```

## What to expect

`preflight` -> **FAIL** and a non-zero exit code (1). The problem list flags:

- `even server count (2) — HA etcd quorum needs an odd number`
- `duplicate node names`
- `duplicate node IPs`
- `1 artifact file(s) missing`

## How to act

This is the gate working as intended. Fix the spec: give the third node a unique
name and IP, add or remove a server to make the count odd, and either stage the
missing tarball or correct its `path`. Re-run until `RESULT: PASS` and the exit
code is `0` — only then carry it across the gap. In CI:

```bash
python -m bootkit preflight cluster.yaml || { echo "blocked"; exit 1; }
```
