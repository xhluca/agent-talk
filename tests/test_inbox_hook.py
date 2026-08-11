"""The Codex inbox hook must not lose messages when a spool is rewritten.

The hook tracks its place in each spool as a byte offset. A follower restart
can truncate a spool and refill it to exactly its old length between two hook
runs; the size alone then looks unchanged, and a cursor validated only by size
silently drops the new message. The cursor therefore also stores a fingerprint
of the spool's first bytes and starts over when the fingerprint stops matching.

Asserts:
  1. An appended message is delivered once and not repeated on the next run.
  2. A spool truncated and refilled to the SAME byte length with a different
     message still delivers that message (the regression).
  3. When the cursor starts over after a truncation, ids already delivered are
     not delivered again.
"""

import json
import os
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HOOK = os.path.join(ROOT, "extensions", "codex", "inbox-hook.py")


def record_line(mid, text):
    return json.dumps({"id": mid, "from": "ff", "name": "alice",
                       "text": text}) + "\n"


class TestInboxHookCursor(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        sessions = os.path.join(self.tmp.name, "user", "sessions")
        os.makedirs(sessions)
        self.spool = os.path.join(sessions, "demo.ndjson")

    def run_hook(self):
        """Run the stop hook once; return the delivered texts (may be [])."""
        res = subprocess.run(
            [sys.executable, HOOK, "stop"], input="{}",
            capture_output=True, text=True,
            env=dict(os.environ, AGENT_TALK_CODEX_SPOOLS=self.spool))
        self.assertEqual(res.returncode, 0, res.stderr)
        if not res.stdout.strip():
            return []
        out = json.loads(res.stdout)
        self.assertEqual(out.get("decision"), "block")
        return [out["reason"]]

    def write_spool(self, content):
        with open(self.spool, "w") as fh:
            fh.write(content)

    def test_append_delivers_once(self):
        self.write_spool(record_line("m1", "first question"))
        self.assertIn("first question", "".join(self.run_hook()))
        self.assertEqual(self.run_hook(), [], "an unchanged spool redelivered")
        with open(self.spool, "a") as fh:
            fh.write(record_line("m2", "second question"))
        delivered = "".join(self.run_hook())
        self.assertIn("second question", delivered)
        self.assertNotIn("first question", delivered)
        print("PASS 1: appends deliver once and only the new lines")

    def test_truncate_and_regrow_to_same_size(self):
        first = record_line("aaaa1111", "question one")
        self.write_spool(first)
        self.run_hook()

        # Refill to exactly the old byte length with a different message, as a
        # follower restart between two hook runs can. Same size, new content.
        pad = len(first) - len(record_line("bbbb2222", "question two"))
        second = record_line("bbbb2222", "question two" + " " * pad)
        self.write_spool(second)
        self.assertEqual(os.path.getsize(self.spool), len(first),
                         "the test must regrow the spool to the same size")

        delivered = "".join(self.run_hook())
        self.assertIn("question two", delivered,
                      "a truncated-and-refilled spool of unchanged size "
                      "must still deliver its new message")
        print("PASS 2: truncate-and-regrow to the same size still delivers")

    def test_reset_does_not_redeliver_seen_ids(self):
        old = record_line("m1", "already answered")
        self.write_spool(old)
        self.run_hook()

        # Rewritten spool: a new message first, then the old one again. The
        # fingerprint no longer matches, so the cursor starts from the top and
        # must lean on the delivered-id list to skip the old message.
        self.write_spool(record_line("m2", "the new question") + old)
        delivered = "".join(self.run_hook())
        self.assertIn("the new question", delivered)
        self.assertNotIn("already answered", delivered)
        self.assertEqual(self.run_hook(), [], "nothing further should arrive")
        print("PASS 3: a cursor reset does not redeliver already-seen ids")


if __name__ == "__main__":
    unittest.main()
