#!/usr/bin/env python3
"""Create a portfolio-safe copy of RedCode JSON evidence."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
from typing import Any


SECRET_KEYS = {
    "apikey",
    "api_key",
    "authorization",
    "cookie",
    "password",
    "passwordrepeat",
    "secret",
    "set-cookie",
    "token",
}
EMAIL_KEYS = {"email"}
JWT_PATTERN = re.compile(r"\beyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\b")


def redact(value: Any, key: str = "") -> Any:
    normalized = key.lower()
    if normalized in SECRET_KEYS or normalized.endswith("token"):
        return "<redacted>"
    if normalized in EMAIL_KEYS:
        return "<redacted-email>"
    if isinstance(value, dict):
        return {item_key: redact(item, item_key) for item_key, item in value.items()}
    if isinstance(value, list):
        return [redact(item) for item in value]
    if isinstance(value, str):
        return JWT_PATTERN.sub("<redacted-jwt>", value)
    return value


def redact_directory(source: Path, destination: Path) -> int:
    destination.mkdir(parents=True, exist_ok=True)
    count = 0
    for source_file in sorted(source.glob("*.json")):
        data = json.loads(source_file.read_text(encoding="utf-8"))
        output_file = destination / source_file.name
        output_file.write_text(
            json.dumps(redact(data), indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        count += 1
    return count


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("destination", type=Path)
    args = parser.parse_args()

    if not args.source.is_dir():
        parser.error(f"source directory does not exist: {args.source}")
    count = redact_directory(args.source, args.destination)
    if count == 0:
        parser.error("source directory contains no JSON evidence")
    print(f"redacted {count} evidence files into {args.destination}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
