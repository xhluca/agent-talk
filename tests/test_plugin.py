"""Static checks on the agent-talk plugin (no external deps)."""
import glob, json, os, pathlib, subprocess, unittest
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
        # These commands do not exist before retalk 0.3.0-rc.1, so a skill that
        # teaches them must say so and keep the manual add path as fallback.
        for f in SKILLS:
            text = pathlib.Path(f).read_text()
            if "invite code" not in text.lower():
                continue
            self.assertIn("0.3.0-rc.1", text,
                          f"{f}: mentions invite codes without the version floor")

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
        # 0.3.0-rc.1, so a line carrying it must say which of those it is.
        for f in SKILLS:
            for ln in pathlib.Path(f).read_text().splitlines():
                if 'RETALK_PASSPHRASE="$(cat' not in ln:
                    continue
                self.assertRegex(
                    ln.lower(), r"fallback|older retalk",
                    f"{f}: reads the passphrase inline: {ln.strip()}")

    def test_passphrase_path_skills_state_the_retalk_floor(self):
        # --passphrase-path does not exist before retalk 0.3.0-rc.1, where it
        # dies at argument parsing, so a skill that teaches it must say so.
        for f in SKILLS:
            text = pathlib.Path(f).read_text()
            if "--passphrase-path" not in text:
                continue
            self.assertIn("0.3.0-rc.1", text,
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


if __name__ == "__main__":
    unittest.main()
