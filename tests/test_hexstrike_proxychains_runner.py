import importlib.util
from pathlib import Path
import unittest


MODULE_PATH = (
    Path(__file__).resolve().parents[1] / "scripts" / "hexstrike_proxychains_runner.py"
)
SPEC = importlib.util.spec_from_file_location("hexstrike_proxychains_runner", MODULE_PATH)
runner = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(runner)


class ProxychainsRunnerTests(unittest.TestCase):
    def test_prefixes_shell_command(self):
        self.assertEqual(
            runner.prefix_command("nmap -sV example.test", ["proxychains4", "-q"], shell=True),
            "proxychains4 -q nmap -sV example.test",
        )

    def test_prefixes_argument_list(self):
        self.assertEqual(
            runner.prefix_command(["nuclei", "-u", "https://example.test"], ["proxychains4", "-q"], shell=False),
            ["proxychains4", "-q", "nuclei", "-u", "https://example.test"],
        )

    def test_does_not_duplicate_prefix(self):
        self.assertEqual(
            runner.prefix_command("proxychains4 -q nmap -sV example.test", ["proxychains4", "-q"], shell=True),
            "proxychains4 -q nmap -sV example.test",
        )


if __name__ == "__main__":
    unittest.main()
