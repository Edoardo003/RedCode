#!/usr/bin/env python3
"""Start HexStrike with a mandatory proxychains command prefix.

The upstream HexStrike server is downloaded as local state, so RedCode keeps
the enforcement point here instead of patching that checkout.  The runner
patches ``subprocess.Popen`` before executing the server module; Python's
``subprocess.run`` and related helpers use the same constructor internally.
"""

from __future__ import annotations

import os
from pathlib import Path
import runpy
import shlex
import shutil
import subprocess
import sys
from typing import Sequence


DEFAULT_PREFIX = "proxychains4 -q"


def command_prefix() -> list[str]:
    """Return the required prefix and fail closed when it is unavailable."""
    value = os.environ.get("REDCODE_COMMAND_PREFIX", DEFAULT_PREFIX).strip()
    prefix = shlex.split(value)
    if not prefix:
        raise RuntimeError("REDCODE_COMMAND_PREFIX must not be empty")
    if shutil.which(prefix[0]) is None:
        raise RuntimeError(
            f"required command prefix is unavailable: {prefix[0]}; "
            "install proxychains4 or set REDCODE_COMMAND_PREFIX"
        )
    return prefix


def prefix_command(
    command: str | Sequence[str], prefix: Sequence[str], *, shell: bool
) -> str | list[str]:
    """Add *prefix* once while preserving subprocess' string/list semantics."""
    if isinstance(command, str):
        if command.lstrip().startswith(f"{prefix[0]} ") or command.lstrip() == prefix[0]:
            return command
        return f"{shlex.join(prefix)} {command}"

    result = list(command)
    if result[: len(prefix)] == list(prefix):
        return result
    return [*prefix, *result]


def install_subprocess_prefix() -> None:
    """Install the prefix once for every command spawned by this process."""
    prefix = command_prefix()
    original_popen = subprocess.Popen

    class ProxychainsPopen(original_popen):
        def __init__(self, args, *args_, **kwargs):
            prefixed = prefix_command(
                args, prefix, shell=bool(kwargs.get("shell", False))
            )
            super().__init__(prefixed, *args_, **kwargs)

    subprocess.Popen = ProxychainsPopen


def main() -> int:
    if len(sys.argv) < 2:
        print(
            "usage: hexstrike_proxychains_runner.py <hexstrike_server.py> [args...]",
            file=sys.stderr,
        )
        return 2

    server = Path(sys.argv[1]).resolve()
    if not server.is_file():
        print(f"HexStrike server not found: {server}", file=sys.stderr)
        return 2

    try:
        install_subprocess_prefix()
    except RuntimeError as error:
        print(f"RedCode proxychains enforcement error: {error}", file=sys.stderr)
        return 1

    sys.argv = [str(server), *sys.argv[2:]]
    runpy.run_path(str(server), run_name="__main__")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
