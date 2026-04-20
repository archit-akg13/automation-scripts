"""directory_diff.py — Compare two directory trees by content hash and report drift.

Walks a SOURCE and a TARGET directory recursively, hashes every regular file,
and reports four categories of differences:

    added    — present in TARGET, missing in SOURCE
    removed  — present in SOURCE, missing in TARGET
    modified — present in both but with different content hashes
    moved    — same content hash but different relative path

Designed for stdlib-only use. Useful for backup verification, deploy auditing,
and detecting silent file corruption between mirrored trees.

Usage:
    python directory_diff.py SOURCE TARGET
    python directory_diff.py SOURCE TARGET --json
    python directory_diff.py SOURCE TARGET --algorithm sha256 --ignore '*.pyc' '__pycache__'

Exit codes:
    0 — directories are identical
    1 — drift found (any added/removed/modified/moved entries)
    2 — usage / setup error (missing path, unreadable file, etc.)
"""

from __future__ import annotations

import argparse
import fnmatch
import hashlib
import json
import os
import sys
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Iterable


CHUNK_SIZE = 1024 * 1024  # 1 MiB streaming reads


@dataclass
class DiffReport:
    source: str
    target: str
    algorithm: str
    added: list[str] = field(default_factory=list)
    removed: list[str] = field(default_factory=list)
    modified: list[str] = field(default_factory=list)
    moved: list[dict] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    @property
    def is_clean(self) -> bool:
        return not (self.added or self.removed or self.modified or self.moved)


def hash_file(path: Path, algorithm: str) -> str:
    """Stream-hash a single file and return its hex digest."""
    h = hashlib.new(algorithm)
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(CHUNK_SIZE), b""):
            h.update(chunk)
    return h.hexdigest()


def should_ignore(rel: str, patterns: Iterable[str]) -> bool:
    """Return True if any path segment matches any glob pattern."""
    parts = rel.split(os.sep)
    for pattern in patterns:
        if fnmatch.fnmatch(rel, pattern):
            return True
        if any(fnmatch.fnmatch(p, pattern) for p in parts):
            return True
    return False


def index_tree(root: Path, algorithm: str, ignore: list[str], errors: list[str]) -> dict[str, str]:
    """Return {relative_path: content_hash} for every regular file under root."""
    if not root.exists():
        raise FileNotFoundError(f"path does not exist: {root}")
    if not root.is_dir():
        raise NotADirectoryError(f"path is not a directory: {root}")

    index: dict[str, str] = {}
    for dirpath, dirnames, filenames in os.walk(root):
        # Prune ignored directories in place so os.walk skips them entirely.
        rel_dir = os.path.relpath(dirpath, root)
        dirnames[:] = [
            d for d in dirnames
            if not should_ignore(os.path.join(rel_dir, d) if rel_dir != "." else d, ignore)
        ]
        for name in filenames:
            full = Path(dirpath) / name
            rel = os.path.relpath(full, root)
            if should_ignore(rel, ignore):
                continue
            try:
                index[rel] = hash_file(full, algorithm)
            except (OSError, PermissionError) as exc:
                errors.append(f"{rel}: {exc}")
    return index


def compute_diff(src_index: dict[str, str], tgt_index: dict[str, str]) -> tuple[list[str], list[str], list[str], list[dict]]:
    """Compare two indexes and bucket the differences."""
    src_paths = set(src_index)
    tgt_paths = set(tgt_index)

    added = sorted(tgt_paths - src_paths)
    removed = sorted(src_paths - tgt_paths)

    modified: list[str] = []
    for path in sorted(src_paths & tgt_paths):
        if src_index[path] != tgt_index[path]:
            modified.append(path)

    # Detect moves: a file is "moved" when its hash exists only in removed (source)
    # AND only in added (target), at a different path. Promote those out of
    # added/removed into a dedicated moved bucket.
    src_only_by_hash: dict[str, list[str]] = {}
    for p in removed:
        src_only_by_hash.setdefault(src_index[p], []).append(p)

    tgt_only_by_hash: dict[str, list[str]] = {}
    for p in added:
        tgt_only_by_hash.setdefault(tgt_index[p], []).append(p)

    moved: list[dict] = []
    for digest, src_paths_for_hash in list(src_only_by_hash.items()):
        tgt_paths_for_hash = tgt_only_by_hash.get(digest, [])
        # Pair them up greedily — N to N when counts match, otherwise pair what we can.
        pair_count = min(len(src_paths_for_hash), len(tgt_paths_for_hash))
        for i in range(pair_count):
            moved.append({
                "from": src_paths_for_hash[i],
                "to": tgt_paths_for_hash[i],
                "hash": digest,
            })
        # Remove paired entries from added/removed
        for i in range(pair_count):
            removed.remove(src_paths_for_hash[i])
            added.remove(tgt_paths_for_hash[i])

    return added, removed, modified, moved


def render_text(report: DiffReport) -> str:
    lines: list[str] = []
    lines.append(f"Comparing {report.source} -> {report.target} ({report.algorithm})")
    lines.append("")

    if report.is_clean and not report.errors:
        lines.append("OK: directories are identical.")
        return "
".join(lines)

    if report.added:
        lines.append(f"Added ({len(report.added)}):")
        lines.extend(f"  + {p}" for p in report.added)
        lines.append("")
    if report.removed:
        lines.append(f"Removed ({len(report.removed)}):")
        lines.extend(f"  - {p}" for p in report.removed)
        lines.append("")
    if report.modified:
        lines.append(f"Modified ({len(report.modified)}):")
        lines.extend(f"  ~ {p}" for p in report.modified)
        lines.append("")
    if report.moved:
        lines.append(f"Moved ({len(report.moved)}):")
        lines.extend(f"  > {m['from']} -> {m['to']}" for m in report.moved)
        lines.append("")
    if report.errors:
        lines.append(f"Errors ({len(report.errors)}):")
        lines.extend(f"  ! {e}" for e in report.errors)
        lines.append("")

    return "
".join(lines).rstrip() + "
"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="directory_diff",
        description="Compare two directory trees by content hash and report drift.",
    )
    parser.add_argument("source", help="reference directory")
    parser.add_argument("target", help="directory to compare against the reference")
    parser.add_argument(
        "--algorithm",
        default="sha256",
        choices=sorted(hashlib.algorithms_guaranteed),
        help="hash algorithm to use (default: sha256)",
    )
    parser.add_argument(
        "--ignore",
        nargs="*",
        default=[".git", "__pycache__", "*.pyc", ".DS_Store"],
        help="glob patterns to skip (matched against full path or any segment)",
    )
    parser.add_argument(
        "--json",
        dest="as_json",
        action="store_true",
        help="emit a JSON report instead of a human-readable summary",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    src = Path(args.source).resolve()
    tgt = Path(args.target).resolve()

    errors: list[str] = []
    try:
        src_index = index_tree(src, args.algorithm, args.ignore, errors)
        tgt_index = index_tree(tgt, args.algorithm, args.ignore, errors)
    except (FileNotFoundError, NotADirectoryError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    added, removed, modified, moved = compute_diff(src_index, tgt_index)
    report = DiffReport(
        source=str(src),
        target=str(tgt),
        algorithm=args.algorithm,
        added=added,
        removed=removed,
        modified=modified,
        moved=moved,
        errors=errors,
    )

    if args.as_json:
        print(json.dumps(asdict(report), indent=2))
    else:
        print(render_text(report), end="")

    return 0 if report.is_clean else 1


if __name__ == "__main__":
    sys.exit(main())

