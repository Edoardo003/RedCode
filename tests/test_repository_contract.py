import json
from pathlib import Path
import re
import unittest


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

    def test_readme_internal_links_resolve(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        links = re.findall(r"\]\(([^)]+)\)", readme)
        for link in links:
            target = link.split("#", 1)[0]
            if not target or "://" in target:
                continue
            self.assertTrue((ROOT / target).exists(), link)

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

    def test_tool_installer_has_explicit_profiles(self):
        installer = (ROOT / "install-tools.sh").read_text(encoding="utf-8")
        for profile in ("core", "web", "network", "ctf"):
            self.assertIn(f"[{profile}]", installer)
        self.assertNotIn("curl |", installer)
        self.assertNotIn("wget |", installer)


if __name__ == "__main__":
    unittest.main()
