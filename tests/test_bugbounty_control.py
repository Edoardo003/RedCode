import contextlib
import importlib.util
import io
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import sqlite3
import sys
import tempfile
import threading
import unittest


ROOT = Path(__file__).resolve().parents[1]
CONTROL_PATH = ROOT / "scripts" / "redcode_control.py"
CONTROL_SPEC = importlib.util.spec_from_file_location("redcode_control", CONTROL_PATH)
control = importlib.util.module_from_spec(CONTROL_SPEC)
assert CONTROL_SPEC.loader is not None
CONTROL_SPEC.loader.exec_module(control)
sys.modules["redcode_control"] = control

BUGBOUNTY_PATH = ROOT / "scripts" / "bugbounty_control.py"
BUGBOUNTY_SPEC = importlib.util.spec_from_file_location("bugbounty_control", BUGBOUNTY_PATH)
bugbounty = importlib.util.module_from_spec(BUGBOUNTY_SPEC)
assert BUGBOUNTY_SPEC.loader is not None
BUGBOUNTY_SPEC.loader.exec_module(bugbounty)


class BugBountyControlTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.db = self.root / "redcode.db"
        self.manifest = self.root / "engagement.json"
        self.policy = self.root / "policy.md"
        self.manifest.write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "name": "example-program",
                    "workflow": "assessment",
                    "mode": "normal",
                    "in_scope": ["*.example.test"],
                    "out_of_scope": ["admin.example.test"],
                    "allowed_actions": ["hunt", "exploit"],
                    "rate_limit_per_second": 2,
                    "notes": "",
                }
            ),
            encoding="utf-8",
        )
        self.policy.write_text("Authorized example policy", encoding="utf-8")
        self.original_control_root = control.ROOT
        self.original_bugbounty_root = bugbounty.ROOT
        control.ROOT = self.root
        bugbounty.ROOT = self.root
        (self.root / "migrations").mkdir()
        (self.root / "schema.sql").write_text((ROOT / "schema.sql").read_text(encoding="utf-8"), encoding="utf-8")
        for source in (ROOT / "migrations").glob("*.sql"):
            (self.root / "migrations" / source.name).write_text(source.read_text(encoding="utf-8"), encoding="utf-8")

    def tearDown(self):
        control.ROOT = self.original_control_root
        bugbounty.ROOT = self.original_bugbounty_root
        self.temp.cleanup()

    def run_command(self, *arguments):
        output = io.StringIO()
        with contextlib.redirect_stdout(output), contextlib.redirect_stderr(output):
            result = bugbounty.main(
                [*arguments, "--db", str(self.db), "--manifest", str(self.manifest)]
            )
        return result, output.getvalue()

    def fetchone(self, query, parameters=()):
        connection = sqlite3.connect(self.db)
        connection.row_factory = sqlite3.Row
        try:
            return connection.execute(query, parameters).fetchone()
        finally:
            connection.close()

    def fetchall(self, query, parameters=()):
        connection = sqlite3.connect(self.db)
        connection.row_factory = sqlite3.Row
        try:
            return connection.execute(query, parameters).fetchall()
        finally:
            connection.close()

    def test_end_to_end_human_approved_workflow(self):
        result, _ = self.run_command(
            "onboard",
            "--program-name",
            "Example",
            "--policy-file",
            str(self.policy),
            "--scope",
            "*.example.test",
            "--reviewed-by",
            "analyst",
        )
        self.assertEqual(result, 0)
        self.assertEqual(
            self.run_command("identity", "add", "--label", "user-a", "--role", "member")[0],
            0,
        )

        export = self.root / "selected.json"
        export.write_text(
            json.dumps(
                {
                    "messages": [
                        {
                            "id": "history-1",
                            "url": "https://alice:login-secret@api.example.test/api/orders/123?token=secret&view=private#session-secret",
                            "method": "GET",
                            "headers": {
                                "Authorization": "Bearer secret-token",
                                "Cookie": "session=secret-cookie",
                                "Content-Type": "application/json",
                            },
                            "body": {"account": "alice", "password": "secret-password"},
                        },
                        {
                            "id": "history-2",
                            "url": "https://api.example.test/api/orders/123",
                            "method": "PATCH",
                            "headers": {"Authorization": "Bearer secret-token"},
                            "body": {"state": "updated"},
                        },
                        {
                            "id": "excluded",
                            "url": "https://admin.example.test/api/users/1",
                            "method": "GET",
                        },
                    ]
                }
            ),
            encoding="utf-8",
        )
        result, output = self.run_command(
            "ingest",
            "--file",
            str(export),
            "--identity",
            "user-a",
            "--include-bodies",
        )
        self.assertEqual(result, 0, output)
        self.assertIn("2 message(s) imported, 1 skipped", output)
        self.assertEqual(self.run_command("ingest", "--file", str(export), "--identity", "user-a")[0], 0)
        self.assertEqual(
            self.fetchone("SELECT COUNT(*) AS count FROM burp_message_refs")["count"], 2
        )
        artifact = next((self.root / "output").rglob("burp-import-*.redacted.json"))
        artifact_text = artifact.read_text(encoding="utf-8")
        self.assertNotIn("secret-token", artifact_text)
        self.assertNotIn("secret-cookie", artifact_text)
        self.assertNotIn("secret-password", artifact_text)
        self.assertNotIn("alice", artifact_text)
        self.assertIn("{id}", self.fetchone("SELECT path_template FROM endpoints")["path_template"])
        persisted_scope = self.fetchone("SELECT scope FROM targets WHERE domain = 'api.example.test'")["scope"]
        self.assertEqual(persisted_scope, "https://api.example.test")
        self.assertNotIn("secret", persisted_scope)

        self.assertEqual(self.run_command("map")[0], 0)
        self.assertEqual(self.run_command("queue", "--generate")[0], 0)
        hypothesis = self.fetchone("SELECT hypothesis_id FROM hypotheses ORDER BY priority DESC LIMIT 1")
        self.assertIsNotNone(hypothesis)
        result, _ = self.run_command(
            "plan",
            "create",
            "--hypothesis",
            hypothesis["hypothesis_id"],
            "--identity",
            "user-a",
            "--control",
            "Read an object owned by user-a",
            "--single-change",
            "Use one already-authorized object reference",
            "--expected-result",
            "Server rejects unauthorized access",
            "--minimum-proof",
            "One redacted authorization response",
            "--stop-condition",
            "Stop at first unexpected response",
            "--cleanup",
            "No state change expected",
            "--created-by",
            "analyst",
        )
        self.assertEqual(result, 0)
        plan = self.fetchone("SELECT id, plan_sha256 FROM test_plans")
        self.assertEqual(
            self.run_command(
                "approve", str(plan["id"]), "--approved-by", "analyst", "--confirm", "wrong"
            )[0],
            1,
        )
        self.assertEqual(
            self.run_command(
                "approve",
                str(plan["id"]),
                "--approved-by",
                "analyst",
                "--confirm",
                plan["plan_sha256"],
            )[0],
            0,
        )
        self.assertEqual(self.run_command("begin-test", str(plan["id"]), "--operator", "analyst")[0], 0)
        evidence = self.root / "output" / "example-program" / "scans" / "mappa" / "evidence.md"
        evidence.write_text("Redacted control and approved variation differ.", encoding="utf-8")
        self.assertEqual(
            self.run_command(
                "record",
                str(plan["id"]),
                "--outcome",
                "candidate",
                "--request-count",
                "1",
                "--evidence",
                str(evidence),
                "--summary",
                "Minimal impact evidence captured",
                "--operator",
                "analyst",
            )[0],
            0,
        )
        evidence.write_text("Modified after the approved test.", encoding="utf-8")
        self.assertEqual(
            self.run_command(
                "confirm",
                "--hypothesis",
                hypothesis["hypothesis_id"],
                "--title",
                "Cross-account order access",
                "--severity",
                "high",
                "--impact",
                "An authorized user can access another user's order.",
                "--reviewed-by",
                "analyst",
            )[0],
            1,
        )
        evidence.write_text("Redacted control and approved variation differ.", encoding="utf-8")
        self.assertEqual(
            self.run_command(
                "confirm",
                "--hypothesis",
                hypothesis["hypothesis_id"],
                "--title",
                "Cross-account order access",
                "--severity",
                "high",
                "--impact",
                "An authorized user can access another user's order.",
                "--reviewed-by",
                "analyst",
            )[0],
            0,
        )
        self.assertEqual(
            self.run_command("report", "--hypothesis", hypothesis["hypothesis_id"])[0],
            0,
        )
        report = next((self.root / "output").rglob("*-hackerone-draft.md"))
        self.assertIn("Draft only", report.read_text(encoding="utf-8"))
        self.assertEqual(self.fetchone("SELECT status FROM hypotheses")["status"], "confirmed")

    def test_program_policy_prohibits_action_even_when_manifest_allows_it(self):
        result, _ = self.run_command(
            "onboard",
            "--program-name",
            "Example",
            "--policy-file",
            str(self.policy),
            "--scope",
            "*.example.test",
            "--prohibit-action",
            "exploit",
            "--restriction-reason",
            "No active testing",
            "--reviewed-by",
            "analyst",
        )
        self.assertEqual(result, 0)
        result, output = self.run_command("check", "api.example.test", "exploit")
        self.assertEqual(result, 1)
        self.assertIn("program policy prohibits exploit", output)

    def test_policy_snapshot_tampering_fails_closed(self):
        self.assertEqual(
            self.run_command(
                "onboard",
                "--program-name",
                "Example",
                "--policy-file",
                str(self.policy),
                "--scope",
                "*.example.test",
                "--reviewed-by",
                "analyst",
            )[0],
            0,
        )
        snapshot = self.fetchone("SELECT snapshot_path FROM policy_snapshots")
        (self.root / snapshot["snapshot_path"]).write_text("tampered", encoding="utf-8")
        result, output = self.run_command("check", "api.example.test", "hunt")
        self.assertEqual(result, 1)
        self.assertIn("no longer matches", output)

    def test_policy_refresh_cancels_active_plan_and_can_be_repeated(self):
        onboard_args = (
            "onboard",
            "--program-name",
            "Example",
            "--policy-file",
            str(self.policy),
            "--scope",
            "*.example.test",
            "--reviewed-by",
            "analyst",
        )
        self.assertEqual(self.run_command(*onboard_args)[0], 0)
        connection = sqlite3.connect(self.db)
        try:
            engagement_id = connection.execute("SELECT id FROM engagements").fetchone()[0]
            connection.execute(
                "INSERT INTO targets(domain, scope, type) VALUES ('api.example.test', 'https://api.example.test', 'web')"
            )
            target_id = connection.execute("SELECT id FROM targets").fetchone()[0]
            connection.execute(
                "INSERT INTO endpoints "
                "(engagement_id, target_id, endpoint_key, host, method, path_template, protocol, state_change) "
                "VALUES (?, ?, 'https://api.example.test GET /api/orders/{id}', 'api.example.test', 'GET', '/api/orders/{id}', 'https', 0)",
                (engagement_id, target_id),
            )
            endpoint_id = connection.execute("SELECT id FROM endpoints").fetchone()[0]
            connection.execute(
                "INSERT INTO hypotheses (engagement_id, target_id, endpoint_id, hypothesis_id, statement) "
                "VALUES (?, ?, ?, 'HYP-REFRESH', 'Refresh test')",
                (engagement_id, target_id, endpoint_id),
            )
            connection.commit()
        finally:
            connection.close()
        self.assertEqual(
            self.run_command(
                "plan",
                "create",
                "--hypothesis",
                "HYP-REFRESH",
                "--control",
                "Read one known object",
                "--single-change",
                "Use one permitted object reference",
                "--expected-result",
                "Server rejects unauthorized access",
                "--minimum-proof",
                "One redacted response",
                "--stop-condition",
                "Stop after unexpected behavior",
                "--cleanup",
                "No state change",
                "--created-by",
                "analyst",
            )[0],
            0,
        )
        plan = self.fetchone("SELECT id, plan_sha256 FROM test_plans")
        self.assertEqual(
            self.run_command(
                "approve",
                str(plan["id"]),
                "--approved-by",
                "analyst",
                "--confirm",
                plan["plan_sha256"],
            )[0],
            0,
        )
        self.policy.write_text("Updated authorized example policy", encoding="utf-8")
        self.assertEqual(self.run_command(*onboard_args)[0], 0)
        self.assertEqual(self.fetchone("SELECT status FROM test_plans")["status"], "cancelled")
        self.assertEqual(self.fetchone("SELECT status FROM hypotheses")["status"], "queued")
        self.assertEqual(self.run_command(*onboard_args)[0], 0)

    def test_expired_execution_cannot_be_recorded(self):
        self.assertEqual(
            self.run_command(
                "onboard",
                "--program-name",
                "Example",
                "--policy-file",
                str(self.policy),
                "--scope",
                "*.example.test",
                "--reviewed-by",
                "analyst",
            )[0],
            0,
        )
        connection = sqlite3.connect(self.db)
        try:
            engagement_id = connection.execute("SELECT id FROM engagements").fetchone()[0]
            snapshot_id = connection.execute("SELECT id FROM policy_snapshots").fetchone()[0]
            connection.execute(
                "INSERT INTO targets(domain, scope, type) VALUES ('api.example.test', 'https://api.example.test', 'web')"
            )
            target_id = connection.execute("SELECT id FROM targets").fetchone()[0]
            connection.execute(
                "INSERT INTO endpoints "
                "(engagement_id, target_id, endpoint_key, host, method, path_template, protocol) "
                "VALUES (?, ?, 'https://api.example.test GET /api/orders/{id}', 'api.example.test', 'GET', '/api/orders/{id}', 'https')",
                (engagement_id, target_id),
            )
            endpoint_id = connection.execute("SELECT id FROM endpoints").fetchone()[0]
            connection.execute(
                "INSERT INTO hypotheses (engagement_id, target_id, endpoint_id, hypothesis_id, statement, status) "
                "VALUES (?, ?, ?, 'HYP-EXPIRED', 'Expired authorization test', 'testing')",
                (engagement_id, target_id, endpoint_id),
            )
            hypothesis_id = connection.execute("SELECT id FROM hypotheses").fetchone()[0]
            connection.execute(
                "INSERT INTO test_plans "
                "(engagement_id, hypothesis_id, policy_snapshot_id, action, target, method, path_template, "
                "max_requests, rate_limit_per_second, plan_json, plan_sha256, status, expires_at) "
                "VALUES (?, ?, ?, 'exploit', 'https://api.example.test/api/orders/{id}', 'GET', '/api/orders/{id}', "
                "2, 1, '{}', 'test-hash', 'testing', '2000-01-01T00:00:00+00:00')",
                (engagement_id, hypothesis_id, snapshot_id),
            )
            plan_id = connection.execute("SELECT id FROM test_plans").fetchone()[0]
            connection.execute("INSERT INTO approval_executions(test_plan_id) VALUES (?)", (plan_id,))
            connection.commit()
        finally:
            connection.close()
        evidence = self.root / "output" / "example-program" / "scans" / "mappa" / "expired.md"
        evidence.parent.mkdir(parents=True, exist_ok=True)
        evidence.write_text("unused", encoding="utf-8")
        result, output = self.run_command(
            "record",
            str(plan_id),
            "--outcome",
            "candidate",
            "--request-count",
            "1",
            "--evidence",
            str(evidence),
            "--summary",
            "Should not be accepted",
            "--operator",
            "analyst",
        )
        self.assertEqual(result, 1)
        self.assertIn("approval has expired", output)
        self.assertEqual(self.fetchone("SELECT status FROM test_plans")["status"], "expired")
        self.assertEqual(self.fetchone("SELECT status FROM approval_executions")["status"], "cancelled")
        self.assertEqual(self.fetchone("SELECT status FROM hypotheses")["status"], "queued")

    def test_contextual_mapping_and_manual_hypothesis(self):
        self.assertEqual(
            self.run_command(
                "onboard",
                "--program-name",
                "Example",
                "--policy-file",
                str(self.policy),
                "--scope",
                "*.example.test",
                "--duplicate-risk",
                "1",
                "--reviewed-by",
                "analyst",
            )[0],
            0,
        )
        self.assertEqual(
            self.run_command(
                "identity",
                "add",
                "--label",
                "member-a",
                "--tenant",
                "tenant-a",
                "--role",
                "member",
            )[0],
            0,
        )
        export = self.root / "orders.json"
        export.write_text(
            json.dumps(
                [
                    {
                        "id": "same-local-id",
                        "url": "https://api.example.test/api/orders/1?include=lines",
                        "method": "PATCH",
                    }
                ]
            ),
            encoding="utf-8",
        )
        self.assertEqual(
            self.run_command("ingest", "--file", str(export), "--identity", "member-a")[0],
            0,
        )
        self.assertEqual(self.run_command("map")[0], 0)
        self.assertEqual(
            self.run_command(
                "workflow",
                "annotate",
                "--host",
                "api.example.test",
                "--name",
                "api",
                "--actor",
                "member-a",
                "--object",
                "order",
                "--state",
                "paid",
                "--sensitivity",
                "5",
                "--notes",
                "Orders change state after payment.",
            )[0],
            0,
        )
        workflow = self.fetchone(
            "SELECT actors_json, objects_json, states_json, sensitivity FROM application_workflows"
        )
        self.assertIn("member-a", workflow["actors_json"])
        self.assertIn("order", workflow["objects_json"])
        self.assertIn("paid", workflow["states_json"])
        self.assertEqual(workflow["sensitivity"], 5)
        self.assertEqual(self.run_command("map")[0], 0)
        remapped = self.fetchone(
            "SELECT states_json, sensitivity FROM application_workflows WHERE workflow_key = 'api.example.test:api'"
        )
        self.assertIn("paid", remapped["states_json"])
        self.assertEqual(remapped["sensitivity"], 5)
        self.assertEqual(self.run_command("queue", "--generate")[0], 0)
        generated = self.fetchone(
            "SELECT impact_score FROM hypotheses WHERE statement LIKE 'Verify that %'"
        )
        self.assertEqual(generated["impact_score"], 5)
        endpoint = self.fetchone("SELECT id FROM endpoints")
        self.assertEqual(
            self.run_command(
                "hypothesis",
                "add",
                "--endpoint-id",
                str(endpoint["id"]),
                "--statement",
                "A member cannot update an order from another tenant after payment.",
                "--actor",
                "member-a",
                "--object-owner",
                "tenant-b",
                "--object-state",
                "paid",
                "--created-by",
                "analyst",
            )[0],
            0,
        )
        hypothesis = self.fetchone(
            "SELECT actor_label, object_owner, object_state, impact_score, priority "
            "FROM hypotheses WHERE statement LIKE 'A member cannot update%'"
        )
        self.assertEqual(hypothesis["actor_label"], "member-a")
        self.assertEqual(hypothesis["object_owner"], "tenant-b")
        self.assertEqual(hypothesis["object_state"], "paid")
        self.assertEqual(hypothesis["impact_score"], 5)
        self.assertGreater(hypothesis["priority"], 0)

    def test_import_fingerprint_deduplicates_changed_export_and_preserves_source_reference(self):
        self.assertEqual(
            self.run_command(
                "onboard",
                "--program-name",
                "Example",
                "--policy-file",
                str(self.policy),
                "--scope",
                "*.example.test",
                "--reviewed-by",
                "analyst",
            )[0],
            0,
        )
        first = self.root / "first.json"
        second = self.root / "second.json"
        first.write_text(
            json.dumps([
                {"id": "1", "url": "https://api.example.test/api/orders/1", "method": "GET"}
            ]),
            encoding="utf-8",
        )
        second.write_text(
            json.dumps([
                {"id": "1", "url": "https://api.example.test/api/orders/999", "method": "GET"},
                {"id": "1", "url": "https://api.example.test/api/orders", "method": "POST"},
            ]),
            encoding="utf-8",
        )
        self.assertEqual(self.run_command("ingest", "--file", str(first))[0], 0)
        self.assertEqual(self.run_command("ingest", "--file", str(second))[0], 0)
        self.assertEqual(
            self.fetchone("SELECT COUNT(*) AS count FROM burp_message_refs")["count"], 2
        )
        source_refs = {
            row["source_message_ref"]
            for row in self.fetchall("SELECT source_message_ref FROM burp_message_refs")
        }
        self.assertEqual(source_refs, {"1"})
        self.assertEqual(
            self.fetchone("SELECT COUNT(*) AS count FROM burp_message_refs WHERE request_fingerprint IS NOT NULL")["count"],
            2,
        )

    def test_burp_probe_checks_standard_mcp_tools(self):
        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                content_length = int(self.headers.get("Content-Length", "0"))
                payload = json.loads(self.rfile.read(content_length))
                method = payload.get("method")
                if method == "initialize":
                    response = {
                        "jsonrpc": "2.0",
                        "id": payload["id"],
                        "result": {"serverInfo": {"name": "test-burp", "version": "1"}},
                    }
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Mcp-Session-Id", "test-session")
                    self.end_headers()
                    self.wfile.write(json.dumps(response).encode("utf-8"))
                    return
                if method == "notifications/initialized":
                    self.send_response(202)
                    self.end_headers()
                    return
                if method == "tools/list":
                    response = {
                        "jsonrpc": "2.0",
                        "id": payload["id"],
                        "result": {"tools": [{"name": "history"}, {"name": "site_map"}]},
                    }
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.end_headers()
                    self.wfile.write(json.dumps(response).encode("utf-8"))
                    return
                self.send_response(400)
                self.end_headers()

            def log_message(self, format, *args):
                return

        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            output = io.StringIO()
            with contextlib.redirect_stdout(output), contextlib.redirect_stderr(output):
                result = bugbounty.main(
                    [
                        "burp",
                        "probe",
                        "--url",
                        f"http://127.0.0.1:{server.server_port}/mcp",
                        "--require-tool",
                        "history",
                    ]
                )
            self.assertEqual(result, 0, output.getvalue())
            self.assertIn("test-burp", output.getvalue())
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                missing = bugbounty.main(
                    [
                        "burp",
                        "probe",
                        "--url",
                        f"http://127.0.0.1:{server.server_port}/mcp",
                        "--require-tool",
                        "repeater",
                    ]
                )
            self.assertEqual(missing, 1)
        finally:
            server.shutdown()
            server.server_close()


if __name__ == "__main__":
    unittest.main()
