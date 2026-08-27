#!/usr/bin/env python3
"""Persistent, human-approved workflow controls for RedCode bug-bounty work.

This script intentionally does not send requests to a target. It turns policy,
selected Burp exports, hypotheses, approvals, evidence, and report drafts into
auditable local state. Network actions remain analyst-approved and must use the
matching reviewed manual workflow outside this controller.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import hmac
import json
import os
from pathlib import Path
import re
import secrets
import sqlite3
import sys
from typing import Any, Iterable
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse
from urllib.request import Request, urlopen

import redcode_control as control


ROOT = control.ROOT
REDACTED = "[REDACTED]"
OMITTED = "[OMITTED]"
SENSITIVE_NAMES = {
    "authorization",
    "cookie",
    "set-cookie",
    "proxy-authorization",
    "x-api-key",
    "x-auth-token",
    "x-csrf-token",
    "csrf",
    "token",
    "secret",
    "password",
    "passwd",
    "session",
}
SAFE_HEADER_NAMES = {
    "accept",
    "content-type",
    "host",
    "origin",
    "referer",
    "user-agent",
    "x-requested-with",
}
UUID_SEGMENT = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$",
    re.IGNORECASE,
)
NUMERIC_SEGMENT = re.compile(r"^\d+$")
OPAQUE_SEGMENT = re.compile(r"^[A-Za-z0-9_-]{20,}$")
SHORT_IDENTIFIER_SEGMENT = re.compile(r"^[A-Za-z0-9_-]{6,}$")
GENERIC_SHORT_IDENTIFIER_SEGMENT = re.compile(r"^[A-Za-z0-9]{6,}$")
SAFE_LABEL = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
FIELD_CAMEL_BOUNDARY = re.compile(r"([a-z0-9])([A-Z])")
FIELD_SEPARATOR = re.compile(r"[^A-Za-z0-9]+")
IDENTIFIER_FIELD_SUFFIX = re.compile(r"(?:^|_)(?:id|identifier)$")
PII_FIELD_NAMES = {
    "address", "email", "first_name", "ip", "last_name", "name", "phone", "username",
}
IDENTIFIER_HMAC_KEY_BYTES = 32
MAX_IDENTIFIER_CONTEXTS = 80
MAX_IDENTIFIER_MESSAGE_REFS = 40
MAX_IDENTIFIER_FACTS_PER_MESSAGE = 500


class BugBountyError(RuntimeError):
    """A recoverable problem that should be shown to the analyst."""


def utc_now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0)


def utc_text(value: dt.datetime | None = None) -> str:
    return (value or utc_now()).isoformat()


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_path(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def identifier_key_path() -> Path:
    """Return the ignored local key used for identifier-only correlation."""
    return ROOT / "output" / ".redcode" / "identifier-hmac.key"


def identifier_hmac_key(connection: sqlite3.Connection, engagement_id: int) -> bytes:
    """Load or create the local HMAC key without persisting raw identifiers."""
    path = identifier_key_path()
    try:
        key = path.read_bytes()
    except FileNotFoundError:
        existing = connection.execute(
            "SELECT COUNT(*) AS count FROM identifier_registry WHERE engagement_id = ?",
            (engagement_id,),
        ).fetchone()
        count = int(existing["count"] if isinstance(existing, sqlite3.Row) else existing[0]) if existing else 0
        if count > 0:
            raise BugBountyError(
                f"identifier fingerprint key is missing; restore {path} before importing more traffic"
            )
        key = secrets.token_bytes(IDENTIFIER_HMAC_KEY_BYTES)
        write_private(path, key)
    except OSError as error:
        raise BugBountyError(f"cannot read identifier fingerprint key: {error}") from error
    if len(key) != IDENTIFIER_HMAC_KEY_BYTES:
        raise BugBountyError(f"identifier fingerprint key is invalid: {path}")
    return key


def identifier_fingerprint(key: bytes, engagement_id: int, value: Any) -> str:
    """Create an engagement-scoped fingerprint; the original value is never stored."""
    message = f"{engagement_id}:".encode("utf-8") + str(value).encode("utf-8")
    return "hmac-sha256:" + hmac.new(key, message, hashlib.sha256).hexdigest()


def require_label(value: str, field: str = "label") -> str:
    if not SAFE_LABEL.fullmatch(value):
        raise BugBountyError(
            f"{field} must contain only letters, numbers, dots, underscores, or hyphens"
        )
    return value


def require_text(value: str, field: str, maximum: int = 1000) -> str:
    text = value.strip()
    if not text:
        raise BugBountyError(f"{field} must not be empty")
    if len(text) > maximum:
        raise BugBountyError(f"{field} must be at most {maximum} characters")
    return text


def output_directory(manifest: dict[str, Any]) -> Path:
    path = ROOT / "output" / manifest["name"] / "scans" / "mappa"
    path.mkdir(parents=True, exist_ok=True)
    if os.name != "nt":
        path.chmod(0o700)
    return path


def write_private(path: Path, content: str | bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(content, str):
        path.write_text(content, encoding="utf-8")
    else:
        path.write_bytes(content)
    if os.name != "nt":
        path.chmod(0o600)


def is_within(path: Path, parent: Path) -> bool:
    try:
        path.resolve().relative_to(parent.resolve())
    except ValueError:
        return False
    return True


def connect(args: argparse.Namespace) -> tuple[sqlite3.Connection, dict[str, Any], Path, int]:
    manifest_file = control.manifest_path(args.manifest)
    try:
        manifest = control.read_manifest(manifest_file)
    except ValueError as error:
        raise BugBountyError(str(error)) from error
    if manifest["workflow"] != "assessment":
        raise BugBountyError("bug-bounty work requires an assessment engagement manifest")
    if "hunt" not in manifest["allowed_actions"]:
        raise BugBountyError("the active manifest must allow the hunt action")

    db_path = control.database_path(args.db)
    try:
        control.migrate_database(db_path)
    except (OSError, sqlite3.Error, RuntimeError) as error:
        raise BugBountyError(f"database migration failed: {error}") from error
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    engagement_id = ensure_engagement(connection, manifest, manifest_file)
    return connection, manifest, manifest_file, engagement_id


def ensure_engagement(
    connection: sqlite3.Connection, manifest: dict[str, Any], manifest_file: Path
) -> int:
    connection.execute(
        "INSERT INTO engagements (engagement_key, name, workflow, mode, manifest_path) "
        "VALUES (?, ?, ?, ?, ?) "
        "ON CONFLICT(engagement_key) DO UPDATE SET "
        "name=excluded.name, workflow=excluded.workflow, mode=excluded.mode, "
        "manifest_path=excluded.manifest_path, updated_at=datetime('now')",
        (
            manifest["name"],
            manifest["name"],
            manifest["workflow"],
            manifest["mode"],
            str(manifest_file),
        ),
    )
    row = connection.execute(
        "SELECT id FROM engagements WHERE engagement_key = ?", (manifest["name"],)
    ).fetchone()
    assert row is not None
    return int(row["id"])


def get_program(connection: sqlite3.Connection, engagement_id: int) -> sqlite3.Row:
    row = connection.execute(
        "SELECT * FROM bug_bounty_programs WHERE engagement_id = ?", (engagement_id,)
    ).fetchone()
    if row is None:
        raise BugBountyError("program not onboarded; run ./redcode bugbounty onboard first")
    return row


def ensure_target(connection: sqlite3.Connection, target: str, scope: str) -> int:
    host, _, _, _ = control.target_parts(target)
    connection.execute(
        "INSERT INTO targets (domain, scope, type) VALUES (?, ?, 'web') "
        "ON CONFLICT(domain) DO UPDATE SET scope=excluded.scope",
        (host, scope),
    )
    row = connection.execute("SELECT id FROM targets WHERE domain = ?", (host,)).fetchone()
    assert row is not None
    return int(row["id"])


def identity_row(
    connection: sqlite3.Connection, engagement_id: int, label: str
) -> sqlite3.Row:
    row = connection.execute(
        "SELECT * FROM identities WHERE engagement_id = ? AND label = ?",
        (engagement_id, label),
    ).fetchone()
    if row is None:
        raise BugBountyError(
            f"unknown symbolic identity '{label}'; add it with ./redcode bugbounty identity add"
        )
    return row


def policy_snapshot(connection: sqlite3.Connection, engagement_id: int) -> sqlite3.Row:
    row = connection.execute(
        "SELECT * FROM policy_snapshots WHERE engagement_id = ? "
        "AND status = 'reviewed' ORDER BY reviewed_at DESC LIMIT 1",
        (engagement_id,),
    ).fetchone()
    if row is None:
        raise BugBountyError("no reviewed program-policy snapshot is available")
    snapshot_path = (ROOT / row["snapshot_path"]).resolve()
    if not is_within(snapshot_path, ROOT / "output") or not snapshot_path.is_file():
        raise BugBountyError(
            "reviewed program-policy snapshot is missing or outside output/; re-onboard the program"
        )
    if sha256_path(snapshot_path) != row["sha256"]:
        raise BugBountyError(
            "reviewed program-policy snapshot no longer matches its recorded hash; re-onboard the program"
        )
    return row


def policy_decision(
    connection: sqlite3.Connection,
    manifest: dict[str, Any],
    engagement_id: int,
    target: str,
    action: str,
) -> tuple[bool, str]:
    allowed, reason = control.scope_decision(manifest, target, action)
    if not allowed:
        return False, f"manifest: {reason}"
    try:
        policy_snapshot(connection, engagement_id)
    except BugBountyError as error:
        return False, str(error)

    restriction = connection.execute(
        "SELECT reason FROM program_restrictions WHERE engagement_id = ? AND active = 1 "
        "AND action IN ('all', ?)",
        (engagement_id, action),
    ).fetchone()
    if restriction is not None:
        return False, f"program policy prohibits {action}: {restriction['reason']}"

    rules = connection.execute(
        "SELECT rule, disposition FROM program_scope_rules "
        "WHERE engagement_id = ? AND active = 1",
        (engagement_id,),
    ).fetchall()
    if not rules:
        return False, "program policy has no active scope rules"
    if any(row["disposition"] == "deny" and control.rule_matches(row["rule"], target) for row in rules):
        return False, f"target {target} matches a program-policy exclusion"
    if not any(
        row["disposition"] == "allow" and control.rule_matches(row["rule"], target)
        for row in rules
    ):
        return False, f"target {target} is outside the reviewed program policy"
    return True, f"{action} is allowed by the manifest and reviewed program policy"


def require_policy_action(
    connection: sqlite3.Connection,
    manifest: dict[str, Any],
    engagement_id: int,
    target: str,
    action: str,
) -> None:
    allowed, reason = policy_decision(connection, manifest, engagement_id, target, action)
    if not allowed:
        raise BugBountyError(reason)


def record_hypothesis_event(
    connection: sqlite3.Connection,
    hypothesis_db_id: int,
    event_type: str,
    *,
    from_status: str | None = None,
    to_status: str | None = None,
    actor: str | None = None,
    details: dict[str, Any] | None = None,
) -> None:
    connection.execute(
        "INSERT INTO hypothesis_events "
        "(hypothesis_id, event_type, from_status, to_status, actor, details_json) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (
            hypothesis_db_id,
            event_type,
            from_status,
            to_status,
            actor,
            canonical_json(details or {}),
        ),
    )


def redact_url(raw_url: str) -> tuple[str, int, list[str]]:
    parsed = urlparse(raw_url)
    if not parsed.scheme or not parsed.hostname:
        raise BugBountyError(f"Burp message has an invalid URL: {raw_url!r}")
    pairs = parse_qsl(parsed.query, keep_blank_values=True)
    query_names = [key for key, _ in pairs]
    redacted = [(key, REDACTED) for key, _ in pairs]
    host = parsed.hostname or ""
    if parsed.port:
        host = f"{host}:{parsed.port}"
    safe_parts = parsed._replace(netloc=host, query=urlencode(redacted, doseq=True), fragment="")
    extra_redactions = int(bool(parsed.username or parsed.password)) + int(bool(parsed.fragment))
    return urlunparse(safe_parts), len(pairs) + extra_redactions, query_names


def safe_origin(parsed: Any) -> str:
    """Return an origin safe to persist as target scope metadata."""
    if not parsed.scheme or not parsed.hostname:
        raise BugBountyError("cannot derive a safe origin from an invalid URL")
    host = parsed.hostname.lower()
    if parsed.port:
        host = f"{host}:{parsed.port}"
    return f"{parsed.scheme.lower()}://{host}"


def safe_target_scope(target: str) -> str:
    """Normalize a user-supplied URL or hostname before writing target metadata."""
    candidate = target.strip()
    parsed = urlparse(candidate if "://" in candidate else f"//{candidate}")
    if not parsed.hostname:
        raise BugBountyError("target must contain a hostname")
    if parsed.scheme:
        return safe_origin(parsed)
    return parsed.hostname.lower()


def header_pairs(value: Any) -> Iterable[tuple[str, str]]:
    if isinstance(value, dict):
        for name, header_value in value.items():
            yield str(name), str(header_value)
    elif isinstance(value, list):
        for item in value:
            if isinstance(item, dict):
                name = item.get("name") or item.get("key")
                header_value = item.get("value", "")
                if name is not None:
                    yield str(name), str(header_value)
            elif isinstance(item, str) and ":" in item:
                name, header_value = item.split(":", 1)
                yield name.strip(), header_value.strip()
    elif isinstance(value, str):
        for line in value.splitlines():
            if ":" in line:
                name, header_value = line.split(":", 1)
                yield name.strip(), header_value.strip()


def redact_headers(value: Any) -> tuple[dict[str, str], int]:
    result: dict[str, str] = {}
    redactions = 0
    for name, header_value in header_pairs(value):
        normalized = name.lower()
        if normalized in SENSITIVE_NAMES or any(token in normalized for token in SENSITIVE_NAMES):
            result[name] = REDACTED
            redactions += 1
        elif normalized in SAFE_HEADER_NAMES:
            if normalized == "referer":
                try:
                    result[name], count, _ = redact_url(header_value)
                    redactions += count
                except BugBountyError:
                    result[name] = OMITTED
                    redactions += 1
            else:
                result[name] = header_value[:512]
        else:
            result[name] = OMITTED
            redactions += 1
    return result, redactions


def redact_json(value: Any, key: str = "") -> tuple[Any, int]:
    normalized = key.lower()
    if normalized and (
        normalized in SENSITIVE_NAMES
        or any(token in normalized for token in SENSITIVE_NAMES)
    ):
        return REDACTED, 1
    if isinstance(value, dict):
        result: dict[str, Any] = {}
        count = 0
        for child_key, child_value in value.items():
            redacted, child_count = redact_json(child_value, str(child_key))
            result[str(child_key)] = redacted
            count += child_count
        return result, count
    if isinstance(value, list):
        result_list: list[Any] = []
        count = 0
        for item in value[:100]:
            redacted, child_count = redact_json(item, key)
            result_list.append(redacted)
            count += child_count
        return result_list, count
    if value is None or isinstance(value, bool):
        return value, 0
    return OMITTED, 1


def redact_body(value: Any) -> tuple[Any, int]:
    if value is None or value == "":
        return None, 0
    if isinstance(value, (dict, list)):
        return redact_json(value)
    text = str(value)
    try:
        return redact_json(json.loads(text))
    except (TypeError, json.JSONDecodeError):
        pairs = parse_qsl(text, keep_blank_values=True)
        if pairs and "=" in text:
            return {key: REDACTED for key, _ in pairs}, len(pairs)
    return {"omitted_sha256": sha256_bytes(text.encode("utf-8")), "bytes": len(text)}, 1


def normalize_path(path: str) -> tuple[str, bool]:
    """Normalize the generic endpoint shape, independent of semantic overlay."""
    segments = path.split("/")
    normalized: list[str] = []
    has_object_id = False
    for segment in segments:
        # Keep generic endpoint keys independent of semantic observations.  A
        # short identifier is normalized only when it has no separators; route
        # names such as ``campaigns_data_v2`` remain distinct endpoints.  The
        # semantic overlay still observes broader candidates separately via
        # path_identifier_segments.
        if generic_identifier_segment(segment):
            normalized.append("{id}")
            has_object_id = True
        else:
            normalized.append(segment)
    result = "/".join(normalized) or "/"
    return result if result.startswith("/") else f"/{result}", has_object_id


def generic_identifier_segment(segment: str) -> bool:
    """Return whether a segment belongs to the generic endpoint key shape."""
    if NUMERIC_SEGMENT.fullmatch(segment) or UUID_SEGMENT.fullmatch(segment) or OPAQUE_SEGMENT.fullmatch(segment):
        return True
    if not GENERIC_SHORT_IDENTIFIER_SEGMENT.fullmatch(segment):
        return False
    return bool(re.search(r"[A-Za-z]", segment) and re.search(r"\d", segment))


def is_identifier_segment(segment: str) -> bool:
    """Classify structure only; this deliberately does not assign an entity role."""
    if NUMERIC_SEGMENT.fullmatch(segment) or UUID_SEGMENT.fullmatch(segment) or OPAQUE_SEGMENT.fullmatch(segment):
        return True
    if not SHORT_IDENTIFIER_SEGMENT.fullmatch(segment):
        return False
    return bool(re.search(r"[A-Za-z]", segment) and re.search(r"\d", segment))


def path_identifier_segments(path: str) -> list[tuple[int, str]]:
    """Return 1-based non-empty path positions and their raw candidate values."""
    return [
        (position, segment)
        for position, segment in enumerate((part for part in path.split("/") if part), start=1)
        if is_identifier_segment(segment)
    ]


def normalize_field_label(value: Any) -> str:
    text = FIELD_CAMEL_BOUNDARY.sub(r"\1_\2", str(value)).strip()
    text = FIELD_SEPARATOR.sub("_", text).strip("_").lower()
    return text[:128]


def is_safe_identifier_field(label: str) -> bool:
    normalized = normalize_field_label(label)
    if not normalized or normalized in PII_FIELD_NAMES:
        return False
    if normalized in SENSITIVE_NAMES or any(token in normalized for token in SENSITIVE_NAMES):
        return False
    return bool(IDENTIFIER_FIELD_SUFFIX.search(normalized))


def scalar_identifier(value: Any) -> str | None:
    if value is None or isinstance(value, bool) or isinstance(value, (dict, list)):
        return None
    text = str(value)
    if not text or len(text) > 512:
        return None
    return text


def message_value(message: dict[str, Any], name: str, default: Any = None) -> Any:
    request = message.get("request")
    if isinstance(request, dict) and name in request:
        return request[name]
    return message.get(name, default)


def message_part_value(
    message: dict[str, Any], part: str, name: str, default: Any = None
) -> Any:
    value = message.get(part)
    if isinstance(value, dict) and name in value:
        return value[name]
    if part == "request":
        return message_value(message, name, default)
    aliases = {
        "response": ("response", "response_data"),
        "request": ("request",),
    }
    for alias in aliases.get(part, (part,)):
        candidate = message.get(alias)
        if isinstance(candidate, dict) and name in candidate:
            return candidate[name]
    return message.get(f"{part}_{name}", default)


def structured_body(value: Any) -> tuple[Any, str | None]:
    """Decode JSON/form data for in-memory observation only."""
    if isinstance(value, (dict, list)):
        return value, "json"
    if value is None or value == "":
        return None, None
    text = str(value)
    try:
        return json.loads(text), "json"
    except (TypeError, json.JSONDecodeError):
        pairs = parse_qsl(text, keep_blank_values=True)
        if pairs and "=" in text:
            return {key: item for key, item in pairs}, "form"
    return None, None


def iter_structured_values(value: Any, path: tuple[str, ...] = ()) -> Iterable[tuple[str, tuple[str, ...], Any]]:
    if isinstance(value, dict):
        for key, child in value.items():
            child_path = path + (str(key),)
            if isinstance(child, (dict, list)):
                yield from iter_structured_values(child, child_path)
            else:
                yield str(key), child_path, child
    elif isinstance(value, list):
        for index, child in enumerate(value[:100]):
            child_path = path + (str(index),)
            if isinstance(child, (dict, list)):
                yield from iter_structured_values(child, child_path)
            elif path:
                yield path[-1], child_path, child


def identifier_observation_facts(
    message: dict[str, Any],
    raw_url: str,
    *,
    engagement_id: int,
    endpoint_id: int,
    source_reference: str,
    hmac_key: bytes,
) -> list[dict[str, Any]]:
    """Extract safe identifier facts while raw values are still in memory."""
    facts: list[dict[str, Any]] = []

    def add_fact(
        value: Any,
        *,
        context: str,
        field_label: str | None = None,
        field_path: str | None = None,
        position: int | None = None,
        require_identifier_shape: bool = False,
    ) -> None:
        if len(facts) >= MAX_IDENTIFIER_FACTS_PER_MESSAGE:
            return
        raw = scalar_identifier(value)
        if raw is None or (require_identifier_shape and not is_identifier_segment(raw)):
            return
        if field_label is not None and not is_safe_identifier_field(field_label):
            return
        facts.append(
            {
                "fingerprint": identifier_fingerprint(hmac_key, engagement_id, raw),
                "context": context,
                "endpoint_id": endpoint_id,
                "position": position,
                "field_label": normalize_field_label(field_label) if field_label else None,
                "observed_label": str(field_label)[:128] if field_label else None,
                "field_path": (field_path or "")[:256] or None,
                "message_ref": source_reference,
            }
        )

    parsed = urlparse(raw_url)
    for position, raw in path_identifier_segments(parsed.path or "/"):
        add_fact(raw, context="path", position=position, require_identifier_shape=True)
    for label, value in parse_qsl(parsed.query, keep_blank_values=True):
        add_fact(
            value,
            context="query",
            field_label=label,
            field_path=label,
            require_identifier_shape=not is_safe_identifier_field(label),
        )

    for part in ("request", "response"):
        body = message_part_value(message, part, "body")
        if body is None:
            candidate = message.get(part)
            if part == "response":
                candidate = candidate or message.get("response_data") or message.get("response_body")
            if isinstance(candidate, (dict, list)) and (
                isinstance(candidate, list)
                or not any(key in candidate for key in ("body", "headers", "status", "status_code", "method"))
            ):
                body = candidate
        decoded, format_name = structured_body(body)
        if decoded is None or format_name is None:
            continue
        context = f"{part}_{format_name}"
        for label, field_path, value in iter_structured_values(decoded):
            add_fact(
                value,
                context=context,
                field_label=label,
                field_path=".".join(field_path),
            )
    return facts


def message_url(message: dict[str, Any]) -> str:
    value = message_value(message, "url")
    if value:
        return str(value)
    host = message_value(message, "host")
    path = message_value(message, "path", "/")
    scheme = message_value(message, "scheme", "https")
    if host:
        return f"{scheme}://{host}{path}"
    raise BugBountyError("Burp message is missing url or host/path")


def parse_messages(source: Path) -> list[dict[str, Any]]:
    try:
        text = source.read_text(encoding="utf-8")
    except OSError as error:
        raise BugBountyError(f"cannot read Burp export: {error}") from error
    try:
        decoded = json.loads(text)
    except json.JSONDecodeError:
        decoded = []
        for line_number, line in enumerate(text.splitlines(), start=1):
            if not line.strip():
                continue
            try:
                decoded.append(json.loads(line))
            except json.JSONDecodeError as error:
                raise BugBountyError(
                    f"invalid JSONL in Burp export at line {line_number}: {error}"
                ) from error
    if isinstance(decoded, dict):
        for key in ("messages", "items", "history", "site_map"):
            if isinstance(decoded.get(key), list):
                decoded = decoded[key]
                break
        else:
            decoded = [decoded]
    if not isinstance(decoded, list) or any(not isinstance(item, dict) for item in decoded):
        raise BugBountyError("Burp export must be a JSON array, JSONL, or an object containing messages")
    return decoded


def merged_endpoint_metadata(
    existing_json: str | None,
    *,
    query_parameters: list[str],
    identity_label: str,
    has_object_id: bool,
) -> dict[str, Any]:
    """Preserve accumulated safe endpoint observations across imports."""
    try:
        existing = json.loads(existing_json or "{}")
    except json.JSONDecodeError:
        existing = {}
    if not isinstance(existing, dict):
        existing = {}
    prior_parameters = existing.get("query_parameters", [])
    prior_identities = existing.get("identity_labels", [])
    if not isinstance(prior_parameters, list):
        prior_parameters = []
    if not isinstance(prior_identities, list):
        prior_identities = []
    metadata = dict(existing)
    metadata.update(
        {
            "query_parameters": sorted({str(item) for item in prior_parameters} | set(query_parameters)),
            "identity_labels": sorted({str(item) for item in prior_identities} | {identity_label}),
            "has_object_identifier": bool(existing.get("has_object_identifier")) or has_object_id,
        }
    )
    return metadata


def json_list(value: str | None) -> list[Any]:
    try:
        decoded = json.loads(value or "[]")
    except json.JSONDecodeError:
        return []
    return decoded if isinstance(decoded, list) else []


def context_key(fact: dict[str, Any]) -> str:
    return canonical_json(
        {
            "context": fact.get("context"),
            "endpoint_id": fact.get("endpoint_id"),
            "position": fact.get("position"),
            "field_label": fact.get("field_label"),
            "field_path": fact.get("field_path"),
        }
    )


def merge_identifier_facts(
    connection: sqlite3.Connection,
    engagement_id: int,
    facts: Iterable[dict[str, Any]],
) -> None:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for fact in facts:
        grouped.setdefault(str(fact["fingerprint"]), []).append(fact)
    for fingerprint, fingerprint_facts in grouped.items():
        row = connection.execute(
            "SELECT roles_json, contexts_json FROM identifier_registry "
            "WHERE engagement_id = ? AND fingerprint = ?",
            (engagement_id, fingerprint),
        ).fetchone()
        roles = [item for item in json_list(row["roles_json"] if row else None) if isinstance(item, dict)]
        contexts = [item for item in json_list(row["contexts_json"] if row else None) if isinstance(item, dict)]
        for fact in fingerprint_facts:
            key = context_key(fact)
            existing = next((item for item in contexts if item.get("key") == key), None)
            if existing is None:
                existing = {
                    "key": key,
                    "context": fact.get("context"),
                    "endpoint_id": fact.get("endpoint_id"),
                    "position": fact.get("position"),
                    "field_label": fact.get("field_label"),
                    "observed_label": fact.get("observed_label"),
                    "field_path": fact.get("field_path"),
                    "occurrences": 0,
                    "message_refs": [],
                }
                contexts.append(existing)
            existing["occurrences"] = min(10000, int(existing.get("occurrences", 0)) + 1)
            refs = existing.setdefault("message_refs", [])
            if fact.get("message_ref") and fact["message_ref"] not in refs:
                refs.append(fact["message_ref"])
                del refs[:-MAX_IDENTIFIER_MESSAGE_REFS]
        if len(contexts) > MAX_IDENTIFIER_CONTEXTS:
            contexts.sort(key=lambda item: (str(item.get("context")), str(item.get("field_path"))))
            contexts = contexts[:MAX_IDENTIFIER_CONTEXTS]
        connection.execute(
            "INSERT INTO identifier_registry (engagement_id, fingerprint, roles_json, contexts_json) "
            "VALUES (?, ?, ?, ?) ON CONFLICT(engagement_id, fingerprint) DO UPDATE SET "
            "roles_json=excluded.roles_json, contexts_json=excluded.contexts_json, updated_at=datetime('now')",
            (engagement_id, fingerprint, canonical_json(roles), canonical_json(contexts)),
        )


def role_evidence(contexts: list[dict[str, Any]], role: str) -> dict[str, Any]:
    field_contexts = [item for item in contexts if item.get("field_label") == role]
    path_contexts = [item for item in contexts if item.get("context") == "path"]
    field_occurrences = sum(int(item.get("occurrences", 0)) for item in field_contexts)
    path_occurrences = sum(int(item.get("occurrences", 0)) for item in path_contexts)
    messages = {
        ref
        for item in field_contexts + path_contexts
        for ref in item.get("message_refs", [])
        if isinstance(ref, str)
    }
    if field_occurrences >= 3 and path_occurrences >= 2 and len(messages) >= 3:
        confidence, status = "high", "inferred"
    elif field_occurrences >= 2 and path_occurrences >= 1 and len(messages) >= 2:
        confidence, status = "medium", "inferred"
    elif field_occurrences and path_occurrences:
        confidence, status = "low", "proposed"
    else:
        confidence, status = "low", "observed"
    aliases = sorted({str(item.get("observed_label")) for item in field_contexts if item.get("observed_label")})
    return {
        "role": role,
        "status": status,
        "confidence": confidence,
        "field_observations": field_occurrences,
        "path_observations": path_occurrences,
        "message_count": len(messages),
        "aliases": aliases,
    }


def endpoint_metadata(endpoint: sqlite3.Row) -> dict[str, Any]:
    try:
        decoded = json.loads(endpoint["metadata_json"] or "{}")
    except json.JSONDecodeError:
        decoded = {}
    return decoded if isinstance(decoded, dict) else {}


def semantic_display_template(generic_template: str, parameters: list[dict[str, Any]]) -> str:
    segments = [part for part in generic_template.split("/") if part]
    selected = {
        int(item["position"]): str(item["selected_role"])
        for item in parameters
        if item.get("selected_role") and isinstance(item.get("position"), int)
    }
    rendered = [selected.get(position, segment) for position, segment in enumerate(segments, start=1)]
    return "/" + "/".join(rendered) if rendered else "/"


def refresh_identifier_semantics(
    connection: sqlite3.Connection,
    engagement_id: int,
    endpoint_ids: Iterable[int],
) -> None:
    registry_rows = connection.execute(
        "SELECT fingerprint, roles_json, contexts_json FROM identifier_registry "
        "WHERE engagement_id = ?",
        (engagement_id,),
    ).fetchall()
    path_bindings: dict[tuple[int, int], list[dict[str, Any]]] = {}
    global_role_contexts: dict[str, list[dict[str, Any]]] = {}
    for registry in registry_rows:
        contexts = [item for item in json_list(registry["contexts_json"]) if isinstance(item, dict)]
        for context in contexts:
            role = context.get("field_label")
            if not role:
                continue
            global_role_contexts.setdefault(str(role), []).append(context)
            global_role_contexts[str(role)].extend(
                item for item in contexts if item.get("context") == "path"
            )
    for registry in registry_rows:
        contexts = [item for item in json_list(registry["contexts_json"]) if isinstance(item, dict)]
        roles = [item for item in json_list(registry["roles_json"]) if isinstance(item, dict)]
        role_names = sorted({str(item.get("field_label")) for item in contexts if item.get("field_label")})
        role_objects = {str(item.get("role")): item for item in roles if item.get("role")}
        for role in role_names:
            evidence = role_evidence(global_role_contexts.get(role, contexts), role)
            prior = role_objects.get(role, {})
            if prior.get("status") in {"confirmed", "contradicted"}:
                evidence["status"] = prior["status"]
            for key in ("reviewed_by", "reviewed_at", "review_note"):
                if prior.get(key) is not None:
                    evidence[key] = prior[key]
            role_objects[role] = evidence
        connection.execute(
            "UPDATE identifier_registry SET roles_json = ?, updated_at=datetime('now') "
            "WHERE engagement_id = ? AND fingerprint = ?",
            (canonical_json(sorted(role_objects.values(), key=lambda item: str(item.get("role")))), engagement_id, registry["fingerprint"]),
        )
        for context in contexts:
            if context.get("context") != "path" or context.get("endpoint_id") is None or context.get("position") is None:
                continue
            for role, evidence in role_objects.items():
                if any(item.get("field_label") == role for item in contexts):
                    path_bindings.setdefault((int(context["endpoint_id"]), int(context["position"])), []).append(
                        {
                            "role": role,
                            "fingerprint": registry["fingerprint"],
                            "status": evidence.get("status", "observed"),
                            "confidence": evidence.get("confidence", "low"),
                            "field_observations": evidence.get("field_observations", 0),
                            "path_observations": evidence.get("path_observations", 0),
                        }
                    )
    ids = sorted(set(int(value) for value in endpoint_ids))
    if not ids:
        return
    placeholders = ",".join("?" for _ in ids)
    endpoints = connection.execute(
        f"SELECT id, host, path_template, metadata_json FROM endpoints WHERE engagement_id = ? AND id IN ({placeholders})",
        [engagement_id, *ids],
    ).fetchall()
    workflow_rows = connection.execute(
        "SELECT id, workflow_key, semantics_json FROM application_workflows WHERE engagement_id = ?",
        (engagement_id,),
    ).fetchall()
    workflows_by_key = {str(row["workflow_key"]): row for row in workflow_rows}
    lead_updates: dict[int, list[dict[str, Any]]] = {}
    for endpoint in endpoints:
        metadata = endpoint_metadata(endpoint)
        old_semantic = metadata.get("semantic_path") if isinstance(metadata.get("semantic_path"), dict) else {}
        parameters: list[dict[str, Any]] = []
        path_parts = [part for part in endpoint["path_template"].split("/") if part]
        positions = [position for position, part in enumerate(path_parts, start=1) if part == "{id}"]
        for position in positions:
            candidates_by_role: dict[str, dict[str, Any]] = {}
            for candidate in path_bindings.get((int(endpoint["id"]), position), []):
                current = candidates_by_role.get(candidate["role"])
                if current is None or (candidate["field_observations"], candidate["path_observations"]) > (
                    current["field_observations"], current["path_observations"]
                ):
                    candidates_by_role[candidate["role"]] = candidate
            prior_parameter = next(
                (item for item in old_semantic.get("parameters", []) if item.get("position") == position),
                {},
            ) if isinstance(old_semantic.get("parameters"), list) else {}
            prior_candidates = {
                str(item.get("role")): item
                for item in prior_parameter.get("candidates", [])
                if isinstance(item, dict) and item.get("role")
            }
            for role, candidate in prior_candidates.items():
                if role not in candidates_by_role and candidate.get("status") in {"confirmed", "contradicted"}:
                    candidates_by_role[role] = candidate
                elif role in candidates_by_role and candidate.get("status") in {"confirmed", "contradicted"}:
                    candidates_by_role[role].update(
                        {key: value for key, value in candidate.items() if key in {"status", "reviewed_by", "reviewed_at", "review_note"}}
                    )
            parameter = {
                "position": position,
                "status": "unknown" if not candidates_by_role else "proposed",
                "candidates": sorted(candidates_by_role.values(), key=lambda item: str(item.get("role"))),
            }
            selected = prior_parameter.get("selected_role")
            if selected:
                parameter["selected_role"] = selected
                parameter["status"] = "confirmed"
            parameters.append(parameter)
        semantic_path = {
            "generic_template": endpoint["path_template"],
            "parameters": parameters,
            "display_template": semantic_display_template(endpoint["path_template"], parameters),
        }
        metadata["semantic_path"] = semantic_path
        connection.execute(
            "UPDATE endpoints SET metadata_json = ?, last_seen_at=last_seen_at WHERE id = ?",
            (canonical_json(metadata), endpoint["id"]),
        )
        named_parameters = [
            item for item in parameters
            if item.get("candidates") and any(
                candidate.get("role")
                and candidate.get("status") not in {"contradicted", "unknown"}
                for candidate in item["candidates"]
            )
        ]
        roles = sorted({
            str(candidate["role"])
            for item in named_parameters
            for candidate in item.get("candidates", [])
            if candidate.get("role") and candidate.get("status") != "contradicted"
        })
        if len(named_parameters) >= 2 and len(roles) >= 2:
            workflow = workflows_by_key.get(f"{endpoint['host']}:{root_segment(endpoint['path_template'])}")
            if workflow is not None:
                lead = {
                    "id": semantic_key(
                        "identifier-lead",
                        {"endpoint_id": int(endpoint["id"]), "roles": roles},
                    ),
                    "endpoint_id": int(endpoint["id"]),
                    "roles": roles,
                    "relation": "candidate-scope",
                    "status": "proposed",
                    "evidence": "Named identifier candidates co-occur on one observed endpoint.",
                }
                lead_updates.setdefault(int(workflow["id"]), []).append(lead)
    for workflow_id, leads in lead_updates.items():
        row = next(item for item in workflow_rows if int(item["id"]) == workflow_id)
        semantics = workflow_semantics(row["semantics_json"])
        prior = {
            str(item.get("id")): item
            for item in semantics.get("identifier_leads", [])
            if isinstance(item, dict) and item.get("id")
        }
        for lead in leads:
            old = prior.get(lead["id"])
            if old and old.get("status") in {"confirmed", "rejected"}:
                lead = {**lead, **old}
            prior[lead["id"]] = lead
        semantics["identifier_leads"] = sorted(prior.values(), key=lambda item: str(item.get("id")))
        connection.execute(
            "UPDATE application_workflows SET semantics_json = ?, updated_at=datetime('now') WHERE id = ?",
            (canonical_json(semantics), workflow_id),
        )


def upsert_endpoint(
    connection: sqlite3.Connection,
    engagement_id: int,
    target_id: int,
    parsed: Any,
    method: str,
    path_template: str,
    *,
    query_parameters: list[str],
    identity_label: str,
    has_object_id: bool,
) -> int:
    endpoint_key = f"{parsed.scheme.lower()}://{parsed.hostname.lower()} {method} {path_template}"
    state_change = int(method in {"POST", "PUT", "PATCH", "DELETE"})
    existing = connection.execute(
        "SELECT metadata_json FROM endpoints WHERE engagement_id = ? AND endpoint_key = ?",
        (engagement_id, endpoint_key),
    ).fetchone()
    metadata = merged_endpoint_metadata(
        existing["metadata_json"] if existing is not None else None,
        query_parameters=query_parameters,
        identity_label=identity_label,
        has_object_id=has_object_id,
    )
    connection.execute(
        "INSERT INTO endpoints "
        "(engagement_id, target_id, endpoint_key, host, method, path_template, protocol, "
        "state_change, auth_required, source, metadata_json) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'burp', ?) "
        "ON CONFLICT(engagement_id, endpoint_key) DO UPDATE SET "
        "last_seen_at=datetime('now'), state_change=MAX(endpoints.state_change, excluded.state_change), "
        "auth_required=MAX(COALESCE(endpoints.auth_required, 0), excluded.auth_required), "
        "metadata_json=excluded.metadata_json",
        (
            engagement_id,
            target_id,
            endpoint_key,
            parsed.hostname.lower(),
            method,
            path_template,
            parsed.scheme.lower(),
            state_change,
            int(identity_label != "anon"),
            canonical_json(metadata),
        ),
    )
    row = connection.execute(
        "SELECT id FROM endpoints WHERE engagement_id = ? AND endpoint_key = ?",
        (engagement_id, endpoint_key),
    ).fetchone()
    assert row is not None
    return int(row["id"])


def command_onboard(args: argparse.Namespace) -> int:
    connection, manifest, _, engagement_id = connect(args)
    try:
        policy_file = Path(args.policy_file).expanduser().resolve()
        if not policy_file.is_file():
            raise BugBountyError(f"policy snapshot file not found: {policy_file}")
        policy_bytes = policy_file.read_bytes()
        if len(policy_bytes) > 5 * 1024 * 1024:
            raise BugBountyError("policy snapshot is larger than 5 MiB")
        program_dir = output_directory(manifest)
        digest = sha256_bytes(policy_bytes)
        snapshot_name = (
            f"policy-{utc_now().strftime('%Y%m%dT%H%M%SZ')}-{digest[:12]}"
            f"{policy_file.suffix or '.txt'}"
        )
        snapshot_path = program_dir / snapshot_name
        write_private(snapshot_path, policy_bytes)

        old_snapshots = connection.execute(
            "SELECT id FROM policy_snapshots WHERE engagement_id = ? AND status = 'reviewed'",
            (engagement_id,),
        ).fetchall()
        if old_snapshots:
            connection.execute(
                "UPDATE policy_snapshots SET status = 'superseded' "
                "WHERE engagement_id = ? AND status = 'reviewed'",
                (engagement_id,),
            )
        connection.execute(
            "INSERT INTO policy_snapshots "
            "(engagement_id, source_url, snapshot_path, sha256, reviewed_by, reviewed_at, notes) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                engagement_id,
                args.policy_url,
                str(snapshot_path.relative_to(ROOT)),
                digest,
                args.reviewed_by,
                utc_text(),
                args.policy_notes,
            ),
        )
        snapshot_id = int(connection.execute("SELECT last_insert_rowid()").fetchone()[0])
        active_plans = connection.execute(
            "SELECT p.id, p.hypothesis_id, p.status, h.status AS hypothesis_status "
            "FROM test_plans p JOIN hypotheses h ON h.id = p.hypothesis_id "
            "WHERE p.engagement_id = ? AND p.status IN ('draft', 'approved', 'testing')",
            (engagement_id,),
        ).fetchall()
        connection.execute(
            "DELETE FROM program_scope_rules WHERE engagement_id = ? AND active = 0",
            (engagement_id,),
        )
        connection.execute(
            "DELETE FROM program_restrictions WHERE engagement_id = ? AND active = 0",
            (engagement_id,),
        )
        connection.execute(
            "UPDATE program_scope_rules SET active = 0 WHERE engagement_id = ? AND active = 1",
            (engagement_id,),
        )
        connection.execute(
            "UPDATE program_restrictions SET active = 0 WHERE engagement_id = ? AND active = 1",
            (engagement_id,),
        )
        if active_plans:
            connection.execute(
                "UPDATE approval_executions SET status = 'cancelled', completed_at = datetime('now'), "
                "result_summary = COALESCE(result_summary, 'Cancelled because the reviewed policy changed') "
                "WHERE test_plan_id IN (SELECT id FROM test_plans WHERE engagement_id = ?) "
                "AND status = 'started'",
                (engagement_id,),
            )
            connection.execute(
                "UPDATE test_plans SET status = CASE WHEN status = 'draft' THEN 'superseded' ELSE 'cancelled' END, "
                "updated_at = datetime('now') WHERE engagement_id = ? "
                "AND status IN ('draft', 'approved', 'testing')",
                (engagement_id,),
            )
            reset_hypotheses: set[int] = set()
            for plan in active_plans:
                if plan["hypothesis_status"] in {"approved", "testing"} and plan["hypothesis_id"] not in reset_hypotheses:
                    reset_hypotheses.add(int(plan["hypothesis_id"]))
                    connection.execute(
                        "UPDATE hypotheses SET status = 'queued' WHERE id = ?",
                        (plan["hypothesis_id"],),
                    )
                    record_hypothesis_event(
                        connection,
                        int(plan["hypothesis_id"]),
                        "policy-changed",
                        from_status=plan["hypothesis_status"],
                        to_status="queued",
                        actor=args.reviewed_by,
                        details={"cancelled_plan_id": plan["id"]},
                    )
        for rule in args.scope:
            connection.execute(
                "INSERT INTO program_scope_rules (engagement_id, rule, disposition, source_snapshot_id) "
                "VALUES (?, ?, 'allow', ?)",
                (engagement_id, rule, snapshot_id),
            )
        for rule in args.out_of_scope or []:
            connection.execute(
                "INSERT INTO program_scope_rules (engagement_id, rule, disposition, source_snapshot_id) "
                "VALUES (?, ?, 'deny', ?)",
                (engagement_id, rule, snapshot_id),
            )
        for action in args.prohibit_action or []:
            connection.execute(
                "INSERT INTO program_restrictions "
                "(engagement_id, action, reason, source_snapshot_id) VALUES (?, ?, ?, ?)",
                (engagement_id, action, args.restriction_reason or "program policy", snapshot_id),
            )
        connection.execute(
            "INSERT INTO bug_bounty_programs "
            "(engagement_id, platform, program_name, program_url, policy_url, policy_snapshot_path, "
            "currency, minimum_bounty, maximum_bounty, account_requirements, duplicate_risk, notes) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?) "
            "ON CONFLICT(engagement_id) DO UPDATE SET "
            "platform=excluded.platform, program_name=excluded.program_name, "
            "program_url=excluded.program_url, policy_url=excluded.policy_url, "
            "policy_snapshot_path=excluded.policy_snapshot_path, currency=excluded.currency, "
            "minimum_bounty=excluded.minimum_bounty, maximum_bounty=excluded.maximum_bounty, "
            "account_requirements=excluded.account_requirements, duplicate_risk=excluded.duplicate_risk, "
            "notes=excluded.notes, updated_at=datetime('now')",
            (
                engagement_id,
                args.platform,
                args.program_name,
                args.program_url,
                args.policy_url,
                str(snapshot_path.relative_to(ROOT)),
                args.currency,
                args.minimum_bounty,
                args.maximum_bounty,
                args.account_requirements,
                args.duplicate_risk,
                args.notes,
            ),
        )
        connection.execute(
            "INSERT INTO identities (engagement_id, label, auth_state, notes) VALUES (?, 'anon', 'anonymous', ?) "
            "ON CONFLICT(engagement_id, label) DO NOTHING",
            (engagement_id, "Baseline unauthenticated traffic"),
        )
        connection.execute(
            "INSERT INTO hunt_sessions (engagement_id, objective, status) VALUES (?, ?, 'running')",
            (engagement_id, args.objective or "Initial program mapping"),
        )
        connection.commit()
        print(f"Program onboarded: {args.program_name} ({args.platform})")
        print(f"Reviewed policy snapshot: {snapshot_path.relative_to(ROOT)}")
        print(f"Program policy scope: {len(args.scope)} allow rule(s), {len(args.out_of_scope or [])} exclusion(s)")
        print("Next: add symbolic identities, then import a selected redacted Burp export.")
        return 0
    finally:
        connection.close()


def command_identity_add(args: argparse.Namespace) -> int:
    connection, manifest, _, engagement_id = connect(args)
    try:
        label = require_label(args.label)
        target_id = None
        if args.target:
            require_policy_action(connection, manifest, engagement_id, args.target, "hunt")
            target_id = ensure_target(connection, args.target, safe_target_scope(args.target))
        connection.execute(
            "INSERT INTO identities "
            "(engagement_id, target_id, label, tenant, role, auth_state, burp_label, notes) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?) "
            "ON CONFLICT(engagement_id, label) DO UPDATE SET "
            "target_id=excluded.target_id, tenant=excluded.tenant, role=excluded.role, "
            "auth_state=excluded.auth_state, burp_label=excluded.burp_label, notes=excluded.notes, "
            "updated_at=datetime('now')",
            (
                engagement_id,
                target_id,
                label,
                args.tenant,
                args.role,
                args.auth_state,
                args.burp_label,
                args.notes,
            ),
        )
        connection.commit()
        print(f"Symbolic identity saved: {label}")
        return 0
    finally:
        connection.close()


def command_check(args: argparse.Namespace) -> int:
    connection, manifest, _, engagement_id = connect(args)
    try:
        get_program(connection, engagement_id)
        allowed, reason = policy_decision(
            connection, manifest, engagement_id, args.target, args.action
        )
        print(("ALLOW: " if allowed else "DENY: ") + reason)
        return 0 if allowed else 1
    finally:
        connection.close()


def command_ingest(args: argparse.Namespace) -> int:
    connection, manifest, _, engagement_id = connect(args)
    try:
        get_program(connection, engagement_id)
        identity = identity_row(connection, engagement_id, args.identity)
        source = Path(args.file).expanduser().resolve()
        messages = parse_messages(source)
        source_hash = sha256_path(source)
        cursor = args.cursor or source_hash[:16]
        connection.execute(
            "INSERT INTO burp_import_runs "
            "(engagement_id, source_kind, source_path, source_sha256, cursor_value) "
            "VALUES (?, ?, ?, ?, ?)",
            (engagement_id, args.source_kind, str(source), source_hash, cursor),
        )
        import_id = int(connection.execute("SELECT last_insert_rowid()").fetchone()[0])
        artifact_path = output_directory(manifest) / f"burp-import-{import_id}.redacted.json"
        artifacts: list[dict[str, Any]] = []
        hmac_key = identifier_hmac_key(connection, engagement_id)
        identifier_endpoint_ids: set[int] = set()
        imported = skipped = redactions = 0
        for index, message in enumerate(messages, start=1):
            try:
                raw_url = message_url(message)
                safe_url, url_redactions, query_parameters = redact_url(raw_url)
                parsed = urlparse(raw_url)
                require_policy_action(connection, manifest, engagement_id, raw_url, "hunt")
                method = str(message_value(message, "method", "GET")).upper()
                if method not in {"GET", "HEAD", "OPTIONS", "POST", "PUT", "PATCH", "DELETE"}:
                    raise BugBountyError(f"unsupported HTTP method in Burp export: {method}")
                path_template, has_object_id = normalize_path(parsed.path or "/")
                persisted_url = urlunparse(urlparse(safe_url)._replace(path=path_template))
                # Targets are persisted long-lived. Never retain raw query values,
                # userinfo, or fragments there merely because Burp observed them.
                target_id = ensure_target(connection, safe_url, safe_origin(parsed))
                endpoint_id = upsert_endpoint(
                    connection,
                    engagement_id,
                    target_id,
                    parsed,
                    method,
                    path_template,
                    query_parameters=query_parameters,
                    identity_label=str(identity["label"]),
                    has_object_id=has_object_id,
                )
                source_reference = str(
                    message.get("id")
                    or message.get("message_id")
                    or message.get("reference")
                    or f"{source_hash[:16]}-{index}"
                )
                # Burp message identifiers are commonly unique only within one
                # export/project. Namespace them by the selected export so two
                # distinct sources cannot overwrite each other's provenance.
                reference = f"{source_hash[:16]}:{source_reference}"
                fingerprint = sha256_bytes(
                    canonical_json(
                        {
                            "identity_id": int(identity["id"]),
                            "method": method,
                            "url": persisted_url,
                        }
                    ).encode("utf-8")
                )
                headers, header_redactions = redact_headers(message_value(message, "headers", {}))
                body, body_redactions = redact_body(message_value(message, "body"))
                redactions += url_redactions + header_redactions + body_redactions
                identifier_facts = identifier_observation_facts(
                    message,
                    raw_url,
                    engagement_id=engagement_id,
                    endpoint_id=endpoint_id,
                    source_reference=reference,
                    hmac_key=hmac_key,
                )
                try:
                    connection.execute(
                        "INSERT INTO burp_message_refs "
                        "(engagement_id, import_run_id, endpoint_id, identity_id, message_ref, source_message_ref, "
                        "request_fingerprint, method, url, request_artifact_path) "
                        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                        (
                            engagement_id,
                            import_id,
                            endpoint_id,
                            int(identity["id"]),
                            reference,
                            source_reference,
                            fingerprint,
                            method,
                            persisted_url,
                            str(artifact_path.relative_to(ROOT)) if args.include_bodies else None,
                        ),
                    )
                except sqlite3.IntegrityError:
                    # Endpoint-level request deduplication must not discard
                    # safe semantic observations from a later export.
                    merge_identifier_facts(connection, engagement_id, identifier_facts)
                    if identifier_facts:
                        identifier_endpoint_ids.add(endpoint_id)
                    skipped += 1
                    continue
                merge_identifier_facts(connection, engagement_id, identifier_facts)
                if identifier_facts:
                    identifier_endpoint_ids.add(endpoint_id)
                if args.include_bodies:
                    artifacts.append(
                        {
                            "reference": reference,
                            "method": method,
                            "url": persisted_url,
                            "headers": headers,
                            "body": body,
                        }
                    )
                imported += 1
            except BugBountyError:
                skipped += 1

        artifact_hash = None
        if args.include_bodies and artifacts:
            artifact_text = json.dumps({"messages": artifacts}, indent=2, ensure_ascii=False) + "\n"
            write_private(artifact_path, artifact_text)
            artifact_hash = sha256_path(artifact_path)
            connection.execute(
                "UPDATE burp_message_refs SET request_sha256 = ? WHERE import_run_id = ?",
                (artifact_hash, import_id),
            )
            connection.execute(
                "INSERT OR IGNORE INTO evidence (path, sha256, mime_type, size_bytes, notes) "
                "VALUES (?, ?, 'application/json', ?, ?)",
                (
                    str(artifact_path.relative_to(ROOT)),
                    artifact_hash,
                    artifact_path.stat().st_size,
                    f"Redacted Burp import {import_id}",
                ),
            )
        connection.execute(
            "UPDATE burp_import_runs SET messages_seen = ?, messages_imported = ?, "
            "messages_skipped = ?, redacted_fields = ?, status = 'completed', completed_at = datetime('now') "
            "WHERE id = ?",
            (len(messages), imported, skipped, redactions, import_id),
        )
        refresh_identifier_semantics(connection, engagement_id, identifier_endpoint_ids)
        connection.execute(
            "UPDATE hunt_sessions SET endpoints_seen = ("
            "SELECT COUNT(*) FROM endpoints WHERE engagement_id = ?) "
            "WHERE id = (SELECT id FROM hunt_sessions WHERE engagement_id = ? "
            "AND status = 'running' ORDER BY started_at DESC LIMIT 1)",
            (engagement_id, engagement_id),
        )
        connection.commit()
        print(
            f"Burp import {import_id}: {imported} message(s) imported, {skipped} skipped, "
            f"{redactions} value(s) redacted."
        )
        if artifact_hash:
            print(f"Redacted artifact: {artifact_path.relative_to(ROOT)}")
        print("Next: ./redcode bugbounty map, then ./redcode bugbounty queue --generate")
        return 0
    except Exception as error:
        connection.rollback()
        if isinstance(error, BugBountyError):
            print(f"Bug-bounty ingest failed: {error}", file=sys.stderr)
            return 1
        raise
    finally:
        connection.close()


def root_segment(path_template: str) -> str:
    parts = [part for part in path_template.split("/") if part and part != "{id}"]
    return parts[0] if parts else "root"


def json_string_set(value: str | None) -> set[str]:
    try:
        decoded = json.loads(value or "[]")
    except json.JSONDecodeError:
        return set()
    if not isinstance(decoded, list):
        return set()
    return {str(item) for item in decoded if isinstance(item, (str, int, float))}


def json_object(value: str | None) -> dict[str, Any]:
    try:
        decoded = json.loads(value or "{}")
    except json.JSONDecodeError:
        return {}
    return decoded if isinstance(decoded, dict) else {}


def workflow_semantics(value: str | None) -> dict[str, Any]:
    """Return the compact, analyst-confirmed workflow model.

    This intentionally keeps business semantics in the workflow record rather
    than inferring them from redacted HTTP values.  Lists are used for durable,
    explainable graph edges and reasoning artifacts.
    """
    decoded = json_object(value)
    states = decoded.get("states", {})
    transitions = decoded.get("transitions", [])
    invariants = decoded.get("invariants", [])
    observations = decoded.get("observations", [])
    identifier_leads = decoded.get("identifier_leads", [])
    relationships = decoded.get("relationships", [])
    return {
        "version": 1,
        "states": states if isinstance(states, dict) else {},
        "transitions": [item for item in transitions if isinstance(item, dict)],
        "invariants": [item for item in invariants if isinstance(item, dict)],
        "observations": [item for item in observations if isinstance(item, dict)],
        "identifier_leads": [item for item in identifier_leads if isinstance(item, dict)],
        "relationships": [item for item in relationships if isinstance(item, dict)],
    }


def ensure_semantic_states(semantics: dict[str, Any], states: Iterable[str]) -> dict[str, Any]:
    result = workflow_semantics(canonical_json(semantics))
    for state in states:
        result["states"].setdefault(str(state), {"terminal": False})
    return result


def semantic_key(prefix: str, value: dict[str, Any]) -> str:
    digest = hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()[:20]
    return f"{prefix}:{digest}"


def workflow_row(
    connection: sqlite3.Connection, engagement_id: int, host: str, name: str
) -> sqlite3.Row:
    row = connection.execute(
        "SELECT * FROM application_workflows WHERE engagement_id = ? AND workflow_key = ?",
        (engagement_id, f"{host}:{name}"),
    ).fetchone()
    if row is None:
        raise BugBountyError("workflow is not mapped; run ingest and map first")
    return row


def save_workflow_semantics(
    connection: sqlite3.Connection, workflow_id: int, semantics: dict[str, Any], states: Iterable[str]
) -> None:
    connection.execute(
        "UPDATE application_workflows SET states_json = ?, semantics_json = ?, updated_at=datetime('now') "
        "WHERE id = ?",
        (canonical_json(sorted(set(states))), canonical_json(semantics), workflow_id),
    )


def endpoint_identity_context(
    connection: sqlite3.Connection, engagement_id: int
) -> dict[int, list[sqlite3.Row]]:
    rows = connection.execute(
        "SELECT b.endpoint_id, i.label, i.tenant, i.role, i.auth_state, COUNT(*) AS observations "
        "FROM burp_message_refs b JOIN identities i ON i.id = b.identity_id "
        "WHERE b.engagement_id = ? GROUP BY b.endpoint_id, i.id "
        "ORDER BY b.endpoint_id, i.label",
        (engagement_id,),
    ).fetchall()
    result: dict[int, list[sqlite3.Row]] = {}
    for row in rows:
        result.setdefault(int(row["endpoint_id"]), []).append(row)
    return result


def describe_identity(row: sqlite3.Row) -> str:
    details = [value for value in (row["role"], row["tenant"]) if value]
    return f"{row['label']} ({', '.join(details)})" if details else str(row["label"])


def workflow_key_for(endpoint: sqlite3.Row) -> str:
    return f"{endpoint['host']}:{root_segment(endpoint['path_template'])}"


def existing_workflow_context(
    connection: sqlite3.Connection, engagement_id: int
) -> dict[str, dict[str, Any]]:
    rows = connection.execute(
        "SELECT * FROM application_workflows WHERE engagement_id = ?", (engagement_id,)
    ).fetchall()
    return {
        str(row["workflow_key"]): {
            "id": int(row["id"]),
            "target_id": row["target_id"],
            "name": str(row["name"]),
            "actors": json_string_set(row["actors_json"]),
            "objects": json_string_set(row["objects_json"]),
            "states": json_string_set(row["states_json"]),
            "semantics": workflow_semantics(row["semantics_json"]),
            "sensitivity": int(row["sensitivity"]),
            "notes": row["notes"],
        }
        for row in rows
    }


def inferred_workflow_sensitivity(name: str) -> int:
    return 3 if name.lower() in {"admin", "billing", "account", "users", "payments"} else 1


def command_map(args: argparse.Namespace) -> int:
    connection, manifest, _, engagement_id = connect(args)
    try:
        get_program(connection, engagement_id)
        endpoints = connection.execute(
            "SELECT e.*, COUNT(DISTINCT b.identity_id) AS identity_count "
            "FROM endpoints e LEFT JOIN burp_message_refs b ON b.endpoint_id = e.id "
            "WHERE e.engagement_id = ? GROUP BY e.id ORDER BY e.host, e.path_template, e.method",
            (engagement_id,),
        ).fetchall()
        identities_by_endpoint = endpoint_identity_context(connection, engagement_id)
        prior_workflows = existing_workflow_context(connection, engagement_id)
        workflows: dict[str, dict[str, Any]] = {}
        gaps: list[str] = []
        for endpoint in endpoints:
            if endpoint["coverage_status"] == "observed":
                connection.execute(
                    "UPDATE endpoints SET coverage_status = 'mapped' WHERE id = ?", (endpoint["id"],)
                )
            group = workflow_key_for(endpoint)
            existing = prior_workflows.get(group, {})
            workflow = workflows.setdefault(
                group,
                {
                    "target_id": endpoint["target_id"],
                    "host": endpoint["host"],
                    "name": root_segment(endpoint["path_template"]),
                    "actors": set(existing.get("actors", set())),
                    "objects": set(existing.get("objects", set())),
                    "states": set(existing.get("states", set())) | {"observed"},
                    "sensitivity": max(
                        int(existing.get("sensitivity", 0)),
                        inferred_workflow_sensitivity(root_segment(endpoint["path_template"])),
                    ),
                },
            )
            workflow["objects"].add(
                endpoint["object_type"]
                or ("object" if "{id}" in endpoint["path_template"] else "resource")
            )
            identities = identities_by_endpoint.get(int(endpoint["id"]), [])
            if identities:
                workflow["actors"].update(describe_identity(identity) for identity in identities)
            else:
                workflow["actors"].add("authenticated" if endpoint["auth_required"] else "anonymous")
            identity_count = len({str(identity["label"]) for identity in identities})
            tenant_count = len({str(identity["tenant"]) for identity in identities if identity["tenant"]})
            if endpoint["state_change"] and identity_count < 2:
                gaps.append(
                    f"{endpoint['method']} {endpoint['host']}{endpoint['path_template']}: "
                    "state-changing endpoint observed with fewer than two symbolic identities"
                )
            if "{id}" in endpoint["path_template"] and tenant_count < 2:
                gaps.append(
                    f"{endpoint['method']} {endpoint['host']}{endpoint['path_template']}: "
                    "object reference has no cross-tenant coverage"
                )
        for key, workflow in workflows.items():
            connection.execute(
                "INSERT INTO application_workflows "
                "(engagement_id, target_id, workflow_key, name, states_json, actors_json, objects_json, sensitivity) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?) "
                "ON CONFLICT(engagement_id, workflow_key) DO UPDATE SET "
                "target_id=excluded.target_id, name=excluded.name, "
                "states_json=excluded.states_json, actors_json=excluded.actors_json, "
                "objects_json=excluded.objects_json, sensitivity=MAX(application_workflows.sensitivity, excluded.sensitivity), "
                "updated_at=datetime('now')",
                (
                    engagement_id,
                    workflow["target_id"],
                    key,
                    f"{workflow['host']} / {workflow['name']}",
                    canonical_json(sorted(workflow["states"])),
                    canonical_json(sorted(workflow["actors"])),
                    canonical_json(sorted(workflow["objects"])),
                    3 if workflow["name"] in {"admin", "billing", "account", "users"} else 1,
                ),
            )
        refresh_identifier_semantics(
            connection,
            engagement_id,
            [int(endpoint["id"]) for endpoint in endpoints],
        )
        report_path = output_directory(manifest) / "application-map.md"
        lines = [
            "# Application map",
            "",
            f"Generated: {utc_text()}",
            "",
            "## Endpoints",
            "",
            "| Method | Endpoint | Auth | State change | Symbolic identities | Coverage |",
            "| --- | --- | --- | --- | --- | --- |",
        ]
        for endpoint in endpoints:
            identity_details = ", ".join(
                describe_identity(identity)
                for identity in identities_by_endpoint.get(int(endpoint["id"]), [])
            ) or "-"
            lines.append(
                f"| {endpoint['method']} | {endpoint['host']}{endpoint['path_template']} | "
                f"{'yes' if endpoint['auth_required'] else 'no'} | "
                f"{'yes' if endpoint['state_change'] else 'no'} | {identity_details} | mapped |"
            )
        lines.extend(["", "## Coverage gaps", ""])
        lines.extend([f"- {gap}" for gap in gaps] or ["- No obvious structural gaps from imported metadata."])
        write_private(report_path, "\n".join(lines) + "\n")
        connection.commit()
        print(f"Mapped {len(endpoints)} endpoint(s) and {len(workflows)} workflow group(s).")
        print(f"Coverage gaps: {len(gaps)}")
        print(f"Map: {report_path.relative_to(ROOT)}")
        print("Add business context with: ./redcode bugbounty workflow annotate --help")
        return 0
    finally:
        connection.close()


def priority_for(
    endpoint: sqlite3.Row,
    identities: list[sqlite3.Row],
    workflow: dict[str, Any] | None,
    program_duplicate_risk: int | None,
) -> tuple[dict[str, int], int]:
    has_object = "{id}" in endpoint["path_template"]
    identity_count = len({str(identity["label"]) for identity in identities})
    tenant_count = len({str(identity["tenant"]) for identity in identities if identity["tenant"]})
    observations = sum(int(identity["observations"]) for identity in identities)
    sensitivity = int(workflow["sensitivity"]) if workflow else inferred_workflow_sensitivity(
        root_segment(endpoint["path_template"])
    )
    components = {
        "boundary": 5 if has_object and tenant_count < 2 else (
            4 if has_object or endpoint["state_change"] else 2
        ),
        "impact": min(5, max(2, sensitivity + (1 if endpoint["state_change"] else 0))),
        "novelty": min(
            5,
            2 + int(identity_count < 2) + int(tenant_count < 2) + int(endpoint["coverage_status"] != "tested"),
        ),
        "evidence": min(5, 1 + min(2, identity_count) + int(observations >= 2)),
        "duplicate_risk": 2 if program_duplicate_risk is None else int(program_duplicate_risk),
        "test_cost": 1 if endpoint["method"] in {"GET", "HEAD", "OPTIONS"} else 2,
        "operational_risk": min(5, 1 + int(endpoint["state_change"]) + sensitivity // 3),
    }
    return components, mappa_priority(components)


def mappa_priority(components: dict[str, int]) -> int:
    return (
        3 * components["boundary"]
        + 2 * components["impact"]
        + 2 * components["novelty"]
        + components["evidence"]
        - 2 * components["duplicate_risk"]
        - components["test_cost"]
        - components["operational_risk"]
    )


def semantic_priority_for(
    endpoint: sqlite3.Row,
    identities: list[sqlite3.Row],
    workflow: dict[str, Any],
    program_duplicate_risk: int | None,
    *,
    confidence: int,
    sensitivity: int,
    authorization_effect: str = "none",
    terminal: bool = False,
    trust_boundaries: Iterable[str] = (),
) -> tuple[dict[str, int], int]:
    components, _ = priority_for(endpoint, identities, workflow, program_duplicate_risk)
    if authorization_effect in {"revoke", "transfer"} or list(trust_boundaries):
        components["boundary"] = max(components["boundary"], 4)
    if terminal:
        components["novelty"] = max(components["novelty"], 4)
    components["impact"] = max(components["impact"], min(5, max(2, sensitivity)))
    components["evidence"] = max(components["evidence"], min(5, confidence))
    return components, mappa_priority(components)


def endpoint_for_semantic_seed(
    endpoints: list[sqlite3.Row], endpoint_id: int | None
) -> sqlite3.Row | None:
    if endpoint_id is not None:
        return next((row for row in endpoints if int(row["id"]) == int(endpoint_id)), None)
    return next((row for row in endpoints if row["state_change"]), None) or (endpoints[0] if endpoints else None)


def semantic_seed(
    *,
    workflow: dict[str, Any],
    endpoint: sqlite3.Row,
    kind: str,
    source_id: str,
    invariant: str,
    assumption: str,
    violation: str,
    suggested_control: str,
    suggested_change: str,
    expected_result: str,
    actor_label: str,
    object_state: str,
    authorization_effect: str,
    trust_boundaries: Iterable[str],
    confidence: int,
    sensitivity: int,
    terminal: bool,
    identities: list[sqlite3.Row],
    duplicate_risk: int | None,
) -> dict[str, Any]:
    boundaries = sorted(set(str(value) for value in trust_boundaries))
    components, priority = semantic_priority_for(
        endpoint,
        identities,
        workflow,
        duplicate_risk,
        confidence=confidence,
        sensitivity=sensitivity,
        authorization_effect=authorization_effect,
        terminal=terminal,
        trust_boundaries=boundaries,
    )
    identity = semantic_key(
        "semantic",
        {
            "workflow": workflow["id"],
            "endpoint": int(endpoint["id"]),
            "source": source_id,
            "kind": kind,
            "authorization_effect": authorization_effect,
        },
    )
    reasoning = {
        "generator": "workflow-semantics-v1",
        "kind": kind,
        "workflow": workflow["name"],
        "source_id": source_id,
        "observed_endpoint": f"{endpoint['method']} {endpoint['path_template']}",
        "invariant": invariant,
        "assumption": assumption,
        "violation": violation,
        "suggested_control": suggested_control,
        "suggested_single_change": suggested_change,
        "expected_result": expected_result,
        "authorization_effect": authorization_effect,
        "trust_boundaries": boundaries,
        "confidence": confidence,
    }
    statement = f"{violation} Expected invariant: {invariant}"
    return {
        "semantic_key": identity,
        "statement": statement,
        "actor_label": actor_label,
        "action": endpoint["method"],
        "object_owner": "workflow-defined-boundary" if boundaries else "workflow-defined-object",
        "object_state": object_state,
        "components": components,
        "priority": priority,
        "reasoning": reasoning,
    }


def semantic_hypothesis_seeds(
    workflow: dict[str, Any],
    endpoints: list[sqlite3.Row],
    identities_by_endpoint: dict[int, list[sqlite3.Row]],
    duplicate_risk: int | None,
) -> list[tuple[sqlite3.Row, dict[str, Any]]]:
    """Derive proposals from confirmed workflow semantics, never endpoint names alone."""
    semantics = workflow.get("semantics", {})
    seeds: list[tuple[sqlite3.Row, dict[str, Any]]] = []
    invariants = semantics.get("invariants", [])
    for transition in semantics.get("transitions", []):
        endpoint = endpoint_for_semantic_seed(endpoints, transition.get("endpoint_id"))
        if endpoint is None:
            continue
        from_state = str(transition.get("from", "observed"))
        to_state = str(transition.get("to", "observed"))
        states = semantics.get("states", {})
        terminal = bool(isinstance(states.get(to_state), dict) and states[to_state].get("terminal"))
        confidence = int(transition.get("confidence", 3))
        sensitivity = max(int(workflow.get("sensitivity", 0)), 4 if transition.get("sensitive") else 0)
        actors = transition.get("actors") or []
        actor = str(actors[0]) if actors else "authorized-user"
        identities = identities_by_endpoint.get(int(endpoint["id"]), [])
        related = [item for item in invariants if item.get("transition_id") == transition.get("id")]
        if terminal and not related:
            invariant = f"An object in terminal state {to_state} cannot perform actions that require {from_state}."
            assumption = "Server-side lifecycle validation is re-evaluated after the transition."
            seeds.append((endpoint, semantic_seed(
                workflow=workflow, endpoint=endpoint, kind="terminal-state", source_id=str(transition["id"]),
                invariant=invariant, assumption=assumption,
                violation=(f"An action valid while {from_state} may remain accepted after the object reaches terminal state {to_state}."),
                suggested_control=f"Perform {endpoint['method']} {endpoint['path_template']} while the object is {from_state}.",
                suggested_change=f"Move the same object to {to_state}, then repeat the same action once.",
                expected_result=f"The repeated action is rejected because {to_state} is terminal.",
                actor_label=actor, object_state=to_state, authorization_effect=str(transition.get("authorization_effect", "none")),
                trust_boundaries=transition.get("trust_boundaries", []), confidence=confidence,
                sensitivity=sensitivity, terminal=True, identities=identities, duplicate_risk=duplicate_risk,
            )))
        for prerequisite in transition.get("prerequisites", []):
            invariant = f"Transition {from_state} -> {to_state} requires: {prerequisite}."
            seeds.append((endpoint, semantic_seed(
                workflow=workflow, endpoint=endpoint, kind="transition-prerequisite", source_id=str(transition["id"]),
                invariant=invariant, assumption="Server-side transition validation enforces declared prerequisites.",
                violation=f"The workflow may allow transition to {to_state} without required prerequisite: {prerequisite}.",
                suggested_control=f"Use the observed transition with the prerequisite satisfied.",
                suggested_change=f"Attempt the same transition once without: {prerequisite}.",
                expected_result=f"The transition is rejected until {prerequisite} is satisfied.",
                actor_label=actor, object_state=from_state, authorization_effect=str(transition.get("authorization_effect", "none")),
                trust_boundaries=transition.get("trust_boundaries", []), confidence=confidence,
                sensitivity=sensitivity, terminal=terminal, identities=identities, duplicate_risk=duplicate_risk,
            )))
        effect = str(transition.get("authorization_effect", "none"))
        if effect in {"revoke", "transfer"}:
            capability = ", ".join(str(value) for value in transition.get("capabilities", [])) or "the affected capability"
            invariant = f"After {from_state} -> {to_state}, {actor} must no longer retain {capability}."
            seeds.append((endpoint, semantic_seed(
                workflow=workflow, endpoint=endpoint, kind="authorization-change", source_id=str(transition["id"]),
                invariant=invariant,
                assumption="Authorization is re-evaluated after the workflow transition and stale grants are invalidated.",
                violation=f"{actor} may retain {capability} after {from_state} -> {to_state}.",
                suggested_control=f"Establish that {actor} can use {capability} before {from_state} -> {to_state}.",
                suggested_change=f"Perform {from_state} -> {to_state}, then repeat one protected action with the same identity.",
                expected_result=f"The protected action is denied after the authorization change.",
                actor_label=actor, object_state=to_state, authorization_effect=effect,
                trust_boundaries=transition.get("trust_boundaries", []), confidence=confidence,
                sensitivity=sensitivity, terminal=terminal, identities=identities, duplicate_risk=duplicate_risk,
            )))
        boundaries = transition.get("trust_boundaries", [])
        if boundaries:
            boundary_text = ", ".join(str(value) for value in boundaries)
            invariant = f"The {actor} action remains within the declared trust boundary: {boundary_text}."
            seeds.append((endpoint, semantic_seed(
                workflow=workflow, endpoint=endpoint, kind="trust-boundary", source_id=str(transition["id"]),
                invariant=invariant,
                assumption="The server validates the actor, tenant, and object boundary at the transition.",
                violation=f"The transition {from_state} -> {to_state} may cross {boundary_text} without the required authorization.",
                suggested_control=f"Perform {endpoint['method']} {endpoint['path_template']} with the authorized {actor} context.",
                suggested_change=f"Repeat the transition while changing only the actor, tenant, or object across {boundary_text}.",
                expected_result="The server rejects the request when the declared trust boundary is crossed.",
                actor_label=actor, object_state=to_state, authorization_effect=effect,
                trust_boundaries=boundaries, confidence=confidence, sensitivity=sensitivity,
                terminal=terminal, identities=identities, duplicate_risk=duplicate_risk,
            )))
    for invariant_data in invariants:
        protected = invariant_data.get("endpoint_ids") or []
        scoped_endpoints = [
            endpoint for endpoint in endpoints if int(endpoint["id"]) in {int(value) for value in protected}
        ] or ([endpoint_for_semantic_seed(endpoints, None)] if endpoints else [])
        for endpoint in [item for item in scoped_endpoints if item is not None]:
            assumption = str((invariant_data.get("assumptions") or ["The application enforces this invariant server-side."])[0])
            actor = str((invariant_data.get("actors") or ["authorized-user"])[0])
            state = ", ".join(str(value) for value in invariant_data.get("states", [])) or "the declared workflow state"
            seeds.append((endpoint, semantic_seed(
                workflow=workflow, endpoint=endpoint, kind="invariant", source_id=str(invariant_data["id"]),
                invariant=str(invariant_data["statement"]), assumption=assumption,
                violation=f"The declared workflow invariant may be violated through {endpoint['method']} {endpoint['path_template']}.",
                suggested_control=f"Establish the expected behavior for {endpoint['method']} {endpoint['path_template']} in {state}.",
                suggested_change="Change only the workflow state, actor, or boundary identified by the invariant.",
                expected_result="The server preserves the declared invariant.", actor_label=actor,
                object_state=state, authorization_effect="none",
                trust_boundaries=invariant_data.get("trust_boundaries", []),
                confidence=int(invariant_data.get("confidence", 3)),
                sensitivity=max(int(workflow.get("sensitivity", 0)), int(invariant_data.get("sensitivity", 0))),
                terminal=False, identities=identities_by_endpoint.get(int(endpoint["id"]), []), duplicate_risk=duplicate_risk,
            )))
    for relationship in semantics.get("relationships", []):
        if relationship.get("status") != "confirmed":
            continue
        from_role = str(relationship.get("from_role", "identifier"))
        to_role = str(relationship.get("to_role", "scope"))
        relation = str(relationship.get("relation", "scoped-by"))
        endpoint = endpoint_for_semantic_seed(endpoints, relationship.get("endpoint_id"))
        if endpoint is None:
            for candidate_endpoint in endpoints:
                semantic_path = semantic_path_for_endpoint(candidate_endpoint)
                roles = {
                    str(candidate.get("role"))
                    for parameter in semantic_path.get("parameters", [])
                    if isinstance(parameter, dict)
                    for candidate in parameter.get("candidates", [])
                    if isinstance(candidate, dict)
                    and candidate.get("role")
                    and candidate.get("status") != "contradicted"
                }
                if {from_role, to_role} <= roles:
                    endpoint = candidate_endpoint
                    break
        if endpoint is None:
            continue
        invariant = f"The {from_role} remains correctly scoped to the related {to_role}."
        seeds.append((endpoint, semantic_seed(
            workflow=workflow,
            endpoint=endpoint,
            kind="identifier-relationship",
            source_id=str(relationship["id"]),
            invariant=invariant,
            assumption="The server binds related identifiers to the same authorized object and tenant context.",
            violation=f"A request may combine a {from_role} with a different {to_role} and retain access.",
            suggested_control=f"Replay {endpoint['method']} {endpoint['path_template']} with the observed identifier pair.",
            suggested_change=f"Change only the {to_role} while keeping the {from_role} and authenticated identity constant.",
            expected_result="The server rejects the mismatched identifier relationship.",
            actor_label="authorized-user",
            object_state="observed",
            authorization_effect="none",
            trust_boundaries=[relation],
            confidence=3,
            sensitivity=max(int(workflow.get("sensitivity", 0)), 3),
            terminal=False,
            identities=identities_by_endpoint.get(int(endpoint["id"]), []),
            duplicate_risk=duplicate_risk,
        )))
    return seeds


def save_generated_semantic_hypothesis(
    connection: sqlite3.Connection,
    engagement_id: int,
    workflow: dict[str, Any],
    endpoint: sqlite3.Row,
    seed: dict[str, Any],
) -> bool:
    row = connection.execute(
        "SELECT id, hypothesis_id, status FROM hypotheses WHERE engagement_id = ? AND semantic_key = ?",
        (engagement_id, seed["semantic_key"]),
    ).fetchone()
    if row is not None:
        if row["status"] == "queued":
            components = seed["components"]
            connection.execute(
                "UPDATE hypotheses SET statement = ?, actor_label = ?, action = ?, object_owner = ?, object_state = ?, "
                "boundary_score = ?, impact_score = ?, novelty_score = ?, evidence_score = ?, duplicate_risk = ?, "
                "test_cost = ?, operational_risk = ?, priority = ?, reasoning_json = ?, updated_at=datetime('now') WHERE id = ?",
                (
                    seed["statement"], seed["actor_label"], seed["action"], seed["object_owner"], seed["object_state"],
                    components["boundary"], components["impact"], components["novelty"], components["evidence"],
                    components["duplicate_risk"], components["test_cost"], components["operational_risk"],
                    seed["priority"], canonical_json(seed["reasoning"]), row["id"],
                ),
            )
        return False
    hypothesis_key = f"HYP-{hashlib.sha256(seed['semantic_key'].encode()).hexdigest()[:10].upper()}"
    components = seed["components"]
    connection.execute(
        "INSERT INTO hypotheses "
        "(engagement_id, target_id, endpoint_id, workflow_id, hypothesis_id, semantic_key, statement, actor_label, "
        "action, object_owner, object_state, channel, boundary_score, impact_score, novelty_score, evidence_score, "
        "duplicate_risk, test_cost, operational_risk, priority, reasoning_json) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'http', ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            engagement_id, endpoint["target_id"], endpoint["id"], workflow["id"], hypothesis_key,
            seed["semantic_key"], seed["statement"], seed["actor_label"], seed["action"], seed["object_owner"],
            seed["object_state"], components["boundary"], components["impact"], components["novelty"],
            components["evidence"], components["duplicate_risk"], components["test_cost"], components["operational_risk"],
            seed["priority"], canonical_json(seed["reasoning"]),
        ),
    )
    created = connection.execute("SELECT id FROM hypotheses WHERE hypothesis_id = ?", (hypothesis_key,)).fetchone()
    assert created is not None
    record_hypothesis_event(
        connection, int(created["id"]), "created-semantic", to_status="queued", actor="bugbounty-control",
        details={"priority_components": components, "semantic_key": seed["semantic_key"], "reasoning": seed["reasoning"]},
    )
    return True


def command_queue(args: argparse.Namespace) -> int:
    connection, manifest, _, engagement_id = connect(args)
    try:
        program = get_program(connection, engagement_id)
        created = 0
        if args.generate:
            identities_by_endpoint = endpoint_identity_context(connection, engagement_id)
            workflows = existing_workflow_context(connection, engagement_id)
            endpoints = connection.execute(
                "SELECT * FROM endpoints WHERE engagement_id = ? "
                "AND (state_change = 1 OR path_template LIKE '%{id}%')",
                (engagement_id,),
            ).fetchall()
            for endpoint in endpoints:
                identities = identities_by_endpoint.get(int(endpoint["id"]), [])
                workflow = workflows.get(workflow_key_for(endpoint))
                components, priority = priority_for(
                    endpoint,
                    identities,
                    workflow,
                    program["duplicate_risk"],
                )
                seed = f"{engagement_id}:{endpoint['id']}:ownership-boundary"
                hypothesis_key = f"HYP-{hashlib.sha256(seed.encode()).hexdigest()[:10].upper()}"
                actor_label = str(identities[0]["label"]) if identities else "authorized-user"
                object_owner = (
                    "different-authorized-tenant"
                    if any(identity["tenant"] for identity in identities)
                    else "different-authorized-user"
                )
                workflow_states = (workflow or {}).get("states", set()) - {"observed"}
                object_state = sorted(workflow_states)[0] if workflow_states else "observed"
                statement = (
                    f"Verify that {actor_label} cannot access or alter a {object_owner} "
                    f"object through {endpoint['method']} {endpoint['path_template']} "
                    f"while it is in the {object_state} state."
                )
                cursor = connection.execute(
                    "INSERT OR IGNORE INTO hypotheses "
                    "(engagement_id, target_id, endpoint_id, workflow_id, hypothesis_id, statement, actor_label, "
                    "action, object_owner, object_state, channel, boundary_score, impact_score, "
                    "novelty_score, evidence_score, duplicate_risk, test_cost, operational_risk, priority) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'http', ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        engagement_id,
                        endpoint["target_id"],
                        endpoint["id"],
                        workflow["id"] if workflow else None,
                        hypothesis_key,
                        statement,
                        actor_label,
                        endpoint["method"],
                        object_owner,
                        object_state,
                        components["boundary"],
                        components["impact"],
                        components["novelty"],
                        components["evidence"],
                        components["duplicate_risk"],
                        components["test_cost"],
                        components["operational_risk"],
                        priority,
                    ),
                )
                if cursor.rowcount:
                    created += 1
                    row = connection.execute(
                        "SELECT id FROM hypotheses WHERE hypothesis_id = ?", (hypothesis_key,)
                    ).fetchone()
                    assert row is not None
                    record_hypothesis_event(
                        connection,
                        int(row["id"]),
                        "created",
                        to_status="queued",
                        actor="bugbounty-control",
                        details={"priority_components": components},
                    )
            workflow_endpoints: dict[str, list[sqlite3.Row]] = {}
            all_endpoints = connection.execute(
                "SELECT * FROM endpoints WHERE engagement_id = ? ORDER BY host, path_template, method",
                (engagement_id,),
            ).fetchall()
            for endpoint in all_endpoints:
                workflow_endpoints.setdefault(workflow_key_for(endpoint), []).append(endpoint)
            for workflow_key, workflow in workflows.items():
                for endpoint, seed in semantic_hypothesis_seeds(
                    workflow,
                    workflow_endpoints.get(workflow_key, []),
                    identities_by_endpoint,
                    program["duplicate_risk"],
                ):
                    created += int(
                        save_generated_semantic_hypothesis(
                            connection, engagement_id, workflow, endpoint, seed
                        )
                    )
        rows = connection.execute(
            "SELECT h.*, e.host, e.method, e.path_template, e.metadata_json FROM hypotheses h "
            "LEFT JOIN endpoints e ON e.id = h.endpoint_id "
            "WHERE h.engagement_id = ? AND h.status IN ('queued', 'approved', 'testing', 'candidate') "
            "ORDER BY h.priority DESC, h.created_at ASC LIMIT ?",
            (engagement_id, args.limit),
        ).fetchall()
        connection.commit()
        if created:
            print(f"Generated {created} new MAPPA hypothesis/hypotheses.")
        if not rows:
            print("No active MAPPA hypotheses. Import selected Burp traffic and run map/queue --generate.")
            return 0
        print("MAPPA queue")
        for row in rows:
            reasoning = json_object(row["reasoning_json"])
            semantic_path = semantic_path_for_endpoint(row) if row["metadata_json"] else {}
            display_path = semantic_path.get("display_template") or row["path_template"]
            print(
                f"- {row['hypothesis_id']} [{row['status']}, priority {row['priority']}]: "
                f"{row['method']} {row['host']}{display_path}\n"
                f"  Why: boundary={row['boundary_score']}, impact={row['impact_score']}, "
                f"novelty={row['novelty_score']}, evidence={row['evidence_score']}; "
                f"duplicate risk={row['duplicate_risk']}, cost={row['test_cost']}, "
                f"operational risk={row['operational_risk']}\n"
                f"  Context: actor={row['actor_label'] or '-'}, owner={row['object_owner'] or '-'}, "
                f"state={row['object_state'] or '-'}, channel={row['channel'] or '-'}\n"
                f"  {row['statement']}"
            )
            if reasoning:
                print(
                    f"  Reasoning: invariant={reasoning.get('invariant', '-')}; "
                    f"assumption={reasoning.get('assumption', '-')}\n"
                    f"  Suggested control: {reasoning.get('suggested_control', '-')}\n"
                    f"  Single change: {reasoning.get('suggested_single_change', '-')}\n"
                    f"  Expected: {reasoning.get('expected_result', '-')}"
                )
        return 0
    finally:
        connection.close()


def workflow_annotation_target(
    connection: sqlite3.Connection, engagement_id: int, host: str, name: str
) -> int:
    endpoints = connection.execute(
        "SELECT target_id, path_template FROM endpoints WHERE engagement_id = ? AND host = ?",
        (engagement_id, host.lower()),
    ).fetchall()
    for endpoint in endpoints:
        if root_segment(endpoint["path_template"]) == name:
            return int(endpoint["target_id"])
    raise BugBountyError("workflow is not represented by a mapped endpoint; run ingest and map first")


def command_workflow_annotate(args: argparse.Namespace) -> int:
    connection, manifest, _, engagement_id = connect(args)
    try:
        get_program(connection, engagement_id)
        host = control.target_parts(args.host)[0]
        name = require_label(args.name, "workflow name")
        target_id = workflow_annotation_target(connection, engagement_id, host, name)
        require_policy_action(connection, manifest, engagement_id, host, "hunt")
        for label in args.actor or []:
            identity_row(connection, engagement_id, label)
        key = f"{host}:{name}"
        existing = connection.execute(
            "SELECT * FROM application_workflows WHERE engagement_id = ? AND workflow_key = ?",
            (engagement_id, key),
        ).fetchone()
        existing_actors = json_string_set(existing["actors_json"]) if existing else set()
        existing_objects = json_string_set(existing["objects_json"]) if existing else set()
        existing_states = json_string_set(existing["states_json"]) if existing else {"observed"}
        objects = {require_label(value, "object") for value in args.object or []}
        states = {require_label(value, "state") for value in args.state or []}
        sensitivity = args.sensitivity
        if sensitivity is None:
            sensitivity = int(existing["sensitivity"]) if existing else inferred_workflow_sensitivity(name)
        semantics = ensure_semantic_states(
            workflow_semantics(existing["semantics_json"] if existing else None),
            existing_states | states,
        )
        connection.execute(
            "INSERT INTO application_workflows "
            "(engagement_id, target_id, workflow_key, name, states_json, semantics_json, actors_json, objects_json, sensitivity, notes) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?) "
            "ON CONFLICT(engagement_id, workflow_key) DO UPDATE SET "
            "target_id=excluded.target_id, name=excluded.name, states_json=excluded.states_json, semantics_json=excluded.semantics_json, "
            "actors_json=excluded.actors_json, objects_json=excluded.objects_json, "
            "sensitivity=excluded.sensitivity, notes=excluded.notes, updated_at=datetime('now')",
            (
                engagement_id,
                target_id,
                key,
                f"{host} / {name}",
                canonical_json(sorted(existing_states | states)),
                canonical_json(semantics),
                canonical_json(sorted(existing_actors | set(args.actor or []))),
                canonical_json(sorted(existing_objects | objects)),
                sensitivity,
                args.notes if args.notes is not None else (existing["notes"] if existing else None),
            ),
        )
        connection.commit()
        print(f"Workflow annotated: {key} (sensitivity {sensitivity}/5).")
        return 0
    finally:
        connection.close()


def semantic_workflow_for_args(
    connection: sqlite3.Connection, manifest: dict[str, Any], engagement_id: int, args: argparse.Namespace
) -> tuple[str, str, sqlite3.Row, dict[str, Any]]:
    host = control.target_parts(args.host)[0]
    name = require_label(args.name, "workflow name")
    require_policy_action(connection, manifest, engagement_id, host, "hunt")
    row = workflow_row(connection, engagement_id, host, name)
    return host, name, row, workflow_semantics(row["semantics_json"])


def workflow_endpoint_ids(
    connection: sqlite3.Connection, engagement_id: int, workflow_key: str, endpoint_ids: Iterable[int]
) -> list[int]:
    verified: list[int] = []
    for endpoint_id in endpoint_ids:
        endpoint = endpoint_row(connection, engagement_id, endpoint_id)
        if workflow_key_for(endpoint) != workflow_key:
            raise BugBountyError("endpoint does not belong to the selected workflow")
        verified.append(int(endpoint["id"]))
    return sorted(set(verified))


def command_workflow_state_set(args: argparse.Namespace) -> int:
    connection, manifest, _, engagement_id = connect(args)
    try:
        get_program(connection, engagement_id)
        _, _, workflow, semantics = semantic_workflow_for_args(connection, manifest, engagement_id, args)
        state = require_label(args.state, "state")
        if args.terminal is None:
            raise BugBountyError("choose either --terminal or --not-terminal")
        metadata = semantics["states"].setdefault(state, {})
        metadata["terminal"] = bool(args.terminal)
        if args.notes is not None:
            metadata["notes"] = require_text(args.notes, "state notes")
        states = json_string_set(workflow["states_json"]) | {state}
        save_workflow_semantics(connection, int(workflow["id"]), semantics, states)
        connection.commit()
        print(f"Workflow state updated: {state} (terminal={str(bool(args.terminal)).lower()}).")
        return 0
    finally:
        connection.close()


def command_workflow_transition_add(args: argparse.Namespace) -> int:
    connection, manifest, _, engagement_id = connect(args)
    try:
        get_program(connection, engagement_id)
        host, name, workflow, semantics = semantic_workflow_for_args(connection, manifest, engagement_id, args)
        from_state = require_label(args.from_state, "from state")
        to_state = require_label(args.to_state, "to state")
        if from_state == to_state:
            raise BugBountyError("a transition must change state")
        for label in args.actor or []:
            identity_row(connection, engagement_id, label)
        endpoint_id = None
        if args.endpoint_id is not None:
            endpoint_id = workflow_endpoint_ids(
                connection, engagement_id, f"{host}:{name}", [args.endpoint_id]
            )[0]
        transition = {
            "from": from_state,
            "to": to_state,
            "endpoint_id": endpoint_id,
            "actors": sorted(set(args.actor or [])),
            "prerequisites": [require_text(value, "prerequisite") for value in args.prerequisite or []],
            "postconditions": [require_text(value, "postcondition") for value in args.postcondition or []],
            "authorization_effect": args.authorization_effect,
            "capabilities": [require_text(value, "capability", 200) for value in args.capability or []],
            "trust_boundaries": [require_label(value, "trust boundary") for value in args.trust_boundary or []],
            "sensitive": bool(args.sensitive),
            "confidence": args.confidence,
            "notes": require_text(args.notes, "transition notes") if args.notes else None,
        }
        transition["id"] = semantic_key(
            "transition",
            {key: value for key, value in transition.items() if key not in {"notes", "confidence", "sensitive"}},
        )
        semantics = ensure_semantic_states(semantics, {from_state, to_state})
        semantics["transitions"] = [
            item for item in semantics["transitions"] if item.get("id") != transition["id"]
        ] + [transition]
        states = json_string_set(workflow["states_json"]) | {from_state, to_state}
        save_workflow_semantics(connection, int(workflow["id"]), semantics, states)
        connection.commit()
        print(f"Workflow transition saved: {transition['id']} ({from_state} -> {to_state}).")
        print("Next: add an invariant or run queue --generate to review eligible semantic proposals.")
        return 0
    finally:
        connection.close()


def command_workflow_invariant_add(args: argparse.Namespace) -> int:
    connection, manifest, _, engagement_id = connect(args)
    try:
        get_program(connection, engagement_id)
        host, name, workflow, semantics = semantic_workflow_for_args(connection, manifest, engagement_id, args)
        for label in args.actor or []:
            identity_row(connection, engagement_id, label)
        assumptions = [require_text(value, "assumption") for value in args.assumption or []]
        if not assumptions:
            raise BugBountyError("an invariant needs at least one --assumption")
        transition_id = args.transition
        if transition_id and not any(item.get("id") == transition_id for item in semantics["transitions"]):
            raise BugBountyError("invariant references an unknown workflow transition")
        states = [require_label(value, "state") for value in args.state or []]
        endpoint_ids = workflow_endpoint_ids(
            connection, engagement_id, f"{host}:{name}", args.endpoint_id or []
        )
        invariant = {
            "statement": require_text(args.statement, "invariant", 2000),
            "states": sorted(set(states)),
            "transition_id": transition_id,
            "endpoint_ids": endpoint_ids,
            "actors": sorted(set(args.actor or [])),
            "assumptions": assumptions,
            "trust_boundaries": [require_label(value, "trust boundary") for value in args.trust_boundary or []],
            "confidence": args.confidence,
            "sensitivity": args.sensitivity,
            "notes": require_text(args.notes, "invariant notes") if args.notes else None,
        }
        invariant["id"] = semantic_key(
            "invariant",
            {key: value for key, value in invariant.items() if key not in {"notes", "confidence", "sensitivity"}},
        )
        semantics = ensure_semantic_states(semantics, states)
        semantics["invariants"] = [
            item for item in semantics["invariants"] if item.get("id") != invariant["id"]
        ] + [invariant]
        all_states = json_string_set(workflow["states_json"]) | set(states)
        save_workflow_semantics(connection, int(workflow["id"]), semantics, all_states)
        connection.commit()
        print(f"Workflow invariant saved: {invariant['id']}.")
        return 0
    finally:
        connection.close()


def command_workflow_learn(args: argparse.Namespace) -> int:
    connection, manifest, _, engagement_id = connect(args)
    try:
        get_program(connection, engagement_id)
        _, _, workflow, semantics = semantic_workflow_for_args(connection, manifest, engagement_id, args)
        if args.plan_id is not None:
            plan = plan_row(connection, engagement_id, args.plan_id)
            if plan["hypothesis_db_id"] is None:
                raise BugBountyError("learning plan has no hypothesis")
        observation_text = require_text(args.observation, "observation", 2000)
        observation = {
            "id": semantic_key("observation", {"workflow": int(workflow["id"]), "text": observation_text}),
            "text": observation_text,
            "plan_id": args.plan_id,
            "confidence": args.confidence,
            "recorded_at": utc_text(),
        }
        semantics["observations"] = semantics["observations"] + [observation]
        save_workflow_semantics(
            connection, int(workflow["id"]), semantics, json_string_set(workflow["states_json"])
        )
        connection.commit()
        print("Workflow learning observation saved. Re-run queue --generate to refresh queued proposals.")
        return 0
    finally:
        connection.close()


def semantic_path_for_endpoint(endpoint: sqlite3.Row) -> dict[str, Any]:
    metadata = endpoint_metadata(endpoint)
    semantic_path = metadata.get("semantic_path")
    return semantic_path if isinstance(semantic_path, dict) else {
        "generic_template": endpoint["path_template"],
        "parameters": [],
        "display_template": endpoint["path_template"],
    }


def save_endpoint_semantic_path(
    connection: sqlite3.Connection, endpoint: sqlite3.Row, semantic_path: dict[str, Any]
) -> None:
    metadata = endpoint_metadata(endpoint)
    metadata["semantic_path"] = semantic_path
    connection.execute(
        "UPDATE endpoints SET metadata_json = ? WHERE id = ?",
        (canonical_json(metadata), endpoint["id"]),
    )


def command_identifier_list(args: argparse.Namespace) -> int:
    connection, _, _, engagement_id = connect(args)
    try:
        get_program(connection, engagement_id)
        rows = connection.execute(
            "SELECT id, host, method, path_template, metadata_json FROM endpoints "
            "WHERE engagement_id = ? ORDER BY host, path_template, method",
            (engagement_id,),
        ).fetchall()
        registry_count = int(connection.execute(
            "SELECT COUNT(*) FROM identifier_registry WHERE engagement_id = ?",
            (engagement_id,),
        ).fetchone()[0])
        print(f"Identifier registry: {registry_count} fingerprint(s), raw values are never stored.")
        for endpoint in rows:
            semantic_path = semantic_path_for_endpoint(endpoint)
            parameters = semantic_path.get("parameters", [])
            if not parameters:
                continue
            print(f"- endpoint {endpoint['id']}: {endpoint['method']} {endpoint['host']}{endpoint['path_template']}")
            print(f"  display: {semantic_path.get('display_template', endpoint['path_template'])}")
            for parameter in parameters:
                candidates = ", ".join(
                    f"{item.get('role')} ({item.get('status', 'unknown')}, {item.get('confidence', 'low')})"
                    for item in parameter.get("candidates", [])
                    if isinstance(item, dict)
                ) or "unknown"
                print(f"  position {parameter.get('position')}: {candidates}")
        return 0
    finally:
        connection.close()


def identifier_endpoint_update(
    connection: sqlite3.Connection,
    engagement_id: int,
    endpoint_id: int,
    position: int,
    role: str,
    *,
    status: str,
    reviewer: str,
    note: str,
) -> None:
    endpoint = endpoint_row(connection, engagement_id, endpoint_id)
    semantic_path = semantic_path_for_endpoint(endpoint)
    parameters = semantic_path.setdefault("parameters", [])
    parameter = next((item for item in parameters if item.get("position") == position), None)
    if parameter is None:
        raise BugBountyError("identifier position is not a normalized path parameter")
    selected = parameter.get("selected_role")
    if status == "confirmed" and selected and selected != role:
        raise BugBountyError(
            f"position {position} is already confirmed as {selected}; reject it explicitly before correcting it"
        )
    candidates = [item for item in parameter.get("candidates", []) if isinstance(item, dict)]
    candidate = next((item for item in candidates if item.get("role") == role), None)
    if candidate is None:
        candidate = {"role": role, "confidence": "low", "field_observations": 0, "path_observations": 0}
        candidates.append(candidate)
    candidate.update({
        "role": role,
        "status": status,
        "reviewed_by": reviewer,
        "reviewed_at": utc_text(),
        "review_note": note,
    })
    parameter["candidates"] = sorted(candidates, key=lambda item: str(item.get("role")))
    if status == "confirmed":
        parameter["selected_role"] = role
        parameter["status"] = "confirmed"
    elif parameter.get("selected_role") == role:
        parameter.pop("selected_role", None)
        parameter["status"] = "proposed" if candidates else "unknown"
    semantic_path["display_template"] = semantic_display_template(
        endpoint["path_template"], parameters
    )
    save_endpoint_semantic_path(connection, endpoint, semantic_path)


def command_identifier_confirm(args: argparse.Namespace) -> int:
    connection, manifest, _, engagement_id = connect(args)
    try:
        get_program(connection, engagement_id)
        endpoint = endpoint_row(connection, engagement_id, args.endpoint_id)
        require_policy_action(connection, manifest, engagement_id, endpoint["host"], "hunt")
        role = normalize_field_label(require_text(args.role, "role"))
        if not is_safe_identifier_field(role):
            raise BugBountyError("role must be an identifier-style label such as app_group_id")
        reviewer = require_text(args.confirmed_by, "confirmed-by", 200)
        note = require_text(args.note, "note", 1000) if args.note else "Analyst confirmed semantic identifier role."
        identifier_endpoint_update(
            connection, engagement_id, args.endpoint_id, args.position, role,
            status="confirmed", reviewer=reviewer, note=note,
        )
        connection.commit()
        print(f"Identifier role confirmed: endpoint {args.endpoint_id}, position {args.position} -> {role}.")
        return 0
    finally:
        connection.close()


def command_identifier_reject(args: argparse.Namespace) -> int:
    connection, manifest, _, engagement_id = connect(args)
    try:
        get_program(connection, engagement_id)
        endpoint = endpoint_row(connection, engagement_id, args.endpoint_id)
        require_policy_action(connection, manifest, engagement_id, endpoint["host"], "hunt")
        role = normalize_field_label(require_text(args.role, "role"))
        if not is_safe_identifier_field(role):
            raise BugBountyError("role must be an identifier-style label such as app_group_id")
        reviewer = require_text(args.rejected_by, "rejected-by", 200)
        reason = require_text(args.reason, "reason", 1000)
        identifier_endpoint_update(
            connection, engagement_id, args.endpoint_id, args.position, role,
            status="contradicted", reviewer=reviewer, note=reason,
        )
        connection.commit()
        print(f"Identifier role rejected: endpoint {args.endpoint_id}, position {args.position} -> {role}.")
        return 0
    finally:
        connection.close()


def workflow_by_id(connection: sqlite3.Connection, engagement_id: int, workflow_id: int) -> sqlite3.Row:
    row = connection.execute(
        "SELECT * FROM application_workflows WHERE engagement_id = ? AND id = ?",
        (engagement_id, workflow_id),
    ).fetchone()
    if row is None:
        raise BugBountyError(f"workflow not found: {workflow_id}")
    return row


def command_identifier_relationship_list(args: argparse.Namespace) -> int:
    connection, _, _, engagement_id = connect(args)
    try:
        get_program(connection, engagement_id)
        rows = connection.execute(
            "SELECT id, workflow_key, name, semantics_json FROM application_workflows "
            "WHERE engagement_id = ? ORDER BY workflow_key",
            (engagement_id,),
        ).fetchall()
        for row in rows:
            semantics = workflow_semantics(row["semantics_json"])
            for lead in semantics.get("identifier_leads", []):
                print(f"- workflow {row['id']} {row['workflow_key']}: lead {lead.get('id')} roles={','.join(lead.get('roles', []))} status={lead.get('status', 'proposed')}")
            for relation in semantics.get("relationships", []):
                print(f"- workflow {row['id']} {row['workflow_key']}: {relation.get('from_role')} -[{relation.get('relation')}]-> {relation.get('to_role')} status={relation.get('status')}")
        return 0
    finally:
        connection.close()


def command_identifier_relationship_confirm(args: argparse.Namespace) -> int:
    connection, manifest, _, engagement_id = connect(args)
    try:
        get_program(connection, engagement_id)
        workflow = workflow_by_id(connection, engagement_id, args.workflow_id)
        require_policy_action(connection, manifest, engagement_id, workflow["workflow_key"].split(":", 1)[0], "hunt")
        from_role = normalize_field_label(require_text(args.from_role, "from-role"))
        to_role = normalize_field_label(require_text(args.to_role, "to-role"))
        relation = require_label(args.relation, "relation")
        if from_role == to_role:
            raise BugBountyError("relationship endpoints must be distinct roles")
        confirmed_by = require_text(args.confirmed_by, "confirmed-by", 200)
        semantics = workflow_semantics(workflow["semantics_json"])
        valid_roles = {
            str(role)
            for lead in semantics.get("identifier_leads", [])
            if isinstance(lead, dict)
            and lead.get("status") not in {"rejected", "contradicted"}
            for role in lead.get("roles", [])
        }
        if valid_roles and not {from_role, to_role} <= valid_roles:
            raise BugBountyError("relationship roles are not present in an observed identifier lead")
        workflow_host, workflow_name = str(workflow["workflow_key"]).split(":", 1)
        confirmed_roles: set[str] = set()
        related_endpoints = connection.execute(
            "SELECT * FROM endpoints WHERE engagement_id = ? AND host = ?",
            (engagement_id, workflow_host),
        ).fetchall()
        for endpoint in related_endpoints:
            if root_segment(endpoint["path_template"]) != workflow_name:
                continue
            for parameter in semantic_path_for_endpoint(endpoint).get("parameters", []):
                selected = parameter.get("selected_role")
                if selected:
                    confirmed_roles.add(str(selected))
        if not {from_role, to_role} <= confirmed_roles:
            raise BugBountyError(
                "confirm both identifier roles on an endpoint before confirming their relationship"
            )
        relationship = {
            "id": semantic_key(
                "identifier-relationship",
                {"workflow_id": int(workflow["id"]), "from_role": from_role, "to_role": to_role, "relation": relation},
            ),
            "from_role": from_role,
            "to_role": to_role,
            "relation": relation,
            "status": "confirmed",
            "confirmed_by": confirmed_by,
            "confirmed_at": utc_text(),
            "notes": require_text(args.note, "note", 1000) if args.note else None,
        }
        semantics["relationships"] = [
            item for item in semantics.get("relationships", []) if item.get("id") != relationship["id"]
        ] + [relationship]
        save_workflow_semantics(connection, int(workflow["id"]), semantics, json_string_set(workflow["states_json"]))
        connection.commit()
        print(f"Identifier relationship confirmed: {from_role} -[{relation}]-> {to_role}.")
        return 0
    finally:
        connection.close()


def endpoint_row(connection: sqlite3.Connection, engagement_id: int, endpoint_id: int) -> sqlite3.Row:
    row = connection.execute(
        "SELECT * FROM endpoints WHERE engagement_id = ? AND id = ?", (engagement_id, endpoint_id)
    ).fetchone()
    if row is None:
        raise BugBountyError(f"endpoint not found: {endpoint_id}")
    return row


def command_hypothesis_add(args: argparse.Namespace) -> int:
    connection, manifest, _, engagement_id = connect(args)
    try:
        program = get_program(connection, engagement_id)
        endpoint = endpoint_row(connection, engagement_id, args.endpoint_id)
        target = f"{endpoint['protocol']}://{endpoint['host']}{endpoint['path_template']}"
        require_policy_action(connection, manifest, engagement_id, target, "hunt")
        identity_row(connection, engagement_id, args.actor)
        if len(args.statement.strip()) > 2000:
            raise BugBountyError("hypothesis statement must be at most 2000 characters")
        identities = endpoint_identity_context(connection, engagement_id).get(int(endpoint["id"]), [])
        workflow = existing_workflow_context(connection, engagement_id).get(workflow_key_for(endpoint))
        components, _ = priority_for(endpoint, identities, workflow, program["duplicate_risk"])
        overrides = {
            "boundary": args.boundary_score,
            "impact": args.impact_score,
            "novelty": args.novelty_score,
            "evidence": args.evidence_score,
            "duplicate_risk": args.duplicate_risk,
            "test_cost": args.test_cost,
            "operational_risk": args.operational_risk,
        }
        for key, value in overrides.items():
            if value is not None:
                components[key] = value
        priority = mappa_priority(components)
        seed = canonical_json(
            {
                "engagement": engagement_id,
                "endpoint": int(endpoint["id"]),
                "statement": args.statement.strip(),
                "actor": args.actor,
                "owner": args.object_owner,
                "state": args.object_state,
                "channel": args.channel,
            }
        )
        hypothesis_key = f"HYP-{hashlib.sha256(seed.encode()).hexdigest()[:10].upper()}"
        cursor = connection.execute(
            "INSERT OR IGNORE INTO hypotheses "
            "(engagement_id, target_id, endpoint_id, workflow_id, hypothesis_id, statement, actor_label, "
            "action, object_owner, object_state, channel, boundary_score, impact_score, novelty_score, "
            "evidence_score, duplicate_risk, test_cost, operational_risk, priority) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                engagement_id,
                endpoint["target_id"],
                endpoint["id"],
                workflow["id"] if workflow else None,
                hypothesis_key,
                args.statement.strip(),
                args.actor,
                args.action or endpoint["method"],
                args.object_owner,
                args.object_state,
                args.channel,
                components["boundary"],
                components["impact"],
                components["novelty"],
                components["evidence"],
                components["duplicate_risk"],
                components["test_cost"],
                components["operational_risk"],
                priority,
            ),
        )
        if cursor.rowcount:
            row = connection.execute(
                "SELECT id FROM hypotheses WHERE hypothesis_id = ?", (hypothesis_key,)
            ).fetchone()
            assert row is not None
            record_hypothesis_event(
                connection,
                int(row["id"]),
                "created-manual",
                to_status="queued",
                actor=args.created_by,
                details={"priority_components": components},
            )
            print(f"Added MAPPA hypothesis {hypothesis_key} (priority {priority}).")
        else:
            print(f"MAPPA hypothesis already exists: {hypothesis_key}.")
        connection.commit()
        return 0
    finally:
        connection.close()


def hypothesis_with_endpoint(
    connection: sqlite3.Connection, engagement_id: int, hypothesis_key: str
) -> sqlite3.Row:
    row = connection.execute(
        "SELECT h.*, e.host, e.method AS endpoint_method, e.path_template, e.protocol "
        "FROM hypotheses h JOIN endpoints e ON e.id = h.endpoint_id "
        "WHERE h.engagement_id = ? AND h.hypothesis_id = ?",
        (engagement_id, hypothesis_key),
    ).fetchone()
    if row is None:
        raise BugBountyError(f"hypothesis not found: {hypothesis_key}")
    return row


def command_plan_create(args: argparse.Namespace) -> int:
    connection, manifest, _, engagement_id = connect(args)
    try:
        hypothesis = hypothesis_with_endpoint(connection, engagement_id, args.hypothesis)
        if hypothesis["status"] != "queued":
            raise BugBountyError(
                f"a test plan can be created only for a queued hypothesis (current: {hypothesis['status']})"
            )
        active_plan = connection.execute(
            "SELECT id FROM test_plans WHERE hypothesis_id = ? AND status IN ('approved', 'testing')",
            (hypothesis["id"],),
        ).fetchone()
        if active_plan is not None:
            raise BugBountyError(
                f"hypothesis already has active plan {active_plan['id']}; complete, cancel, or wait for it to expire"
            )
        target = f"{hypothesis['protocol']}://{hypothesis['host']}{hypothesis['path_template']}"
        require_policy_action(connection, manifest, engagement_id, target, args.action)
        if args.identity:
            identity_row(connection, engagement_id, args.identity)
        snapshot = policy_snapshot(connection, engagement_id)
        plan = {
            "hypothesis_id": hypothesis["hypothesis_id"],
            "target": target,
            "method": hypothesis["endpoint_method"],
            "identity": args.identity,
            "action": args.action,
            "control": args.control,
            "single_change": args.single_change,
            "expected_result": args.expected_result,
            "minimum_proof": args.minimum_proof,
            "stop_condition": args.stop_condition,
            "cleanup": args.cleanup,
            "max_requests": args.max_requests,
        }
        reasoning = json_object(hypothesis["reasoning_json"])
        if reasoning:
            plan["workflow_reasoning"] = reasoning
        plan_json = canonical_json(plan)
        plan_hash = sha256_bytes(plan_json.encode("utf-8"))
        connection.execute(
            "UPDATE test_plans SET status = 'superseded', updated_at = datetime('now') "
            "WHERE hypothesis_id = ? AND status = 'draft'",
            (hypothesis["id"],),
        )
        connection.execute(
            "INSERT INTO test_plans "
            "(engagement_id, hypothesis_id, policy_snapshot_id, action, target, method, path_template, identity_label, "
            "max_requests, rate_limit_per_second, plan_json, plan_sha256) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                engagement_id,
                hypothesis["id"],
                snapshot["id"],
                args.action,
                target,
                hypothesis["endpoint_method"],
                hypothesis["path_template"],
                args.identity,
                args.max_requests,
                manifest.get("rate_limit_per_second", 10),
                plan_json,
                plan_hash,
            ),
        )
        plan_id = int(connection.execute("SELECT last_insert_rowid()").fetchone()[0])
        record_hypothesis_event(
            connection,
            int(hypothesis["id"]),
            "plan-created",
            from_status=hypothesis["status"],
            to_status=hypothesis["status"],
            actor=args.created_by,
            details={"plan_id": plan_id, "plan_sha256": plan_hash},
        )
        connection.commit()
        print(f"Draft test plan {plan_id} created for {hypothesis['hypothesis_id']}.")
        print(f"Plan hash: {plan_hash}")
        print("Review the plan, then approve it with the exact hash as --confirm.")
        return 0
    finally:
        connection.close()


def plan_row(connection: sqlite3.Connection, engagement_id: int, plan_id: int) -> sqlite3.Row:
    row = connection.execute(
        "SELECT p.*, h.hypothesis_id, h.status AS hypothesis_status, h.id AS hypothesis_db_id "
        "FROM test_plans p JOIN hypotheses h ON h.id = p.hypothesis_id "
        "WHERE p.engagement_id = ? AND p.id = ?",
        (engagement_id, plan_id),
    ).fetchone()
    if row is None:
        raise BugBountyError(f"test plan not found: {plan_id}")
    return row


def require_current_plan_policy(
    connection: sqlite3.Connection, engagement_id: int, plan: sqlite3.Row
) -> None:
    snapshot = policy_snapshot(connection, engagement_id)
    if plan["policy_snapshot_id"] != snapshot["id"]:
        raise BugBountyError("test plan was created under a superseded policy snapshot")


def plan_is_expired(plan: sqlite3.Row) -> bool:
    try:
        expires_at = dt.datetime.fromisoformat(plan["expires_at"] or "")
    except ValueError as error:
        raise BugBountyError("test plan has an invalid approval expiry") from error
    return expires_at <= utc_now()


def expire_plan(connection: sqlite3.Connection, plan: sqlite3.Row, actor: str) -> None:
    """Close a stale authorization and return its hypothesis to the queue."""
    connection.execute(
        "UPDATE approval_executions SET status = 'cancelled', completed_at = datetime('now'), "
        "result_summary = COALESCE(result_summary, 'Cancelled because the plan approval expired') "
        "WHERE test_plan_id = ? AND status = 'started'",
        (plan["id"],),
    )
    connection.execute(
        "UPDATE test_plans SET status = 'expired', updated_at = datetime('now') WHERE id = ?",
        (plan["id"],),
    )
    if plan["hypothesis_status"] in {"approved", "testing"}:
        connection.execute("UPDATE hypotheses SET status = 'queued' WHERE id = ?", (plan["hypothesis_db_id"],))
        record_hypothesis_event(
            connection,
            int(plan["hypothesis_db_id"]),
            "approval-expired",
            from_status=plan["hypothesis_status"],
            to_status="queued",
            actor=actor,
            details={"plan_id": plan["id"]},
        )


def verified_candidate_evidence(
    connection: sqlite3.Connection, hypothesis: sqlite3.Row
) -> list[str]:
    """Return only evidence still bound to a completed approved execution."""
    try:
        evidence_paths = json.loads(hypothesis["evidence_refs"] or "[]")
    except json.JSONDecodeError as error:
        raise BugBountyError("candidate evidence references are invalid") from error
    if not isinstance(evidence_paths, list) or not evidence_paths or any(
        not isinstance(path, str) for path in evidence_paths
    ):
        raise BugBountyError("confirmation requires an evidence reference")

    verified: list[str] = []
    for relative_path in evidence_paths:
        evidence_path = (ROOT / relative_path).resolve()
        if not is_within(evidence_path, ROOT / "output") or not evidence_path.is_file():
            raise BugBountyError("candidate evidence is missing or outside output/")
        digest = sha256_path(evidence_path)
        evidence_row = connection.execute(
            "SELECT sha256 FROM evidence WHERE path = ?", (relative_path,)
        ).fetchone()
        execution_row = connection.execute(
            "SELECT e.evidence_sha256 FROM approval_executions e "
            "JOIN test_plans p ON p.id = e.test_plan_id "
            "WHERE p.hypothesis_id = ? AND e.status = 'completed' "
            "AND e.evidence_path = ? AND e.evidence_sha256 = ? "
            "ORDER BY e.completed_at DESC LIMIT 1",
            (hypothesis["id"], relative_path, digest),
        ).fetchone()
        if (
            evidence_row is None
            or evidence_row["sha256"] != digest
            or execution_row is None
            or execution_row["evidence_sha256"] != digest
        ):
            raise BugBountyError(
                "candidate evidence no longer matches its approved execution record"
            )
        verified.append(relative_path)
    return verified


def command_plan_show(args: argparse.Namespace) -> int:
    connection, _, _, engagement_id = connect(args)
    try:
        row = plan_row(connection, engagement_id, args.plan_id)
        print(json.dumps(json.loads(row["plan_json"]), indent=2, ensure_ascii=False))
        print(f"status: {row['status']}")
        print(f"hash: {row['plan_sha256']}")
        return 0
    finally:
        connection.close()


def command_approve(args: argparse.Namespace) -> int:
    connection, manifest, _, engagement_id = connect(args)
    try:
        plan = plan_row(connection, engagement_id, args.plan_id)
        if plan["status"] != "draft":
            raise BugBountyError(f"only a draft plan can be approved (current: {plan['status']})")
        if plan["hypothesis_status"] != "queued":
            raise BugBountyError(
                f"plan hypothesis must still be queued before approval (current: {plan['hypothesis_status']})"
            )
        if args.confirm != plan["plan_sha256"]:
            raise BugBountyError("--confirm must exactly match the displayed immutable plan hash")
        require_current_plan_policy(connection, engagement_id, plan)
        require_policy_action(connection, manifest, engagement_id, plan["target"], plan["action"])
        expires_at = utc_now() + dt.timedelta(hours=args.expires_hours)
        connection.execute(
            "INSERT INTO approvals (engagement_id, action, scope, approved_by, approved_at, expires_at, notes) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                engagement_id,
                plan["action"],
                plan["target"],
                args.approved_by,
                utc_text(),
                utc_text(expires_at),
                f"Test plan {plan['id']} SHA-256 {plan['plan_sha256']}",
            ),
        )
        approval_id = int(connection.execute("SELECT last_insert_rowid()").fetchone()[0])
        connection.execute(
            "UPDATE test_plans SET status = 'approved', approval_id = ?, approved_by = ?, "
            "approved_at = ?, expires_at = ?, updated_at = datetime('now') WHERE id = ?",
            (approval_id, args.approved_by, utc_text(), utc_text(expires_at), plan["id"]),
        )
        connection.execute("UPDATE hypotheses SET status = 'approved' WHERE id = ?", (plan["hypothesis_db_id"],))
        record_hypothesis_event(
            connection,
            int(plan["hypothesis_db_id"]),
            "approved",
            from_status=plan["hypothesis_status"],
            to_status="approved",
            actor=args.approved_by,
            details={"plan_id": plan["id"], "approval_id": approval_id, "expires_at": utc_text(expires_at)},
        )
        connection.commit()
        print(f"Approved plan {plan['id']} until {utc_text(expires_at)}.")
        print("Before any reviewed Repeater action, run begin-test and obey the plan exactly.")
        return 0
    finally:
        connection.close()


def command_begin_test(args: argparse.Namespace) -> int:
    connection, manifest, _, engagement_id = connect(args)
    try:
        plan = plan_row(connection, engagement_id, args.plan_id)
        if plan["status"] != "approved":
            raise BugBountyError(f"plan is not approved (current: {plan['status']})")
        if plan_is_expired(plan):
            expire_plan(connection, plan, args.operator)
            connection.commit()
            raise BugBountyError("plan approval has expired")
        require_current_plan_policy(connection, engagement_id, plan)
        require_policy_action(connection, manifest, engagement_id, plan["target"], plan["action"])
        connection.execute("UPDATE test_plans SET status = 'testing' WHERE id = ?", (plan["id"],))
        connection.execute("UPDATE hypotheses SET status = 'testing' WHERE id = ?", (plan["hypothesis_db_id"],))
        connection.execute("INSERT INTO approval_executions (test_plan_id) VALUES (?)", (plan["id"],))
        execution_id = int(connection.execute("SELECT last_insert_rowid()").fetchone()[0])
        record_hypothesis_event(
            connection,
            int(plan["hypothesis_db_id"]),
            "testing-started",
            from_status=plan["hypothesis_status"],
            to_status="testing",
            actor=args.operator,
            details={"plan_id": plan["id"], "execution_id": execution_id},
        )
        connection.commit()
        print(f"Test authorization recorded: execution {execution_id}, plan {plan['id']}.")
        print(f"Allowed maximum: {plan['max_requests']} request(s) at {plan['rate_limit_per_second']} request(s)/second.")
        print("This record does not bypass the program policy or authorize any action outside the plan.")
        return 0
    finally:
        connection.close()


def command_record(args: argparse.Namespace) -> int:
    connection, manifest, _, engagement_id = connect(args)
    try:
        plan = plan_row(connection, engagement_id, args.plan_id)
        if plan["status"] != "testing":
            raise BugBountyError("recording requires a test plan in testing state")
        if plan_is_expired(plan):
            expire_plan(connection, plan, args.operator)
            connection.commit()
            raise BugBountyError("plan approval has expired; its active execution was cancelled")
        if args.request_count > plan["max_requests"]:
            raise BugBountyError("request count exceeds the approved maximum")
        require_current_plan_policy(connection, engagement_id, plan)
        require_policy_action(connection, manifest, engagement_id, plan["target"], plan["action"])
        evidence_path = Path(args.evidence).expanduser().resolve()
        if not evidence_path.is_file():
            raise BugBountyError(f"evidence file not found: {evidence_path}")
        if not is_within(evidence_path, ROOT / "output"):
            raise BugBountyError("evidence must be saved under the ignored output/ directory")
        evidence_hash = sha256_path(evidence_path)
        execution = connection.execute(
            "SELECT id FROM approval_executions WHERE test_plan_id = ? AND status = 'started' "
            "ORDER BY started_at DESC LIMIT 1",
            (plan["id"],),
        ).fetchone()
        if execution is None:
            raise BugBountyError("no active execution record exists for this plan")
        outcome_status = "informative" if args.outcome == "blocked" else args.outcome
        if outcome_status not in {"candidate", "rejected", "duplicate", "informative"}:
            raise BugBountyError("invalid recorded outcome")
        relative_path = str(evidence_path.relative_to(ROOT))
        connection.execute(
            "UPDATE approval_executions SET status = 'completed', request_count = ?, evidence_path = ?, "
            "evidence_sha256 = ?, result_summary = ?, completed_at = datetime('now') WHERE id = ?",
            (args.request_count, relative_path, evidence_hash, args.summary, execution["id"]),
        )
        connection.execute(
            "UPDATE test_plans SET status = 'completed', updated_at = datetime('now') WHERE id = ?",
            (plan["id"],),
        )
        connection.execute(
            "UPDATE hypotheses SET status = ?, evidence_refs = ?, notes = ? WHERE id = ?",
            (
                outcome_status,
                canonical_json([relative_path]),
                args.summary,
                plan["hypothesis_db_id"],
            ),
        )
        connection.execute(
            "INSERT OR IGNORE INTO evidence (path, sha256, mime_type, size_bytes, notes) "
            "VALUES (?, ?, ?, ?, ?)",
            (
                relative_path,
                evidence_hash,
                "text/plain",
                evidence_path.stat().st_size,
                f"Bug-bounty test plan {plan['id']}",
            ),
        )
        record_hypothesis_event(
            connection,
            int(plan["hypothesis_db_id"]),
            "test-recorded",
            from_status="testing",
            to_status=outcome_status,
            actor=args.operator,
            details={"plan_id": plan["id"], "execution_id": execution["id"], "evidence": relative_path},
        )
        connection.commit()
        print(f"Recorded {outcome_status} outcome for {plan['hypothesis_id']}.")
        if outcome_status == "candidate":
            print("Review the evidence and use confirm only after minimum impact is established.")
        return 0
    finally:
        connection.close()


def command_confirm(args: argparse.Namespace) -> int:
    connection, _, _, engagement_id = connect(args)
    try:
        hypothesis = hypothesis_with_endpoint(connection, engagement_id, args.hypothesis)
        if hypothesis["status"] != "candidate":
            raise BugBountyError("only a candidate hypothesis can be confirmed")
        evidence = verified_candidate_evidence(connection, hypothesis)
        finding_key = f"BB-{hypothesis['hypothesis_id']}"
        connection.execute(
            "INSERT INTO findings "
            "(engagement_id, target_id, finding_id, phase, type, severity, title, url, evidence, confidence, status, raw_path) "
            "VALUES (?, ?, ?, 'exploit', 'bug-bounty', ?, ?, ?, ?, 'confirmed', 'confirmed', ?) "
            "ON CONFLICT(finding_id) DO UPDATE SET severity=excluded.severity, title=excluded.title, "
            "evidence=excluded.evidence, status='confirmed', confidence='confirmed', raw_path=excluded.raw_path, "
            "updated_at=datetime('now')",
            (
                engagement_id,
                hypothesis["target_id"],
                finding_key,
                args.severity,
                args.title,
                f"{hypothesis['protocol']}://{hypothesis['host']}{hypothesis['path_template']}",
                args.impact,
                evidence[0],
            ),
        )
        connection.execute("UPDATE hypotheses SET status = 'confirmed' WHERE id = ?", (hypothesis["id"],))
        connection.execute(
            "UPDATE hunt_sessions SET findings_confirmed = findings_confirmed + 1 "
            "WHERE id = (SELECT id FROM hunt_sessions WHERE engagement_id = ? "
            "AND status = 'running' ORDER BY started_at DESC LIMIT 1)",
            (engagement_id,),
        )
        record_hypothesis_event(
            connection,
            int(hypothesis["id"]),
            "confirmed",
            from_status="candidate",
            to_status="confirmed",
            actor=args.reviewed_by,
            details={"finding_id": finding_key, "impact": args.impact},
        )
        connection.commit()
        print(f"Confirmed finding {finding_key}. Submission remains a manual analyst action.")
        return 0
    finally:
        connection.close()


def command_report(args: argparse.Namespace) -> int:
    connection, manifest, _, engagement_id = connect(args)
    try:
        hypothesis = hypothesis_with_endpoint(connection, engagement_id, args.hypothesis)
        if hypothesis["status"] != "confirmed":
            raise BugBountyError("a report draft requires a confirmed hypothesis")
        finding = connection.execute(
            "SELECT * FROM findings WHERE engagement_id = ? AND finding_id = ?",
            (engagement_id, f"BB-{hypothesis['hypothesis_id']}"),
        ).fetchone()
        if finding is None:
            raise BugBountyError("confirmed hypothesis has no corresponding finding")
        program = get_program(connection, engagement_id)
        evidence = verified_candidate_evidence(connection, hypothesis)
        report_dir = ROOT / "output" / manifest["name"] / "reports"
        report_path = report_dir / f"{hypothesis['hypothesis_id'].lower()}-{args.format}-draft.md"
        template = [
            f"# {finding['title']}",
            "",
            f"**Program:** {program['program_name']}",
            f"**Severity (analyst assessed):** {finding['severity']}",
            f"**Affected endpoint:** {finding['url']}",
            "",
            "## Summary",
            "",
            finding["evidence"] or "Impact evidence is recorded in the attached artifact.",
            "",
            "## Reproduction",
            "",
            "Use the saved, analyst-approved test plan and the redacted evidence bundle. "
            "Do not include live credentials, tokens, cookies, or unrelated user data.",
            "",
            "## Evidence",
            "",
        ]
        template.extend([f"- `{path}`" for path in evidence])
        template.extend(
            [
                "",
                "## Remediation",
                "",
                "Enforce authorization on the server for the requested object and action; "
                "derive authorization from the authenticated identity rather than client-controlled identifiers.",
                "",
                "## Submission status",
                "",
                "Draft only. RedCode does not submit findings to a bug-bounty platform.",
            ]
        )
        write_private(report_path, "\n".join(template) + "\n")
        finding_id = int(finding["id"])
        connection.execute(
            "INSERT INTO bug_bounty_submissions (engagement_id, finding_id, platform, status, notes) "
            "VALUES (?, ?, ?, 'draft', ?)",
            (engagement_id, finding_id, args.format, f"Draft at {report_path.relative_to(ROOT)}"),
        )
        connection.commit()
        print(f"Draft report: {report_path.relative_to(ROOT)}")
        print("Review, redact, and submit it manually through the program platform.")
        return 0
    finally:
        connection.close()


def command_status(args: argparse.Namespace) -> int:
    connection, _, _, engagement_id = connect(args)
    try:
        program = get_program(connection, engagement_id)
        policy = policy_snapshot(connection, engagement_id)
        endpoint_count = connection.execute(
            "SELECT COUNT(*) FROM endpoints WHERE engagement_id = ?", (engagement_id,)
        ).fetchone()[0]
        identity_count = connection.execute(
            "SELECT COUNT(*) FROM identities WHERE engagement_id = ?", (engagement_id,)
        ).fetchone()[0]
        hypothesis_counts = connection.execute(
            "SELECT status, COUNT(*) AS count FROM hypotheses WHERE engagement_id = ? GROUP BY status",
            (engagement_id,),
        ).fetchall()
        import_row = connection.execute(
            "SELECT * FROM burp_import_runs WHERE engagement_id = ? ORDER BY id DESC LIMIT 1",
            (engagement_id,),
        ).fetchone()
        top = connection.execute(
            "SELECT hypothesis_id, priority, statement FROM hypotheses WHERE engagement_id = ? "
            "AND status = 'queued' ORDER BY priority DESC LIMIT 3",
            (engagement_id,),
        ).fetchall()
        print(f"Program: {program['program_name']} ({program['platform']})")
        print(f"Reviewed policy: {policy['reviewed_at']} ({policy['snapshot_path']})")
        print(f"Map: {endpoint_count} endpoint(s), {identity_count} symbolic identity/identities")
        if import_row:
            print(
                f"Latest Burp import: #{import_row['id']} {import_row['status']} "
                f"({import_row['messages_imported']} imported, {import_row['messages_skipped']} skipped)"
            )
        else:
            print("Latest Burp import: none")
        print("Hypotheses: " + ", ".join(f"{row['status']}={row['count']}" for row in hypothesis_counts))
        if top:
            print("Next candidates:")
            for row in top:
                print(f"- {row['hypothesis_id']} (priority {row['priority']}): {row['statement']}")
        return 0
    finally:
        connection.close()


def command_session(args: argparse.Namespace) -> int:
    connection, _, _, engagement_id = connect(args)
    try:
        row = connection.execute(
            "SELECT id, status FROM hunt_sessions WHERE engagement_id = ? AND status = 'running' "
            "ORDER BY started_at DESC LIMIT 1",
            (engagement_id,),
        ).fetchone()
        if row is None:
            raise BugBountyError("no running hunt session exists")
        connection.execute(
            "UPDATE hunt_sessions SET status = ?, notes = ?, ended_at = datetime('now') WHERE id = ?",
            (args.status, args.notes, row["id"]),
        )
        connection.commit()
        print(f"Hunt session {row['id']} marked {args.status}.")
        return 0
    finally:
        connection.close()


def mcp_response_payload(raw: bytes) -> dict[str, Any]:
    text = raw.decode("utf-8", errors="replace").strip()
    if text.startswith("data:"):
        pieces = [line[5:].strip() for line in text.splitlines() if line.startswith("data:")]
        text = "\n".join(pieces)
    try:
        value = json.loads(text)
    except json.JSONDecodeError as error:
        raise BugBountyError("Burp MCP returned a non-JSON response") from error
    if not isinstance(value, dict):
        raise BugBountyError("Burp MCP returned an invalid JSON-RPC response")
    if "error" in value:
        raise BugBountyError(f"Burp MCP error: {value['error']}")
    return value


def mcp_post(
    url: str,
    payload: dict[str, Any],
    session_id: str | None = None,
    *,
    allow_empty_response: bool = False,
) -> tuple[dict[str, Any], str | None]:
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
    }
    if session_id:
        headers["Mcp-Session-Id"] = session_id
    request = Request(url, data=canonical_json(payload).encode("utf-8"), headers=headers, method="POST")
    try:
        with urlopen(request, timeout=10) as response:
            body = response.read()
            if not body and allow_empty_response:
                return {}, response.headers.get("Mcp-Session-Id") or session_id
            return mcp_response_payload(body), response.headers.get("Mcp-Session-Id") or session_id
    except (HTTPError, URLError, TimeoutError, OSError) as error:
        raise BugBountyError(f"Burp MCP request failed: {error}") from error


def command_burp_probe(args: argparse.Namespace) -> int:
    url = args.url or os.environ.get("BURP_MCP_URL")
    if not url:
        raise BugBountyError("BURP_MCP_URL is not configured")
    initialized, session_id = mcp_post(
        url,
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2025-03-26",
                "capabilities": {},
                "clientInfo": {"name": "redcode-bugbounty", "version": "1"},
            },
        },
    )
    mcp_post(
        url,
        {"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}},
        session_id,
        allow_empty_response=True,
    )
    tools, _ = mcp_post(
        url,
        {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}},
        session_id,
    )
    names = sorted(
        str(item.get("name"))
        for item in tools.get("result", {}).get("tools", [])
        if isinstance(item, dict) and item.get("name")
    )
    missing = sorted(set(args.require_tool or []) - set(names))
    server_info = initialized.get("result", {}).get("serverInfo", {})
    print(f"Burp MCP: {server_info.get('name', 'unknown')} {server_info.get('version', '')}".strip())
    print("Tools: " + (", ".join(names) if names else "none reported"))
    if missing:
        print("Missing required tools: " + ", ".join(missing), file=sys.stderr)
        return 1
    return 0


def add_common_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--db", help="SQLite database path")
    parser.add_argument("--manifest", help="engagement manifest path")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="redcode bugbounty", description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    onboard = subparsers.add_parser("onboard", help="save a reviewed program-policy snapshot")
    add_common_arguments(onboard)
    onboard.add_argument("--platform", default="hackerone")
    onboard.add_argument("--program-name", required=True)
    onboard.add_argument("--program-url")
    onboard.add_argument("--policy-url")
    onboard.add_argument("--policy-file", required=True)
    onboard.add_argument("--scope", action="append", required=True, help="reviewed policy allow rule")
    onboard.add_argument("--out-of-scope", action="append", help="reviewed policy exclusion")
    onboard.add_argument("--prohibit-action", action="append", choices=sorted(control.ACTIONS | {"all"}))
    onboard.add_argument("--restriction-reason")
    onboard.add_argument("--reviewed-by", required=True)
    onboard.add_argument("--policy-notes")
    onboard.add_argument("--objective")
    onboard.add_argument("--currency")
    onboard.add_argument("--minimum-bounty", type=float)
    onboard.add_argument("--maximum-bounty", type=float)
    onboard.add_argument("--duplicate-risk", type=int, choices=range(0, 6))
    onboard.add_argument("--account-requirements")
    onboard.add_argument("--notes")
    onboard.set_defaults(func=command_onboard)

    identity = subparsers.add_parser("identity", help="manage symbolic test identities")
    identity_subparsers = identity.add_subparsers(dest="identity_command", required=True)
    identity_add = identity_subparsers.add_parser("add", help="add or update a symbolic identity")
    add_common_arguments(identity_add)
    identity_add.add_argument("--label", required=True)
    identity_add.add_argument("--target")
    identity_add.add_argument("--tenant")
    identity_add.add_argument("--role")
    identity_add.add_argument("--auth-state", choices=("anonymous", "authenticated", "limited"), default="authenticated")
    identity_add.add_argument("--burp-label")
    identity_add.add_argument("--notes")
    identity_add.set_defaults(func=command_identity_add)

    check = subparsers.add_parser("check", help="intersect manifest and reviewed policy scope")
    add_common_arguments(check)
    check.add_argument("target")
    check.add_argument("action", choices=sorted(control.ACTIONS))
    check.set_defaults(func=command_check)

    ingest = subparsers.add_parser("ingest", help="import a selected Burp JSON or JSONL export")
    add_common_arguments(ingest)
    ingest.add_argument("--file", required=True)
    ingest.add_argument("--identity", default="anon")
    ingest.add_argument("--source-kind", choices=("history", "site_map", "export"), default="export")
    ingest.add_argument("--cursor")
    ingest.add_argument("--include-bodies", action="store_true", help="save redacted request structures")
    ingest.set_defaults(func=command_ingest)

    identifier = subparsers.add_parser(
        "identifier", help="inspect and review redacted semantic identifier candidates"
    )
    identifier_subparsers = identifier.add_subparsers(dest="identifier_command", required=True)
    identifier_list = identifier_subparsers.add_parser("list", help="list identifier candidates and review status")
    add_common_arguments(identifier_list)
    identifier_list.set_defaults(func=command_identifier_list)
    identifier_confirm = identifier_subparsers.add_parser("confirm", help="confirm one identifier role")
    add_common_arguments(identifier_confirm)
    identifier_confirm.add_argument("--endpoint-id", type=int, required=True)
    identifier_confirm.add_argument("--position", type=int, required=True, choices=range(1, 101))
    identifier_confirm.add_argument("--role", required=True)
    identifier_confirm.add_argument("--confirmed-by", required=True)
    identifier_confirm.add_argument("--note")
    identifier_confirm.set_defaults(func=command_identifier_confirm)
    identifier_reject = identifier_subparsers.add_parser("reject", help="reject one identifier role candidate")
    add_common_arguments(identifier_reject)
    identifier_reject.add_argument("--endpoint-id", type=int, required=True)
    identifier_reject.add_argument("--position", type=int, required=True, choices=range(1, 101))
    identifier_reject.add_argument("--role", required=True)
    identifier_reject.add_argument("--reason", required=True)
    identifier_reject.add_argument("--rejected-by", required=True)
    identifier_reject.set_defaults(func=command_identifier_reject)
    identifier_relationship = identifier_subparsers.add_parser(
        "relationship", help="inspect or confirm relationships between identifier roles"
    )
    relationship_subparsers = identifier_relationship.add_subparsers(
        dest="relationship_command", required=True
    )
    relationship_list = relationship_subparsers.add_parser("list", help="list relationship leads and confirmations")
    add_common_arguments(relationship_list)
    relationship_list.set_defaults(func=command_identifier_relationship_list)
    relationship_confirm = relationship_subparsers.add_parser("confirm", help="confirm an identifier relationship")
    add_common_arguments(relationship_confirm)
    relationship_confirm.add_argument("--workflow-id", type=int, required=True)
    relationship_confirm.add_argument("--from-role", required=True)
    relationship_confirm.add_argument("--to-role", required=True)
    relationship_confirm.add_argument("--relation", default="scoped-by")
    relationship_confirm.add_argument("--confirmed-by", required=True)
    relationship_confirm.add_argument("--note")
    relationship_confirm.set_defaults(func=command_identifier_relationship_confirm)

    map_command = subparsers.add_parser("map", help="derive a persistent endpoint/workflow map")
    add_common_arguments(map_command)
    map_command.set_defaults(func=command_map)

    workflow = subparsers.add_parser(
        "workflow", help="add analyst-reviewed business context to a mapped workflow"
    )
    workflow_subparsers = workflow.add_subparsers(dest="workflow_command", required=True)
    workflow_annotate = workflow_subparsers.add_parser(
        "annotate", help="merge symbolic actors, objects, states, and sensitivity"
    )
    add_common_arguments(workflow_annotate)
    workflow_annotate.add_argument("--host", required=True)
    workflow_annotate.add_argument("--name", required=True, help="mapped first path segment")
    workflow_annotate.add_argument("--actor", action="append", help="existing symbolic identity label")
    workflow_annotate.add_argument("--object", action="append", help="safe object type label")
    workflow_annotate.add_argument("--state", action="append", help="safe lifecycle-state label")
    workflow_annotate.add_argument("--sensitivity", type=int, choices=range(0, 6))
    workflow_annotate.add_argument("--notes")
    workflow_annotate.set_defaults(func=command_workflow_annotate)

    workflow_state = workflow_subparsers.add_parser(
        "state", help="record analyst-confirmed lifecycle state semantics"
    )
    workflow_state_subparsers = workflow_state.add_subparsers(
        dest="workflow_state_command", required=True
    )
    workflow_state_set = workflow_state_subparsers.add_parser(
        "set", help="mark a workflow state as terminal or non-terminal"
    )
    add_common_arguments(workflow_state_set)
    workflow_state_set.add_argument("--host", required=True)
    workflow_state_set.add_argument("--name", required=True)
    workflow_state_set.add_argument("--state", required=True)
    terminal_group = workflow_state_set.add_mutually_exclusive_group(required=True)
    terminal_group.add_argument("--terminal", dest="terminal", action="store_true")
    terminal_group.add_argument("--not-terminal", dest="terminal", action="store_false")
    workflow_state_set.add_argument("--notes")
    workflow_state_set.set_defaults(func=command_workflow_state_set)

    workflow_transition = workflow_subparsers.add_parser(
        "transition", help="record an analyst-confirmed workflow transition"
    )
    workflow_transition_subparsers = workflow_transition.add_subparsers(
        dest="workflow_transition_command", required=True
    )
    workflow_transition_add = workflow_transition_subparsers.add_parser(
        "add", help="add a lifecycle transition and its security semantics"
    )
    add_common_arguments(workflow_transition_add)
    workflow_transition_add.add_argument("--host", required=True)
    workflow_transition_add.add_argument("--name", required=True)
    workflow_transition_add.add_argument("--from-state", required=True)
    workflow_transition_add.add_argument("--to-state", required=True)
    workflow_transition_add.add_argument("--endpoint-id", type=int)
    workflow_transition_add.add_argument("--actor", action="append", help="existing symbolic identity")
    workflow_transition_add.add_argument("--prerequisite", action="append")
    workflow_transition_add.add_argument("--postcondition", action="append")
    workflow_transition_add.add_argument(
        "--authorization-effect", choices=("none", "grant", "revoke", "transfer"), default="none"
    )
    workflow_transition_add.add_argument("--capability", action="append")
    workflow_transition_add.add_argument("--trust-boundary", action="append")
    workflow_transition_add.add_argument("--sensitive", action="store_true")
    workflow_transition_add.add_argument("--confidence", type=int, choices=range(0, 6), default=3)
    workflow_transition_add.add_argument("--notes")
    workflow_transition_add.set_defaults(func=command_workflow_transition_add)

    workflow_invariant = workflow_subparsers.add_parser(
        "invariant", help="record a workflow property and its implementation assumptions"
    )
    workflow_invariant_subparsers = workflow_invariant.add_subparsers(
        dest="workflow_invariant_command", required=True
    )
    workflow_invariant_add = workflow_invariant_subparsers.add_parser(
        "add", help="add an analyst-confirmed security invariant"
    )
    add_common_arguments(workflow_invariant_add)
    workflow_invariant_add.add_argument("--host", required=True)
    workflow_invariant_add.add_argument("--name", required=True)
    workflow_invariant_add.add_argument("--statement", required=True)
    workflow_invariant_add.add_argument("--state", action="append")
    workflow_invariant_add.add_argument("--transition")
    workflow_invariant_add.add_argument("--endpoint-id", type=int, action="append")
    workflow_invariant_add.add_argument("--actor", action="append")
    workflow_invariant_add.add_argument("--assumption", action="append", required=True)
    workflow_invariant_add.add_argument("--trust-boundary", action="append")
    workflow_invariant_add.add_argument("--confidence", type=int, choices=range(0, 6), default=3)
    workflow_invariant_add.add_argument("--sensitivity", type=int, choices=range(0, 6), default=0)
    workflow_invariant_add.add_argument("--notes")
    workflow_invariant_add.set_defaults(func=command_workflow_invariant_add)

    workflow_learn = workflow_subparsers.add_parser(
        "learn", help="record analyst-reviewed learning that corrects the workflow model"
    )
    add_common_arguments(workflow_learn)
    workflow_learn.add_argument("--host", required=True)
    workflow_learn.add_argument("--name", required=True)
    workflow_learn.add_argument("--observation", required=True)
    workflow_learn.add_argument("--plan-id", type=int)
    workflow_learn.add_argument("--confidence", type=int, choices=range(0, 6), default=3)
    workflow_learn.set_defaults(func=command_workflow_learn)

    queue = subparsers.add_parser("queue", help="show or generate MAPPA hypotheses")
    add_common_arguments(queue)
    queue.add_argument("--generate", action="store_true")
    queue.add_argument("--limit", type=int, default=10)
    queue.set_defaults(func=command_queue)

    hypothesis = subparsers.add_parser(
        "hypothesis", help="add a specific analyst-reviewed MAPPA hypothesis"
    )
    hypothesis_subparsers = hypothesis.add_subparsers(dest="hypothesis_command", required=True)
    hypothesis_add = hypothesis_subparsers.add_parser(
        "add", help="add a contextual hypothesis for an already mapped endpoint"
    )
    add_common_arguments(hypothesis_add)
    hypothesis_add.add_argument("--endpoint-id", type=int, required=True)
    hypothesis_add.add_argument("--statement", required=True)
    hypothesis_add.add_argument("--actor", required=True, help="existing symbolic identity label")
    hypothesis_add.add_argument("--action", help="short action label; defaults to the endpoint method")
    hypothesis_add.add_argument("--object-owner", required=True)
    hypothesis_add.add_argument("--object-state", required=True)
    hypothesis_add.add_argument("--channel", default="http")
    hypothesis_add.add_argument("--boundary-score", type=int, choices=range(0, 6))
    hypothesis_add.add_argument("--impact-score", type=int, choices=range(0, 6))
    hypothesis_add.add_argument("--novelty-score", type=int, choices=range(0, 6))
    hypothesis_add.add_argument("--evidence-score", type=int, choices=range(0, 6))
    hypothesis_add.add_argument("--duplicate-risk", type=int, choices=range(0, 6))
    hypothesis_add.add_argument("--test-cost", type=int, choices=range(0, 6))
    hypothesis_add.add_argument("--operational-risk", type=int, choices=range(0, 6))
    hypothesis_add.add_argument("--created-by", required=True)
    hypothesis_add.set_defaults(func=command_hypothesis_add)

    plan = subparsers.add_parser("plan", help="create or inspect an immutable test plan")
    plan_subparsers = plan.add_subparsers(dest="plan_command", required=True)
    plan_create = plan_subparsers.add_parser("create", help="create a draft test plan")
    add_common_arguments(plan_create)
    plan_create.add_argument("--hypothesis", required=True)
    plan_create.add_argument("--action", choices=("scan", "exploit"), default="exploit")
    plan_create.add_argument("--identity")
    plan_create.add_argument("--control", required=True)
    plan_create.add_argument("--single-change", required=True)
    plan_create.add_argument("--expected-result", required=True)
    plan_create.add_argument("--minimum-proof", required=True)
    plan_create.add_argument("--stop-condition", required=True)
    plan_create.add_argument("--cleanup", required=True)
    plan_create.add_argument("--max-requests", type=int, default=2, choices=range(1, 21))
    plan_create.add_argument("--created-by", required=True)
    plan_create.set_defaults(func=command_plan_create)
    plan_show = plan_subparsers.add_parser("show", help="show a test plan and its immutable hash")
    add_common_arguments(plan_show)
    plan_show.add_argument("plan_id", type=int)
    plan_show.set_defaults(func=command_plan_show)

    approve = subparsers.add_parser("approve", help="approve exactly one immutable test plan")
    add_common_arguments(approve)
    approve.add_argument("plan_id", type=int)
    approve.add_argument("--approved-by", required=True)
    approve.add_argument("--expires-hours", type=int, default=1, choices=range(1, 25))
    approve.add_argument("--confirm", required=True, help="exact SHA-256 shown by plan show/create")
    approve.set_defaults(func=command_approve)

    begin = subparsers.add_parser("begin-test", help="record the start of one approved test")
    add_common_arguments(begin)
    begin.add_argument("plan_id", type=int)
    begin.add_argument("--operator", required=True)
    begin.set_defaults(func=command_begin_test)

    record = subparsers.add_parser("record", help="record a completed approved test")
    add_common_arguments(record)
    record.add_argument("plan_id", type=int)
    record.add_argument("--outcome", choices=("candidate", "rejected", "duplicate", "informative", "blocked"), required=True)
    record.add_argument("--request-count", type=int, required=True, choices=range(0, 21))
    record.add_argument("--evidence", required=True)
    record.add_argument("--summary", required=True)
    record.add_argument("--operator", required=True)
    record.set_defaults(func=command_record)

    confirm = subparsers.add_parser("confirm", help="turn an evidenced candidate into a confirmed finding")
    add_common_arguments(confirm)
    confirm.add_argument("--hypothesis", required=True)
    confirm.add_argument("--title", required=True)
    confirm.add_argument("--severity", required=True, choices=("critical", "high", "medium", "low", "info"))
    confirm.add_argument("--impact", required=True)
    confirm.add_argument("--reviewed-by", required=True)
    confirm.set_defaults(func=command_confirm)

    report = subparsers.add_parser("report", help="write a draft report; never submits it")
    add_common_arguments(report)
    report.add_argument("--hypothesis", required=True)
    report.add_argument("--format", choices=("hackerone", "bugcrowd"), default="hackerone")
    report.set_defaults(func=command_report)

    status = subparsers.add_parser("status", help="show the next useful program state")
    add_common_arguments(status)
    status.set_defaults(func=command_status)

    session = subparsers.add_parser("session", help="pause or close the active hunt session")
    add_common_arguments(session)
    session.add_argument("status", choices=("paused", "completed"))
    session.add_argument("--notes", required=True)
    session.set_defaults(func=command_session)

    burp = subparsers.add_parser("burp", help="verify a standard streamable-HTTP Burp MCP endpoint")
    burp_subparsers = burp.add_subparsers(dest="burp_command", required=True)
    burp_probe = burp_subparsers.add_parser("probe", help="initialize MCP and list available tools")
    burp_probe.add_argument("--url")
    burp_probe.add_argument("--require-tool", action="append")
    burp_probe.set_defaults(func=command_burp_probe)
    return parser


def main(argv: list[str] | None = None) -> int:
    control.load_dotenv(ROOT / ".env")
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except BugBountyError as error:
        print(f"Bug-bounty error: {error}", file=sys.stderr)
        return 1
    except sqlite3.Error as error:
        print(f"Bug-bounty database error: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
