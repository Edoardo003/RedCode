import importlib.util
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "redcode_control.py"
SPEC = importlib.util.spec_from_file_location("redcode_control", MODULE_PATH)
control = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(control)


class ManifestTests(unittest.TestCase):
    def setUp(self):
        self.manifest = {
            "schema_version": 1,
            "name": "example-assessment",
            "workflow": "assessment",
            "mode": "normal",
            "in_scope": ["example.test", "*.example.test", "10.10.0.0/16"],
            "out_of_scope": ["admin.example.test", "10.10.99.10"],
            "allowed_actions": ["recon", "scan", "report"],
            "rate_limit_per_second": 10,
            "notes": "",
        }

    def test_valid_manifest(self):
        self.assertEqual(control.validate_manifest(self.manifest), [])

    def test_ctf_manifest_rejects_assessment_actions(self):
        self.manifest["workflow"] = "ctf"
        self.manifest["allowed_actions"] = ["ctf", "scan"]
        errors = control.validate_manifest(self.manifest)
        self.assertTrue(any("CTF manifests" in error for error in errors))

    def test_ctf_manifest_rejects_aggressive_mode(self):
        self.manifest["workflow"] = "ctf"
        self.manifest["mode"] = "aggressive"
        self.manifest["allowed_actions"] = ["ctf"]
        errors = control.validate_manifest(self.manifest)
        self.assertTrue(any("normal mode" in error for error in errors))

    def test_scope_allows_exact_domain(self):
        allowed, _ = control.scope_decision(self.manifest, "example.test", "scan")
        self.assertTrue(allowed)

    def test_scope_allows_wildcard_subdomain(self):
        allowed, _ = control.scope_decision(
            self.manifest, "https://api.example.test/v1", "recon"
        )
        self.assertTrue(allowed)

    def test_out_of_scope_takes_precedence(self):
        allowed, reason = control.scope_decision(
            self.manifest, "admin.example.test", "scan"
        )
        self.assertFalse(allowed)
        self.assertIn("out-of-scope", reason)

    def test_scope_allows_cidr(self):
        allowed, _ = control.scope_decision(self.manifest, "10.10.20.5", "scan")
        self.assertTrue(allowed)

    def test_scope_denies_disallowed_action(self):
        allowed, reason = control.scope_decision(
            self.manifest, "example.test", "exploit"
        )
        self.assertFalse(allowed)
        self.assertIn("not allowed", reason)

    def test_scope_allows_bug_bounty_hunt(self):
        self.manifest["allowed_actions"].append("hunt")
        allowed, _ = control.scope_decision(self.manifest, "example.test", "hunt")
        self.assertTrue(allowed)

    def test_url_rule_matches_origin_and_path(self):
        manifest = dict(self.manifest)
        manifest["in_scope"] = ["http://127.0.0.1:3000/api"]
        allowed, _ = control.scope_decision(
            manifest, "http://127.0.0.1:3000/api/Users", "scan"
        )
        self.assertTrue(allowed)
        denied, _ = control.scope_decision(
            manifest, "http://127.0.0.1:3000/rest/admin", "scan"
        )
        self.assertFalse(denied)


class ArsenalRuntimeConfigTests(unittest.TestCase):
    def test_arsenal_override_disables_direct_network_tools_for_every_agent(self):
        config = control.arsenal_opencode_override(
            json.dumps({"share": "disabled", "permission": {"bash": "ask"}})
        )

        self.assertEqual(config["share"], "disabled")
        self.assertEqual(config["permission"]["bash"], "deny")
        self.assertTrue(config["mcp"]["arsenal"]["enabled"])
        for server in control.ARSENAL_DISABLED_MCP:
            self.assertFalse(config["mcp"][server]["enabled"])
        for agent in control.OPENCODE_AGENTS:
            permissions = config["agent"][agent]["permission"]
            self.assertEqual(permissions["arsenal_*"], "allow")
            for tool in control.ARSENAL_DENIED_TOOLS:
                self.assertEqual(permissions[tool], "deny")

    def test_arsenal_override_rejects_invalid_inline_config(self):
        with self.assertRaisesRegex(ValueError, "invalid JSON"):
            control.arsenal_opencode_override("not-json")


class DatabaseTests(unittest.TestCase):
    def test_fresh_database_uses_schema_v6(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            db = Path(temp_dir) / "fresh.db"
            version, backup = control.migrate_database(db)
            self.assertEqual(version, 6)
            self.assertIsNone(backup)
            connection = sqlite3.connect(db)
            self.assertEqual(connection.execute("PRAGMA user_version").fetchone()[0], 6)
            self.assertIn("engagements", control.table_names(connection))
            self.assertIn("phase", control.table_columns(connection, "scans"))
            for table in (
                "bug_bounty_programs", "identities", "endpoints",
                "application_workflows", "hypotheses", "hunt_sessions",
                "bug_bounty_submissions", "policy_snapshots",
                "program_scope_rules", "program_restrictions", "burp_import_runs",
                "burp_message_refs", "test_plans", "approval_executions",
                "hypothesis_events",
            ):
                self.assertIn(table, control.table_names(connection))
            self.assertIn("policy_snapshot_id", control.table_columns(connection, "test_plans"))
            self.assertTrue(
                {"source_message_ref", "request_fingerprint"}
                <= control.table_columns(connection, "burp_message_refs")
            )
            connection.close()
            repeated_version, repeated_backup = control.migrate_database(db)
            self.assertEqual(repeated_version, 6)
            self.assertIsNone(repeated_backup)

    def test_v1_database_is_backed_up_and_migrated(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            db = Path(temp_dir) / "legacy.db"
            connection = sqlite3.connect(db)
            connection.executescript(
                """
                CREATE TABLE targets (
                  id INTEGER PRIMARY KEY AUTOINCREMENT,
                  domain TEXT NOT NULL UNIQUE
                );
                CREATE TABLE findings (
                  id INTEGER PRIMARY KEY AUTOINCREMENT,
                  target_id INTEGER,
                  finding_id TEXT UNIQUE NOT NULL,
                  phase TEXT NOT NULL,
                  type TEXT NOT NULL,
                  severity TEXT NOT NULL,
                  title TEXT NOT NULL
                );
                CREATE TABLE scans (
                  id INTEGER PRIMARY KEY AUTOINCREMENT,
                  target_id INTEGER,
                  tool TEXT NOT NULL,
                  command TEXT,
                  status TEXT DEFAULT 'running'
                );
                CREATE TABLE credentials (
                  id INTEGER PRIMARY KEY AUTOINCREMENT,
                  target_id INTEGER,
                  finding_id INTEGER
                );
                INSERT INTO targets(domain) VALUES ('legacy.example.test');
                """
            )
            connection.close()

            version, backup = control.migrate_database(db)
            self.assertEqual(version, 6)
            self.assertIsNotNone(backup)
            self.assertTrue(backup.exists())

            connection = sqlite3.connect(db)
            self.assertEqual(connection.execute("PRAGMA user_version").fetchone()[0], 6)
            self.assertEqual(
                connection.execute("SELECT domain FROM targets").fetchone()[0],
                "legacy.example.test",
            )
            scan_columns = control.table_columns(connection, "scans")
            self.assertTrue({"phase", "subdomain", "exit_code"} <= scan_columns)
            connection.close()

    def test_v2_database_is_backed_up_and_migrated(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            db = Path(temp_dir) / "v2.db"
            connection = sqlite3.connect(db)
            connection.executescript(
                """
                CREATE TABLE targets (id INTEGER PRIMARY KEY, domain TEXT UNIQUE);
                CREATE TABLE findings (id INTEGER PRIMARY KEY, finding_id TEXT UNIQUE);
                CREATE TABLE scans (
                  id INTEGER PRIMARY KEY, target_id INTEGER, tool TEXT
                );
                CREATE TABLE credentials (id INTEGER PRIMARY KEY);
                CREATE TABLE schema_migrations (
                  version INTEGER PRIMARY KEY, name TEXT NOT NULL,
                  applied_at TEXT DEFAULT (datetime('now'))
                );
                INSERT INTO schema_migrations(version, name) VALUES (2, 'control_plane');
                """
            )
            connection.executescript(
                (Path(__file__).resolve().parents[1] / "migrations" / "002_control_plane.sql").read_text(encoding="utf-8")
            )
            connection.execute("PRAGMA user_version = 2")
            connection.commit()
            connection.close()

            version, backup = control.migrate_database(db)
            self.assertEqual(version, 6)
            self.assertIsNotNone(backup)
            connection = sqlite3.connect(db)
            self.assertEqual(connection.execute("PRAGMA user_version").fetchone()[0], 6)
            self.assertIn("hypotheses", control.table_names(connection))
            self.assertIn("endpoints", control.table_names(connection))
            connection.close()

    def test_v3_database_is_backed_up_and_migrated_to_assistant_schema(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            db = Path(temp_dir) / "v3.db"
            connection = sqlite3.connect(db)
            connection.executescript(
                (Path(__file__).resolve().parents[1] / "schema.sql")
                .read_text(encoding="utf-8")
                .replace("PRAGMA user_version = 6;", "PRAGMA user_version = 3;")
            )
            for table in (
                "policy_snapshots", "program_scope_rules", "program_restrictions",
                "burp_import_runs", "burp_message_refs", "test_plans",
                "approval_executions", "hypothesis_events",
            ):
                connection.execute(f"DROP TABLE {table}")
            connection.execute("DELETE FROM schema_migrations WHERE version IN (4, 5, 6)")
            connection.commit()
            connection.close()

            version, backup = control.migrate_database(db)
            self.assertEqual(version, 6)
            self.assertIsNotNone(backup)
            self.assertTrue(backup.exists())
            connection = sqlite3.connect(db)
            self.assertEqual(connection.execute("PRAGMA user_version").fetchone()[0], 6)
            self.assertIn("test_plans", control.table_names(connection))
            self.assertIn("hypothesis_events", control.table_names(connection))
            self.assertEqual(
                connection.execute("SELECT COUNT(*) FROM schema_migrations WHERE version = 6").fetchone()[0],
                1,
            )
            self.assertIn("policy_snapshot_id", control.table_columns(connection, "test_plans"))
            self.assertTrue(
                {"source_message_ref", "request_fingerprint"}
                <= control.table_columns(connection, "burp_message_refs")
            )
            connection.close()


class ManifestFileTests(unittest.TestCase):
    def test_example_manifest_is_valid(self):
        example = json.loads(
            (Path(__file__).resolve().parents[1] / "engagement.example.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(control.validate_manifest(example), [])

    def test_activation_writes_opencode_context(self):
        example_path = Path(__file__).resolve().parents[1] / "engagement.example.json"
        example = json.loads(example_path.read_text(encoding="utf-8"))
        original_root = control.ROOT
        try:
            with tempfile.TemporaryDirectory() as temp_dir:
                control.ROOT = Path(temp_dir)
                context = control.activate_manifest(example_path, example, quiet=True)
                self.assertTrue(context.is_file())
                activated = json.loads(context.read_text(encoding="utf-8"))
                self.assertEqual(activated["name"], "juice-shop-local")
                self.assertIn("activated_at", activated)
        finally:
            control.ROOT = original_root

    def test_runtime_profile_replaces_stale_mode(self):
        original_root = control.ROOT
        try:
            with tempfile.TemporaryDirectory() as temp_dir:
                control.ROOT = Path(temp_dir)
                path = control.activate_runtime_mode("arsenal", quiet=True)
                control.activate_runtime_mode("standalone", quiet=True)
                runtime = json.loads(path.read_text(encoding="utf-8"))
                self.assertEqual(runtime["mode"], "standalone")
        finally:
            control.ROOT = original_root


if __name__ == "__main__":
    unittest.main()
