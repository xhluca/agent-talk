"""The contact-request monitor pushes registrations, and only registrations.

A peer who presents a valid invite code becomes a saved contact, and the
session should hear about it without being asked. That travels on its own
spool (`<user>/sessions/<session-id>.requests.ndjson`) and its own monitor, so
a registration is never rendered as a chat message.

Asserts:
  1. Nothing pending means nothing pushed, and the monitor keeps waiting.
  2. An acceptance that lands in the request spool is pushed into the session.
  3. Message-spool lines are not pushed by this monitor (the inbox monitor
     owns those).
  4. The same record written twice is pushed once, even though the writer
     stamps each copy with its own arrival time, while a genuinely different
     record still gets through.
  5. Without a session id the monitor idles instead of exiting.

The records are the shapes `retalk invite watch` emits. They carry no message
id, which is why the monitor keys its dedupe on the line with `ts` removed
rather than on an id.
"""
import os
import pathlib
import select
import subprocess
import tempfile
import time
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MON = os.path.join(ROOT, "bin", "requests-monitor.sh")

ACCEPTED = ('{"kind":"contact_accepted","code":"wS7nQx2FbK1pR4tZ0aH9Yg",'
            '"from":"0f9a3d2c8b7e65410f9a3d2c8b7e6541",'
            '"name":"sam-claude-webapp","ts":"2026-01-01T00:00:00Z"}')
ACCEPTED_LATER = ACCEPTED.replace("2026-01-01T00:00:00Z", "2026-01-01T00:05:00Z")
REJECTED = ('{"kind":"contact_request_rejected",'
            '"from":"0f9a3d2c8b7e65410f9a3d2c8b7e6541","reason":"consumed",'
            '"ts":"2026-01-01T00:06:00Z"}')


class TestRequestsMonitor(unittest.TestCase):
    def start(self, sid):
        """Run the monitor against a fresh HOME with the session map written."""
        home = tempfile.mkdtemp()
        udir = os.path.join(home, "proj", ".agent-talk", "users", "alice")
        os.makedirs(os.path.join(udir, "sessions"))
        os.makedirs(os.path.join(home, ".agent-talk", "by-session"))
        mon = subprocess.Popen(["bash", MON, sid],
                               env=dict(os.environ, HOME=home),
                               stdout=subprocess.PIPE,
                               stderr=subprocess.DEVNULL, text=True)
        self.addCleanup(self.stop, mon)
        time.sleep(1)                                   # monitor waits for map
        pathlib.Path(home, ".agent-talk", "by-session", sid).write_text(udir + "\n")
        time.sleep(3)                                   # map read, tail attached
        return mon, udir

    @staticmethod
    def stop(mon):
        mon.terminate()
        mon.wait(timeout=5)
        mon.stdout.close()

    @staticmethod
    def read_lines(mon, seconds):
        """Every line the monitor emitted within the window."""
        lines = []
        deadline = time.time() + seconds
        while time.time() < deadline:
            if select.select([mon.stdout], [], [], 1)[0]:
                lines.append(mon.stdout.readline().strip())
        return lines

    def test_stays_quiet_until_a_request_arrives(self):
        mon, udir = self.start("s.req.1")
        self.assertEqual(self.read_lines(mon, 2), [],
                         "no pending request should mean no push")
        self.assertIsNone(mon.poll(), "monitor should keep waiting, not exit")
        print("PASS 1: nothing pending, nothing pushed, monitor still waiting")

        pathlib.Path(udir, "sessions", "s.req.1.requests.ndjson").write_text(
            ACCEPTED + "\n")
        self.assertEqual(self.read_lines(mon, 5), [ACCEPTED])
        print("PASS 2: an arriving registration is pushed into the session")

    def test_ignores_the_message_spool(self):
        mon, udir = self.start("s.req.2")
        pathlib.Path(udir, "sessions", "s.req.2.ndjson").write_text(
            '{"id":"m1","from":"ff","name":"bob","text":"hello"}\n')
        pathlib.Path(udir, "inbox.ndjson").write_text(
            '{"id":"m2","from":"ff","name":"bob","text":"also hello"}\n')
        self.assertEqual(self.read_lines(mon, 4), [],
                         "chat messages belong to the inbox monitor")
        print("PASS 3: the request monitor leaves message spools alone")

    def test_repeat_collapses_but_a_different_record_gets_through(self):
        mon, udir = self.start("s.req.3")
        spool = pathlib.Path(udir, "sessions", "s.req.3.requests.ndjson")
        spool.write_text(ACCEPTED + "\n")
        time.sleep(1)
        with spool.open("a") as fh:
            fh.write(ACCEPTED_LATER + "\n")   # same event, second watcher pass
            fh.write(REJECTED + "\n")         # a different event entirely
        self.assertEqual(self.read_lines(mon, 5), [ACCEPTED, REJECTED])
        print("PASS 4: a re-seen record collapses, a new one still surfaces")

    def test_idles_without_session_id(self):
        home = tempfile.mkdtemp()
        mon = subprocess.Popen(["bash", MON, "${CLAUDE_SESSION_ID}"],
                               env=dict(os.environ, HOME=home),
                               stdout=subprocess.PIPE,
                               stderr=subprocess.DEVNULL, text=True)
        self.addCleanup(self.stop, mon)
        time.sleep(1)
        self.assertFalse(select.select([mon.stdout], [], [], 1)[0],
                         "monitor should emit nothing without a session id")
        self.assertIsNone(mon.poll(), "monitor should keep idling, not exit")
        print("PASS 5: no session id means it idles rather than exiting")


if __name__ == "__main__":
    unittest.main()
