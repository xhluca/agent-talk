"""The Codex installer writes the hooks and the codex-with-daemon launcher.

`install-hooks.py` appends the marked hook block to `$CODEX_HOME/config.toml`
and copies the `codex-with-daemon` launcher to `~/.local/bin`. The launcher
starts Codex's app-server daemon and then execs `codex --remote unix://` so
the session attaches to it; when the daemon cannot start it must say so and
run plain Codex anyway, because losing idle wake must never cost a working
session.

Asserts:
  1. A fresh install writes the hook block and an executable launcher, and
     reports the launcher path.
  2. Re-running changes neither file and says both are already installed.
  3. --check exits 1 and reports the missing pieces before the install, exits
     0 and reports both installed after, and never writes anything.
  4. The installer warns when the launcher directory is not on PATH, and only
     then.
  5. The launcher warns on stderr and still execs plain codex, arguments
     intact and no --remote, when the daemon fails to start.
  6. The launcher attaches with --remote unix:// and adds no output of its
     own when the daemon starts cleanly.
  7. With no codex on PATH the launcher warns and exits 127.
  8. A daemon that was already running gets a stderr note exactly when
     AGENT_TALK_CODEX_SPOOLS is set, because the daemon keeps the environment
     it started with; the session still attaches.
"""

import os
import stat
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INSTALLER = os.path.join(ROOT, "extensions", "codex", "install-hooks.py")
LAUNCHER_SRC = os.path.join(ROOT, "extensions", "codex", "codex-with-daemon")
MARKER = "# >>> agent-talk inbox hooks >>>"


def read(path):
    with open(path) as fh:
        return fh.read()


class TestInstaller(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.home = self.tmp.name
        self.config = os.path.join(self.home, ".codex", "config.toml")
        self.dest = os.path.join(self.home, ".local", "bin",
                                 "codex-with-daemon")

    def run_installer(self, *args, path="/usr/bin:/bin"):
        env = dict(os.environ, HOME=self.home, PATH=path,
                   CODEX_HOME=os.path.join(self.home, ".codex"))
        return subprocess.run([sys.executable, INSTALLER, *args],
                              capture_output=True, text=True, env=env)

    def test_fresh_install_writes_hooks_and_launcher(self):
        res = self.run_installer()
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertIn(MARKER, read(self.config))
        self.assertEqual(read(self.dest), read(LAUNCHER_SRC))
        self.assertTrue(os.stat(self.dest).st_mode & stat.S_IXUSR,
                        "the installed launcher must be executable")
        self.assertIn(self.dest, res.stdout,
                      "the installer must say where it put the launcher")
        print("PASS 1: fresh install writes the hooks and an executable "
              "launcher, and says where")

    def test_rerun_is_idempotent(self):
        self.run_installer()
        before = (read(self.config), read(self.dest))
        res = self.run_installer()
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertEqual((read(self.config), read(self.dest)), before,
                         "a second run must not change either file")
        self.assertIn("hooks already installed", res.stdout)
        self.assertIn("launcher already installed", res.stdout)
        print("PASS 2: re-running changes nothing and says so")

    def test_check_reports_and_never_writes(self):
        res = self.run_installer("--check")
        self.assertEqual(res.returncode, 1)
        self.assertIn("hooks not installed", res.stdout)
        self.assertIn("launcher missing", res.stdout)
        self.assertFalse(os.path.exists(self.config),
                         "--check must not create the config")
        self.assertFalse(os.path.exists(self.dest),
                         "--check must not install the launcher")

        self.run_installer()
        res = self.run_installer("--check")
        self.assertEqual(res.returncode, 0, res.stdout)
        self.assertIn("hooks installed", res.stdout)
        self.assertIn("launcher installed", res.stdout)
        print("PASS 3: --check reports accurately before and after, "
              "writing nothing")

    def test_path_warning_only_when_bin_dir_missing_from_path(self):
        res = self.run_installer()
        self.assertIn("not on your PATH", res.stdout)
        bindir = os.path.dirname(self.dest)
        res = self.run_installer(path="/usr/bin:/bin:" + bindir)
        self.assertNotIn("not on your PATH", res.stdout)
        print("PASS 4: the PATH warning appears exactly when the bin dir "
              "is not on PATH")


class TestLauncher(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.bin = os.path.join(self.tmp.name, "bin")
        os.makedirs(self.bin)

    def stub_codex(self, daemon_status):
        """A fake codex: `codex app-server ...` prints the daemon status JSON
        (or an error), anything else echoes its arguments so the test can see
        the exec happened. The real `daemon start` exits 0 either way it
        succeeds, so the launcher must read the status, not the exit code."""
        path = os.path.join(self.bin, "codex")
        with open(path, "w") as fh:
            fh.write('#!/bin/sh\n'
                     'if [ "$1" = "app-server" ]; then echo \'%s\'; exit 0; fi\n'
                     'echo "codex-ran $@"\n' % daemon_status)
        os.chmod(path, 0o755)

    def run_launcher(self, *args, spools=None):
        env = dict(os.environ, PATH=self.bin)
        env.pop("AGENT_TALK_CODEX_SPOOLS", None)
        if spools is not None:
            env["AGENT_TALK_CODEX_SPOOLS"] = spools
        return subprocess.run(["/bin/sh", LAUNCHER_SRC, *args],
                              capture_output=True, text=True, env=env)

    def test_daemon_failure_warns_and_still_runs_codex(self):
        self.stub_codex('{"error":"no standalone install"}')
        res = self.run_launcher("resume", "--last")
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertIn("codex-ran resume --last", res.stdout,
                      "codex must still run, arguments intact")
        self.assertNotIn("--remote", res.stdout,
                         "with no daemon there is nothing to attach to")
        err = res.stderr.splitlines()
        self.assertEqual(len(err), 2, res.stderr)
        self.assertIn("daemon", err[0])
        self.assertIn("idle-session wake is off", err[0])
        self.assertIn("next prompt", err[1])
        print("PASS 5: a failed daemon start warns twice on stderr and "
              "still runs plain codex")

    def test_daemon_success_attaches_quietly(self):
        self.stub_codex('{"status":"started","backend":"pid"}')
        res = self.run_launcher("--version")
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertIn("codex-ran --remote unix:// --version", res.stdout,
                      "the session must attach to the daemon it started")
        self.assertEqual(res.stderr, "")
        print("PASS 6: a clean daemon start attaches with --remote and "
              "adds no output of its own")

    def test_missing_codex_warns_and_exits_127(self):
        res = self.run_launcher()
        self.assertEqual(res.returncode, 127)
        self.assertIn("daemon", res.stderr)
        self.assertIn("next prompt", res.stderr)
        print("PASS 7: with no codex on PATH the launcher warns and "
              "exits 127")

    def test_already_running_notes_stale_environment(self):
        self.stub_codex('{"status":"alreadyRunning","backend":"pid"}')
        res = self.run_launcher("--version", spools="/tmp/spool.ndjson")
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertIn("codex-ran --remote unix:// --version", res.stdout)
        self.assertIn("environment it started with", res.stderr,
                      "a running daemon cannot pick up a new spool list")

        res = self.run_launcher("--version")
        self.assertEqual(res.stderr, "",
                         "without spools set there is nothing to note")
        self.assertIn("codex-ran --remote unix:// --version", res.stdout)
        print("PASS 8: an already-running daemon is noted exactly when "
              "AGENT_TALK_CODEX_SPOOLS is set")


if __name__ == "__main__":
    unittest.main()
