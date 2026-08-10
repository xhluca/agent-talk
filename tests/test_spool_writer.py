"""The spool writer fans one follower's output out to per-session spools.

Asserts:
  1. A record is copied to every session registered to this user, and to no
     session registered to a different user.
  2. Each record gains an arrival timestamp, which retalk does not provide.
  3. Legacy `<user>/inbox.ndjson` keeps being written by default, and stops
     with --no-legacy.
  4. --gc removes the spool of a session that is gone and keeps a live one.
  5. Spools are created 0600, since they hold decrypted message text.
"""

import json
import os
import pathlib
import subprocess
import sys
import tempfile
import time
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WRITER = os.path.join(ROOT, "bin", "spool-writer.py")


class TestSpoolWriter(unittest.TestCase):
    def setUp(self):
        self.home = tempfile.mkdtemp()
        self.user = os.path.join(self.home, "proj", ".agent-talk", "users", "alice")
        self.other = os.path.join(self.home, "proj", ".agent-talk", "users", "bob")
        os.makedirs(self.user)
        os.makedirs(self.other)
        self.registry = os.path.join(self.home, ".agent-talk", "by-session")
        os.makedirs(self.registry)

    def register(self, sid, user_dir):
        pathlib.Path(self.registry, sid).write_text(user_dir + "\n")

    def run_writer(self, lines, *extra):
        res = subprocess.run([sys.executable, WRITER, "--user", self.user, *extra],
                             input="".join(l + "\n" for l in lines),
                             capture_output=True, text=True,
                             env=dict(os.environ, HOME=self.home))
        self.assertEqual(res.returncode, 0, res.stderr)
        return res

    def spool(self, sid, user_dir=None):
        return os.path.join(user_dir or self.user, "sessions", sid + ".ndjson")

    def read(self, path):
        with open(path) as fh:
            return [json.loads(l) for l in fh if l.strip()]

    def test_fans_out_to_registered_sessions_only(self):
        self.register("s-one", self.user)
        self.register("s-two", self.user)
        self.register("s-elsewhere", self.other)
        self.run_writer(['{"id":"m1","from":"ff","name":"bob","text":"hello"}'])

        for sid in ("s-one", "s-two"):
            got = self.read(self.spool(sid))
            self.assertEqual([r["text"] for r in got], ["hello"])
        self.assertFalse(os.path.exists(self.spool("s-elsewhere", self.other)),
                         "a session mapped to another user must not be written")
        print("PASS 1: each registered session gets its own copy")

        stamped = self.read(self.spool("s-one"))[0]
        self.assertIn("ts", stamped)
        self.assertRegex(stamped["ts"], r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
        print("PASS 2: records gain an arrival timestamp")

        mode = os.stat(self.spool("s-one")).st_mode & 0o777
        self.assertEqual(mode, 0o600, f"spool mode {oct(mode)} should be 0600")
        print("PASS 5: spools are created 0600")

    def test_legacy_spool_default_on_and_optional_off(self):
        self.register("s-one", self.user)
        legacy = os.path.join(self.user, "inbox.ndjson")
        self.run_writer(['{"id":"m1","text":"kept"}'])
        self.assertEqual([r["text"] for r in self.read(legacy)], ["kept"])

        os.remove(legacy)
        self.run_writer(['{"id":"m2","text":"skipped"}'], "--no-legacy")
        self.assertFalse(os.path.exists(legacy),
                         "--no-legacy must not recreate the old spool")
        self.assertEqual([r["text"] for r in self.read(self.spool("s-one"))],
                         ["kept", "skipped"])
        print("PASS 3: legacy spool written by default, suppressed on request")

    def test_gc_removes_dead_sessions_and_keeps_live_ones(self):
        self.register("s-live", self.user)
        self.register("s-dead", self.user)
        self.run_writer(['{"id":"m1","text":"hi"}'])
        self.assertTrue(os.path.exists(self.spool("s-dead")))

        os.remove(os.path.join(self.registry, "s-dead"))  # session ended
        res = subprocess.run([sys.executable, WRITER, "--user", self.user, "--gc"],
                             capture_output=True, text=True,
                             env=dict(os.environ, HOME=self.home))
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertFalse(os.path.exists(self.spool("s-dead")),
                         "an unregistered session's spool should be swept")
        self.assertTrue(os.path.exists(self.spool("s-live")),
                        "a registered session's spool must survive")
        print("PASS 4: --gc sweeps gone sessions, keeps live ones")

    def test_gc_sweeps_a_long_cold_registered_session(self):
        # Nothing removes registry entries, so age is the main staleness signal.
        self.register("s-cold", self.user)
        self.run_writer(['{"id":"m1","text":"old"}'])
        cold = self.spool("s-cold")
        ancient = time.time() - 40 * 86400
        os.utime(cold, (ancient, ancient))
        subprocess.run([sys.executable, WRITER, "--user", self.user, "--gc",
                        "--max-age-days", "14"],
                       capture_output=True, text=True,
                       env=dict(os.environ, HOME=self.home))
        self.assertFalse(os.path.exists(cold),
                         "a spool untouched past --max-age-days should be swept")
        print("PASS 4b: --gc sweeps long-cold spools even if still registered")


if __name__ == "__main__":
    unittest.main()
