# Demo 01 — Plan a disconnected RKE2 cluster

`bootstrap.yaml` describes a 3-server (HA) + 2-agent RKE2 cluster, the artifacts
to carry (an images tarball + a registry seed), and a bootstrap manifest.

## Run it

```bash
# Validate topology + that every referenced artifact exists.
python -m bootkit preflight demos/01-basic/bootstrap.yaml

# Build the carry list (artifact sizes + sha256).
python -m bootkit manifest demos/01-basic/bootstrap.yaml

# Emit the ordered, per-node bootstrap plan.
python -m bootkit plan demos/01-basic/bootstrap.yaml
```

## What you should see

`preflight` passes: 3 servers (odd → valid etcd quorum), 2 agents, both
artifacts present. `plan` emits phases in the correct order:

```
-- stage --        (every node)
-- init-server --  cp-1 starts with --cluster-init
-- join-server --  cp-2, cp-3 join cp-1
-- join-agent --   worker-1, worker-2 join
-- seed-registry --
-- apply --        kubectl apply -f bootstrap/cni.yaml
```

Try setting `nodes` to two servers and re-running `preflight` — it flags the
even server count as an etcd-quorum risk.
