# bootkit

**Air-gapped cluster bootstrap planner.** Turn a declarative node inventory plus
an artifact set into the ordered, per-node plan to stand up a disconnected
Kubernetes cluster (k3s / RKE2-style) — and the verified carry list to get the
artifacts across the gap.

Part of the **Cognis Neural Suite**. Pure Python standard library.

---

## Why

Bootstrapping Kubernetes in a disconnected environment is a sequencing problem:
stage the right artifacts on each node, init the first control-plane, join the
rest in the right order, seed the registry, then apply your manifests. bootkit
computes that plan from one spec file and verifies — on the *connected* side —
that every artifact you'll need is actually there.

## The spec

```yaml
name: edge-cluster
distro: rke2
token: super-secret-cluster-token
nodes:
  - {name: cp-1, role: server, ip: 10.0.0.11}
  - {name: cp-2, role: server, ip: 10.0.0.12}
  - {name: cp-3, role: server, ip: 10.0.0.13}
  - {name: worker-1, role: agent, ip: 10.0.0.21}
artifacts:
  - {name: rke2-install, type: tarball, path: artifacts/rke2-images.tar}
  - {name: registry-seed, type: registry, path: artifacts/registry}
manifests: [bootstrap/cni.yaml]
```

## Commands

```bash
# Validate topology (odd server count, unique names/IPs) + artifact presence.
python -m bootkit preflight bootstrap.yaml

# Build the artifact carry list with sizes + sha256.
python -m bootkit manifest bootstrap.yaml

# Emit the ordered per-node bootstrap plan.
python -m bootkit plan bootstrap.yaml

# Run as a local MCP server (stdio JSON-RPC).
python -m bootkit mcp
```

## What sets bootkit apart

- **Sequencing done right.** init-server → join-servers → join-agents →
  seed-registry → apply, with the join address derived from the first server.
- **Preflight that catches real mistakes.** Even etcd quorum, duplicate
  names/IPs, missing artifact files — found before you walk into the SCIF.
- **Verified carry list.** Per-artifact sha256 so you can confirm integrity on
  the far side.
- **MCP-native** (`plan` / `preflight` / `manifest`) and an opt-in local-fleet AI
  hook (default OFF) that reviews the topology for resilience risks.
- **Completes the air-gap suite:** mirror images with
  [oradeck](https://github.com/cognis-digital/oradeck), bundle the app with
  [airlock](https://github.com/cognis-digital/airlock), and bring up the cluster
  with bootkit.

## Tests

```bash
python -m pytest -q     # or: python -m unittest discover -s tests
```

## Interoperability

`bootkit` composes with the 300+ tool Cognis suite — JSON in/out and a shared
OpenAI-compatible `/v1` backbone. See **[INTEROP.md](INTEROP.md)** for the
suite map, composition patterns, and reference stacks.

## Integrations

Forward `bootkit`'s findings to STIX/MISP/Sigma/Splunk/Elastic/Slack/webhooks via
[`cognis-connect`](https://github.com/cognis-digital/cognis-connect). See **[INTEGRATIONS.md](INTEGRATIONS.md)**.

## License

Cognis Open Collaboration License (COCL) 1.0 — see [`LICENSE`](LICENSE).
© 2026 Cognis Digital LLC. Original Cognis work; no third-party code, names, or
branding.

<!-- cognis:domains:start -->
## Domains

**Primary domain:** AI & ML  ·  **JTF MERIDIAN division:** ATHENA-PRIME · SAGE

**Topics:** `cognis` `ai` `llm` `machine-learning`

Part of the **Cognis Neural Suite** — 300+ source-available tools organized across 12 domains under the JTF MERIDIAN command structure. See the [suite on GitHub](https://github.com/cognis-digital) and [jtf-meridian](https://github.com/cognis-digital/jtf-meridian) for how the pieces fit together.
<!-- cognis:domains:end -->

## Usage — step by step

`bootkit` turns a node inventory + artifact set into the ordered install plan to seed a disconnected k3s/RKE2-style cluster.

1. **Install** (pure stdlib, Python 3.10+):
   ```bash
   pip install "git+https://github.com/cognis-digital/bootkit.git"
   ```
2. **Preflight your spec** to validate topology and that every artifact is present before you cross the air-gap (exits non-zero on failure):
   ```bash
   bootkit preflight cluster.yaml
   ```
3. **Build the carry manifest** (per-artifact size + sha256) and estimate the transfer over your link:
   ```bash
   bootkit manifest cluster.yaml
   bootkit estimate cluster.yaml --mbps 100
   ```
4. **Emit the ordered bootstrap plan**, or render per-node install scripts to run on the far side:
   ```bash
   bootkit plan cluster.yaml
   bootkit render cluster.yaml --out-dir ./scripts
   ```
5. **Automate in CI** — gate on preflight, then archive the plan as JSON:
   ```bash
   bootkit preflight cluster.yaml && bootkit plan cluster.yaml --format json > plan.json
   ```
   Or run it as a local MCP server (stdio JSON-RPC): `bootkit mcp`.
