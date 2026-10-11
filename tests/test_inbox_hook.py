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

import concurrent.futures
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

if os.name != "nt":
    import fcntl
else:
    import msvcrt

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HOOK = os.path.join(ROOT, "extensions", "codex", "inbox-hook.py")


def load_hook():
    spec = importlib.util.spec_from_file_location("inbox_hook", HOOK)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


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
            capture_output=True, text=True, timeout=2,
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

    def test_shared_cursor_contention_defers_without_blocking(self):
        self.write_spool(record_line("m1", "waiting for the cursor lock"))
        lock_path = os.path.join(os.path.dirname(self.spool),
                                 ".codex-hook-state.json.lock")
        with open(lock_path, "ab") as lock:
            if os.name == "nt":
                msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                fcntl.flock(lock, fcntl.LOCK_EX)
            try:
                # A hook must finish while the other process still holds the
                # lock, without committing a cursor or reporting delivery.
                self.assertEqual(self.run_hook(), [])
                self.assertFalse(os.path.exists(os.path.join(
                    os.path.dirname(self.spool), ".codex-hook-state.json")))
            finally:
                if os.name == "nt":
                    lock.seek(0)
                    msvcrt.locking(lock.fileno(), msvcrt.LK_UNLCK, 1)
                else:
                    fcntl.flock(lock, fcntl.LOCK_UN)
        self.assertIn("waiting for the cursor lock", "".join(self.run_hook()))
        self.assertEqual(self.run_hook(), [])

    def test_parallel_hooks_deliver_each_spool_once(self):
        # All spools share one cursor file. Concurrent hooks must preserve
        # other sessions' entries as well as deduplicating their own spool.
        spools = []
        for i in range(8):
            spool = os.path.join(os.path.dirname(self.spool), f"s{i}.ndjson")
            with open(spool, "w") as fh:
                fh.write(record_line(f"m{i}", f"question {i}"))
            spools.append(spool)

        def run(spool):
            return subprocess.run(
                [sys.executable, HOOK, "stop"], input="{}",
                capture_output=True, text=True, timeout=10,
                env=dict(os.environ, AGENT_TALK_CODEX_SPOOLS=spool))

        with concurrent.futures.ThreadPoolExecutor(max_workers=16) as pool:
            results = list(pool.map(run, spools * 2))
        for result in results:
            self.assertEqual(result.returncode, 0, result.stderr)
        output = "".join(result.stdout for result in results)
        # Contended hooks defer to a later lifecycle event. Drain every spool
        # once more after concurrent hooks finish to collect deferred records.
        output += "".join(run(spool).stdout for spool in spools)
        for i, spool in enumerate(spools):
            self.assertEqual(output.count(f"question {i}"), 1)
            self.assertEqual(run(spool).stdout, "",
                             "another session overwrote this spool's cursor")

    def test_windows_spool_paths_keep_drive_letters(self):
        hook = load_hook()
        paths = [r"C:\Users\example\sessions\one.ndjson",
                 r"D:\Work\sessions\two.ndjson"]
        with patch.object(hook.os, "pathsep", ";"), patch.dict(
                os.environ, AGENT_TALK_CODEX_SPOOLS=" ; ".join(paths)):
            self.assertEqual(hook.spools(), paths)

    def test_posix_spool_paths_keep_colon_separator(self):
        hook = load_hook()
        with patch.object(hook.os, "pathsep", ":"), patch.dict(
                os.environ, AGENT_TALK_CODEX_SPOOLS=" /one.ndjson : /two.ndjson : "):
            self.assertEqual(hook.spools(), ["/one.ndjson", "/two.ndjson"])

    def assert_persistence_failure_defers(self, failure):
        hook = load_hook()
        self.write_spool(record_line("m1", "already delivered"))
        self.assertEqual(len(hook.drain(self.spool)), 1)
        with open(hook.state_path(self.spool), "rb") as fh:
            prior_state = fh.read()
        with open(self.spool, "a") as fh:
            fh.write(record_line("m2", "pending until persisted"))
        real_open = open

        def fail_temp_open(path, mode="r", *args, **kwargs):
            if str(path).endswith(".tmp") and mode == "w":
                raise OSError("synthetic cursor write failure")
            return real_open(path, mode, *args, **kwargs)

        failing_operation = (patch.object(hook.os, "replace", side_effect=OSError(
            "synthetic cursor replace failure")) if failure == "replace" else
            patch("builtins.open", side_effect=fail_temp_open))
        with failing_operation:
            self.assertEqual(hook.drain(self.spool), [])
            self.assertEqual(hook.drain(self.spool), [])
            with open(hook.state_path(self.spool), "rb") as fh:
                self.assertEqual(fh.read(), prior_state)
        self.assertEqual(hook.drain(self.spool),
                         [{"name": "alice", "text": "pending until persisted"}])
        self.assertEqual(hook.drain(self.spool), [])

    def test_cursor_replace_failure_defers_delivery(self):
        self.assert_persistence_failure_defers("replace")

    def test_cursor_write_failure_defers_delivery(self):
        self.assert_persistence_failure_defers("write")

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
        original_size = os.path.getsize(self.spool)  # includes native CRLF translation
        self.run_hook()

        # Refill to exactly the old byte length with a different message, as a
        # follower restart between two hook runs can. Same size, new content.
        pad = len(first) - len(record_line("bbbb2222", "question two"))
        second = record_line("bbbb2222", "question two" + " " * pad)
        self.write_spool(second)
        self.assertEqual(os.path.getsize(self.spool), original_size,
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
