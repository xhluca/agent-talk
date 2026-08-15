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


ACCEPTED = ('{"kind": "contact_accepted", "code": "abc", "from": "%s", '
            '"name": "carol", "card": {}}' % ("f" * 32))


class TestAcceptanceCoversTheNewPeer(unittest.TestCase):
    """A peer who registers with an invite code must end up in the delivery path.

    The watcher saved the contact but nothing followed it: `receive-from` was
    only written when it happened to be empty, and a running follower's peer
    list is fixed when it starts. So the first message from a brand-new peer,
    which is the whole point of an invite code, sat on the relay until someone
    ran `receive` naming them.
    """

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.user = self._tmp.name

    def tearDown(self):
        run(FOLLOW, "stop", self.user)
        self._tmp.cleanup()

    def accept(self, env=None):
        """Run the watcher's acceptance handler on one contact_accepted line."""
        script = (f'source "{WATCH}" status "{self.user}" >/dev/null 2>&1; '
                  f"cover_contact '{ACCEPTED}'")
        return subprocess.run(["bash", "-c", script], capture_output=True,
                              text=True, timeout=60,
                              env={**os.environ, **(env or {})})

    def write(self, name, value):
        pathlib.Path(self.user, name).write_text(value + "\n")

    def read(self, name):
        return pathlib.Path(self.user, name).read_text().strip()

    def test_receive_from_is_set_when_it_was_unset(self):
        self.write("check-mode", "manual")
        self.accept()
        self.assertEqual(self.read("receive-from"), "carol")

    def test_receive_from_widens_when_it_names_someone_else(self):
        # The regression: an inviter already talking to bob kept receive-from
        # at "bob", so carol's first message was never drained.
        self.write("check-mode", "manual")
        self.write("receive-from", "bob")
        self.accept()
        self.assertEqual(self.read("receive-from"), "*contacts*")

    def test_an_all_contacts_scope_is_left_alone(self):
        self.write("check-mode", "manual")
        self.write("receive-from", "*contacts*")
        self.accept()
        self.assertEqual(self.read("receive-from"), "*contacts*")

    def test_manual_mode_widens_the_scope_but_starts_no_follower(self):
        # Manual is a deliberate choice to read on demand; do not override it.
        self.write("check-mode", "manual")
        self.write("receive-from", "bob")
        self.accept()
        self.assertEqual(self.read("receive-from"), "*contacts*")
        self.assertEqual(list(pathlib.Path(self.user).glob("follow.*.pid")), [])

    def test_auto_mode_restarts_the_follower_covering_the_new_peer(self):
        stub = pathlib.Path(self.user, "stub")
        stub.mkdir()
        (stub / "retalk").write_text(
            '#!/usr/bin/env bash\n'
            'case "$*" in\n'
            '  *"contacts --json"*) echo \'{"name": "bob"}\'; echo \'{"name": "carol"}\' ;;\n'
            '  *) sleep 1 ;;\n'
            'esac\n')
        (stub / "retalk").chmod(0o755)

        self.write("check-mode", "auto")
        self.write("receive-from", "bob")
        r = self.accept(env={"PATH": f"{stub}:{os.environ['PATH']}"})
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.read("receive-from"), "*contacts*")
        pids = [p.name for p in pathlib.Path(self.user).glob("follow.*.pid")]
        self.assertTrue(any("carol" in p for p in pids),
                        f"no follower covers carol: {pids}")

    def test_a_restart_keeps_the_options_the_follower_had(self):
        # Losing --wake-codex here would silently stop an idle Codex session
        # from receiving, which is the feature the restart exists to serve.
        self.write("check-mode", "auto")
        self.write("receive-from", "bob")
        pathlib.Path(self.user, "follow.opts").write_text(
            "--interval\n5\n--wake-codex\n")
        stub = pathlib.Path(self.user, "stub")
        stub.mkdir()
        (stub / "retalk").write_text(
            '#!/usr/bin/env bash\n'
            'case "$*" in\n'
            '  *"contacts --json"*) echo \'{"name": "carol"}\' ;;\n'
            '  *) echo "$*" >> "$AT_TEST_LOG"; sleep 1 ;;\n'
            'esac\n')
        (stub / "retalk").chmod(0o755)
        self.accept(env={"PATH": f"{stub}:{os.environ['PATH']}"})

        opts = pathlib.Path(self.user, "follow.opts").read_text().split()
        self.assertIn("--wake-codex", opts)
        self.assertIn("5", opts)


if __name__ == "__main__":
    unittest.main()
