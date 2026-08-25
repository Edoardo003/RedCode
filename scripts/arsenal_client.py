#!/usr/bin/env python3
"""Bounded client for Arsenal's read-only and proposal-only agent APIs."""

from __future__ import annotations

import datetime as dt
import json
import os
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode, urlparse
from urllib.request import ProxyHandler, Request, build_opener

PROTOCOL_NAME = "arsenal-agent-context"
PROTOCOL_VERSION = "1.0"
AGENT_API_PATH = "/api/agent/v1"
ACTIONS_PROTOCOL_NAME = "arsenal-agent-actions"
ACTIONS_PROTOCOL_VERSION = "1.0"
ACTIONS_API_PATH = "/api/agent-actions/v1"
MAX_RESPONSE_BYTES = 4 * 1024 * 1024
DEFAULT_TIMEOUT = 10.0
LOOPBACK_HOSTS = {"127.0.0.1", "::1", "localhost"}
MAX_TOKEN_BYTES = 1024
REQUIRED_CAPABILITIES = {
    "workspace.list",
    "workspace.context.read",
    "job.list",
    "job.read",
    "result.preview.read",
    "artifact.metadata.read",
    "execution_provider.list",
    "tool.operation.read",
}
REQUIRED_ACTION_CAPABILITIES = {
    "block.draft.propose",
    "block.draft.status.read",
    "job.run.request",
    "job.run_request.status.read",
}


class ArsenalClientError(RuntimeError):
    """Raised when the Arsenal endpoint or response violates the client contract."""


def path_segment(value: str, label: str) -> str:
    if not isinstance(value, str) or not value or len(value) > 512:
        raise ArsenalClientError(f"{label} must be a non-empty bounded string")
    return quote(value, safe="")


def normalize_arsenal_url(value: str, *, allow_remote: bool = False) -> str:
    candidate = value.strip().rstrip("/")
    parsed = urlparse(candidate)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ArsenalClientError("Arsenal URL must be an absolute HTTP(S) URL")
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ArsenalClientError("Arsenal URL must not contain credentials, query, or fragment")
    if parsed.hostname.lower() not in LOOPBACK_HOSTS and not allow_remote:
        raise ArsenalClientError("Arsenal 7C connections are restricted to loopback hosts")
    if parsed.hostname.lower() not in LOOPBACK_HOSTS and parsed.scheme != "https":
        raise ArsenalClientError("Remote Arsenal connections require HTTPS")
    if parsed.path not in {"", "/"}:
        raise ArsenalClientError("Arsenal URL must contain only the origin, without a path")
    return candidate


def session_path(explicit: str | None = None, root: Path | None = None) -> Path:
    configured = explicit or os.environ.get("ARSENAL_SESSION")
    if configured:
        path = Path(configured).expanduser()
        return path if path.is_absolute() else (root or Path.cwd()) / path
    base = root or Path.cwd()
    return base / "output" / ".redcode" / "current-arsenal-session.json"


def agent_token_path(explicit: str | None = None) -> Path:
    configured = explicit or os.environ.get("ARSENAL_AGENT_TOKEN_FILE")
    if configured:
        return Path(os.path.abspath(Path(configured).expanduser()))
    configured_data = os.environ.get("ARSENAL_DATA_DIR")
    if configured_data:
        return Path(
            os.path.abspath(Path(configured_data).expanduser() / "agent-token")
        )
    xdg_data_home = os.environ.get("XDG_DATA_HOME")
    base = (
        Path(xdg_data_home).expanduser()
        if xdg_data_home
        else Path.home() / ".local" / "share"
    )
    return Path(os.path.abspath(base / "arsenal" / "agent-token"))


def read_agent_token(path: Path) -> str:
    try:
        if (
            path.is_symlink()
            or not path.is_file()
            or path.stat().st_size > MAX_TOKEN_BYTES
        ):
            raise ArsenalClientError(f"Arsenal agent token file is invalid: {path}")
        token = path.read_text(encoding="utf-8").strip()
    except OSError as exc:
        raise ArsenalClientError(f"Cannot read Arsenal agent token file: {path}") from exc
    if not 32 <= len(token) <= 512:
        raise ArsenalClientError(f"Arsenal agent token file is invalid: {path}")
    if os.name != "nt" and path.stat().st_mode & 0o077:
        raise ArsenalClientError(
            f"Arsenal agent token file must not be accessible by other users: {path}"
        )
    return token


class ArsenalClient:
    def __init__(
        self,
        base_url: str,
        timeout: float = DEFAULT_TIMEOUT,
        token_file: str | None = None,
        allow_remote: bool = False,
    ) -> None:
        self.base_url = normalize_arsenal_url(base_url, allow_remote=allow_remote)
        self.timeout = timeout
        self.token_file = agent_token_path(token_file)
        self._opener = build_opener(ProxyHandler({}))

    def _headers(self) -> dict[str, str]:
        return {
            "Accept": "application/json",
            "Authorization": f"Bearer {read_agent_token(self.token_file)}",
            "User-Agent": "RedCode-Arsenal-Client/1.0",
        }

    def _get(self, path: str, query: dict[str, Any] | None = None) -> Any:
        suffix = f"?{urlencode(query)}" if query else ""
        request = Request(
            f"{self.base_url}{AGENT_API_PATH}{path}{suffix}",
            headers=self._headers(),
            method="GET",
        )
        try:
            with self._opener.open(request, timeout=self.timeout) as response:
                declared_size = response.headers.get("Content-Length")
                if declared_size and int(declared_size) > MAX_RESPONSE_BYTES:
                    raise ArsenalClientError("Arsenal response exceeds the client size limit")
                body = response.read(MAX_RESPONSE_BYTES + 1)
                protocol_header = response.headers.get("X-Arsenal-Agent-Protocol")
        except HTTPError as exc:
            detail = exc.read(2048).decode("utf-8", errors="replace")
            raise ArsenalClientError(
                f"Arsenal request failed with HTTP {exc.code}: {detail}"
            ) from exc
        except (URLError, TimeoutError, OSError, ValueError) as exc:
            raise ArsenalClientError(f"Arsenal request failed: {exc}") from exc
        if len(body) > MAX_RESPONSE_BYTES:
            raise ArsenalClientError("Arsenal response exceeds the client size limit")
        if protocol_header != PROTOCOL_VERSION:
            raise ArsenalClientError(
                "Arsenal response has an incompatible or missing protocol header"
            )
        try:
            return json.loads(body)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ArsenalClientError("Arsenal returned invalid JSON") from exc

    def _action_request(
        self,
        method: str,
        path: str,
        payload: dict[str, Any] | None = None,
    ) -> Any:
        body = None if payload is None else json.dumps(payload).encode("utf-8")
        headers = self._headers()
        if body is not None:
            headers["Content-Type"] = "application/json"
        request = Request(
            f"{self.base_url}{ACTIONS_API_PATH}{path}",
            data=body,
            headers=headers,
            method=method,
        )
        try:
            with self._opener.open(request, timeout=self.timeout) as response:
                declared_size = response.headers.get("Content-Length")
                if declared_size and int(declared_size) > MAX_RESPONSE_BYTES:
                    raise ArsenalClientError("Arsenal response exceeds the client size limit")
                response_body = response.read(MAX_RESPONSE_BYTES + 1)
                protocol_header = response.headers.get(
                    "X-Arsenal-Agent-Actions-Protocol"
                )
        except HTTPError as exc:
            detail = exc.read(4096).decode("utf-8", errors="replace")
            raise ArsenalClientError(
                f"Arsenal proposal request failed with HTTP {exc.code}: {detail}"
            ) from exc
        except (URLError, TimeoutError, OSError, ValueError) as exc:
            raise ArsenalClientError(f"Arsenal proposal request failed: {exc}") from exc
        if len(response_body) > MAX_RESPONSE_BYTES:
            raise ArsenalClientError("Arsenal response exceeds the client size limit")
        if protocol_header != ACTIONS_PROTOCOL_VERSION:
            raise ArsenalClientError(
                "Arsenal proposal response has an incompatible or missing protocol header"
            )
        try:
            return json.loads(response_body)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ArsenalClientError("Arsenal returned invalid proposal JSON") from exc

    def manifest(self) -> dict[str, Any]:
        data = self._get("/manifest")
        if not isinstance(data, dict):
            raise ArsenalClientError("Arsenal manifest must be a JSON object")
        if data.get("protocol_name") != PROTOCOL_NAME:
            raise ArsenalClientError("Arsenal protocol name is not supported")
        if data.get("protocol_version") != PROTOCOL_VERSION:
            raise ArsenalClientError("Arsenal protocol version is not supported")
        if data.get("access_mode") != "read_only":
            raise ArsenalClientError("Arsenal endpoint is not read-only")
        self._validate_authentication(data, "read")
        capabilities = data.get("capabilities")
        if not isinstance(capabilities, list):
            raise ArsenalClientError("Arsenal manifest capabilities are invalid")
        missing = sorted(REQUIRED_CAPABILITIES - set(capabilities))
        if missing:
            raise ArsenalClientError(
                f"Arsenal is missing required capabilities: {', '.join(missing)}"
            )
        return data

    def actions_manifest(self) -> dict[str, Any]:
        data = self._action_request("GET", "/manifest")
        if not isinstance(data, dict):
            raise ArsenalClientError("Arsenal actions manifest must be a JSON object")
        if data.get("protocol_name") != ACTIONS_PROTOCOL_NAME:
            raise ArsenalClientError("Arsenal actions protocol name is not supported")
        if data.get("protocol_version") != ACTIONS_PROTOCOL_VERSION:
            raise ArsenalClientError("Arsenal actions protocol version is not supported")
        if data.get("access_mode") != "proposal_only":
            raise ArsenalClientError("Arsenal action endpoint is not proposal-only")
        self._validate_authentication(data, "action")
        capabilities = data.get("capabilities")
        if not isinstance(capabilities, list):
            raise ArsenalClientError("Arsenal action capabilities are invalid")
        missing = sorted(REQUIRED_ACTION_CAPABILITIES - set(capabilities))
        if missing:
            raise ArsenalClientError(
                f"Arsenal is missing proposal capabilities: {', '.join(missing)}"
            )
        return data

    def operation_schema(self, operation_id: str) -> dict[str, Any]:
        data = self._get(f"/operations/{path_segment(operation_id, 'operation_id')}")
        if not isinstance(data, dict) or data.get("id") != operation_id:
            raise ArsenalClientError("Arsenal operation schema is invalid")
        parameters = data.get("parameters")
        if not isinstance(parameters, list):
            raise ArsenalClientError("Arsenal operation parameters are invalid")
        return data

    @staticmethod
    def _validate_authentication(data: dict[str, Any], label: str) -> None:
        authentication = data.get("authentication")
        if (
            not isinstance(authentication, dict)
            or authentication.get("scheme") != "bearer"
            or authentication.get("token_source") != "local_private_file"
        ):
            raise ArsenalClientError(
                f"Arsenal {label} protocol does not advertise supported authentication"
            )

    def list_workspaces(self, limit: int = 100) -> dict[str, Any]:
        return self._object(self._get("/workspaces", {"limit": limit}), "workspace list")

    def workspace_context(
        self,
        workspace_id: str,
        *,
        job_limit: int = 10,
        finding_limit: int = 10,
        resource_limit: int = 100,
        block_limit: int = 100,
    ) -> dict[str, Any]:
        workspace = path_segment(workspace_id, "workspace id")
        return self._object(
            self._get(
                f"/workspaces/{workspace}/context",
                {
                    "job_limit": job_limit,
                    "finding_limit": finding_limit,
                    "resource_limit": resource_limit,
                    "block_limit": block_limit,
                },
            ),
            "workspace context",
        )

    def list_jobs(
        self,
        workspace_id: str,
        *,
        limit: int = 20,
        finding_limit: int = 10,
        cursor: str | None = None,
    ) -> dict[str, Any]:
        workspace = path_segment(workspace_id, "workspace id")
        query: dict[str, Any] = {"limit": limit, "finding_limit": finding_limit}
        if cursor:
            query["cursor"] = cursor
        return self._object(
            self._get(f"/workspaces/{workspace}/jobs", query), "job list"
        )

    def get_job(
        self, workspace_id: str, job_id: str, *, finding_limit: int = 25
    ) -> dict[str, Any]:
        workspace = path_segment(workspace_id, "workspace id")
        job = path_segment(job_id, "job id")
        return self._object(
            self._get(
                f"/workspaces/{workspace}/jobs/{job}",
                {"finding_limit": finding_limit},
            ),
            "job detail",
        )

    def propose_block_draft(
        self,
        workspace_id: str,
        *,
        idempotency_key: str,
        name: str,
        operation_id: str,
        values: dict[str, Any],
        rationale: str,
        source_session: str | None = None,
        resource_bindings: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        workspace = path_segment(workspace_id, "workspace id")
        return self._action_object(
            self._action_request(
                "POST",
                f"/workspaces/{workspace}/block-drafts",
                {
                    "source_client": "redcode",
                    "source_session": source_session,
                    "idempotency_key": idempotency_key,
                    "name": name,
                    "operation_id": operation_id,
                    "values": values,
                    "resource_bindings": resource_bindings or {},
                    "rationale": rationale,
                },
            ),
            "block draft",
        )

    def get_block_draft(self, workspace_id: str, draft_id: str) -> dict[str, Any]:
        workspace = path_segment(workspace_id, "workspace id")
        draft = path_segment(draft_id, "draft id")
        return self._action_object(
            self._action_request(
                "GET",
                f"/workspaces/{workspace}/block-drafts/{draft}",
            ),
            "block draft",
        )

    def request_block_run(
        self,
        workspace_id: str,
        *,
        idempotency_key: str,
        block_id: str,
        block_revision: int,
        rationale: str,
        source_session: str | None = None,
    ) -> dict[str, Any]:
        workspace = path_segment(workspace_id, "workspace id")
        return self._run_request_object(
            self._action_request(
                "POST",
                f"/workspaces/{workspace}/run-requests",
                {
                    "source_client": "redcode",
                    "source_session": source_session,
                    "idempotency_key": idempotency_key,
                    "block_id": block_id,
                    "block_revision": block_revision,
                    "rationale": rationale,
                },
            ),
            "run request",
        )

    def get_run_request(self, workspace_id: str, request_id: str) -> dict[str, Any]:
        workspace = path_segment(workspace_id, "workspace id")
        request = path_segment(request_id, "run request id")
        return self._run_request_object(
            self._action_request(
                "GET",
                f"/workspaces/{workspace}/run-requests/{request}",
            ),
            "run request",
        )

    @staticmethod
    def _object(value: Any, label: str) -> dict[str, Any]:
        if not isinstance(value, dict):
            raise ArsenalClientError(f"Arsenal {label} must be a JSON object")
        if value.get("protocol_version") != PROTOCOL_VERSION:
            raise ArsenalClientError(f"Arsenal {label} has an incompatible protocol")
        return value

    @staticmethod
    def _action_object(value: Any, label: str) -> dict[str, Any]:
        if not isinstance(value, dict):
            raise ArsenalClientError(f"Arsenal {label} must be a JSON object")
        required = {"id", "workspace_id", "status", "operation_id", "values"}
        if not required.issubset(value):
            raise ArsenalClientError(f"Arsenal {label} is incomplete")
        return value

    @staticmethod
    def _run_request_object(value: Any, label: str) -> dict[str, Any]:
        if not isinstance(value, dict):
            raise ArsenalClientError(f"Arsenal {label} must be a JSON object")
        required = {
            "id",
            "workspace_id",
            "block_id",
            "block_revision",
            "status",
            "rationale",
        }
        if not required.issubset(value):
            raise ArsenalClientError(f"Arsenal {label} is incomplete")
        return value


def create_session(
    client: ArsenalClient,
    workspace_id: str,
    destination: Path,
) -> dict[str, Any]:
    manifest = client.manifest()
    actions_manifest = client.actions_manifest()
    context = client.workspace_context(
        workspace_id,
        job_limit=1,
        finding_limit=0,
        resource_limit=1,
        block_limit=1,
    )
    workspace = context.get("workspace")
    if not isinstance(workspace, dict) or workspace.get("id") != workspace_id:
        raise ArsenalClientError("Arsenal returned a different workspace than requested")
    session = {
        "schema_version": 1,
        "mode": "arsenal",
        "arsenal_url": client.base_url,
        "agent_token_file": str(client.token_file),
        "workspace": {
            "id": workspace_id,
            "name": workspace.get("name", workspace_id),
        },
        "protocol_name": manifest["protocol_name"],
        "protocol_version": manifest["protocol_version"],
        "arsenal_version": manifest.get("arsenal_version"),
        "capabilities": manifest["capabilities"],
        "actions_protocol_name": actions_manifest["protocol_name"],
        "actions_protocol_version": actions_manifest["protocol_version"],
        "action_capabilities": actions_manifest["capabilities"],
        "trust_policy": manifest.get("trust_policy", {}),
        "connected_at": dt.datetime.now(dt.timezone.utc).isoformat(),
    }
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(session, indent=2) + "\n", encoding="utf-8")
    if os.name != "nt":
        destination.chmod(0o600)
    return session


def load_session(path: Path) -> dict[str, Any]:
    try:
        session = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ArsenalClientError(f"Arsenal session not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ArsenalClientError(f"Arsenal session contains invalid JSON: {path}") from exc
    if not isinstance(session, dict):
        raise ArsenalClientError("Arsenal session root must be a JSON object")
    workspace = session.get("workspace")
    if (
        session.get("schema_version") != 1
        or session.get("mode") != "arsenal"
        or session.get("protocol_name") != PROTOCOL_NAME
        or session.get("protocol_version") != PROTOCOL_VERSION
        or session.get("actions_protocol_name") != ACTIONS_PROTOCOL_NAME
        or session.get("actions_protocol_version") != ACTIONS_PROTOCOL_VERSION
        or not isinstance(workspace, dict)
        or not isinstance(workspace.get("id"), str)
    ):
        raise ArsenalClientError("Arsenal session is incompatible or incomplete")
    normalize_arsenal_url(str(session.get("arsenal_url", "")))
    token_file = session.get("agent_token_file")
    if token_file is not None and (
        not isinstance(token_file, str) or not Path(token_file).is_absolute()
    ):
        raise ArsenalClientError("Arsenal session token path is invalid")
    return session


def client_from_session(path: Path) -> tuple[ArsenalClient, str]:
    session = load_session(path)
    workspace = session["workspace"]
    return (
        ArsenalClient(
            session["arsenal_url"],
            token_file=session.get("agent_token_file"),
        ),
        workspace["id"],
    )
