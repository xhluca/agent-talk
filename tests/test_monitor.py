"""The inbox monitor resolves this session's user from the session->user map
and pushes new spool lines (no retalk needed)."""
import os, pathlib, select, subprocess, tempfile, time, unittest
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MON = os.path.join(ROOT, "bin", "inbox-monitor.sh")


class TestMonitor(unittest.TestCase):
    def test_resolves_user_from_map_and_pushes(self):
        home = tempfile.mkdtemp()
        sid = "s.test.1"
        udir = os.path.join(home, "proj", ".agent-talk", "users", "alice")  # local-scope abs dir
        os.makedirs(udir)
        os.makedirs(os.path.join(home, ".agent-talk", "by-session"))
        mon = subprocess.Popen(["bash", MON, sid], env=dict(os.environ, HOME=home),
                               stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
        try:
            time.sleep(1)  # monitor waits for the map
            pathlib.Path(home, ".agent-talk", "by-session", sid).write_text(udir + "\n")
            time.sleep(3)  # monitor reads map + attaches tail
            pathlib.Path(udir, "inbox.ndjson").write_text('{"text":"hi"}\n')
            line = ""
            if select.select([mon.stdout], [], [], 5)[0]:
                line = mon.stdout.readline().strip()
            self.assertEqual(line, '{"text":"hi"}')
        finally:
            mon.terminate(); mon.wait(timeout=5)

    def test_pushes_from_this_session_spool(self):
        home = tempfile.mkdtemp()
        sid = "s.test.2"
        udir = os.path.join(home, "proj", ".agent-talk", "users", "alice")
        os.makedirs(os.path.join(udir, "sessions"))
        os.makedirs(os.path.join(home, ".agent-talk", "by-session"))
        mon = subprocess.Popen(["bash", MON, sid], env=dict(os.environ, HOME=home),
                               stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
        try:
            time.sleep(1)
            pathlib.Path(home, ".agent-talk", "by-session", sid).write_text(udir + "\n")
            time.sleep(3)
            pathlib.Path(udir, "sessions", sid + ".ndjson").write_text(
                '{"id":"m1","text":"session scoped"}\n')
            line = ""
            if select.select([mon.stdout], [], [], 5)[0]:
                line = mon.stdout.readline().strip()
            self.assertEqual(line, '{"id":"m1","text":"session scoped"}')
        finally:
            mon.terminate(); mon.wait(timeout=5)

    def test_emits_a_record_once_when_it_lands_in_both_spools(self):
        # The writer keeps the legacy spool during the transition, so the same
        # record can appear twice. The session must see it once.
        home = tempfile.mkdtemp()
        sid = "s.test.3"
        udir = os.path.join(home, "proj", ".agent-talk", "users", "alice")
        os.makedirs(os.path.join(udir, "sessions"))
        os.makedirs(os.path.join(home, ".agent-talk", "by-session"))
        mon = subprocess.Popen(["bash", MON, sid], env=dict(os.environ, HOME=home),
                               stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
        try:
            time.sleep(1)
            pathlib.Path(home, ".agent-talk", "by-session", sid).write_text(udir + "\n")
            time.sleep(3)
            record = '{"id":"dup1","text":"only once"}\n'
            pathlib.Path(udir, "sessions", sid + ".ndjson").write_text(record)
            time.sleep(1)
            with open(os.path.join(udir, "inbox.ndjson"), "a") as fh:
                fh.write(record)
            lines = []
            deadline = time.time() + 5
            while time.time() < deadline:
                if select.select([mon.stdout], [], [], 1)[0]:
                    lines.append(mon.stdout.readline().strip())
                    continue
                if lines:
                    break
            self.assertEqual(lines, ['{"id":"dup1","text":"only once"}'])
        finally:
            mon.terminate(); mon.wait(timeout=5)

    def test_idles_without_session_id(self):
        home = tempfile.mkdtemp()
        mon = subprocess.Popen(["bash", MON, "${CLAUDE_SESSION_ID}"],
                               env=dict(os.environ, HOME=home),
                               stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
        try:
            time.sleep(1)
            self.assertFalse(select.select([mon.stdout], [], [], 1)[0],
                             "monitor should emit nothing without a session id")
            self.assertIsNone(mon.poll(), "monitor should keep idling, not exit")
        finally:
            mon.terminate(); mon.wait(timeout=5)


if __name__ == "__main__":
    unittest.main()
