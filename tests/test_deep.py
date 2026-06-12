"""Deep tests for bootkit — preflight rules, plan order, manifest, MCP."""

import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bootkit import (
    build_carry_manifest, load_spec, plan_bootstrap, preflight, review_topology,
)
from bootkit.core import BootkitError
from bootkit import mcp_server

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SPEC = os.path.join(REPO_ROOT, "demos", "01-basic", "bootstrap.yaml")
BASE = os.path.dirname(SPEC)


class TestPreflight(unittest.TestCase):
    def test_even_servers_flagged(self):
        spec = {"distro": "k3s", "nodes": [
            {"name": "a", "role": "server", "ip": "1"},
            {"name": "b", "role": "server", "ip": "2"}]}
        res = preflight(spec)
        self.assertFalse(res["ok"])
        self.assertTrue(any("even server" in p for p in res["problems"]))

    def test_no_servers(self):
        res = preflight({"distro": "k3s", "nodes": [
            {"name": "a", "role": "agent", "ip": "1"}]})
        self.assertFalse(res["ok"])

    def test_duplicate_names(self):
        res = preflight({"distro": "k3s", "nodes": [
            {"name": "a", "role": "server", "ip": "1"},
            {"name": "a", "role": "agent", "ip": "2"}]})
        self.assertTrue(any("duplicate node names" in p for p in res["problems"]))

    def test_bad_distro(self):
        res = preflight({"distro": "openshift", "nodes": [
            {"name": "a", "role": "server", "ip": "1"}]})
        self.assertTrue(any("unsupported distro" in p for p in res["problems"]))

    def test_missing_artifact(self):
        spec = {"distro": "k3s",
                "nodes": [{"name": "a", "role": "server", "ip": "1"}],
                "artifacts": [{"name": "x", "path": "nope.tar"}]}
        res = preflight(spec, base_dir="/tmp")
        self.assertIn("nope.tar", res["missing_artifacts"])


class TestPlanOrder(unittest.TestCase):
    def test_init_before_joins(self):
        steps = plan_bootstrap(load_spec(SPEC))
        phases = [s["phase"] for s in steps]
        self.assertLess(phases.index("init-server"), phases.index("join-server"))
        self.assertLess(phases.index("join-server"), phases.index("join-agent"))

    def test_k3s_commands(self):
        spec = {"distro": "k3s", "token": "T", "nodes": [
            {"name": "s1", "role": "server", "ip": "10.0.0.1"},
            {"name": "a1", "role": "agent", "ip": "10.0.0.2"}]}
        steps = plan_bootstrap(spec)
        init = next(s for s in steps if s["phase"] == "init-server")
        self.assertIn("--cluster-init", init["command"])
        join = next(s for s in steps if s["phase"] == "join-agent")
        self.assertIn("10.0.0.1", join["command"])

    def test_no_servers_raises(self):
        with self.assertRaises(BootkitError):
            plan_bootstrap({"distro": "k3s", "nodes": []})


class TestManifest(unittest.TestCase):
    def test_carry_manifest_hashes(self):
        man = build_carry_manifest(load_spec(SPEC), base_dir=BASE)
        self.assertEqual(man["artifact_count"], 2)
        for art in man["artifacts"]:
            self.assertIn("sha256", art)
            self.assertEqual(len(art["sha256"]), 64)
        self.assertGreater(man["total_bytes"], 0)


class TestMcp(unittest.TestCase):
    def test_list_and_plan(self):
        tl = mcp_server.handle_request({"jsonrpc": "2.0", "id": 1, "method": "tools/list"})
        self.assertEqual({t["name"] for t in tl["result"]["tools"]},
                         {"plan", "preflight", "manifest"})
        r = mcp_server.handle_request({
            "jsonrpc": "2.0", "id": 2, "method": "tools/call",
            "params": {"name": "preflight", "arguments": {"spec": SPEC}}})
        self.assertFalse(r["result"]["isError"])

    def test_plan_call(self):
        r = mcp_server.handle_request({
            "jsonrpc": "2.0", "id": 3, "method": "tools/call",
            "params": {"name": "plan", "arguments": {"spec": SPEC}}})
        payload = json.loads(r["result"]["content"][0]["text"])
        self.assertTrue(any(s["phase"] == "init-server" for s in payload["plan"]))


class TestAiHook(unittest.TestCase):
    def test_off_by_default(self):
        for v in ("COGNIS_AI_BACKEND", "COGNIS_AI_ENDPOINT"):
            os.environ.pop(v, None)
        out = review_topology(load_spec(SPEC))
        self.assertTrue(out["_ai"].startswith("disabled"))
        self.assertEqual(out["nodes"], 5)


if __name__ == "__main__":
    unittest.main()
