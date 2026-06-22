# Demo 02 — Single-node k3s edge appliance

## Where this comes from

A field-deployed sensor box (call it `sensor-edge-01`) needs to run a handful of
containers with **no network uplink**. One physical machine acts as both the
control plane and the workload host. You stage the k3s air-gap image tarball on
a USB drive, walk it to the box, and bring k3s up offline.

A single server is a perfectly valid quorum (1 is odd), so preflight passes —
this is the smallest real cluster bootkit will plan.

## Run it

```bash
python -m bootkit preflight demos/02-single-node-k3s/bootstrap.yaml
python -m bootkit plan      demos/02-single-node-k3s/bootstrap.yaml
python -m bootkit render    demos/02-single-node-k3s/bootstrap.yaml
```

## What to expect

- `preflight` -> **PASS** (1 server, 0 agents, artifact present).
- `plan` shows: `stage` -> `init-server` (with `--cluster-init`) -> `apply`.
  There are **no** `join-server` / `join-agent` phases (nothing to join), and
  **no** `seed-registry` phase because this spec declares no `registry`
  artifact.
- `render` prints exactly one script, `appliance-1.sh`.

## How to act

Copy the rendered `appliance-1.sh` onto the box and run it. Because the spec has
no registry seed, your workload manifest must reference images that are already
in the staged tarball.
