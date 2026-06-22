# Demo 03 — 5-server HA k3s cell with a registry seed

## Where this comes from

A disconnected data-center cell that must survive node loss. You run **five**
control-plane servers so etcd keeps quorum even with two down, plus four agents
for workload capacity. Images are mirrored offline into a registry seed (e.g.
exported by oradeck) and applied as two bootstrap manifests after bring-up.

## Run it

```bash
python -m bootkit preflight demos/03-k3s-ha-quorum/bootstrap.yaml
python -m bootkit plan      demos/03-k3s-ha-quorum/bootstrap.yaml
python -m bootkit manifest  demos/03-k3s-ha-quorum/bootstrap.yaml
```

## What to expect

- `preflight` -> **PASS**: 5 servers (odd -> healthy quorum), 4 agents, unique
  names + IPs, both artifacts present.
- `plan` order: `stage` on all 9 nodes -> `init-server` on **cp-1** -> four
  `join-server` steps (cp-2..cp-5 join cp-1 at `https://10.20.0.11:6443`) ->
  four `join-agent` steps -> `seed-registry` -> two `apply` steps.
- `manifest` lists both artifacts with sizes and sha256.

## How to act

The join address for every server and agent is derived from the **first** server
(cp-1). If you re-order `nodes` so a different server is first, the join target
changes — preflight/plan will reflect that, so keep your intended init node at
the top of the list.
