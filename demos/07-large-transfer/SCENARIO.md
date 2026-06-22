# Demo 07 — Estimate the carry over a slow link

## Where this comes from

A remote site reachable only by a slow, intermittent link (or a literal USB walk
between two air-gapped rooms). Before committing, you want to know how big the
carry is and roughly how long the transfer takes at different link speeds.

The artifacts here are real placeholder files (~6.6 MB + ~1 MB) so the estimate
is concrete; in production you point the spec at your actual multi-GB tarballs.

## Run it

```bash
python -m bootkit manifest demos/07-large-transfer/bootstrap.yaml
python -m bootkit estimate demos/07-large-transfer/bootstrap.yaml --mbps 10
python -m bootkit estimate demos/07-large-transfer/bootstrap.yaml --mbps 1000
python -m bootkit estimate demos/07-large-transfer/bootstrap.yaml --format json
```

## What to expect

- `manifest` totals the two artifacts (~7.6 MB) with per-file sha256.
- `estimate --mbps 10` reports a transfer time of a few seconds; `--mbps 1000`
  reports far less. A **faster link yields a smaller `estimated_seconds`** —
  scale the same math up to your real artifact sizes to plan the walk.
- `--format json` gives `total_bytes`, `link_mbps`, `estimated_seconds`, and a
  human-readable duration.

## How to act

Pick the worst plausible link speed and use that estimate as your time budget.
If the carry is too large, prune images upstream (e.g. with oradeck) before you
build the bundle.
