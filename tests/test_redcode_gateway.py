import os
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from scripts.redcode_gateway import (
    GatewayError,
    GatewayServer,
    GatewayState,
    ensure_private_token,
    extract_text,
    safe_activity,
    validate_identifier,
    validate_origin,
)


class RedCodeGatewayTests(unittest.TestCase):
    def test_private_token_is_persistent_and_bounded(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "nested" / "gateway-token"
            first = ensure_private_token(path)
            second = ensure_private_token(path)

            self.assertEqual(first, second)
            self.assertGreaterEqual(len(first), 32)
            if os.name == "posix":
                self.assertEqual(path.stat().st_mode & 0o077, 0)

    @unittest.skipUnless(os.name == "posix", "symlink semantics are POSIX-specific")
    def test_gateway_token_rejects_symbolic_links(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            target = Path(temp_dir) / "target"
            target.write_text("x" * 48, encoding="utf-8")
            link = Path(temp_dir) / "gateway-token"
            link.symlink_to(target)
            with self.assertRaisesRegex(GatewayError, "symbolic link"):
                ensure_private_token(link)

    def test_remote_arsenal_requires_explicit_enablement(self):
        with self.assertRaisesRegex(GatewayError, "allow-remote-arsenal"):
            validate_origin("https://arsenal.example.test", allow_remote=False)
        self.assertEqual(
            validate_origin("https://arsenal.example.test", allow_remote=True),
            "https://arsenal.example.test",
        )

    def test_origins_with_embedded_paths_or_credentials_are_rejected(self):
        for value in (
            "http://user@127.0.0.1:8000",
            "http://127.0.0.1:8000/api",
            "http://127.0.0.1:8000?token=x",
        ):
            with self.subTest(value=value), self.assertRaises(GatewayError):
                validate_origin(value, allow_remote=False)

    def test_identifier_and_event_projection_are_bounded(self):
        self.assertEqual(validate_identifier("turn-1", "turn_id"), "turn-1")
        with self.assertRaises(GatewayError):
            validate_identifier("../turn", "turn_id")
        self.assertEqual(
            extract_text({"type": "text", "part": {"type": "text", "text": "hello"}}),
            "hello",
        )
        self.assertEqual(
            safe_activity(
                {
                    "type": "tool_use",
                    "part": {
                        "tool": "arsenal_get_operation_schema",
                        "state": {"status": "completed", "output": "not exposed"},
                    },
                }
            ),
            {
                "kind": "tool",
                "name": "arsenal_get_operation_schema",
                "state": "completed",
            },
        )

    def test_health_endpoint_requires_bearer_token(self):
        state = GatewayState(
            token="x" * 48,
            token_path=Path("unused"),
            allow_remote_arsenal=False,
            opencode_command=sys.executable,
        )
        server = GatewayServer(("127.0.0.1", 0), state)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        origin = f"http://127.0.0.1:{server.server_port}"
        try:
            with self.assertRaises(HTTPError) as unauthorized:
                urlopen(f"{origin}/v1/health", timeout=2)
            self.assertEqual(unauthorized.exception.code, 401)

            request = Request(
                f"{origin}/v1/health",
                headers={"Authorization": f"Bearer {state.token}"},
            )
            with urlopen(request, timeout=2) as response:
                self.assertEqual(response.status, 200)
                self.assertEqual(
                    response.headers["X-RedCode-Gateway-Protocol"], "1.0"
                )
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)


if __name__ == "__main__":
    unittest.main()
