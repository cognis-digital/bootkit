"""Feature tests for bootkit — script rendering, transfer estimate, CLI."""

import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bootkit import (
    estimate_transfer, load_spec, render_scripts, write_scripts,
)
from bootkit.cli import main

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SPEC = os.path.join(REPO_ROOT, "demos", "01-basic", "bootstrap.yaml")
BASE = os.path.dirname(SPEC)


class TestRenderScripts(unittest.TestCase):
    def test_one_script_per_node(self):
        scripts = render_scripts(load_spec(SPEC))
        # 3 servers + 2 agents = 5 nodes all get a script
        self.assertEqual(set(scripts), {"cp-1", "cp-2", "cp-3", "worker-1", "worker-2"})

    def test_init_node_gets_init_command(self):
        scripts = render_scripts(load_spec(SPEC))
        self.assertIn("cluster-init", scripts["cp-1"])
        # an agent gets a join command, not init
        self.assertNotIn("cluster-init", scripts["worker-1"])
        self.assertIn("agent", scripts["worker-1"])

    def test_scripts_are_bash(self):
        scripts = render_scripts(load_spec(SPEC))
        for s in scripts.values():
            self.assertTrue(s.startswith("#!/usr/bin/env bash"))
            self.assertIn("set -euo pipefail", s)

    def test_write_scripts(self):
        with tempfile.TemporaryDirectory() as tmp:
            written = write_scripts(load_spec(SPEC), tmp)
            self.assertEqual(len(written), 5)
            for p in written:
                self.assertTrue(os.path.isfile(p))
                self.assertTrue(p.endswith(".sh"))


class TestEstimate(unittest.TestCase):
    def test_estimate_fields(self):
        est = estimate_transfer(load_spec(SPEC), base_dir=BASE, mbps=100.0)
        self.assertEqual(est["artifact_count"], 2)
        self.assertGreater(est["total_bytes"], 0)
        self.assertGreaterEqual(est["estimated_seconds"], 0)
        self.assertTrue(est["estimated_human"])

    def test_faster_link_less_time(self):
        with tempfile.TemporaryDirectory() as tmp:
            art = os.path.join(tmp, "big.tar")
            with open(art, "wb") as fh:
                fh.write(b"0" * (5 * 1024 * 1024))
            spec = {"name": "c", "distro": "k3s",
                    "nodes": [{"name": "s", "role": "server", "ip": "1"}],
                    "artifacts": [{"name": "big", "type": "tarball", "path": "big.tar"}]}
            slow = estimate_transfer(spec, base_dir=tmp, mbps=10.0)
            fast = estimate_transfer(spec, base_dir=tmp, mbps=1000.0)
            self.assertGreater(slow["estimated_seconds"], fast["estimated_seconds"])
            self.assertGreater(slow["estimated_seconds"], 0)


class TestCliFeatures(unittest.TestCase):
    def test_render_to_stdout(self):
        self.assertEqual(main(["render", SPEC]), 0)

    def test_render_to_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(main(["render", SPEC, "--out-dir", tmp]), 0)
            self.assertTrue(os.path.isfile(os.path.join(tmp, "cp-1.sh")))

    def test_estimate(self):
        self.assertEqual(main(["estimate", SPEC, "--mbps", "50"]), 0)

    def test_estimate_json(self):
        self.assertEqual(main(["estimate", SPEC, "--format", "json"]), 0)


if __name__ == "__main__":
    unittest.main()
