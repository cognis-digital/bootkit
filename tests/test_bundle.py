"""Tests for the carry-bundle feature, flow-style YAML, and the new demos."""

import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bootkit import build_carry_bundle, load_spec, parse_yaml_subset
from bootkit import mcp_server
from bootkit.cli import main

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEMOS = os.path.join(REPO_ROOT, "demos")


def _demo_spec(name):
    for ext in ("bootstrap.yaml", "bootstrap.json"):
        p = os.path.join(DEMOS, name, ext)
        if os.path.isfile(p):
            return p
    raise FileNotFoundError(name)


class TestFlowYaml(unittest.TestCase):
    def test_flow_mapping_in_list(self):
        data = parse_yaml_subset(
            "nodes:\n  - {name: cp-1, role: server, ip: 10.0.0.11}\n")
        self.assertEqual(data["nodes"],
                         [{"name": "cp-1", "role": "server", "ip": "10.0.0.11"}])

    def test_flow_list_value(self):
        data = parse_yaml_subset("manifests: [a.yaml, b.yaml]\n")
        self.assertEqual(data["manifests"], ["a.yaml", "b.yaml"])

    def test_flow_mapping_preserves_dotted_ip(self):
        # The comma-splitter must not break on dots, and ip stays a string.
        data = parse_yaml_subset("nodes:\n  - {name: n, role: agent, ip: 1.2.3.4}\n")
        self.assertEqual(data["nodes"][0]["ip"], "1.2.3.4")


class TestCarryBundle(unittest.TestCase):
    def setUp(self):
        self.spec_path = _demo_spec("09-carry-bundle")
        self.base = os.path.dirname(self.spec_path)
        self.spec = load_spec(self.spec_path)

    def test_bundle_structure(self):
        b = build_carry_bundle(self.spec, base_dir=self.base)
        self.assertEqual(set(b), {"meta", "preflight", "manifest", "plan", "scripts"})

    def test_bundle_meta(self):
        b = build_carry_bundle(self.spec, base_dir=self.base)
        self.assertEqual(b["meta"]["tool"], "bootkit")
        self.assertEqual(b["meta"]["node_count"], 5)
        self.assertEqual(b["meta"]["artifact_count"], 2)
        self.assertTrue(b["meta"]["preflight_ok"])

    def test_bundle_has_script_per_node(self):
        b = build_carry_bundle(self.spec, base_dir=self.base)
        self.assertEqual(set(b["scripts"]),
                         {"cp-1", "cp-2", "cp-3", "w-1", "w-2"})
        for script in b["scripts"].values():
            self.assertTrue(script.startswith("#!/usr/bin/env bash"))

    def test_bundle_manifest_hashes(self):
        b = build_carry_bundle(self.spec, base_dir=self.base)
        for art in b["manifest"]["artifacts"]:
            self.assertIn("sha256", art)
            self.assertEqual(len(art["sha256"]), 64)

    def test_bundle_is_json_serializable(self):
        b = build_carry_bundle(self.spec, base_dir=self.base)
        json.dumps(b)  # must not raise

    def test_bundle_preflight_fail_flag(self):
        spec = load_spec(_demo_spec("04-preflight-fails"))
        base = os.path.dirname(_demo_spec("04-preflight-fails"))
        b = build_carry_bundle(spec, base_dir=base)
        self.assertFalse(b["meta"]["preflight_ok"])


class TestBundleCli(unittest.TestCase):
    def test_bundle_stdout_ok(self):
        self.assertEqual(main(["bundle", _demo_spec("09-carry-bundle")]), 0)

    def test_bundle_out_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = os.path.join(tmp, "carry.json")
            self.assertEqual(main(["bundle", _demo_spec("09-carry-bundle"),
                                   "--out", out]), 0)
            with open(out, encoding="utf-8") as fh:
                data = json.load(fh)
            self.assertTrue(data["meta"]["preflight_ok"])

    def test_bundle_nonzero_on_preflight_fail(self):
        # Bundle on a broken spec returns 1 so CI can gate on it.
        self.assertEqual(main(["bundle", _demo_spec("04-preflight-fails")]), 1)


class TestBundleMcp(unittest.TestCase):
    def test_bundle_tool_listed(self):
        tl = mcp_server.handle_request(
            {"jsonrpc": "2.0", "id": 1, "method": "tools/list"})
        self.assertIn("bundle", {t["name"] for t in tl["result"]["tools"]})

    def test_bundle_tool_call(self):
        r = mcp_server.handle_request({
            "jsonrpc": "2.0", "id": 2, "method": "tools/call",
            "params": {"name": "bundle",
                       "arguments": {"spec": _demo_spec("09-carry-bundle")}}})
        self.assertFalse(r["result"]["isError"])
        payload = json.loads(r["result"]["content"][0]["text"])
        self.assertEqual(set(payload),
                         {"meta", "preflight", "manifest", "plan", "scripts"})


class TestDemosFire(unittest.TestCase):
    """Every passing demo must preflight cleanly via the CLI."""

    PASS_DEMOS = ["01-basic", "02-single-node-k3s", "03-k3s-ha-quorum",
                  "05-generic-distro", "06-json-spec", "07-large-transfer",
                  "08-mcp-session", "09-carry-bundle"]

    def test_passing_demos_preflight(self):
        for d in self.PASS_DEMOS:
            with self.subTest(demo=d):
                self.assertEqual(main(["preflight", _demo_spec(d)]), 0)

    def test_broken_demo_fails_preflight(self):
        self.assertEqual(main(["preflight", _demo_spec("04-preflight-fails")]), 1)

    def test_every_demo_plans(self):
        for d in self.PASS_DEMOS:
            with self.subTest(demo=d):
                self.assertEqual(main(["plan", _demo_spec(d)]), 0)


if __name__ == "__main__":
    unittest.main()
