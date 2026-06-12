# bootkit — Usage Guide

bootkit turns one declarative bootstrap spec into the ordered plan, the verified
carry list, runnable per-node install scripts, and a transfer estimate for
standing up a disconnected k3s/RKE2-style cluster.

## The spec

```yaml
name: edge-cluster
distro: rke2            # k3s | rke2 | generic
token: super-secret-cluster-token
registry: localhost:5000
nodes:
  - {name: cp-1, role: server, ip: 10.0.0.11}
  - {name: cp-2, role: server, ip: 10.0.0.12}
  - {name: cp-3, role: server, ip: 10.0.0.13}
  - {name: worker-1, role: agent, ip: 10.0.0.21}
artifacts:
  - {name: rke2-install, type: tarball,  path: artifacts/rke2-images.tar}
  - {name: registry-seed, type: registry, path: artifacts/registry}
manifests: [bootstrap/cni.yaml]
```

## Commands

### preflight
```bash
python -m bootkit preflight bootstrap.yaml
```
Catches even etcd quorum, duplicate names/IPs, unsupported distro, and missing
artifact files — on the connected side, before you carry anything.

### plan
```bash
python -m bootkit plan bootstrap.yaml
```
Ordered phases: `stage` → `init-server` → `join-server` → `join-agent` →
`seed-registry` → `apply`.

### manifest — verified carry list
```bash
python -m bootkit manifest bootstrap.yaml      # sizes + sha256 per artifact
```

### render — runnable per-node scripts
```bash
python -m bootkit render bootstrap.yaml --out-dir ./install
# -> install/cp-1.sh, cp-2.sh, ..., worker-1.sh
```
Each script is `#!/usr/bin/env bash` with `set -euo pipefail` and only the
commands that node must run, in plan order. Omit `--out-dir` to print them.

### estimate — carry size & transfer time
```bash
python -m bootkit estimate bootstrap.yaml --mbps 100
# carry size + estimated transfer time over a 100 Mbit/s link
```

## MCP server

```bash
python -m bootkit mcp   # plan / preflight / manifest over stdio JSON-RPC
```

## End-to-end (connected -> air-gap)

```bash
python -m bootkit preflight bootstrap.yaml          # validate
python -m bootkit manifest  bootstrap.yaml          # carry list + hashes
python -m bootkit estimate  bootstrap.yaml --mbps 50
python -m bootkit render    bootstrap.yaml --out-dir ./install
# carry ./carry + ./install across the gap, then run install/<node>.sh per node.
```
