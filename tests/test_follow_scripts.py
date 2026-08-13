"""bin/follow.sh and bin/invite-watch.sh: the supervisor scripts the skills call.

These cover everything that does not need retalk installed — argument handling,
the pid-file protocol, and idempotence — so they run in CI. The message path
itself (retalk -> spool) is covered by the opt-in test_roundtrip.py.
"""
import os
import pathlib
import subprocess
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FOLLOW = os.path.join(ROOT, "bin", "follow.sh")
WATCH = os.path.join(ROOT, "bin", "invite-watch.sh")


def run(*args):
    return subprocess.run(args, capture_output=True, text=True, timeout=30)


class TestFollowScript(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.user = self._tmp.name

    def tearDown(self):
        self._tmp.cleanup()

    def test_usage_on_a_bad_action(self):
        for cmd in ([FOLLOW], [FOLLOW, "wat", self.user], [WATCH]):
            r = run(*cmd)
            self.assertEqual(r.returncode, 2, f"{cmd}: expected usage exit 2")
            self.assertIn("follow.sh" if cmd[0] == FOLLOW else "invite-watch.sh",
                          r.stderr)

    def test_start_needs_a_peer(self):
        r = run(FOLLOW, "start", self.user)
        self.assertEqual(r.returncode, 2)
        self.assertIn("peer", r.stderr)

    def test_status_reports_nothing_running(self):
        r = run(FOLLOW, "status", self.user)
        self.assertEqual(r.returncode, 0)
        self.assertIn("not following", r.stdout)
        r = run(WATCH, "status", self.user)
        self.assertEqual(r.returncode, 0)
        self.assertIn("not watching", r.stdout)

    def test_start_is_idempotent_against_a_live_pid(self):
        # A live pid file means another session already started it; starting
        # again must not spawn a second follower for the same peers.
        pathlib.Path(self.user, "follow.bob.pid").write_text(f"{os.getpid()}\n")
        r = run(FOLLOW, "start", self.user, "bob")
        self.assertEqual(r.returncode, 0)
        self.assertIn("already following bob", r.stdout)
        self.assertEqual(pathlib.Path(self.user, "follow.bob.pid").read_text(),
                         f"{os.getpid()}\n")

        pathlib.Path(self.user, "invite-watch.pid").write_text(f"{os.getpid()}\n")
        r = run(WATCH, "start", self.user)
        self.assertEqual(r.returncode, 0)
        self.assertIn("already watching", r.stdout)

    def test_stop_clears_stale_pid_files(self):
        # pid 2**22 is beyond any live pid here; the file is stale and goes.
        stale = pathlib.Path(self.user, "follow.bob+carol.pid")
        stale.write_text("4194304\n")
        r = run(FOLLOW, "stop", self.user)
        self.assertEqual(r.returncode, 0)
        self.assertIn("stopped", r.stdout)
        self.assertFalse(stale.exists())

        stale = pathlib.Path(self.user, "invite-watch.pid")
        stale.write_text("4194304\n")
        r = run(WATCH, "stop", self.user)
        self.assertEqual(r.returncode, 0)
        self.assertFalse(stale.exists())

    def test_status_shows_a_live_follower_and_its_peers(self):
        pathlib.Path(self.user, "follow.bob+carol.pid").write_text(f"{os.getpid()}\n")
        r = run(FOLLOW, "status", self.user)
        self.assertIn("following: bob+carol", r.stdout)

    def test_passphrase_is_named_never_read(self):
        # The scripts must hand retalk a path. If one of them ever grew a
        # `$(cat <passphrase>)` the secret would be back in a command line.
        for p in (FOLLOW, WATCH):
            text = pathlib.Path(p).read_text()
            self.assertIn("--passphrase-path", text)
            self.assertNotIn("$(cat \"$pp\")", text)
            self.assertNotIn("RETALK_PASSPHRASE=", text)


if __name__ == "__main__":
    unittest.main()
