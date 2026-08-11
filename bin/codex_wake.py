"""Best-effort wake of an idle Codex session when new agent-talk mail lands.

The spool writer imports this module when started with --wake-codex. After a
record is appended to a session spool, `maybe_wake` connects to Codex's local
app-server daemon (the control socket under `$CODEX_HOME`) and starts a turn
carrying a short nudge, so a session sitting idle at the prompt handles the
mail instead of waiting for the next prompt. The message body itself is never
pushed: an injected turn arrives with the authority of something the user
typed, so peer-controlled text must not travel this way, and the inbox hook
that fires for the injected turn delivers the body through the normal path
with its existing dedupe cursor.

Everything here is best-effort. The spool append has already happened by the
time this runs, so any failure (no socket, no daemon, refused handshake,
method error, timeout) is swallowed and delivery falls back to the hooks at
the next prompt or end of turn. The whole attempt is bounded by one deadline.

The daemon's socket speaks WebSocket, not raw JSON lines, and rejects
handshakes offering permessage-deflate, so this client does its own minimal
upgrade and framing (standard library only) and offers no extensions.
"""

import base64
import json
import os
import socket
import struct
import time

CONTROL_SOCKET = os.path.join("app-server-control", "app-server-control.sock")
WAKE_STATE_NAME = ".codex-wake-state.json"
HOOK_STATE_NAME = ".codex-hook-state.json"
WAKE_DEADLINE = 3.0  # seconds for the whole attempt: connect, upgrade, calls

# The nudge is deliberately generic. The UserPromptSubmit hook fires for the
# injected turn and attaches the actual messages as context, so the nudge only
# has to make the agent act on what the hook delivers.
NUDGE = (
    "[agent-talk] New mail arrived while this session was idle. The waiting "
    "messages are attached to this prompt as extra context; show them to the "
    "user verbatim as a chat transcript and reply over agent-talk if one is "
    "needed. If nothing is attached, the inbox was already drained; say so "
    "briefly and stop."
)


def control_socket_path():
    home = os.environ.get("CODEX_HOME") or os.path.expanduser("~/.codex")
    return os.path.join(home, CONTROL_SOCKET)


class _Deadline:
    def __init__(self, seconds):
        self.at = time.monotonic() + seconds

    def remaining(self):
        left = self.at - time.monotonic()
        if left <= 0:
            raise TimeoutError("wake attempt out of time")
        return left


def _ws_connect(path, deadline):
    """Open the socket and upgrade to WebSocket. Returns (socket, leftover)."""
    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    sock.settimeout(deadline.remaining())
    sock.connect(path)
    key = base64.b64encode(os.urandom(16)).decode()
    sock.sendall((
        "GET / HTTP/1.1\r\n"
        "Host: localhost\r\n"
        "Connection: Upgrade\r\n"
        "Upgrade: websocket\r\n"
        "Sec-WebSocket-Version: 13\r\n"
        f"Sec-WebSocket-Key: {key}\r\n"
        "\r\n"
    ).encode())
    buf = b""
    while b"\r\n\r\n" not in buf:
        sock.settimeout(deadline.remaining())
        chunk = sock.recv(4096)
        if not chunk:
            raise OSError("connection closed during handshake")
        buf += chunk
    head, _, leftover = buf.partition(b"\r\n\r\n")
    if b" 101" not in head.split(b"\r\n", 1)[0]:
        raise OSError("websocket upgrade refused")
    return sock, leftover


def _send_text(sock, deadline, payload):
    """One masked text frame; clients must mask, servers must not."""
    data = payload.encode("utf-8")
    mask = os.urandom(4)
    head = bytearray([0x81])  # FIN + text
    n = len(data)
    if n < 126:
        head.append(0x80 | n)
    elif n < 1 << 16:
        head.append(0x80 | 126)
        head += struct.pack(">H", n)
    else:
        head.append(0x80 | 127)
        head += struct.pack(">Q", n)
    head += mask
    sock.settimeout(deadline.remaining())
    sock.sendall(bytes(head) + bytes(b ^ mask[i % 4] for i, b in enumerate(data)))


class _Frames:
    """Reads server frames; yields whole text messages, skips everything else."""

    def __init__(self, sock, leftover):
        self.sock = sock
        self.buf = leftover

    def _need(self, n, deadline):
        while len(self.buf) < n:
            self.sock.settimeout(deadline.remaining())
            chunk = self.sock.recv(65536)
            if not chunk:
                raise OSError("connection closed")
            self.buf += chunk

    def _frame(self, deadline):
        self._need(2, deadline)
        b0, b1 = self.buf[0], self.buf[1]
        fin, opcode, n, off = b0 & 0x80, b0 & 0x0F, b1 & 0x7F, 2
        if n == 126:
            self._need(4, deadline)
            n, off = struct.unpack(">H", self.buf[2:4])[0], 4
        elif n == 127:
            self._need(10, deadline)
            n, off = struct.unpack(">Q", self.buf[2:10])[0], 10
        mask = None
        if b1 & 0x80:  # servers should not mask, but tolerate one that does
            self._need(off + 4, deadline)
            mask, off = self.buf[off:off + 4], off + 4
        self._need(off + n, deadline)
        payload = self.buf[off:off + n]
        self.buf = self.buf[off + n:]
        if mask:
            payload = bytes(b ^ mask[i % 4] for i, b in enumerate(payload))
        return fin, opcode, payload

    def next_text(self, deadline):
        parts, in_text = [], False
        while True:
            fin, opcode, payload = self._frame(deadline)
            if opcode == 0x8:
                raise OSError("server sent close")
            if opcode == 0x1 or (opcode == 0x0 and in_text):
                parts.append(payload)
                in_text = True
                if fin:
                    return b"".join(parts).decode("utf-8", "replace")
            # ping, pong, binary: nothing to do on a connection this short


class _Client:
    def __init__(self, path, deadline):
        self.deadline = deadline
        self.sock, leftover = _ws_connect(path, deadline)
        self.frames = _Frames(self.sock, leftover)
        self.next_id = 1

    def request(self, method, params):
        rid, self.next_id = self.next_id, self.next_id + 1
        _send_text(self.sock, self.deadline,
                   json.dumps({"id": rid, "method": method, "params": params}))
        while True:  # the daemon also streams notifications; match on id
            data = json.loads(self.frames.next_text(self.deadline))
            if isinstance(data, dict) and data.get("id") == rid:
                if "error" in data:
                    raise OSError(f"{method} failed: {data['error']}")
                return data.get("result")

    def notify(self, method, params):
        _send_text(self.sock, self.deadline,
                   json.dumps({"method": method, "params": params}))

    def close(self):
        try:
            self.sock.close()
        except OSError:
            pass


def _thread_ids(result):
    """Loaded thread ids from thread/loaded/list, whatever the exact shape."""
    if isinstance(result, dict):
        for key in ("data", "threadIds", "threads"):
            if key in result:
                result = result[key]
                break
    ids = []
    if isinstance(result, list):
        for item in result:
            if isinstance(item, str):
                ids.append(item)
            elif isinstance(item, dict) and item.get("id"):
                ids.append(item["id"])
    return ids


def _thread_is_busy(client, thread_id):
    """True only when the thread positively reports a turn in progress.

    A busy session needs no nudge: the Stop hook delivers waiting mail the
    moment the turn ends, and interjecting with turn/steer would interrupt
    work in progress to say something the turn boundary handles anyway. A
    failed or unrecognizable read does not block the nudge, because nudging
    a busy thread is only noise while not nudging an idle one loses the wake.
    """
    try:
        res = client.request("thread/read", {"threadId": thread_id})
        status = res["thread"]["status"]["type"]
    except Exception:
        return False
    return status != "idle"


def _wake_state_path(user_dir):
    return os.path.join(user_dir, "sessions", WAKE_STATE_NAME)


def _load_wake_state(user_dir):
    try:
        with open(_wake_state_path(user_dir)) as fh:
            data = json.load(fh)
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def _save_wake_state(user_dir, data):
    path = _wake_state_path(user_dir)
    try:
        with open(path + ".tmp", "w") as fh:
            json.dump(data, fh)
        os.replace(path + ".tmp", path)
    except OSError:
        pass  # best-effort bookkeeping; worst case is one extra nudge


def _hook_offset(spool):
    """Bytes of this spool the Codex inbox hook has already consumed."""
    state = os.path.join(os.path.dirname(os.path.abspath(spool)),
                         HOOK_STATE_NAME)
    try:
        with open(state) as fh:
            data = json.load(fh)
    except (OSError, ValueError):
        return 0
    if not isinstance(data, dict):
        return 0
    for key in (os.path.abspath(spool), os.path.realpath(spool)):
        entry = data.get(key)
        if isinstance(entry, dict):
            try:
                return int(entry.get("offset", 0))
            except (TypeError, ValueError):
                return 0
    return 0


def _nudge_due(user_dir, spools):
    """True unless every spool still has the last nudge outstanding.

    A nudge is outstanding for a spool while the hook's cursor sits below the
    size recorded when that nudge was sent: the mail it announced has not been
    read, so another nudge would add nothing. The session draining the spool
    (cursor at or past the mark), a spool never nudged about, and a spool that
    shrank (rotated or swept, making the mark meaningless) all re-arm it.
    """
    state = _load_wake_state(user_dir)
    for spool in spools:
        try:
            size = os.path.getsize(spool)
        except OSError:
            continue
        mark = state.get(os.path.abspath(spool))
        if not isinstance(mark, (int, float)) or size < mark:
            return True
        if _hook_offset(spool) >= mark:
            return True
    return False


def _mark_nudged(user_dir, spools):
    state = _load_wake_state(user_dir)
    for spool in spools:
        try:
            state[os.path.abspath(spool)] = os.path.getsize(spool)
        except OSError:
            pass
    _save_wake_state(user_dir, state)


def maybe_wake(user_dir, spools):
    """Nudge the one loaded Codex thread, if a nudge is due. Never raises,
    never prints: by the time this runs the record is already in the spool,
    and a wake that cannot happen must cost nothing."""
    try:
        path = control_socket_path()
        if not spools or not os.path.exists(path):
            return
        if not _nudge_due(user_dir, spools):
            return
        deadline = _Deadline(WAKE_DEADLINE)
        client = _Client(path, deadline)
        try:
            client.request("initialize",
                           {"clientInfo": {"name": "agent-talk", "version": "0"}})
            client.notify("initialized", {})
            ids = _thread_ids(client.request("thread/loaded/list", {}))
            # Thread ids are Codex's, not agent-talk's, and nothing maps one to
            # a session, so only the unambiguous case is taken: exactly one
            # loaded thread. With several, waking stands down rather than risk
            # injecting into the wrong session; hooks still deliver.
            if len(ids) != 1:
                return
            if _thread_is_busy(client, ids[0]):
                return  # the Stop hook delivers when the running turn ends
            client.request("turn/start",
                           {"threadId": ids[0],
                            "input": [{"type": "text", "text": NUDGE}]})
        finally:
            client.close()
        # Reached only after turn/start succeeded, so a failed attempt leaves
        # no mark and the next record retries.
        _mark_nudged(user_dir, spools)
    except Exception:
        pass
