# Demo 06 — JSON spec straight out of CI

## Where this comes from

A pipeline generates the cluster topology programmatically and emits **JSON**
(easier to template than YAML). bootkit reads `.json` specs natively — same
schema as YAML, just a different on-disk format — so the same commands work
unchanged.

## Run it

```bash
python -m bootkit preflight demos/06-json-spec/bootstrap.json
python -m bootkit plan      demos/06-json-spec/bootstrap.json --format json > plan.json
python -m bootkit manifest  demos/06-json-spec/bootstrap.json --format json
```

## What to expect

- `preflight` -> **PASS** (3 servers, 3 agents, both artifacts present).
- `plan --format json` writes a structured plan you can archive as a build
  artifact or diff between runs.
- The registry is `registry.internal:5000` (from the spec), so the
  `seed-registry` step targets that address.

## How to act

This is the CI-friendly path: generate the spec, **gate on preflight**, archive
the JSON plan, and hand the plan + carry manifest to whoever crosses the gap.

```bash
python -m bootkit preflight demos/06-json-spec/bootstrap.json \
  && python -m bootkit plan demos/06-json-spec/bootstrap.json --format json > plan.json
```
