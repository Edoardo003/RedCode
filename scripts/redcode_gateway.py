#!/usr/bin/env python3
"""Authenticated streaming gateway between Arsenal and RedCode/OpenCode."""

from __future__ import annotations

import argparse
import datetime as dt
import hmac
import json
import os
import re
import secrets
import shutil
import signal
import ssl
import subprocess
import threading
from collections import deque
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

try:
    from arsenal_client import ArsenalClient, ArsenalClientError, create_session
    from redcode_control import ROOT, activate_runtime_mode, arsenal_opencode_override
except ModuleNotFoundError:
    from scripts.arsenal_client import ArsenalClient, ArsenalClientError, create_session
    from scripts.redcode_control import (
        ROOT,
        activate_runtime_mode,
        arsenal_opencode_override,
    )


PROTOCOL_NAME = "redcode-chat-gateway"
PROTOCOL_VERSION = "1.0"
MAX_REQUEST_BYTES = 32 * 1024
MAX_PROMPT_CHARS = 12_000
MAX_ASSISTANT_CHARS = 2_000_000
ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,159}$")
LOOPBACK_HOSTS = {"127.0.0.1", "::1", "localhost"}


class GatewayError(RuntimeError):
    """A bounded error safe to return to the Arsenal backend."""


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def default_token_path() -> Path:
    configured = os.environ.get("REDCODE_GATEWAY_TOKEN_FILE")
    if configured:
        return Path(os.path.abspath(Path(configured).expanduser()))
    xdg_data = os.environ.get("XDG_DATA_HOME")
    base = Path(xdg_data).expanduser() if xdg_data else Path.home() / ".local" / "share"
    return Path(os.path.abspath(base / "redcode" / "chat-gateway-token"))


def ensure_private_token(path: Path) -> str:
    if path.is_symlink():
        raise GatewayError(f"Gateway token must not be a symbolic link: {path}")
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    if os.name == "posix":
        path.parent.chmod(0o700)
    try:
        token = path.read_text(encoding="utf-8").strip()
    except FileNotFoundError:
        token = secrets.token_urlsafe(48)
        descriptor = os.open(
            path,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0),
            0o600,
        )
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(f"{token}\n")
    if not 32 <= len(token) <= 512:
        raise GatewayError(f"Gateway token is invalid: {path}")
    if os.name == "posix":
        path.chmod(0o600)
    return token


def validate_origin(origin: str, *, allow_remote: bool) -> str:
    parsed = urlparse(origin)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise GatewayError("arsenal_url must be an http(s) origin")
    if parsed.path not in {"", "/"} or parsed.query or parsed.fragment or parsed.username:
        raise GatewayError("arsenal_url must not contain credentials, a path, query, or fragment")
    if not allow_remote and parsed.hostname not in LOOPBACK_HOSTS:
        raise GatewayError("remote Arsenal origins require --allow-remote-arsenal")
    if parsed.hostname not in LOOPBACK_HOSTS and parsed.scheme != "https":
        raise GatewayError("remote Arsenal origins require HTTPS")
    return origin.rstrip("/")


def validate_identifier(value: Any, label: str) -> str:
    if not isinstance(value, str) or not ID_PATTERN.fullmatch(value):
        raise GatewayError(f"{label} is invalid")
    return value


def extract_text(event: dict[str, Any]) -> str | None:
    if event.get("type") != "text":
        return None
    part = event.get("part")
    if isinstance(part, dict) and isinstance(part.get("text"), str):
        return part["text"]
    if isinstance(event.get("text"), str):
        return event["text"]
    return None


def safe_activity(event: dict[str, Any]) -> dict[str, Any] | None:
    if event.get("type") != "tool_use":
        return None
    part = event.get("part")
    if not isinstance(part, dict):
        return {"kind": "tool", "name": "unknown", "state": "running"}
    state = part.get("state")
    state_name = state.get("status") if isinstance(state, dict) else state
    return {
        "kind": "tool",
        "name": str(part.get("tool") or part.get("name") or "unknown")[:120],
        "state": str(state_name or "running")[:40],
    }


class GatewayState:
    def __init__(
        self,
        *,
        token: str,
        token_path: Path,
        allow_remote_arsenal: bool,
        opencode_command: str,
    ) -> None:
        self.token = token
        self.token_path = token_path
        self.allow_remote_arsenal = allow_remote_arsenal
        self.opencode_command = opencode_command
        self._processes: dict[str, subprocess.Popen[str]] = {}
        self._lock = threading.Lock()

    def register(self, turn_id: str, process: subprocess.Popen[str]) -> None:
        with self._lock:
            if turn_id in self._processes:
                raise GatewayError("turn_id is already active")
            self._processes[turn_id] = process

    def unregister(self, turn_id: str) -> None:
        with self._lock:
            self._processes.pop(turn_id, None)

    def cancel(self, turn_id: str) -> bool:
        with self._lock:
            process = self._processes.get(turn_id)
        if process is None or process.poll() is not None:
            return False
        try:
            if os.name == "posix":
                os.killpg(process.pid, signal.SIGINT)
            else:
                process.send_signal(signal.CTRL_BREAK_EVENT)
        except OSError:
            return False
        return True


class GatewayServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, address: tuple[str, int], state: GatewayState) -> None:
        super().__init__(address, GatewayHandler)
        self.state = state


class GatewayHandler(BaseHTTPRequestHandler):
    server: GatewayServer
    protocol_version = "HTTP/1.1"

    def log_message(self, format_string: str, *arguments: object) -> None:
        print(f"[gateway] {self.address_string()} {format_string % arguments}")

    def _authorized(self) -> bool:
        supplied = self.headers.get("Authorization", "")
        prefix = "Bearer "
        return supplied.startswith(prefix) and hmac.compare_digest(
            supplied[len(prefix) :], self.server.state.token
        )

    def _json(self, status: int, payload: dict[str, Any]) -> None:
        encoded = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(encoded)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-RedCode-Gateway-Protocol", PROTOCOL_VERSION)
        self.end_headers()
        self.wfile.write(encoded)

    def _read_json(self) -> dict[str, Any]:
        raw_length = self.headers.get("Content-Length")
        try:
            length = int(raw_length or "0")
        except ValueError as exc:
            raise GatewayError("invalid Content-Length") from exc
        if length <= 0 or length > MAX_REQUEST_BYTES:
            raise GatewayError("request body size is invalid")
        try:
            payload = json.loads(self.rfile.read(length))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise GatewayError("request body must be valid JSON") from exc
        if not isinstance(payload, dict):
            raise GatewayError("request body must be a JSON object")
        return payload

    def _begin_stream(self) -> None:
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "application/x-ndjson")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Connection", "close")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-RedCode-Gateway-Protocol", PROTOCOL_VERSION)
        self.end_headers()

    def _event(self, event_type: str, **payload: Any) -> None:
        encoded = json.dumps(
            {"type": event_type, "timestamp": utc_now(), **payload},
            separators=(",", ":"),
        ).encode("utf-8") + b"\n"
        self.wfile.write(encoded)
        self.wfile.flush()

    def do_GET(self) -> None:
        if not self._authorized():
            self._json(HTTPStatus.UNAUTHORIZED, {"error": "authentication required"})
            return
        if self.path == "/v1/health":
            self._json(
                HTTPStatus.OK,
                {
                    "status": "ok",
                    "protocol_name": PROTOCOL_NAME,
                    "protocol_version": PROTOCOL_VERSION,
                    "opencode_available": shutil.which(self.server.state.opencode_command)
                    is not None,
                },
            )
            return
        self._json(HTTPStatus.NOT_FOUND, {"error": "route not found"})

    def do_POST(self) -> None:
        if not self._authorized():
            self._json(HTTPStatus.UNAUTHORIZED, {"error": "authentication required"})
            return
        cancel_match = re.fullmatch(r"/v1/chat/turns/([^/]+)/cancel", self.path)
        if cancel_match:
            try:
                turn_id = validate_identifier(cancel_match.group(1), "turn_id")
                cancelled = self.server.state.cancel(turn_id)
            except GatewayError as exc:
                self._json(HTTPStatus.BAD_REQUEST, {"error": str(exc)})
                return
            self._json(HTTPStatus.OK, {"cancelled": cancelled})
            return
        if self.path != "/v1/chat/turns":
            self._json(HTTPStatus.NOT_FOUND, {"error": "route not found"})
            return
        try:
            payload = self._read_json()
            self._stream_turn(payload)
        except GatewayError as exc:
            self._json(HTTPStatus.BAD_REQUEST, {"error": str(exc)})

    def _stream_turn(self, payload: dict[str, Any]) -> None:
        turn_id = validate_identifier(payload.get("turn_id"), "turn_id")
        workspace_id = validate_identifier(payload.get("workspace_id"), "workspace_id")
        provider_session_id = payload.get("provider_session_id")
        if provider_session_id is not None:
            provider_session_id = validate_identifier(
                provider_session_id, "provider_session_id"
            )
        prompt = payload.get("content")
        if not isinstance(prompt, str) or not prompt.strip():
            raise GatewayError("content must be a non-empty string")
        if len(prompt) > MAX_PROMPT_CHARS:
            raise GatewayError(f"content exceeds {MAX_PROMPT_CHARS} characters")
        arsenal_url = validate_origin(
            str(payload.get("arsenal_url") or "http://127.0.0.1:8000"),
            allow_remote=self.server.state.allow_remote_arsenal,
        )
        token_file = payload.get("arsenal_token_file")
        if token_file is not None and not isinstance(token_file, str):
            raise GatewayError("arsenal_token_file must be a path")
        client = ArsenalClient(
            arsenal_url,
            token_file=token_file,
            allow_remote=self.server.state.allow_remote_arsenal,
        )
        try:
            client.manifest()
            session_dir = ROOT / "output" / ".redcode" / "gateway-sessions"
            session_path = session_dir / f"{workspace_id}.json"
            create_session(client, workspace_id, session_path)
        except ArsenalClientError as exc:
            raise GatewayError(f"Arsenal handshake failed: {exc}") from exc

        activate_runtime_mode("arsenal", quiet=True)
        environment = os.environ.copy()
        environment.update(
            {
                "REDCODE_MODE": "arsenal",
                "ARSENAL_URL": arsenal_url,
                "ARSENAL_SESSION": str(session_path),
                "ARSENAL_WORKSPACE": workspace_id,
                "OPENCODE_CONFIG_CONTENT": json.dumps(
                    arsenal_opencode_override(environment.get("OPENCODE_CONFIG_CONTENT")),
                    separators=(",", ":"),
                ),
            }
        )
        arguments = [
            self.server.state.opencode_command,
            "run",
            "--format",
            "json",
            "--agent",
            "redcode",
        ]
        if provider_session_id:
            arguments.extend(["--session", provider_session_id])
        else:
            arguments.extend(["--title", f"Arsenal {workspace_id[:8]}"])
        arguments.append(prompt.strip())
        process_options: dict[str, Any] = {}
        if os.name == "posix":
            process_options["start_new_session"] = True
        elif hasattr(subprocess, "CREATE_NEW_PROCESS_GROUP"):
            process_options["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
        try:
            process = subprocess.Popen(
                arguments,
                cwd=ROOT,
                env=environment,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace",
                bufsize=1,
                **process_options,
            )
        except OSError as exc:
            raise GatewayError(f"Cannot start OpenCode: {exc}") from exc
        try:
            self.server.state.register(turn_id, process)
        except Exception:
            process.terminate()
            raise
        self._begin_stream()
        self._event("turn.started", turn_id=turn_id)
        discovered_session = provider_session_id
        text_seen = False
        emitted_characters = 0
        stderr_tail: deque[str] = deque(maxlen=50)

        def drain_stderr() -> None:
            if process.stderr is None:
                return
            for line in process.stderr:
                stderr_tail.append(line[-2000:])

        stderr_thread = threading.Thread(target=drain_stderr, daemon=True)
        stderr_thread.start()
        try:
            assert process.stdout is not None
            for raw_line in process.stdout:
                try:
                    event = json.loads(raw_line)
                except json.JSONDecodeError:
                    continue
                if not isinstance(event, dict):
                    continue
                candidate_session = event.get("sessionID")
                if isinstance(candidate_session, str) and candidate_session != discovered_session:
                    discovered_session = candidate_session
                    self._event("session.bound", provider_session_id=discovered_session)
                text = extract_text(event)
                if text:
                    emitted_characters += len(text)
                    if emitted_characters > MAX_ASSISTANT_CHARS:
                        self.server.state.cancel(turn_id)
                        self._event(
                            "turn.failed",
                            error="OpenCode response exceeded the gateway output limit",
                        )
                        return
                    text_seen = True
                    self._event("assistant.delta", content=text)
                activity = safe_activity(event)
                if activity:
                    self._event("assistant.activity", activity=activity)
            exit_code = process.wait()
            stderr_thread.join(timeout=1)
            stderr = "".join(stderr_tail).strip()
            if exit_code == 0:
                self._event(
                    "turn.completed",
                    provider_session_id=discovered_session,
                    empty=not text_seen,
                )
            else:
                self._event(
                    "turn.failed",
                    error=(stderr[-1000:] or f"OpenCode exited with code {exit_code}"),
                    exit_code=exit_code,
                )
        except (BrokenPipeError, ConnectionResetError):
            self.server.state.cancel(turn_id)
        finally:
            self.server.state.unregister(turn_id)
            if process.poll() is None:
                process.terminate()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("start", nargs="?", default="start", choices=("start",))
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--token-file", type=Path, default=default_token_path())
    parser.add_argument("--opencode-command", default="opencode")
    parser.add_argument("--allow-remote-arsenal", action="store_true")
    parser.add_argument("--allow-remote-bind", action="store_true")
    parser.add_argument("--tls-cert", type=Path)
    parser.add_argument("--tls-key", type=Path)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if args.host not in LOOPBACK_HOSTS:
        if not args.allow_remote_bind:
            raise SystemExit("Non-loopback binding requires --allow-remote-bind")
        if not args.tls_cert or not args.tls_key:
            raise SystemExit("Non-loopback binding requires --tls-cert and --tls-key")
    if bool(args.tls_cert) != bool(args.tls_key):
        raise SystemExit("--tls-cert and --tls-key must be provided together")
    token_path = Path(os.path.abspath(args.token_file.expanduser()))
    token = ensure_private_token(token_path)
    state = GatewayState(
        token=token,
        token_path=token_path,
        allow_remote_arsenal=args.allow_remote_arsenal,
        opencode_command=args.opencode_command,
    )
    server = GatewayServer((args.host, args.port), state)
    scheme = "http"
    if args.tls_cert and args.tls_key:
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.load_cert_chain(args.tls_cert, args.tls_key)
        server.socket = context.wrap_socket(server.socket, server_side=True)
        scheme = "https"
    print(f"RedCode chat gateway {PROTOCOL_VERSION}: {scheme}://{args.host}:{args.port}")
    print(f"Private token: {token_path}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
