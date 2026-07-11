import importlib.util
import json
from pathlib import Path
import tempfile
import unittest


MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "redact_evidence.py"
ROOT = MODULE_PATH.parents[1]
SPEC = importlib.util.spec_from_file_location("redact_evidence", MODULE_PATH)
redactor = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(redactor)


class EvidenceRedactionTests(unittest.TestCase):
    def test_nested_secrets_and_identity_are_redacted(self):
        source = {
            "request_headers": {"Authorization": "Bearer eyJaaa.bbb.ccc"},
            "request_body": {
                "email": "operator@example.test",
                "password": "secret",
                "passwordRepeat": "secret",
            },
            "response_body": {"authentication": {"token": "eyJaaa.bbb.ccc"}},
            "status": 201,
        }
        result = redactor.redact(source)
        rendered = json.dumps(result)
        self.assertNotIn("operator@example.test", rendered)
        self.assertNotIn("secret", rendered)
        self.assertNotIn("eyJaaa", rendered)
        self.assertEqual(result["status"], 201)

    def test_directory_redaction_preserves_json_files(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "source"
            destination = root / "destination"
            source.mkdir()
            (source / "exchange.json").write_text(
                json.dumps({"email": "test@example.test", "role": "admin"}),
                encoding="utf-8",
            )
            self.assertEqual(redactor.redact_directory(source, destination), 1)
            output = json.loads((destination / "exchange.json").read_text())
            self.assertEqual(output["email"], "<redacted-email>")
            self.assertEqual(output["role"], "admin")

    def test_tracked_fixture_contains_no_raw_credentials_or_jwts(self):
        evidence = ROOT / "examples" / "juice-shop-e2e" / "evidence"
        files = sorted(evidence.glob("*.json"))
        self.assertEqual(len(files), 6)
        for path in files:
            text = path.read_text(encoding="utf-8")
            self.assertNotIn("Bearer ", text, path.name)
            self.assertNotRegex(text, r"\beyJ[A-Za-z0-9_-]+\.", path.name)
            self.assertNotRegex(text, r"[A-Za-z0-9._%+-]+@example\.test", path.name)
            self.assertNotIn("RedCodeE2E!", text, path.name)


if __name__ == "__main__":
    unittest.main()
