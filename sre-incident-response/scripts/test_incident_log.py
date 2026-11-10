#!/usr/bin/env python3
"""Smoke test for incident_log.py: open, add, sort, check, durations, save, list.

Run: python3 -m unittest discover -s sre-incident-response/scripts -p 'test_*.py'
"""
import glob
import os
import subprocess
import sys
import tempfile
import unittest

SCRIPT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "incident_log.py")


class IncidentLogTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = self.tmp.name
        self.run_ok("open", self.dir, "db-down", "--title", "DB down")
        self.log = glob.glob(os.path.join(self.dir, "*", "*.md"))[0]

    def run_cmd(self, *args, stdin=None):
        env = dict(os.environ, INCIDENT_LOG_NOW="2026-10-07T10:15:00")
        return subprocess.run([sys.executable, SCRIPT, *args], input=stdin, env=env,
                              capture_output=True, text=True)

    def run_ok(self, *args, stdin=None):
        r = self.run_cmd(*args, stdin=stdin)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        return r.stdout

    def timeline(self):
        with open(self.log) as f:
            return [line for line in f if line.startswith("- 20")]

    def test_open_names_by_clock_and_never_overwrites(self):
        self.assertTrue(self.log.endswith("2026-10-07-1015-db-down.md"))
        self.assertIn("id=2026-10-07-1015-db-down-2", self.run_ok("open", self.dir, "db-down"))
        self.assertEqual(self.run_cmd("open", self.dir, "Bad Slug").returncode, 2)

    def test_add_inserts_in_event_time_order(self):
        self.run_ok("add", self.log, "alerted", "monitor", "p99 high", "--at", "10:05")
        self.run_ok("add", self.log, "impact-start", "human", "errors", "--at", "10:00")
        self.run_ok("add", self.log, "engaged", "human", "on it")
        tags = [line.split("[")[1].split("]")[0] for line in self.timeline()]
        self.assertEqual(tags, ["impact-start", "alerted", "engaged"])
        self.assertIn("logged 10:15:00Z", self.timeline()[0])  # a late entry shows it
        out = self.run_ok("durations", self.log)
        self.assertIn("detect    5 min", out)
        self.assertIn("resolve   not recorded", out)
        self.assertIn("3 timeline entries", self.run_ok("check", self.log))

    def test_add_rejects_bad_input(self):
        self.assertEqual(self.run_cmd("add", self.log, "bogus", "human", "x").returncode, 2)
        backdated = self.run_cmd("add", self.log, "note", "observed", "x", "--at", "10:00")
        self.assertEqual(backdated.returncode, 2)
        self.assertEqual(self.timeline(), [])

    def test_check_warns_on_disorder_and_sort_repairs_it(self):
        self.run_ok("add", self.log, "impact-start", "human", "errors", "--at", "10:00")
        self.run_ok("add", self.log, "alerted", "monitor", "p99 high", "--at", "10:05")
        with open(self.log) as f:
            lines = f.readlines()
        i = lines.index(self.timeline()[0])
        lines[i], lines[i + 1] = lines[i + 1], lines[i]
        with open(self.log, "w") as f:
            f.writelines(lines)
        self.assertIn("run: sort", self.run_ok("check", self.log))  # a warning, not an error
        self.run_ok("sort", self.log)
        self.assertNotIn("run: sort", self.run_ok("check", self.log))
        self.assertIn("[impact-start]", self.timeline()[0])

    def test_save_and_list(self):
        self.assertIn("link=k8s-triage.md", self.run_ok("save", self.log, "k8s-triage", stdin="body\n"))
        self.assertIn("link=k8s-triage-2.md", self.run_ok("save", self.log, "k8s-triage", stdin="again\n"))
        self.assertIn("open", self.run_ok("list", self.dir, "--active"))


if __name__ == "__main__":
    unittest.main()
