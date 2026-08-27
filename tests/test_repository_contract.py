import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def parse_jsonc(path: Path):
    text = path.read_text(encoding="utf-8")
    output = []
    in_string = False
    escaped = False
    index = 0

    while index < len(text):
        char = text[index]
        next_char = text[index + 1] if index + 1 < len(text) else ""
        if in_string:
            output.append(char)
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            index += 1
            continue
        if char == '"':
            in_string = True
            output.append(char)
            index += 1
            continue
        if char == "/" and next_char == "/":
            index = text.find("\n", index)
            if index == -1:
                break
            output.append("\n")
            index += 1
            continue
        output.append(char)
        index += 1

    normalized = re.sub(r",\s*([}\]])", r"\1", "".join(output))
    return json.loads(normalized)


def frontmatter(path: Path):
    lines = path.read_text(encoding="utf-8").splitlines()
    if not lines or lines[0] != "---":
        return {}
    result = {}
    for line in lines[1:]:
        if line == "---":
            break
        if ":" in line:
            key, value = line.split(":", 1)
            result[key.strip()] = value.strip().strip('"')
    return result


class RepositoryContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.config = parse_jsonc(ROOT / "opencode.jsonc")

    def test_configured_agents_match_prompt_files(self):
        configured = set(self.config["agent"]) - {"compaction"}
        prompts = {path.stem for path in (ROOT / ".opencode/agent").glob("*.md")}
        self.assertEqual(configured, prompts)
        self.assertEqual(frontmatter(ROOT / ".opencode/agent/redcode.md")["mode"], "primary")
        for agent in prompts - {"redcode"}:
            self.assertEqual(
                frontmatter(ROOT / ".opencode/agent" / f"{agent}.md")["mode"],
                "subagent",
            )

    def test_command_agent_references_exist(self):
        configured = set(self.config["agent"])
        for path in (ROOT / ".opencode/command").glob("*.md"):
            agent = frontmatter(path).get("agent")
            if agent:
                self.assertIn(agent, configured, path.name)

    def test_skill_names_match_directories(self):
        for path in (ROOT / ".opencode/skills").glob("*/SKILL.md"):
            metadata = frontmatter(path)
            self.assertEqual(metadata.get("name"), path.parent.name, str(path))
            self.assertTrue(metadata.get("description"), str(path))

    def test_theme_has_light_and_dark_values(self):
        theme = json.loads(
            (ROOT / ".opencode/themes/redcode.json").read_text(encoding="utf-8")
        )
        for key, value in theme["theme"].items():
            self.assertEqual(set(value), {"dark", "light"}, key)

    def test_internal_markdown_links_resolve(self):
        markdown_files = list(ROOT.glob("*.md"))
        for directory in ("docs", "examples", ".opencode/agent", ".opencode/command", ".opencode/skills"):
            markdown_files.extend((ROOT / directory).rglob("*.md"))

        for path in markdown_files:
            links = re.findall(r"\]\(([^)]+)\)", path.read_text(encoding="utf-8"))
            for link in links:
                target = link.split("#", 1)[0]
                if not target or re.match(
                    r"^[a-z][a-z0-9+.-]*:", target, re.IGNORECASE
                ):
                    continue
                self.assertTrue((path.parent / target).resolve().exists(), f"{path}: {link}")

    def test_json_contract_files_parse(self):
        for relative in (
            ".env.example",
            "engagement.example.json",
            "engagement.schema.json",
            "tui.json",
            ".opencode/themes/redcode.json",
        ):
            if relative.endswith(".json"):
                json.loads((ROOT / relative).read_text(encoding="utf-8"))

    def test_runtime_packages_are_pinned(self):
        config = (ROOT / "opencode.jsonc").read_text(encoding="utf-8")
        setup = (ROOT / "setup.sh").read_text(encoding="utf-8")
        self.assertNotIn("@latest", config)
        self.assertNotIn("@latest", setup)

    def test_bug_bounty_agent_is_local_assistance_only(self):
        agent = self.config["agent"]["bugbounty"]
        for permission in ("filesystem_*", "sqlite_*"):
            self.assertEqual(agent["permission"][permission], "allow")
        for permission in ("hexstrike_*", "burp_*", "playwright_*", "fetch_*"):
            self.assertEqual(agent["permission"][permission], "deny")
        self.assertTrue(self.config["mcp"]["burp"]["enabled"])
        self.assertTrue((ROOT / ".opencode/command/bugbounty.md").is_file())
        self.assertTrue((ROOT / ".opencode/skills/mappa-bugbounty/SKILL.md").is_file())

    def test_schema_contains_bug_bounty_state(self):
        schema = (ROOT / "schema.sql").read_text(encoding="utf-8")
        for table in (
            "bug_bounty_programs", "identities", "endpoints",
            "application_workflows", "hypotheses", "hunt_sessions",
            "bug_bounty_submissions", "policy_snapshots",
            "program_scope_rules", "program_restrictions", "burp_import_runs",
            "burp_message_refs", "test_plans", "approval_executions",
            "hypothesis_events",
        ):
            self.assertIn(f"CREATE TABLE IF NOT EXISTS {table}", schema)

    def test_bug_bounty_assistant_control_plane_is_tracked(self):
        launcher = (ROOT / "redcode").read_text(encoding="utf-8")
        controller = ROOT / "scripts" / "bugbounty_control.py"
        docs = ROOT / "docs" / "bugbounty-assistant.md"
        self.assertTrue(controller.is_file())
        self.assertTrue(docs.is_file())
        self.assertIn('bugbounty)', launcher)
        self.assertIn("bugbounty_control.py", launcher)

    def test_launcher_enforces_configured_command_prefix(self):
        launcher = (ROOT / "redcode").read_text(encoding="utf-8")
        self.assertIn(': "${REDCODE_COMMAND_PREFIX:=proxychains4 -q}"', launcher)
        self.assertIn("exec_with_prefix python3", launcher)
        self.assertIn("exec_with_prefix opencode", launcher)
        self.assertIn("run_with_prefix python3", launcher)

    def test_python_dependencies_use_project_virtualenv(self):
        setup = (ROOT / "setup.sh").read_text(encoding="utf-8")
        launcher = (ROOT / "redcode").read_text(encoding="utf-8")
        gitignore = (ROOT / ".gitignore").read_text(encoding="utf-8")
        self.assertIn('VENV_DIR="$PROJECT_DIR/.venv"', setup)
        self.assertIn('"$VENV_PYTHON" -m pip install', setup)
        self.assertNotIn("pip3 install", setup)
        self.assertIn('$DIR/.venv/bin', launcher)
        self.assertIn(".venv/", gitignore.splitlines())
        self.assertIn('pip install "mcp>=1.6,<3" ', setup)

    def test_setup_configures_narrow_proxychains_bypasses(self):
        setup = (ROOT / "setup.sh").read_text(encoding="utf-8")
        env_example = (ROOT / ".env.example").read_text(encoding="utf-8")
        self.assertIn("localnet 127.0.0.0/255.0.0.0", setup)
        self.assertIn("localnet ::1/128", setup)
        self.assertIn("255.255.255.255", setup)
        self.assertIn(".redcode-backup", setup)
        self.assertIn("--max-time 3", setup)
        self.assertIn("BURP_MCP_URL=http://10.10.10.10:9876", env_example)
        self.assertNotIn("BURP_MCP_URL=http://10.10.10.10:9876/mcp", env_example)

    def test_arsenal_bridge_is_disabled_until_launcher_handshake(self):
        arsenal = self.config["mcp"]["arsenal"]
        self.assertFalse(arsenal["enabled"])
        self.assertEqual(
            arsenal["command"], ["python3", "scripts/arsenal_mcp.py"]
        )
        self.assertEqual(self.config["permission"]["arsenal_*"], "deny")
        self.assertTrue((ROOT / "scripts/arsenal_client.py").is_file())
        self.assertTrue((ROOT / "scripts/arsenal_mcp.py").is_file())

        from scripts import redcode_control as control

        self.assertEqual(
            control.OPENCODE_AGENTS,
            set(self.config["agent"]) - {"compaction"},
        )

    def test_tool_installer_has_explicit_profiles(self):
        installer = (ROOT / "install-tools.sh").read_text(encoding="utf-8")
        for profile in ("core", "web", "network", "ctf"):
            self.assertIn(f"[{profile}]", installer)
        self.assertNotIn("curl |", installer)
        self.assertNotIn("wget |", installer)


if __name__ == "__main__":
    unittest.main()
