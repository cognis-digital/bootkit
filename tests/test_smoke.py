"""Smoke tests for bootkit. Standard library only."""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bootkit import TOOL_NAME, TOOL_VERSION, load_spec, plan_bootstrap, preflight
from bootkit.cli import main

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SPEC = os.path.join(REPO_ROOT, "demos", "01-basic", "bootstrap.yaml")
BASE = os.path.dirname(SPEC)


class TestMetadata(unittest.TestCase):
    def test_metadata(self):
        self.assertEqual(TOOL_NAME, "bootkit")
        self.assertTrue(TOOL_VERSION)


class TestPlan(unittest.TestCase):
    def test_plan_phases(self):
        steps = plan_bootstrap(load_spec(SPEC))
        phases = [s["phase"] for s in steps]
        self.assertIn("init-server", phases)
        self.assertEqual(phases.count("init-server"), 1)
        self.assertEqual(phases.count("join-server"), 2)
        self.assertEqual(phases.count("join-agent"), 2)
        self.assertIn("seed-registry", phases)
        self.assertIn("apply", phases)

    def test_preflight_ok(self):
        res = preflight(load_spec(SPEC), base_dir=BASE)
        self.assertTrue(res["ok"], res["problems"])
        self.assertEqual(res["servers"], 3)
        self.assertEqual(res["agents"], 2)


class TestCli(unittest.TestCase):
    def test_plan(self):
        self.assertEqual(main(["plan", SPEC]), 0)

    def test_preflight(self):
        self.assertEqual(main(["preflight", SPEC]), 0)

    def test_manifest(self):
        self.assertEqual(main(["manifest", SPEC]), 0)

    def test_no_command_exits_2(self):
        self.assertEqual(main([]), 2)


if __name__ == "__main__":
    unittest.main()
