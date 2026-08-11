"""The spool writer's --wake-codex flag nudges an idle Codex session.

A fake app-server daemon (WebSocket over a unix socket, like the real one)
stands in for Codex. Asserts:
  1. With no control socket the writer behaves exactly as before: records
     land, nothing is printed, no state appears.
  2. Without the flag the writer never touches an existing socket: opt-in.
  3. One record produces exactly one nudge, the nudge carries no message
     body, and the handshake offers no permessage-deflate (the real daemon
     rejects it).
  4. While the nudged mail is still unread, further records add no nudges.
  5. Once the hook cursor shows the mail was read, the next record nudges
     again.
  6. With several loaded threads the writer stands down: it cannot tell
     which thread is which session, and hooks still deliver.
  7. A busy thread is not nudged (Stop delivers at end of turn), and no
     suppression mark is left, so the next record retries.
  8. A server that accepts and then hangs does not break delivery: the
     writer still exits 0 with the record in the spool, within its deadline.
  9. A server that refuses the upgrade does not break delivery either.
"""

import base64
import hashlib
import json
import os
import pathlib
import socket
import struct
import subprocess
import sys
import tempfile
import threading
import time
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WRITER = os.path.join(ROOT, "bin", "spool-writer.py")
WS_GUID = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"


class FakeDaemon(threading.Thread):
    """Just enough of the daemon: WS upgrade, then id-matched JSON replies."""

    def __init__(self, sock_path, threads=("thread-1",), busy=False, mode="ok"):
        super().__init__(daemon=True)
        self.sock_path = sock_path
        self.threads = list(threads)
        self.busy = busy
        self.mode = mode                  # "ok", "hang", or "refuse"
        self.connections = 0
        self.handshakes = []              # raw header lines per connection
        self.requests = []                # every parsed JSON message
        self.turn_texts = []              # text of each turn/start input
        self.stop_flag = threading.Event()
        os.makedirs(os.path.dirname(sock_path), exist_ok=True)
        self.listener = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.listener.bind(sock_path)
        self.listener.listen(4)
        self.listener.settimeout(0.2)

    def run(self):
        while not self.stop_flag.is_set():
            try:
                conn, _ = self.listener.accept()
            except socket.timeout:
                continue
            except OSError:
                break
            self.connections += 1
            try:
                self._serve(conn)
            except Exception:
                pass
            finally:
                try:
                    conn.close()
                except OSError:
                    pass
        self.listener.close()

    def stop(self):
        self.stop_flag.set()
        self.join(timeout=5)

    def _serve(self, conn):
        rf = conn.makefile("rb")
        lines = []
        while True:
            line = rf.readline()
            if not line or line in (b"\r\n", b"\n"):
                break
            lines.append(line.decode("latin-1").strip())
        self.handshakes.append(lines)
        if self.mode == "refuse":
            conn.sendall(b"HTTP/1.1 400 Bad Request\r\n\r\n")
            return
        key = next(l.split(":", 1)[1].strip() for l in lines
                   if l.lower().startswith("sec-websocket-key"))
        accept = base64.b64encode(
            hashlib.sha1((key + WS_GUID).encode()).digest()).decode()
        conn.sendall((
            "HTTP/1.1 101 Switching Protocols\r\n"
            "Upgrade: websocket\r\nConnection: Upgrade\r\n"
            f"Sec-WebSocket-Accept: {accept}\r\n\r\n").encode())
        while True:
            frame = self._read_frame(rf)
            if frame is None:
                return
            opcode, payload = frame
            if opcode == 0x8:
                return
            if opcode != 0x1:
                continue
            msg = json.loads(payload)
            self.requests.append(msg)
            if self.mode == "hang" or msg.get("id") is None:
                continue                  # swallow, or a notification
            self._reply(conn, msg)

    def _read_frame(self, rf):
        head = rf.read(2)
        if len(head) < 2:
            return None
        b0, b1 = head
        n = b1 & 0x7F
        if n == 126:
            n = struct.unpack(">H", rf.read(2))[0]
        elif n == 127:
            n = struct.unpack(">Q", rf.read(8))[0]
        mask = rf.read(4) if b1 & 0x80 else None
        payload = rf.read(n)
        if mask:
            payload = bytes(c ^ mask[i % 4] for i, c in enumerate(payload))
        return b0 & 0x0F, payload

    def _send_text(self, conn, text):
        data = text.encode()
        n = len(data)
        if n < 126:
            head = bytes([0x81, n])
        elif n < 1 << 16:
            head = bytes([0x81, 126]) + struct.pack(">H", n)
        else:
            head = bytes([0x81, 127]) + struct.pack(">Q", n)
        conn.sendall(head + data)

    def _reply(self, conn, msg):
        method = msg.get("method")
        if method == "initialize":
            result = {"userAgent": "fake-daemon"}
        elif method == "thread/loaded/list":
            result = {"data": list(self.threads), "nextCursor": None}
        elif method == "thread/read":
            status = "active" if self.busy else "idle"
            result = {"thread": {"id": msg["params"]["threadId"],
                                 "status": {"type": status}}}
        elif method == "turn/start":
            self.turn_texts.append(msg["params"]["input"][0]["text"])
            result = {"turn": {"id": "turn-1", "status": "inProgress"}}
        else:
            self._send_text(conn, json.dumps(
                {"id": msg["id"], "error": {"message": "unknown method"}}))
            return
        self._send_text(conn, json.dumps({"id": msg["id"], "result": result}))


class TestCodexWake(unittest.TestCase):
    def setUp(self):
        self.home = tempfile.mkdtemp()
        self.user = os.path.join(self.home, "users", "alice")
        os.makedirs(self.user)
        self.registry = os.path.join(self.home, ".agent-talk", "by-session")
        os.makedirs(self.registry)
        pathlib.Path(self.registry, "s-codex").write_text(self.user + "\n")
        self.codex_home = tempfile.mkdtemp()
        self.sock = os.path.join(self.codex_home, "app-server-control",
                                 "app-server-control.sock")
        self.daemon = None

    def tearDown(self):
        if self.daemon:
            self.daemon.stop()

    def start_daemon(self, **kwargs):
        self.daemon = FakeDaemon(self.sock, **kwargs)
        self.daemon.start()
        return self.daemon

    def run_writer(self, lines, wake=True):
        args = [sys.executable, WRITER, "--user", self.user, "--no-legacy"]
        if wake:
            args.append("--wake-codex")
        res = subprocess.run(args, input="".join(l + "\n" for l in lines),
                             capture_output=True, text=True, timeout=120,
                             env=dict(os.environ, HOME=self.home,
                                      CODEX_HOME=self.codex_home))
        self.assertEqual(res.returncode, 0, res.stderr)
        return res

    def spool(self):
        return os.path.join(self.user, "sessions", "s-codex.ndjson")

    def spool_texts(self):
        with open(self.spool()) as fh:
            return [json.loads(l)["text"] for l in fh if l.strip()]

    def mark_drained(self):
        """Pretend the Codex inbox hook consumed the whole spool."""
        state = os.path.join(self.user, "sessions", ".codex-hook-state.json")
        entry = {os.path.abspath(self.spool()):
                 {"offset": os.path.getsize(self.spool()), "ids": []}}
        pathlib.Path(state).write_text(json.dumps(entry))

    def test_no_socket_behaves_as_before(self):
        res = self.run_writer(['{"id":"m1","text":"hello"}',
                               '{"id":"m2","text":"again"}'])
        self.assertEqual(self.spool_texts(), ["hello", "again"])
        self.assertEqual(res.stdout, "")
        self.assertEqual(res.stderr, "")
        self.assertFalse(os.path.exists(os.path.join(
            self.user, "sessions", ".codex-wake-state.json")),
            "no wake happened, so no wake state should appear")
        print("PASS 1: no control socket, delivery exactly as before")

    def test_without_flag_never_connects(self):
        daemon = self.start_daemon()
        self.run_writer(['{"id":"m1","text":"hello"}'], wake=False)
        time.sleep(0.3)
        self.assertEqual(daemon.connections, 0,
                         "without --wake-codex the socket must not be touched")
        self.assertEqual(self.spool_texts(), ["hello"])
        print("PASS 2: waking is opt-in; no flag, no connection")

    def test_one_nudge_and_no_message_body(self):
        daemon = self.start_daemon()
        body = "the-secret-body-marker do not leak"
        self.run_writer([json.dumps({"id": "m1", "name": "bob", "text": body})])
        self.assertEqual(len(daemon.turn_texts), 1, daemon.requests)
        self.assertNotIn("secret-body-marker", daemon.turn_texts[0],
                         "the nudge must never carry the message body")
        self.assertNotIn("bob", daemon.turn_texts[0])
        joined = "\n".join("\n".join(h) for h in daemon.handshakes).lower()
        self.assertNotIn("permessage-deflate", joined,
                         "the real daemon rejects compressed handshakes")
        self.assertEqual(self.spool_texts(), [body])
        print("PASS 3: exactly one nudge, generic text, no compression offer")

    def test_no_second_nudge_while_unread(self):
        daemon = self.start_daemon()
        self.run_writer(['{"id":"m1","text":"one"}',
                         '{"id":"m2","text":"two"}'])
        self.run_writer(['{"id":"m3","text":"three"}'])  # writer restarted too
        self.assertEqual(len(daemon.turn_texts), 1,
                         "unread mail already has a nudge outstanding")
        self.assertEqual(self.spool_texts(), ["one", "two", "three"])
        print("PASS 4: no repeat nudge while the first is outstanding")

    def test_nudges_again_after_drain(self):
        daemon = self.start_daemon()
        self.run_writer(['{"id":"m1","text":"one"}'])
        self.mark_drained()
        self.run_writer(['{"id":"m2","text":"two"}'])
        self.assertEqual(len(daemon.turn_texts), 2,
                         "a drained spool re-arms the nudge")
        print("PASS 5: nudges again once the hook cursor shows a drain")

    def test_stands_down_with_several_threads(self):
        daemon = self.start_daemon(threads=("thread-1", "thread-2"))
        self.run_writer(['{"id":"m1","text":"hello"}'])
        self.assertEqual(len(daemon.turn_texts), 0,
                         "ambiguous thread choice must not inject anywhere")
        self.assertEqual(self.spool_texts(), ["hello"])
        print("PASS 6: several loaded threads, no nudge, delivery intact")

    def test_busy_thread_skipped_then_retried(self):
        daemon = self.start_daemon(busy=True)
        self.run_writer(['{"id":"m1","text":"one"}'])
        self.assertEqual(len(daemon.turn_texts), 0,
                         "a running turn is delivered by the Stop hook")
        self.assertTrue(any(r.get("method") == "thread/read"
                            for r in daemon.requests))
        daemon.busy = False
        self.run_writer(['{"id":"m2","text":"two"}'])
        self.assertEqual(len(daemon.turn_texts), 1,
                         "a busy skip leaves no mark, so the next record retries")
        print("PASS 7: busy thread skipped without suppressing later nudges")

    def test_hanging_server_does_not_break_delivery(self):
        self.start_daemon(mode="hang")
        started = time.monotonic()
        res = self.run_writer(['{"id":"m1","text":"hello"}'])
        elapsed = time.monotonic() - started
        self.assertEqual(self.spool_texts(), ["hello"])
        self.assertEqual(res.stderr, "")
        self.assertLess(elapsed, 30, "the wake attempt must be bounded")
        print(f"PASS 8: hanging daemon, record still delivered ({elapsed:.1f}s)")

    def test_refusing_server_does_not_break_delivery(self):
        daemon = self.start_daemon(mode="refuse")
        res = self.run_writer(['{"id":"m1","text":"hello"}'])
        self.assertEqual(self.spool_texts(), ["hello"])
        self.assertEqual(res.stderr, "")
        self.assertEqual(len(daemon.turn_texts), 0)
        print("PASS 9: refused upgrade, record still delivered")


if __name__ == "__main__":
    unittest.main()
