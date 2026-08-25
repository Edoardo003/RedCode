#!/usr/bin/env python3
"""Local control-plane utilities for RedCode."""

from __future__ import annotations

import argparse
import datetime as dt
import fnmatch
import ipaddress
import json
import os
import re
import shutil
import socket
import sqlite3
import subprocess
import sys
from pathlib import Path
from typing import Any
from urllib.error import URLError
from urllib.parse import urlparse
from urllib.request import urlopen

try:
    from arsenal_client import (
        ArsenalClient,
        ArsenalClientError,
        client_from_session,
        create_session,
    )
    from arsenal_client import (
        session_path as resolve_arsenal_session_path,
    )
except ModuleNotFoundError:
    from scripts.arsenal_client import (
        ArsenalClient,
        ArsenalClientError,
        client_from_session,
        create_session,
    )
    from scripts.arsenal_client import (
        session_path as resolve_arsenal_session_path,
    )


ROOT = Path(__file__).resolve().parents[1]
SCHEMA_VERSION = 6
MANIFEST_VERSION = 1
ACTIONS = {
    "recon",
    "osint",
    "scan",
    "exploit",
    "socialeng",
    "templates",
    "report",
    "hunt",
    "ctf",
}
ASSESSMENT_ACTIONS = [
    "recon",
    "osint",
    "scan",
    "exploit",
    "socialeng",
    "templates",
    "report",
    "hunt",
]
CAPABILITY_PROFILES = {
    "recon": ["nmap", "amass", "subfinder", "httpx"],
    "web": ["nuclei", "nikto", "ffuf", "gobuster", "sqlmap", "dalfox"],
    "exploitation": ["sqlmap", "hydra", "commix", "msfconsole", "searchsploit"],
    "ctf-pwn": ["gdb", "checksec", "pwntools", "ropper"],
    "ctf-rev": ["file", "strings", "radare2", "ghidra", "angr"],
    "ctf-forensics": ["file", "binwalk", "exiftool", "foremost", "volatility3"],
}
OPENCODE_AGENTS = {
    "bugbounty",
    "redcode",
    "recon",
    "scanner",
    "exploiter",
    "osint",
    "socialeng",
    "ctf",
    "reporter",
    "templates",
}
ARSENAL_DISABLED_MCP = {"hexstrike", "fetch", "playwright", "burp"}
ARSENAL_DENIED_TOOLS = {
    "bash",
    "webfetch",
    "websearch",
    *(f"{name}_*" for name in ARSENAL_DISABLED_MCP),
}


def load_dotenv(path: Path) -> None:
    if not path.is_file():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def project_path(value: str | None, default: str) -> Path:
    path = Path(value or default).expanduser()
    return path if path.is_absolute() else ROOT / path


def database_path(explicit: str | None = None) -> Path:
    return project_path(explicit or os.environ.get("REDCODE_DB"), "redcode.db")


def manifest_path(explicit: str | None = None) -> Path:
    return project_path(
        explicit or os.environ.get("REDCODE_ENGAGEMENT"), "engagement.json"
    )


def arsenal_session_path(explicit: str | None = None) -> Path:
    return resolve_arsenal_session_path(explicit, ROOT)


def activate_runtime_mode(mode: str, quiet: bool = False) -> Path:
    path = ROOT / "output" / ".redcode" / "current-runtime.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": 1,
        "mode": mode,
        "activated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
    }
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    if os.name != "nt":
        path.chmod(0o600)
    if not quiet:
        print(f"RedCode runtime profile activated: {mode}")
    return path


def deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def arsenal_opencode_override(existing: str | None = None) -> dict[str, Any]:
    if existing:
        try:
            base = json.loads(existing)
        except json.JSONDecodeError as exc:
            raise ValueError("OPENCODE_CONFIG_CONTENT contains invalid JSON") from exc
        if not isinstance(base, dict):
            raise ValueError("OPENCODE_CONFIG_CONTENT must contain a JSON object")
    else:
        base = {}

    permissions = {name: "deny" for name in sorted(ARSENAL_DENIED_TOOLS)}
    permissions["arsenal_*"] = "allow"
    instructions = base.get("instructions", [])
    if not isinstance(instructions, list):
        instructions = []
    arsenal_instruction = ".opencode/instructions/arsenal-mode.md"
    instructions = [*instructions, arsenal_instruction]
    instructions = list(dict.fromkeys(instructions))
    override = {
        "mcp": {
            "arsenal": {"enabled": True},
            **{
                name: {"enabled": False}
                for name in sorted(ARSENAL_DISABLED_MCP)
            },
        },
        "permission": permissions,
        "instructions": instructions,
        "agent": {
            agent: {"permission": permissions}
            for agent in sorted(OPENCODE_AGENTS)
        },
    }
    return deep_merge(base, override)


def validate_manifest(data: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(data, dict):
        return ["manifest root must be a JSON object"]

    required = {
        "schema_version",
        "name",
        "workflow",
        "mode",
        "in_scope",
        "out_of_scope",
        "allowed_actions",
    }
    missing = sorted(required - set(data))
    if missing:
        errors.append(f"missing required fields: {', '.join(missing)}")

    if data.get("schema_version") != MANIFEST_VERSION:
        errors.append(f"schema_version must be {MANIFEST_VERSION}")
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", str(data.get("name", ""))):
        errors.append("name must be a filesystem-safe identifier")
    if data.get("workflow") not in {"assessment", "ctf"}:
        errors.append("workflow must be assessment or ctf")
    if data.get("mode") not in {"normal", "aggressive"}:
        errors.append("mode must be normal or aggressive")
    if data.get("workflow") == "ctf" and data.get("mode") == "aggressive":
        errors.append("CTF manifests must use normal mode")

    for field in ("in_scope", "out_of_scope", "allowed_actions"):
        value = data.get(field)
        if not isinstance(value, list) or any(
            not isinstance(item, str) or not item.strip() for item in value
        ):
            errors.append(f"{field} must be a list of non-empty strings")

    in_scope = data.get("in_scope", [])
    if isinstance(in_scope, list) and not in_scope:
        errors.append("in_scope must contain at least one rule")

    allowed = data.get("allowed_actions", [])
    if isinstance(allowed, list):
        unknown = sorted(set(allowed) - ACTIONS)
        if unknown:
            errors.append(f"unknown allowed_actions: {', '.join(unknown)}")
        if data.get("workflow") == "ctf" and any(action != "ctf" for action in allowed):
            errors.append("CTF manifests may only allow the ctf action")
        if data.get("workflow") == "assessment" and "ctf" in allowed:
            errors.append("assessment manifests may not allow the ctf action")

    rate = data.get("rate_limit_per_second")
    if rate is not None and (not isinstance(rate, int) or rate < 1):
        errors.append("rate_limit_per_second must be a positive integer")
    return errors


def read_manifest(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ValueError(f"engagement manifest not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid JSON in {path}: {exc}") from exc
    errors = validate_manifest(data)
    if errors:
        raise ValueError("; ".join(errors))
    return data


def target_parts(target: str) -> tuple[str, str | None, int | None, str]:
    candidate = target.strip()
    parsed = urlparse(candidate if "://" in candidate else f"//{candidate}")
    host = (parsed.hostname or candidate).lower().rstrip(".")
    return host, parsed.scheme or None, parsed.port, parsed.path or "/"


def rule_matches(rule: str, target: str) -> bool:
    rule = rule.strip()
    host, scheme, port, path = target_parts(target)

    if "://" in rule:
        parsed_rule = urlparse(rule)
        if scheme != parsed_rule.scheme.lower():
            return False
        if host != (parsed_rule.hostname or "").lower().rstrip("."):
            return False
        if port != parsed_rule.port:
            return False
        rule_path = parsed_rule.path or "/"
        return path == rule_path or path.startswith(rule_path.rstrip("/") + "/")

    try:
        network = ipaddress.ip_network(rule, strict=False)
        return ipaddress.ip_address(host) in network
    except ValueError:
        pass

    normalized = rule.lower().rstrip(".")
    if "*" in normalized or "?" in normalized:
        return fnmatch.fnmatchcase(host, normalized)
    return host == normalized


def scope_decision(manifest: dict[str, Any], target: str, action: str) -> tuple[bool, str]:
    if action not in ACTIONS:
        return False, f"unknown action: {action}"
    if action not in manifest["allowed_actions"]:
        return False, f"action {action} is not allowed by the engagement manifest"
    if any(rule_matches(rule, target) for rule in manifest["out_of_scope"]):
        return False, f"target {target} matches an out-of-scope rule"
    if not any(rule_matches(rule, target) for rule in manifest["in_scope"]):
        return False, f"target {target} does not match an in-scope rule"
    return True, f"{action} is allowed for {target}"


def table_names(connection: sqlite3.Connection) -> set[str]:
    rows = connection.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table'"
    ).fetchall()
    return {row[0] for row in rows}


def table_columns(connection: sqlite3.Connection, table: str) -> set[str]:
    return {row[1] for row in connection.execute(f"PRAGMA table_info({table})")}


def apply_schema(connection: sqlite3.Connection) -> None:
    connection.executescript((ROOT / "schema.sql").read_text(encoding="utf-8"))


def backup_database(connection: sqlite3.Connection, path: Path, version: int) -> Path:
    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%d%H%M%S")
    backup_path = path.with_name(f"{path.name}.v{version}-backup-{stamp}")
    backup_connection = sqlite3.connect(backup_path)
    try:
        connection.backup(backup_connection)
    finally:
        backup_connection.close()
    if os.name != "nt":
        backup_path.chmod(0o600)
    return backup_path


def migrate_database(path: Path, backup: bool = True) -> tuple[int, Path | None]:
    path.parent.mkdir(parents=True, exist_ok=True)
    backup_path: Path | None = None

    connection = sqlite3.connect(path)
    try:
        connection.execute("PRAGMA foreign_keys = ON")
        tables = table_names(connection)
        if "targets" not in tables:
            apply_schema(connection)
            connection.commit()
            return SCHEMA_VERSION, backup_path

        version = connection.execute("PRAGMA user_version").fetchone()[0]
        if version not in {0, 1, 2, 3, 4, 5, 6}:
            raise RuntimeError(f"unsupported database schema version: {version}")

        required_tables = {
            "schema_migrations",
            "engagements",
            "assets",
            "approvals",
            "evidence",
            "finding_relations",
            "bug_bounty_programs",
            "identities",
            "endpoints",
            "application_workflows",
            "hypotheses",
            "hunt_sessions",
            "bug_bounty_submissions",
            "policy_snapshots",
            "program_scope_rules",
            "program_restrictions",
            "burp_import_runs",
            "burp_message_refs",
            "test_plans",
            "approval_executions",
            "hypothesis_events",
        }
        scan_columns = table_columns(connection, "scans")
        plan_columns = table_columns(connection, "test_plans")
        burp_ref_columns = table_columns(connection, "burp_message_refs")
        current = version == SCHEMA_VERSION and required_tables <= tables
        if (
            current
            and {"phase", "subdomain", "engagement_id", "asset_id"} <= scan_columns
            and {"policy_snapshot_id"} <= plan_columns
            and {"source_message_ref", "request_fingerprint"} <= burp_ref_columns
        ):
            return SCHEMA_VERSION, None

        if backup:
            backup_path = backup_database(connection, path, version)

        def apply_migration(version_number: int, filename: str, name: str) -> None:
            migration = (ROOT / "migrations" / filename).read_text(encoding="utf-8")
            connection.executescript(
                "BEGIN IMMEDIATE;\n"
                + migration
                + "\nINSERT OR IGNORE INTO schema_migrations(version, name) "
                f"VALUES ({version_number}, '{name}');\n"
                + f"PRAGMA user_version = {version_number};\nCOMMIT;"
            )

        if version in {0, 1}:
            migration = (ROOT / "migrations" / "002_control_plane.sql").read_text(
                encoding="utf-8"
            )
            connection.executescript(
                "BEGIN IMMEDIATE;\n"
                "CREATE TABLE IF NOT EXISTS schema_migrations (\n"
                "  version INTEGER PRIMARY KEY,\n"
                "  name TEXT NOT NULL,\n"
                "  applied_at TEXT DEFAULT (datetime('now'))\n"
                ");\n"
                "INSERT OR IGNORE INTO schema_migrations(version, name) VALUES (1, 'initial');\n"
                + migration
                + "\nINSERT OR IGNORE INTO schema_migrations(version, name) "
                "VALUES (2, 'control_plane');\nPRAGMA user_version = 2;\nCOMMIT;"
            )
            version = 2
        if version == 2:
            apply_migration(3, "003_bug_bounty.sql", "bug_bounty_state")
            version = 3
        if version == 3:
            apply_migration(4, "004_bug_bounty_assistant.sql", "bug_bounty_assistant")
            version = 4
        if version == 4:
            apply_migration(5, "005_policy_bound_test_plans.sql", "policy_bound_test_plans")
            version = 5
        if version == 5:
            apply_migration(6, "006_burp_provenance_dedupe.sql", "burp_provenance_dedupe")
            version = 6
        if version == 6 and not required_tables <= table_names(connection):
            apply_schema(connection)
            connection.commit()
        return SCHEMA_VERSION, backup_path
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()
        if path.exists() and os.name != "nt":
            path.chmod(0o600)


class Doctor:
    def __init__(self) -> None:
        self.errors = 0
        self.warnings = 0

    def ok(self, message: str) -> None:
        print(f"[OK]   {message}")

    def warn(self, message: str) -> None:
        self.warnings += 1
        print(f"[WARN] {message}")

    def fail(self, message: str) -> None:
        self.errors += 1
        print(f"[FAIL] {message}")

    def check_commands(self) -> None:
        for name in ("opencode", "git", "python3", "node", "npx", "curl"):
            location = shutil.which(name)
            if location:
                self.ok(f"{name}: {location}")
            else:
                self.fail(f"required command not found: {name}")

        node = shutil.which("node")
        if node:
            result = subprocess.run(
                [node, "--version"], capture_output=True, text=True, check=False
            )
            match = re.search(r"v(\d+)", result.stdout)
            if match and int(match.group(1)) >= 22:
                self.ok(f"Node.js version: {result.stdout.strip()}")
            else:
                self.fail("Node.js 22 or newer is required")

        if sys.version_info >= (3, 10):  # noqa: UP036 - doctor validates direct invocation
            self.ok(f"Python version: {sys.version.split()[0]}")
        else:
            self.fail("Python 3.10 or newer is required")

    def check_paths(self) -> None:
        for relative in (
            "opencode.jsonc",
            ".opencode/agent",
            ".opencode/skills",
            "schema.sql",
            "templates",
        ):
            path = ROOT / relative
            if path.exists():
                self.ok(f"project path: {relative}")
            else:
                self.fail(f"missing project path: {relative}")

    def check_manifest(self, path: Path) -> None:
        if not path.exists():
            self.warn(
                f"engagement manifest not found: {path}; create one with "
                "./redcode engagement init --name NAME --scope TARGET"
            )
            return
        try:
            manifest = read_manifest(path)
        except ValueError as exc:
            self.fail(str(exc))
            return
        self.ok(
            f"engagement: {manifest['name']} "
            f"({manifest['workflow']}, {manifest['mode']})"
        )
        self.ok(f"in-scope rules: {len(manifest['in_scope'])}")
        if os.name != "nt" and path.stat().st_mode & 0o077:
            self.warn(f"engagement manifest is readable by other users: {path}")

    def check_database(self, path: Path) -> None:
        if not path.exists():
            self.warn(f"database not found: {path}; run ./redcode db migrate")
            return
        try:
            connection = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
            version = connection.execute("PRAGMA user_version").fetchone()[0]
            tables = table_names(connection)
            columns = table_columns(connection, "scans") if "scans" in tables else set()
            plan_columns = table_columns(connection, "test_plans") if "test_plans" in tables else set()
            burp_ref_columns = (
                table_columns(connection, "burp_message_refs")
                if "burp_message_refs" in tables
                else set()
            )
            connection.close()
        except sqlite3.Error as exc:
            self.fail(f"database check failed: {exc}")
            return

        if version == SCHEMA_VERSION:
            self.ok(f"database schema version: {version}")
        else:
            self.fail(
                f"database schema version is {version}; run ./redcode db migrate"
            )
        required_tables = {
            "engagements", "assets", "approvals", "evidence",
            "bug_bounty_programs", "identities", "endpoints",
            "application_workflows", "hypotheses", "hunt_sessions",
            "bug_bounty_submissions", "policy_snapshots",
            "program_scope_rules", "program_restrictions", "burp_import_runs",
            "burp_message_refs", "test_plans", "approval_executions",
            "hypothesis_events",
        }
        missing_tables = sorted(required_tables - tables)
        if missing_tables:
            self.fail(f"missing database tables: {', '.join(missing_tables)}")
        missing_columns = sorted({"phase", "subdomain"} - columns)
        if missing_columns:
            self.fail(f"scans table missing columns: {', '.join(missing_columns)}")
        missing_plan_columns = sorted({"policy_snapshot_id"} - plan_columns)
        if missing_plan_columns:
            self.fail(f"test_plans table missing columns: {', '.join(missing_plan_columns)}")
        missing_burp_columns = sorted({"source_message_ref", "request_fingerprint"} - burp_ref_columns)
        if missing_burp_columns:
            self.fail(
                "burp_message_refs table missing columns: " + ", ".join(missing_burp_columns)
            )
        if os.name != "nt" and path.stat().st_mode & 0o077:
            self.warn(f"database is readable by other users: {path}")

    def check_hexstrike(self, url: str) -> None:
        health_url = f"{url.rstrip('/')}/health"
        try:
            with urlopen(health_url, timeout=5) as response:
                data = json.load(response)
        except (URLError, TimeoutError, json.JSONDecodeError, OSError) as exc:
            self.fail(f"HexStrike health check failed at {health_url}: {exc}")
            return

        if data.get("status") == "healthy":
            self.ok(f"HexStrike {data.get('version', 'unknown')} is healthy")
        else:
            self.fail(f"HexStrike status: {data.get('status', 'unknown')}")

        available = data.get("total_tools_available")
        total = data.get("total_tools_count")
        if isinstance(available, int) and isinstance(total, int):
            message = f"host tools available: {available}/{total}"
            if available == total:
                self.ok(message)
            else:
                self.warn(message)

        statuses = data.get("tools_status", {})
        if isinstance(statuses, dict):
            for profile, tools in CAPABILITY_PROFILES.items():
                present = [tool for tool in tools if statuses.get(tool) is True]
                missing = [tool for tool in tools if statuses.get(tool) is not True]
                if missing:
                    self.warn(
                        f"capability {profile}: {len(present)}/{len(tools)}; "
                        f"missing {', '.join(missing)}"
                    )
                else:
                    self.ok(f"capability {profile}: {len(present)}/{len(tools)}")

    def check_arsenal(self, path: Path) -> None:
        try:
            client, workspace_id = client_from_session(path)
            manifest = client.manifest()
            actions_manifest = client.actions_manifest()
            context = client.workspace_context(
                workspace_id,
                job_limit=1,
                finding_limit=0,
                resource_limit=1,
                block_limit=1,
            )
        except ArsenalClientError as exc:
            self.fail(f"Arsenal session check failed: {exc}")
            return
        workspace = context["workspace"]
        self.ok(
            f"Arsenal {manifest.get('arsenal_version', 'unknown')} protocol "
            f"{manifest['protocol_version']} read-only + "
            f"{actions_manifest['protocol_version']} proposal-only"
        )
        self.ok(f"Arsenal workspace: {workspace['name']} ({workspace['id']})")
        if os.name != "nt" and path.stat().st_mode & 0o077:
            self.warn(f"Arsenal session is readable by other users: {path}")

    def check_mcp(self) -> None:
        opencode = shutil.which("opencode")
        if not opencode:
            return
        try:
            result = subprocess.run(
                [opencode, "mcp", "list"],
                cwd=ROOT,
                capture_output=True,
                text=True,
                timeout=45,
                check=False,
            )
        except subprocess.TimeoutExpired:
            self.fail("OpenCode MCP check timed out")
            return
        output = re.sub(r"\x1b\[[0-9;]*m", "", result.stdout + result.stderr)
        if result.returncode != 0:
            self.fail(f"OpenCode MCP check failed with exit code {result.returncode}")
            return
        lowered = output.lower()
        if "failed" in lowered or "disconnected" in lowered:
            self.fail("one or more OpenCode MCP servers are disconnected")
        else:
            self.ok("OpenCode MCP list completed without disconnected servers")

    def check_burp(self, url: str | None) -> None:
        if not url:
            self.fail("BURP_MCP_URL is not configured")
            return
        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            self.fail(f"invalid BURP_MCP_URL: {url}")
            return
        port = parsed.port or (443 if parsed.scheme == "https" else 80)
        try:
            with socket.create_connection((parsed.hostname, port), timeout=5):
                pass
        except OSError as exc:
            self.fail(f"Burp MCP is unreachable at {parsed.hostname}:{port}: {exc}")
            return
        self.ok(f"Burp MCP TCP endpoint reachable: {parsed.hostname}:{port}")
        try:
            address = ipaddress.ip_address(parsed.hostname)
        except ValueError:
            address = None
        if parsed.scheme == "http" and address is not None and not address.is_private:
            self.warn("Burp MCP uses plaintext HTTP on a non-private address")

    def summary(self) -> int:
        print()
        print(f"Doctor summary: {self.errors} error(s), {self.warnings} warning(s)")
        return 1 if self.errors else 0


def command_doctor(args: argparse.Namespace) -> int:
    doctor = Doctor()
    print("RedCode doctor")
    print()
    doctor.check_commands()
    doctor.check_paths()
    mode = args.mode or os.environ.get("REDCODE_MODE", "standalone")
    if mode == "arsenal":
        doctor.check_arsenal(arsenal_session_path(args.arsenal_session))
    else:
        doctor.check_manifest(manifest_path(args.manifest))
        doctor.check_database(database_path(args.db))
        doctor.check_hexstrike(
            os.environ.get("HEXSTRIKE_URL", "http://127.0.0.1:8888")
        )
        doctor.check_burp(os.environ.get("BURP_MCP_URL"))
    if not args.skip_mcp:
        doctor.check_mcp()
    return doctor.summary()


def command_db_migrate(args: argparse.Namespace) -> int:
    path = database_path(args.db)
    try:
        version, backup = migrate_database(path, backup=not args.no_backup)
    except (OSError, sqlite3.Error, RuntimeError) as exc:
        print(f"Database migration failed: {exc}", file=sys.stderr)
        return 1
    print(f"Database ready at schema version {version}: {path}")
    if backup:
        print(f"Backup created: {backup}")
    return 0


def command_engagement_init(args: argparse.Namespace) -> int:
    path = manifest_path(args.file)
    if path.exists() and not args.force:
        print(f"Manifest already exists: {path}; use --force to replace it", file=sys.stderr)
        return 1
    actions = args.allow or (["ctf"] if args.workflow == "ctf" else ASSESSMENT_ACTIONS)
    data = {
        "schema_version": MANIFEST_VERSION,
        "name": args.name,
        "workflow": args.workflow,
        "mode": args.mode,
        "in_scope": args.scope,
        "out_of_scope": args.out_of_scope or [],
        "allowed_actions": actions,
        "rate_limit_per_second": args.rate_limit,
        "notes": args.notes or "",
    }
    errors = validate_manifest(data)
    if errors:
        for error in errors:
            print(f"Manifest error: {error}", file=sys.stderr)
        return 1
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    if os.name != "nt":
        path.chmod(0o600)
    print(f"Engagement manifest created: {path}")
    activate_manifest(path, data, quiet=True)

    db = database_path(args.db)
    if db.exists():
        try:
            connection = sqlite3.connect(db)
            connection.execute(
                "INSERT INTO engagements "
                "(engagement_key, name, workflow, mode, manifest_path) "
                "VALUES (?, ?, ?, ?, ?) "
                "ON CONFLICT(engagement_key) DO UPDATE SET "
                "name=excluded.name, workflow=excluded.workflow, "
                "mode=excluded.mode, manifest_path=excluded.manifest_path, "
                "updated_at=datetime('now')",
                (args.name, args.name, args.workflow, args.mode, str(path)),
            )
            connection.commit()
            connection.close()
            print(f"Engagement registered in: {db}")
        except sqlite3.Error as exc:
            print(f"Warning: engagement was not registered in SQLite: {exc}")
    return 0


def activate_manifest(path: Path, data: dict[str, Any], quiet: bool = False) -> Path:
    context_path = ROOT / "output" / ".redcode" / "current-engagement.json"
    context_path.parent.mkdir(parents=True, exist_ok=True)
    context = dict(data)
    context["manifest_path"] = str(path)
    context["activated_at"] = dt.datetime.now(dt.timezone.utc).isoformat()
    context_path.write_text(json.dumps(context, indent=2) + "\n", encoding="utf-8")
    if os.name != "nt":
        context_path.chmod(0o600)
    if not quiet:
        print(f"Engagement activated for OpenCode: {context_path}")
    return context_path


def command_engagement_validate(args: argparse.Namespace) -> int:
    path = manifest_path(args.file)
    try:
        data = read_manifest(path)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print(
        f"Valid engagement: {data['name']} "
        f"({data['workflow']}, {data['mode']}, {len(data['in_scope'])} scope rule(s))"
    )
    return 0


def command_engagement_activate(args: argparse.Namespace) -> int:
    path = manifest_path(args.file)
    try:
        data = read_manifest(path)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    activate_manifest(path, data, quiet=args.quiet)
    return 0


def command_scope_check(args: argparse.Namespace) -> int:
    try:
        data = read_manifest(manifest_path(args.file))
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    allowed, reason = scope_decision(data, args.target, args.action)
    print(("ALLOW: " if allowed else "DENY: ") + reason)
    return 0 if allowed else 1


def select_arsenal_workspace(
    client: ArsenalClient, requested_id: str | None
) -> str:
    if requested_id:
        return requested_id
    response = client.list_workspaces()
    items = response.get("items")
    if not isinstance(items, list) or not items:
        raise ArsenalClientError("Arsenal has no available workspaces")
    valid_items = [
        item
        for item in items
        if isinstance(item, dict)
        and isinstance(item.get("id"), str)
        and isinstance(item.get("name"), str)
    ]
    if not valid_items:
        raise ArsenalClientError("Arsenal returned no valid workspace entries")
    if len(valid_items) == 1:
        return valid_items[0]["id"]
    if not sys.stdin.isatty():
        choices = ", ".join(
            f"{item['name']} ({item['id']})" for item in valid_items
        )
        raise ArsenalClientError(
            f"multiple Arsenal workspaces are available; use --workspace: {choices}"
        )
    print("Available Arsenal workspaces:")
    for index, item in enumerate(valid_items, start=1):
        print(f"  {index}. {item['name']} ({item['id']})")
    raw_choice = input("Select workspace: ").strip()
    try:
        choice = int(raw_choice)
    except ValueError as exc:
        raise ArsenalClientError("workspace selection must be a number") from exc
    if choice < 1 or choice > len(valid_items):
        raise ArsenalClientError("workspace selection is out of range")
    return valid_items[choice - 1]["id"]


def command_arsenal_connect(args: argparse.Namespace) -> int:
    try:
        client = ArsenalClient(args.url, token_file=args.token_file)
        client.manifest()
        workspace_id = select_arsenal_workspace(client, args.workspace)
        session = create_session(
            client, workspace_id, arsenal_session_path(args.session)
        )
        activate_runtime_mode("arsenal", quiet=True)
    except ArsenalClientError as exc:
        print(f"Arsenal connection failed: {exc}", file=sys.stderr)
        return 1
    if not args.quiet:
        workspace = session["workspace"]
        print(
            f"Arsenal session ready: {workspace['name']} ({workspace['id']}) "
            f"using protocol {session['protocol_version']}"
        )
    return 0


def command_arsenal_status(args: argparse.Namespace) -> int:
    path = arsenal_session_path(args.session)
    try:
        client, workspace_id = client_from_session(path)
        manifest = client.manifest()
        actions_manifest = client.actions_manifest()
        context = client.workspace_context(
            workspace_id,
            job_limit=1,
            finding_limit=0,
            resource_limit=1,
            block_limit=1,
        )
    except ArsenalClientError as exc:
        print(f"Arsenal session unavailable: {exc}", file=sys.stderr)
        return 1
    workspace = context["workspace"]
    print(
        f"Arsenal {manifest.get('arsenal_version', 'unknown')} reachable; "
        f"workspace {workspace['name']} ({workspace['id']}); "
        f"protocol {manifest['protocol_version']} read-only + "
        f"{actions_manifest['protocol_version']} proposal-only"
    )
    return 0


def command_arsenal_opencode_config(_args: argparse.Namespace) -> int:
    try:
        config = arsenal_opencode_override(os.environ.get("OPENCODE_CONFIG_CONTENT"))
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print(json.dumps(config, separators=(",", ":")))
    return 0


def command_runtime_activate(args: argparse.Namespace) -> int:
    activate_runtime_mode(args.mode, quiet=args.quiet)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="redcode", description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    doctor = subparsers.add_parser("doctor", help="check local runtime readiness")
    doctor.add_argument("--db")
    doctor.add_argument("--manifest")
    doctor.add_argument("--skip-mcp", action="store_true")
    doctor.add_argument("--mode", choices=("standalone", "arsenal"))
    doctor.add_argument("--arsenal-session")
    doctor.set_defaults(func=command_doctor)

    db = subparsers.add_parser("db", help="manage the RedCode database")
    db_subparsers = db.add_subparsers(dest="db_command", required=True)
    migrate = db_subparsers.add_parser("migrate", help="upgrade the database schema")
    migrate.add_argument("--db")
    migrate.add_argument("--no-backup", action="store_true")
    migrate.set_defaults(func=command_db_migrate)

    engagement = subparsers.add_parser("engagement", help="manage engagement manifests")
    engagement_subparsers = engagement.add_subparsers(
        dest="engagement_command", required=True
    )
    init = engagement_subparsers.add_parser("init", help="create an engagement manifest")
    init.add_argument("--name", required=True)
    init.add_argument("--workflow", choices=("assessment", "ctf"), default="assessment")
    init.add_argument("--mode", choices=("normal", "aggressive"), default="normal")
    init.add_argument("--scope", action="append", required=True)
    init.add_argument("--out-of-scope", action="append")
    init.add_argument("--allow", action="append", choices=sorted(ACTIONS))
    init.add_argument("--rate-limit", type=int, default=10)
    init.add_argument("--notes")
    init.add_argument("--file")
    init.add_argument("--db")
    init.add_argument("--force", action="store_true")
    init.set_defaults(func=command_engagement_init)

    validate = engagement_subparsers.add_parser(
        "validate", help="validate an engagement manifest"
    )
    validate.add_argument("--file")
    validate.set_defaults(func=command_engagement_validate)

    activate = engagement_subparsers.add_parser(
        "activate", help="validate and expose the manifest to OpenCode"
    )
    activate.add_argument("--file")
    activate.add_argument("--quiet", action="store_true")
    activate.set_defaults(func=command_engagement_activate)

    scope = subparsers.add_parser("scope", help="check target and action against a manifest")
    scope_subparsers = scope.add_subparsers(dest="scope_command", required=True)
    check = scope_subparsers.add_parser("check", help="return ALLOW or DENY")
    check.add_argument("target")
    check.add_argument("action", choices=sorted(ACTIONS))
    check.add_argument("--file")
    check.set_defaults(func=command_scope_check)

    arsenal = subparsers.add_parser(
        "arsenal", help="manage a mediated Arsenal workspace session"
    )
    arsenal_subparsers = arsenal.add_subparsers(
        dest="arsenal_command", required=True
    )
    connect = arsenal_subparsers.add_parser(
        "connect", help="negotiate protocol 1.0 and bind a workspace"
    )
    connect.add_argument(
        "--url", default=os.environ.get("ARSENAL_URL", "http://127.0.0.1:8000")
    )
    connect.add_argument("--workspace")
    connect.add_argument("--session")
    connect.add_argument(
        "--token-file",
        default=os.environ.get("ARSENAL_AGENT_TOKEN_FILE"),
        help="path to Arsenal's local agent token (auto-discovered by default)",
    )
    connect.add_argument("--quiet", action="store_true")
    connect.set_defaults(func=command_arsenal_connect)

    status = arsenal_subparsers.add_parser(
        "status", help="verify the bound workspace and protocol"
    )
    status.add_argument("--session")
    status.set_defaults(func=command_arsenal_status)

    runtime_config = arsenal_subparsers.add_parser(
        "opencode-config", help=argparse.SUPPRESS
    )
    runtime_config.set_defaults(func=command_arsenal_opencode_config)

    runtime = subparsers.add_parser("runtime", help=argparse.SUPPRESS)
    runtime_subparsers = runtime.add_subparsers(
        dest="runtime_command", required=True
    )
    runtime_activate = runtime_subparsers.add_parser(
        "activate", help=argparse.SUPPRESS
    )
    runtime_activate.add_argument("--mode", choices=("standalone", "arsenal"), required=True)
    runtime_activate.add_argument("--quiet", action="store_true")
    runtime_activate.set_defaults(func=command_runtime_activate)
    return parser


def main(argv: list[str] | None = None) -> int:
    load_dotenv(ROOT / ".env")
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
