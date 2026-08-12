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
