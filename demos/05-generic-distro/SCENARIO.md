# Demo 05 — Generic distro (kubeadm-style) sequencing

## Where this comes from

You are not on k3s or RKE2 — you drive a kubeadm-style installer (or your own)
but still want bootkit to compute the **order**, the carry list, and run
preflight. Setting `distro: generic` keeps the same init-first / join-rest
sequencing while emitting distro-neutral install commands.

## Run it

```bash
python -m bootkit preflight demos/05-generic-distro/bootstrap.yaml
python -m bootkit plan      demos/05-generic-distro/bootstrap.yaml
python -m bootkit render    demos/05-generic-distro/bootstrap.yaml --out-dir ./scripts
```

## What to expect

- `preflight` -> **PASS** (3 servers, 1 agent).
- `plan` uses **generic** install commands (`bootkit-install --distro generic
  --role ...`) instead of k3s/rke2-specific ones, but the phase order is
  identical: `stage` -> `init-server` -> `join-server` x2 -> `join-agent` ->
  `apply`.
- `render --out-dir ./scripts` writes `master-1.sh` ... `worker-1.sh`.

## How to act

The generic commands are placeholders for your own installer steps — treat the
rendered scripts as the skeleton and substitute your real `kubeadm init` /
`kubeadm join` lines per phase. bootkit guarantees you run them in the right
order on the right nodes.
