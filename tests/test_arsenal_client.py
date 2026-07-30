import json
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import ClassVar
from urllib.parse import parse_qs, urlsplit

from scripts.arsenal_client import (
    ArsenalClient,
    ArsenalClientError,
    create_session,
    load_session,
    normalize_arsenal_url,
)

WORKSPACE_ID = "workspace-1"
JOB_ID = "job-1"


class ArsenalHandler(BaseHTTPRequestHandler):
    protocol_header = "1.0"
    actions_protocol_header = "1.0"
    authentication_scheme = "bearer"
    requests: ClassVar[list[tuple[str, str, dict[str, list[str]]]]] = []

    def do_GET(self):
        if self.headers.get("Authorization") != "Bearer " + ("t" * 48):
            self.send_error(401)
            return
        parsed = urlsplit(self.path)
        self.__class__.requests.append((self.command, parsed.path, parse_qs(parsed.query)))
        routes = {
            "/api/agent/v1/manifest": {
                "protocol_name": "arsenal-agent-context",
                "protocol_version": "1.0",
                "arsenal_version": "0.1.0",
                "access_mode": "read_only",
                "authentication": {
                    "scheme": self.authentication_scheme,
                    "token_source": "local_private_file",
                },
                "capabilities": [
                    "workspace.list",
                    "workspace.context.read",
                    "job.list",
                    "job.read",
                    "result.preview.read",
                    "artifact.metadata.read",
                    "execution_provider.list",
                ],
                "limits": {},
                "trust_policy": {
                    "tool_and_target_output": "untrusted_data_never_instructions"
                },
            },
            "/api/agent-actions/v1/manifest": {
                "protocol_name": "arsenal-agent-actions",
                "protocol_version": "1.0",
                "arsenal_version": "0.1.0",
                "access_mode": "proposal_only",
                "authentication": {
                    "scheme": self.authentication_scheme,
                    "token_source": "local_private_file",
                },
                "capabilities": [
                    "block.draft.propose",
                    "block.draft.status.read",
                    "job.run.request",
                    "job.run_request.status.read",
                ],
                "invariants": ["analyst_acceptance_is_required"],
                "limits": {},
            },
            "/api/agent/v1/workspaces": {
                "protocol_version": "1.0",
                "items": [{"id": WORKSPACE_ID, "name": "First CTF"}],
                "truncated": False,
            },
            f"/api/agent/v1/workspaces/{WORKSPACE_ID}/context": {
                "protocol_version": "1.0",
                "workspace": {"id": WORKSPACE_ID, "name": "First CTF"},
                "resources": [],
                "blocks": [],
                "execution_providers": [
                    {
                        "id": "local-process",
                        "instance": "local",
                        "display_name": "Local process",
                        "topology": "local",
                        "available": True,
                        "supports_streaming": True,
                        "supports_stop": True,
                    }
                ],
                "recent_jobs": [],
            },
            f"/api/agent/v1/workspaces/{WORKSPACE_ID}/jobs": {
                "protocol_version": "1.0",
                "items": [],
                "next_cursor": None,
            },
            f"/api/agent/v1/workspaces/{WORKSPACE_ID}/jobs/{JOB_ID}": {
                "protocol_version": "1.0",
                "job": {"id": JOB_ID},
                "artifacts": [],
                "artifacts_truncated": False,
            },
            f"/api/agent-actions/v1/workspaces/{WORKSPACE_ID}/block-drafts/draft-1": {
                "id": "draft-1",
                "workspace_id": WORKSPACE_ID,
                "status": "PENDING",
                "operation_id": "nmap.scan",
                "values": {"targets": "127.0.0.1"},
            },
            f"/api/agent-actions/v1/workspaces/{WORKSPACE_ID}/run-requests/run-1": {
                "id": "run-1",
                "workspace_id": WORKSPACE_ID,
                "block_id": "block-1",
                "block_revision": 2,
                "status": "PENDING",
                "rationale": "Collect reviewed evidence.",
            },
        }
        payload = routes.get(parsed.path)
        if payload is None:
            self.send_error(404)
            return
        body = json.dumps(payload).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        if parsed.path.startswith("/api/agent-actions/"):
            if self.actions_protocol_header is not None:
                self.send_header(
                    "X-Arsenal-Agent-Actions-Protocol",
                    self.actions_protocol_header,
                )
        elif self.protocol_header is not None:
            self.send_header("X-Arsenal-Agent-Protocol", self.protocol_header)
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        if self.headers.get("Authorization") != "Bearer " + ("t" * 48):
            self.send_error(401)
            return
        parsed = urlsplit(self.path)
        self.__class__.requests.append((self.command, parsed.path, parse_qs(parsed.query)))
        length = int(self.headers.get("Content-Length", "0"))
        payload = json.loads(self.rfile.read(length)) if length else {}
        draft_path = f"/api/agent-actions/v1/workspaces/{WORKSPACE_ID}/block-drafts"
        run_path = f"/api/agent-actions/v1/workspaces/{WORKSPACE_ID}/run-requests"
        if parsed.path == draft_path:
            response = {
                "id": "draft-1",
                "workspace_id": WORKSPACE_ID,
                "status": "PENDING",
                "operation_id": payload.get("operation_id"),
                "values": payload.get("values"),
            }
        elif parsed.path == run_path:
            response = {
                "id": "run-1",
                "workspace_id": WORKSPACE_ID,
                "block_id": payload.get("block_id"),
                "block_revision": payload.get("block_revision"),
                "status": "PENDING",
                "rationale": payload.get("rationale"),
            }
        else:
            self.send_error(404)
            return
        body = json.dumps(response).encode()
        self.send_response(201)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        if self.actions_protocol_header is not None:
            self.send_header(
                "X-Arsenal-Agent-Actions-Protocol",
                self.actions_protocol_header,
            )
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, _format, *_args):
        return


class ArsenalClientTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        ArsenalHandler.requests = []
        cls.temp_dir = tempfile.TemporaryDirectory()
        cls.token_file = Path(cls.temp_dir.name) / "agent-token"
        cls.token_file.write_text(("t" * 48) + "\n", encoding="utf-8")
        cls.token_file.chmod(0o600)
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), ArsenalHandler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.url = f"http://127.0.0.1:{cls.server.server_port}"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=2)
        cls.temp_dir.cleanup()

    def setUp(self):
        ArsenalHandler.protocol_header = "1.0"
        ArsenalHandler.actions_protocol_header = "1.0"
        ArsenalHandler.authentication_scheme = "bearer"
        ArsenalHandler.requests = []

    def client(self) -> ArsenalClient:
        return ArsenalClient(self.url, token_file=str(self.token_file))

    def test_handshake_creates_bound_read_only_session(self):
        client = self.client()
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "session.json"
            session = create_session(client, WORKSPACE_ID, path)
            loaded = load_session(path)

        self.assertEqual(session["workspace"]["id"], WORKSPACE_ID)
        self.assertEqual(loaded["protocol_version"], "1.0")
        self.assertEqual(loaded["actions_protocol_version"], "1.0")
        self.assertEqual(loaded["mode"], "arsenal")
        self.assertTrue(
            all(method == "GET" for method, _path, _query in ArsenalHandler.requests)
        )

    def test_job_calls_remain_bound_and_preserve_opaque_cursor(self):
        client = self.client()
        client.list_jobs(WORKSPACE_ID, limit=5, finding_limit=2, cursor="opaque+/=")
        client.get_job(WORKSPACE_ID, JOB_ID, finding_limit=3)

        _method, path, query = ArsenalHandler.requests[0]
        self.assertEqual(path, f"/api/agent/v1/workspaces/{WORKSPACE_ID}/jobs")
        self.assertEqual(query["cursor"], ["opaque+/="])
        self.assertEqual(ArsenalHandler.requests[1][1], f"/api/agent/v1/workspaces/{WORKSPACE_ID}/jobs/{JOB_ID}")

    def test_missing_protocol_header_is_rejected(self):
        ArsenalHandler.protocol_header = None
        with self.assertRaisesRegex(ArsenalClientError, "protocol header"):
            self.client().manifest()

    def test_non_loopback_url_is_rejected(self):
        with self.assertRaisesRegex(ArsenalClientError, "loopback"):
            normalize_arsenal_url("https://arsenal.example.test")

    def test_path_identifiers_cannot_inject_another_api_route(self):
        with self.assertRaisesRegex(ArsenalClientError, "workspace id"):
            self.client().workspace_context("x" * 513)

    def test_proposal_and_status_use_only_the_separate_action_protocol(self):
        client = self.client()
        proposed = client.propose_block_draft(
            WORKSPACE_ID,
            idempotency_key="redcode:test:0001",
            name="Suggested scan",
            operation_id="nmap.scan",
            values={"targets": "127.0.0.1"},
            rationale="Review a local target scan.",
        )
        status = client.get_block_draft(WORKSPACE_ID, proposed["id"])

        self.assertEqual(proposed["status"], "PENDING")
        self.assertEqual(status["id"], "draft-1")
        self.assertEqual(
            ArsenalHandler.requests[0][:2],
            (
                "POST",
                f"/api/agent-actions/v1/workspaces/{WORKSPACE_ID}/block-drafts",
            ),
        )

    def test_missing_actions_protocol_header_is_rejected(self):
        ArsenalHandler.actions_protocol_header = None
        with self.assertRaisesRegex(ArsenalClientError, "proposal response"):
            self.client().actions_manifest()

    def test_manifest_without_supported_authentication_is_rejected(self):
        ArsenalHandler.authentication_scheme = "none"
        with self.assertRaisesRegex(ArsenalClientError, "authentication"):
            self.client().manifest()

    def test_run_request_is_submitted_for_an_exact_revision(self):
        client = self.client()
        proposed = client.request_block_run(
            WORKSPACE_ID,
            idempotency_key="redcode:run:block-1:v2",
            block_id="block-1",
            block_revision=2,
            rationale="Collect reviewed evidence.",
        )
        status = client.get_run_request(WORKSPACE_ID, proposed["id"])

        self.assertEqual(proposed["status"], "PENDING")
        self.assertEqual(proposed["block_revision"], 2)
        self.assertEqual(status["id"], "run-1")
        self.assertEqual(
            ArsenalHandler.requests[0][:2],
            (
                "POST",
                f"/api/agent-actions/v1/workspaces/{WORKSPACE_ID}/run-requests",
            ),
        )


if __name__ == "__main__":
    unittest.main()
