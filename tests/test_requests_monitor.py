"""The contact-request monitor pushes registrations, and only registrations.

A peer who presents a valid invite code becomes a saved contact, and the
session should hear about it without being asked. That travels on its own
spool (`<user>/sessions/<session-id>.requests.ndjson`) and its own monitor, so
a registration is never rendered as a chat message.

Asserts:
  1. Nothing pending means nothing pushed, and the monitor keeps waiting.
  2. A request that lands in the request spool is pushed into the session.
  3. Message-spool lines are not pushed by this monitor (the inbox monitor
     owns those).
  4. A request repeated under the same id is pushed once.
  5. Without a session id the monitor idles instead of exiting.
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

REQUEST = ('{"id":"req1","kind":"contact_request","from":"0f9a3d2c8b7e6541"'
           ',"name":"sam-claude-webapp"}')


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
            REQUEST + "\n")
        self.assertEqual(self.read_lines(mon, 5), [REQUEST])
        print("PASS 2: an arriving contact request is pushed into the session")

    def test_ignores_the_message_spool(self):
        mon, udir = self.start("s.req.2")
        pathlib.Path(udir, "sessions", "s.req.2.ndjson").write_text(
            '{"id":"m1","from":"ff","name":"bob","text":"hello"}\n')
        pathlib.Path(udir, "inbox.ndjson").write_text(
            '{"id":"m2","from":"ff","name":"bob","text":"also hello"}\n')
        self.assertEqual(self.read_lines(mon, 4), [],
                         "chat messages belong to the inbox monitor")
        print("PASS 3: the request monitor leaves message spools alone")

    def test_repeated_request_is_pushed_once(self):
        mon, udir = self.start("s.req.3")
        spool = pathlib.Path(udir, "sessions", "s.req.3.requests.ndjson")
        spool.write_text(REQUEST + "\n")
        time.sleep(1)
        with spool.open("a") as fh:                      # a retried registration
            fh.write(REQUEST + "\n")
        self.assertEqual(self.read_lines(mon, 5), [REQUEST])
        print("PASS 4: a repeated request id surfaces once")

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
