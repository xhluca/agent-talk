#!/usr/bin/env python3
"""Deterministic, LLM-free validation of the agent-talk plugin artifacts.

Run from the repo root:

    python3 tests/validate_plugin.py

Exits non-zero with clear messages on any problem. No network, no model calls,
no external dependencies (stdlib only). This guards the plugin's own artifacts
so packaging/manifest regressions are caught on every push/PR.

Checks:
  * Every skills/*/SKILL.md: YAML frontmatter delimited by `---`, parses, has
    `name` and `description`, and `name` == the directory name.
  * .claude-plugin/plugin.json and .codex-plugin/plugin.json: valid JSON,
    required fields (name, version, description) present, versions match each
    other, and the codex `skills` field points at an existing directory.
  * .claude-plugin/marketplace.json: valid JSON, lists the `agent-talk` plugin.
  * README.md and docs/README.md: balanced ``` fences and <details>/</details>.
"""
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

_errors = []


def err(msg):
    _errors.append(msg)


# --------------------------------------------------------------------------- #
# Minimal YAML frontmatter parser (top-level `key: value` pairs only).
# We only need `name` and `description`, so a full YAML engine is overkill and
# would pull in a dependency. This handles the flat key/value frontmatter the
# skills use.
# --------------------------------------------------------------------------- #
def parse_frontmatter(text, path):
    """Return dict of top-level frontmatter keys, or None if delimiters bad."""
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        err(f"{path}: frontmatter must start with a line containing only '---'")
        return None
    # find the closing delimiter
    close = None
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            close = i
            break
    if close is None:
        err(f"{path}: frontmatter must end with a line containing only '---'")
        return None
    fm = {}
    for ln in lines[1:close]:
        if not ln.strip() or ln.lstrip().startswith("#"):
            continue
        # top-level keys are unindented; skip continuation / nested lines
        if ln[:1] in (" ", "\t", "-"):
            continue
        if ":" not in ln:
            continue
        key, _, val = ln.partition(":")
        fm[key.strip()] = val.strip()
    return fm


# --------------------------------------------------------------------------- #
# Skills
# --------------------------------------------------------------------------- #
def check_skills():
    skills_dir = os.path.join(ROOT, "skills")
    if not os.path.isdir(skills_dir):
        err("skills/ directory is missing")
        return
    dirs = sorted(
        d for d in os.listdir(skills_dir)
        if os.path.isdir(os.path.join(skills_dir, d))
    )
    if not dirs:
        err("skills/ contains no skill directories")
        return
    for d in dirs:
        skill_md = os.path.join(skills_dir, d, "SKILL.md")
        rel = os.path.relpath(skill_md, ROOT)
        if not os.path.isfile(skill_md):
            err(f"{rel}: missing SKILL.md")
            continue
        with open(skill_md, encoding="utf-8") as fh:
            text = fh.read()
        fm = parse_frontmatter(text, rel)
        if fm is None:
            continue
        if "name" not in fm:
            err(f"{rel}: frontmatter missing required field 'name'")
        if "description" not in fm or not fm.get("description"):
            err(f"{rel}: frontmatter missing/empty required field 'description'")
        name = fm.get("name")
        if name is not None and name != d:
            err(f"{rel}: frontmatter name '{name}' != directory name '{d}'")


# --------------------------------------------------------------------------- #
# JSON manifests
# --------------------------------------------------------------------------- #
def load_json(rel):
    path = os.path.join(ROOT, rel)
    if not os.path.isfile(path):
        err(f"{rel}: file is missing")
        return None
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except json.JSONDecodeError as e:
        err(f"{rel}: invalid JSON: {e}")
        return None


def check_manifests():
    claude = load_json(".claude-plugin/plugin.json")
    codex = load_json(".codex-plugin/plugin.json")

    required = ("name", "version", "description")
    for label, manifest in (("claude", claude), ("codex", codex)):
        if manifest is None:
            continue
        src = (".claude-plugin/plugin.json" if label == "claude"
               else ".codex-plugin/plugin.json")
        for field in required:
            if field not in manifest or manifest.get(field) in (None, ""):
                err(f"{src}: missing/empty required field '{field}'")

    # versions must match each other
    if claude is not None and codex is not None:
        cv = claude.get("version")
        xv = codex.get("version")
        if cv is not None and xv is not None and cv != xv:
            err(
                "version mismatch: .claude-plugin/plugin.json version "
                f"'{cv}' != .codex-plugin/plugin.json version '{xv}'"
            )

    # codex `skills` must point at an existing directory
    if codex is not None:
        skills_ref = codex.get("skills")
        if skills_ref in (None, ""):
            err(".codex-plugin/plugin.json: missing 'skills' field")
        else:
            skills_path = os.path.normpath(os.path.join(ROOT, skills_ref))
            if not os.path.isdir(skills_path):
                err(
                    ".codex-plugin/plugin.json: 'skills' points at "
                    f"'{skills_ref}' which is not an existing directory"
                )


def check_marketplace():
    mp = load_json(".claude-plugin/marketplace.json")
    if mp is None:
        return
    plugins = mp.get("plugins")
    if not isinstance(plugins, list) or not plugins:
        err(".claude-plugin/marketplace.json: 'plugins' must be a non-empty list")
        return
    names = {p.get("name") for p in plugins if isinstance(p, dict)}
    if "agent-talk" not in names:
        err(
            ".claude-plugin/marketplace.json: does not list the 'agent-talk' "
            f"plugin (found: {sorted(n for n in names if n)})"
        )


# --------------------------------------------------------------------------- #
# Markdown balance (nice-to-have)
# --------------------------------------------------------------------------- #
def check_markdown_balance():
    for rel in ("README.md", "docs/README.md"):
        path = os.path.join(ROOT, rel)
        if not os.path.isfile(path):
            # docs/README.md is optional; only flag a missing top-level README.
            if rel == "README.md":
                err(f"{rel}: file is missing")
            continue
        with open(path, encoding="utf-8") as fh:
            text = fh.read()
        fences = sum(1 for ln in text.splitlines() if ln.lstrip().startswith("```"))
        if fences % 2 != 0:
            err(f"{rel}: unbalanced ``` code fences (found {fences}, expected even)")
        opens = text.count("<details")
        closes = text.count("</details>")
        if opens != closes:
            err(
                f"{rel}: unbalanced <details> tags "
                f"({opens} <details>, {closes} </details>)"
            )


def main():
    check_skills()
    check_manifests()
    check_marketplace()
    check_markdown_balance()

    if _errors:
        print("Plugin validation FAILED:", file=sys.stderr)
        for e in _errors:
            print(f"  - {e}", file=sys.stderr)
        print(f"\n{len(_errors)} problem(s) found.", file=sys.stderr)
        return 1
    print("Plugin validation passed: all skill and manifest checks OK.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
