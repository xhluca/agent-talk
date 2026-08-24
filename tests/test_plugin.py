"""Static checks on the agent-talk plugin (no external deps)."""
import glob, json, os, pathlib, re, subprocess, time, unittest
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKILLS = sorted(glob.glob(os.path.join(ROOT, "skills", "*", "SKILL.md")))
EXPECTED = ["init", "id", "add", "verify", "contacts", "send", "receive",
            "sync", "block", "share", "import", "history", "config",
            "relay", "group"]


class TestManifests(unittest.TestCase):
    def test_plugin_json(self):
        d = json.loads(pathlib.Path(ROOT, ".claude-plugin", "plugin.json").read_text())
        self.assertEqual(d["name"], "agent-talk")
        self.assertIn("version", d)

    def test_marketplace_json(self):
        d = json.loads(pathlib.Path(ROOT, ".claude-plugin", "marketplace.json").read_text())
        self.assertTrue(d["plugins"])
        self.assertEqual(d["plugins"][0]["source"], ".")

    def test_monitors_json(self):
        m = json.loads(pathlib.Path(ROOT, "monitors", "monitors.json").read_text())
        self.assertTrue(any(x.get("name") == "retalk-inbox" for x in m))
        # Contact requests ride a second monitor, not the inbox one.
        self.assertTrue(any(x.get("name") == "retalk-requests" for x in m))
        for entry in m:
            script = entry["command"].split()[0].replace(
                "${CLAUDE_PLUGIN_ROOT}", ROOT)
            self.assertTrue(os.access(script, os.X_OK),
                            f"{entry['name']}: {script} is not executable")


class TestSkills(unittest.TestCase):
    def test_all_expected_skills_present(self):
        names = {os.path.basename(os.path.dirname(f)) for f in SKILLS}
        for n in EXPECTED:
            self.assertIn(n, names, f"missing skill: {n}")

    def test_frontmatter_with_description(self):
        for f in SKILLS:
            s = pathlib.Path(f).read_text()
            self.assertTrue(s.startswith("---\n"), f"{f}: no frontmatter")
            self.assertRegex(s, r"(?m)^description:\s*\S", f"{f}: no description")

    def test_never_instructs_receive_all(self):
        # `receive --all` must only ever appear in a safety note, never as an
        # instruction (agent-talk reads only from designated peers).
        for f in SKILLS:
            for ln in pathlib.Path(f).read_text().splitlines():
                if "receive --all" in ln:
                    self.assertRegex(ln.lower(), r"never|not |disallow|sparing",
                                     f"{f}: unsafe --all instruction: {ln.strip()}")

    def test_invite_commands_target_the_identity_inline(self):
        # agent-talk never relies on a saved default identity; every retalk
        # call names one with --dir. The invite-code commands are no different.
        for f in SKILLS:
            for ln in pathlib.Path(f).read_text().splitlines():
                s = ln.strip()
                if not s.startswith(("retalk invite ", "retalk request ")):
                    continue
                self.assertTrue("--dir" in s or "--help" in s,
                                f"{f}: no --dir on: {s}")

    def test_invite_code_skills_state_the_retalk_floor(self):
        # These commands do not exist before retalk 0.3.0, so a skill that
        # teaches them must say so and keep the manual add path as fallback.
        for f in SKILLS:
            text = pathlib.Path(f).read_text()
            if "invite code" not in text.lower():
                continue
            self.assertIn("0.3.0", text,
                          f"{f}: mentions invite codes without the version floor")

    def test_no_prerelease_version_floors(self):
        # The floor is the stable 0.3.0. A skill still naming a release
        # candidate sends the reader looking for a prerelease that the install
        # step no longer asks for.
        for f in SKILLS + [os.path.join(ROOT, "README.md"),
                           os.path.join(ROOT, "docs", "README.md")]:
            for ln in pathlib.Path(f).read_text().splitlines():
                self.assertNotIn("0.3.0rc", ln,
                                 f"{f}: prerelease version floor: {ln.strip()}")
                self.assertNotIn("0.3.0-rc", ln,
                                 f"{f}: prerelease version floor: {ln.strip()}")

    def test_never_teaches_a_prerelease_install(self):
        # `--prerelease allow` (uv) and `--pre` (pip) were correct only while
        # the features lived in a release candidate. Left in an install command,
        # they opt every user into every future candidate, on this install and
        # on every upgrade after it. Prose about the flags is fine; an install
        # command carrying one is the bug.
        for f in SKILLS + [os.path.join(ROOT, "README.md"),
                           os.path.join(ROOT, "docs", "README.md")]:
            for ln in pathlib.Path(f).read_text().splitlines():
                s = ln.strip().lstrip("`> ")
                if not s.startswith(("uv tool install", "pip install",
                                     "pip3 install")):
                    continue
                self.assertNotIn("--prerelease", s,
                                 f"{f}: prerelease install command: {s}")
                self.assertNotRegex(s, r"(?<![-\w])--pre(?![-\w])",
                                    f"{f}: prerelease install command: {s}")

    def test_watch_is_documented_as_needing_a_modern_relay(self):
        # `invite watch` reads without consuming, which is a relay-side
        # capability. Against an older relay it refuses to start, and an agent
        # that has only been told about the client floor cannot tell why.
        for name in ("id", "init"):
            text = pathlib.Path(ROOT, "skills", name, "SKILL.md").read_text()
            self.assertIn("relay is too old", text,
                          f"skills/{name}: does not explain the refusal an "
                          "older relay gives `invite watch`")

    def test_invite_code_skills_qualify_what_a_code_proves(self):
        # A code shows the holder was authorised by the issuer, nothing more.
        # Losing that caveat would leave the skills calling a peer "verified".
        for name in ("id", "init"):
            text = pathlib.Path(ROOT, "skills", name, "SKILL.md").read_text()
            self.assertIn("authoris", text.lower(),
                          f"skills/{name}: invite codes need the authorisation caveat")

    def test_never_reads_the_passphrase_into_a_command(self):
        # The passphrase is named by path (`--passphrase-path`), never read.
        # `RETALK_PASSPHRASE="$(cat ...)" retalk ...` is two problems in one: it
        # pipes a secret file into a process that then talks to the network,
        # which is the shape of credential exfiltration, and the assignment
        # makes it a compound command that no prefix allowlist rule can match.
        # It survives only as the documented fallback for retalk older than
        # 0.3.0, so a line carrying it must say which of those it is.
        for f in SKILLS:
            for ln in pathlib.Path(f).read_text().splitlines():
                if 'RETALK_PASSPHRASE="$(cat' not in ln:
                    continue
                self.assertRegex(
                    ln.lower(), r"fallback|older retalk",
                    f"{f}: reads the passphrase inline: {ln.strip()}")

    def test_passphrase_path_skills_state_the_retalk_floor(self):
        # --passphrase-path does not exist before retalk 0.3.0, where it
        # dies at argument parsing, so a skill that teaches it must say so.
        for f in SKILLS:
            text = pathlib.Path(f).read_text()
            if "--passphrase-path" not in text:
                continue
            self.assertIn("0.3.0", text,
                          f"{f}: uses --passphrase-path without the version floor")

    def test_background_blocks_are_single_commands(self):
        # The follower and the invite watcher used to be inlined as long
        # `nohup env ... bash -c '...'` strings: the hardest commands to
        # allowlist and the most likely to be refused. They live in bin/ now.
        for f in SKILLS:
            text = pathlib.Path(f).read_text()
            self.assertNotIn("nohup env", text,
                             f"{f}: inline background blob; call bin/*.sh instead")
        for script in ("follow.sh", "invite-watch.sh"):
            p = os.path.join(ROOT, "bin", script)
            self.assertTrue(os.access(p, os.X_OK), f"bin/{script} is not executable")

    def test_non_init_skills_use_resolved_user_dir(self):
        # non-init skills must use the resolved <user> dir, not a hardcoded path
        for f in SKILLS:
            if os.path.basename(os.path.dirname(f)) == "init":
                continue
            self.assertNotIn("$HOME/.agent-talk/users/<user>", pathlib.Path(f).read_text(),
                             f"{f}: hardcoded per-user path; use <user>/...")


class TestBinScripts(unittest.TestCase):
    def test_bash_syntax(self):
        for f in glob.glob(os.path.join(ROOT, "bin", "*.sh")):
            r = subprocess.run(["bash", "-n", f], capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, f"{f}: {r.stderr}")

    def _make_zombie(self):
        """A pid that exists and is unreaped, so `kill -0` succeeds on it."""
        # A child this process never waits on stays a zombie until the test
        # ends, which is exactly the state a dead follower is left in whenever
        # PID 1 is not an init that reaps (a container running `sleep infinity`,
        # for one). fork directly rather than through subprocess, which reaps
        # its own children behind our back.
        if not hasattr(os, "fork"):
            self.skipTest("needs fork")
        pid = os.fork()
        if pid == 0:                      # child: exit at once, stay unreaped
            os._exit(0)
        self.addCleanup(lambda: os.waitpid(pid, 0))
        deadline = time.time() + 5
        while time.time() < deadline:
            try:
                state = pathlib.Path(f"/proc/{pid}/status").read_text()
            except OSError:
                break
            if "State:\tZ" in state:
                return pid
            time.sleep(0.05)
        self.skipTest("could not produce a zombie to test against")

    def test_a_zombie_pid_is_not_reported_as_running(self):
        # `kill -0` succeeds on a zombie. Both supervisors used it, so `status`
        # reported a watcher that had been dead for minutes and `start` refused
        # to restart it with "already watching".
        import tempfile
        if not os.path.isdir("/proc"):
            self.skipTest("needs /proc")
        zombie = self._make_zombie()
        for script, pidfile, dead, live in (
                ("invite-watch.sh", "invite-watch.pid",
                 "not watching", "already watching"),
                ("follow.sh", "follow.peer.pid", "not following",
                 "already following")):
            with tempfile.TemporaryDirectory() as ud:
                pathlib.Path(ud, pidfile).write_text(f"{zombie}\n")
                r = self._status_without_session_id(script, ud)
                self.assertIn(dead, r.stdout,
                              f"bin/{script}: a zombie pid reported as running: "
                              f"{r.stdout}")
                self.assertNotIn(live, r.stdout)

    def test_supervisors_detach_the_background_process(self):
        # Without a new session, a watcher or follower started inside a headless
        # `codex exec` turn is killed with that turn's process group the moment
        # the turn ends -- right after the invite code went out.
        for script in ("invite-watch.sh", "follow.sh"):
            text = pathlib.Path(ROOT, "bin", script).read_text()
            self.assertIn("setsid", text,
                          f"bin/{script}: background process is not detached")

    def _status_without_session_id(self, script, user_dir):
        env = dict(os.environ)
        for k in ("CLAUDE_SESSION_ID", "CLAUDE_CODE_SESSION_ID"):
            env.pop(k, None)
        return subprocess.run(
            ["bash", os.path.join(ROOT, "bin", script), "status", user_dir],
            capture_output=True, text=True, env=env)

    def test_status_finds_the_spool_without_claude_session_id(self):
        # CLAUDE_SESSION_ID is substituted into a monitor's command line but is
        # NOT exported into the Bash tool's environment, so `status` used to
        # tail "<user>/sessions/none.requests.ndjson", print "(none yet)", and
        # tell the agent nobody had registered while an accepted registration
        # sat on disk. Both status actions must find the spool anyway.
        import tempfile
        with tempfile.TemporaryDirectory() as ud:
            os.makedirs(os.path.join(ud, "sessions"))
            reg = '{"kind": "contact_accepted", "name": "peer-that-registered"}'
            msg = '{"kind": "message", "body": "message-that-arrived"}'
            pathlib.Path(ud, "sessions", "abc.requests.ndjson").write_text(reg + "\n")
            pathlib.Path(ud, "sessions", "abc.ndjson").write_text(msg + "\n")

            r = self._status_without_session_id("invite-watch.sh", ud)
            self.assertIn("peer-that-registered", r.stdout,
                          f"invite-watch.sh status hid the registration: {r.stdout}")
            self.assertNotIn("(none yet)", r.stdout)

            r = self._status_without_session_id("follow.sh", ud)
            self.assertIn("message-that-arrived", r.stdout,
                          f"follow.sh status hid the message: {r.stdout}")
            # the message spool, not the request spool
            self.assertNotIn("peer-that-registered", r.stdout)

    def test_status_falls_back_to_the_per_identity_request_file(self):
        # On a host with no session map the writer keeps registrations in
        # <user>/requests.ndjson. `status` has to read that too, or it reports
        # "(none yet)" for a peer who has in fact been saved.
        import tempfile
        with tempfile.TemporaryDirectory() as ud:
            os.makedirs(os.path.join(ud, "sessions"))
            pathlib.Path(ud, "requests.ndjson").write_text(
                '{"kind": "contact_accepted", "name": "peer-that-registered"}\n')
            r = self._status_without_session_id("invite-watch.sh", ud)
            self.assertIn("peer-that-registered", r.stdout,
                          f"invite-watch.sh status hid the registration: "
                          f"{r.stdout}")


class TestRelayChoiceIsNotAFootgun(unittest.TestCase):
    """A localhost relay must never be offered without its cost.

    `init` writes the relay into the identity once and no command changes it
    later, and the saved value outranks `retalk config --relay`. So an identity
    created against 127.0.0.1 is unreachable from anywhere else for as long as
    it exists, and its `id --card` advertises localhost to whoever receives it.
    The relay skill used to list "Local only" first as "quickest", with no hint
    that the choice was permanent, and that is exactly how one got created.
    """

    @staticmethod
    def _flat(*parts):
        # These files are hard-wrapped, so a warning sentence routinely spans a
        # newline, and inside a blockquote each line also carries a "> ".
        # Strip the markers, then collapse whitespace, or the test breaks on
        # reflow rather than on the thing it guards.
        raw = pathlib.Path(ROOT, *parts).read_text()
        return re.sub(r"\s+", " ", re.sub(r"(?m)^\s*>\s?", "", raw))

    def test_local_relay_is_offered_only_with_the_permanence_warning(self):
        text = self._flat("skills", "relay", "SKILL.md")
        self.assertIn("Local only", text)
        self.assertIn("no command to change it", text,
                      "relay skill offers a local relay without saying the "
                      "choice is permanent for the identity")
        self.assertIn("throwaway", text.lower(),
                      "relay skill does not scope local-only to identities "
                      "the user is willing to recreate")

    def test_init_warns_before_baking_in_a_relay(self):
        text = self._flat("skills", "init", "SKILL.md")
        self.assertIn("permanent for this identity", text,
                      "init asks for a relay without saying the answer is "
                      "written into the identity for good")
        self.assertRegex(text, r"127\.0\.0\.1|localhost",
                         "init never warns against creating an identity on a "
                         "local relay")

    def test_moving_a_relay_names_the_env_var_not_just_the_flag(self):
        # `--relay` fixes one command; a stranded identity needs every command
        # fixed, and a follower started without it silently polls the old relay.
        text = self._flat("skills", "init", "SKILL.md")
        self.assertIn("RETALK_RELAY", text,
                      "init explains moving a relay without naming the "
                      "environment variable that actually overrides the "
                      "saved value")


class TestDocumentedCommandsExist(unittest.TestCase):
    def test_never_names_the_removed_save_messages_flag(self):
        # retalk renamed --save-messages to --save in July 2026, and the old
        # spelling is now rejected outright ("unrecognized arguments"). Skills
        # older than 0.2.0 still carry it, and an agent reading one of those
        # concluded retalk was behind the doc rather than the reverse, so it
        # waited for a flag that had been deliberately removed.
        #
        # RETALK_SAVE_MESSAGE, the environment variable, is a different thing
        # and still current, so match the flag exactly rather than the string.
        # One mention is legitimate: init explains the skew this caused, and
        # naming the flag is the point there. Allow only a line that marks it
        # as the old name, the same exemption the retalk --version guard uses.
        pattern = re.compile(r"--save-messages\b")
        for f in SKILLS + [os.path.join(ROOT, "README.md")] + sorted(
                glob.glob(os.path.join(ROOT, "docs", "*.md"))) + sorted(
                glob.glob(os.path.join(ROOT, "bin", "*"))):
            if not os.path.isfile(f):
                continue
            for n, ln in enumerate(pathlib.Path(f).read_text(
                    errors="replace").splitlines(), 1):
                if not pattern.search(ln):
                    continue
                self.assertIn(
                    "old name", ln,
                    f"{f}:{n} names --save-messages, which retalk removed; "
                    f"use --save: {ln.strip()}")

    def test_never_tells_the_agent_to_run_retalk_version(self):
        # retalk has no --version flag; the call exits 2 with an argparse usage
        # error and prints nothing useful. It was the skill's own recovery
        # instruction for "did the install take?", so a wrong answer there is a
        # wrong answer at exactly the moment it matters.
        for f in SKILLS:
            for ln in pathlib.Path(f).read_text().splitlines():
                if "retalk --version" not in ln:
                    continue
                self.assertIn("no `retalk --version`", ln,
                              f"{f}: tells the agent to run retalk --version: "
                              f"{ln.strip()}")

    def test_send_and_receive_keep_the_message_log(self):
        # Saving used to ride an `RETALK_SAVE_MESSAGE=1 ` prefix, which is easy
        # to drop: a verification run produced a peer whose own replies were
        # missing from `history` for exactly that reason. Every send/receive the
        # skills show must carry `--save` inside the command instead.
        for name in ("send", "receive"):
            f = os.path.join(ROOT, "skills", name, "SKILL.md")
            for ln in pathlib.Path(f).read_text().splitlines():
                s = ln.strip()
                if not s.startswith(f"retalk {name} "):
                    continue
                if "--help" in s:
                    continue
                self.assertIn("--save", s,
                              f"skills/{name}: message would not be logged: {s}")

    def test_session_map_block_does_not_use_the_unexported_variable(self):
        # Same variable, other end: a pasted ${CLAUDE_SESSION_ID} expands to
        # nothing in the Bash tool, so the session map lands at an empty
        # filename and per-session delivery breaks with nothing reported.
        text = pathlib.Path(ROOT, "skills", "init", "SKILL.md").read_text()
        for ln in text.splitlines():
            s = ln.strip()
            if not s.startswith(("echo ", ": >>", "mkdir ")):
                continue
            self.assertNotIn("${CLAUDE_SESSION_ID}", s,
                             f"skills/init: shell block expands an unexported "
                             f"variable: {s}")


if __name__ == "__main__":
    unittest.main()
