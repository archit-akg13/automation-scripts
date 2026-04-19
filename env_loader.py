"""env_loader.py — Robust .env file loader with type conversion.

A dependency-free replacement for python-dotenv that supports:
  * Quoted values (single and double)
  * Inline comments
  * Variable interpolation (${VAR} and $VAR)
  * Type coercion helpers (get_int, get_bool, get_list, get_float)
  * Required-variable enforcement
  * Multiple .env files with override semantics

Example:
    from env_loader import load_env, get_int, get_bool, require

    load_env(".env", ".env.local")          # later files override earlier ones
    api_key = require("API_KEY")             # raises if missing
    port = get_int("PORT", default=8080)
    debug = get_bool("DEBUG", default=False)
    hosts = get_list("ALLOWED_HOSTS")        # comma-separated

Author: Archit Mittal
License: MIT
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Iterable, List, Optional

__all__ = [
    "load_env",
    "require",
    "get_int",
    "get_float",
    "get_bool",
    "get_list",
    "EnvError",
]


class EnvError(Exception):
    """Raised for missing required variables or malformed .env files."""


# Matches: KEY=VALUE, KEY="VALUE", KEY='VALUE', with optional export prefix.
_LINE_RE = re.compile(
    r"""^\s*(?:export\s+)?           # optional 'export '
        ([A-Za-z_][A-Za-z0-9_]*)     # key
        \s*=\s*
        (.*?)                         # raw value
        \s*$""",
    re.VERBOSE,
)

_INTERP_RE = re.compile(r"\$\{?([A-Za-z_][A-Za-z0-9_]*)\}?")

_TRUE_VALUES = {"1", "true", "yes", "on", "y", "t"}
_FALSE_VALUES = {"0", "false", "no", "off", "n", "f", ""}


def _strip_quotes(value: str):
    """Return (unquoted_value, was_quoted). Quoted values skip interpolation if single-quoted."""
    if len(value) >= 2:
        if value[0] == value[-1] == '"':
            return value[1:-1], False  # double-quoted: still interpolate
        if value[0] == value[-1] == "'":
            return value[1:-1], True   # single-quoted: literal
    return value, False


def _strip_inline_comment(value: str) -> str:
    """Remove trailing '# comment' unless inside quotes."""
    in_single = in_double = False
    for i, ch in enumerate(value):
        if ch == "'" and not in_double:
            in_single = not in_single
        elif ch == '"' and not in_single:
            in_double = not in_double
        elif ch == "#" and not in_single and not in_double:
            return value[:i].rstrip()
    return value


def _interpolate(value: str, env: dict) -> str:
    """Expand ${VAR} and $VAR references using env + os.environ."""
    def replace(match):
        key = match.group(1)
        return env.get(key, os.environ.get(key, ""))
    return _INTERP_RE.sub(replace, value)


def parse_env_file(path) -> dict:
    """Parse a .env file into a dict. Does not mutate os.environ."""
    result: dict = {}
    p = Path(path)
    if not p.is_file():
        raise EnvError(f".env file not found: {p}")

    for lineno, raw in enumerate(p.read_text(encoding="utf-8").splitlines(), start=1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue

        match = _LINE_RE.match(line)
        if not match:
            raise EnvError(f"{p}:{lineno}: malformed line: {raw!r}")

        key, raw_value = match.group(1), match.group(2)
        raw_value = _strip_inline_comment(raw_value)
        value, literal = _strip_quotes(raw_value)
        if not literal:
            value = _interpolate(value, result)
        result[key] = value

    return result


def load_env(*paths, override: bool = False) -> dict:
    """Load one or more .env files into os.environ. Later files override earlier ones."""
    merged: dict = {}
    for path in paths:
        if not Path(path).is_file():
            continue
        merged.update(parse_env_file(path))

    for key, value in merged.items():
        if override or key not in os.environ:
            os.environ[key] = value
    return merged


def require(name: str) -> str:
    """Return os.environ[name] or raise EnvError if missing/empty."""
    value = os.environ.get(name)
    if not value:
        raise EnvError(f"Required environment variable not set: {name}")
    return value


def get_int(name: str, default=None):
    """Return env var as int, or default if missing/unparseable."""
    raw = os.environ.get(name)
    if raw is None or raw == "":
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def get_float(name: str, default=None):
    """Return env var as float, or default if missing/unparseable."""
    raw = os.environ.get(name)
    if raw is None or raw == "":
        return default
    try:
        return float(raw)
    except ValueError:
        return default


def get_bool(name: str, default: bool = False) -> bool:
    """Return env var as bool. Truthy: 1/true/yes/on/y/t (case-insensitive)."""
    raw = os.environ.get(name)
    if raw is None:
        return default
    normalized = raw.strip().lower()
    if normalized in _TRUE_VALUES:
        return True
    if normalized in _FALSE_VALUES:
        return False
    return default


def get_list(name: str, separator: str = ",", default=None):
    """Return env var split on separator with whitespace stripped. Empty items dropped."""
    raw = os.environ.get(name)
    if raw is None or raw == "":
        return list(default) if default is not None else []
    return [item.strip() for item in raw.split(separator) if item.strip()]


if __name__ == "__main__":
    import argparse
    import sys

    parser = argparse.ArgumentParser(description="Inspect parsed .env files.")
    parser.add_argument("files", nargs="+", help="Path(s) to .env file(s)")
    parser.add_argument("--export", action="store_true", help="Print as 'export KEY=VALUE' lines")
    args = parser.parse_args()

    try:
        merged = load_env(*args.files)
    except EnvError as exc:
        print(f"error: {exc}", file=sys.stderr)
        sys.exit(1)

    for key, value in sorted(merged.items()):
        prefix = "export " if args.export else ""
        print(f"{prefix}{key}={value}")
