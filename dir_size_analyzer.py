#!/usr/bin/env python3
"""
dir_size_analyzer.py — Identify the biggest space consumers in a directory tree.

Walks a directory recursively, aggregates total size per subdirectory and per file
extension, then prints the top N offenders. Useful for quickly answering "where
did all my disk space go?" without installing ncdu/baobab.

Examples:
    python dir_size_analyzer.py ~/Downloads
    python dir_size_analyzer.py /var/log --top 20 --by ext
    python dir_size_analyzer.py . --min-mb 100 --json

The script uses os.scandir for speed, handles permission errors gracefully, and
follows-symlinks=False by default so cycles cannot blow up the walk.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections import defaultdict
from pathlib import Path


def human(n):
    """Convert a byte count to a short human-readable string."""
    units = ["B", "KB", "MB", "GB", "TB", "PB"]
    size = float(n)
    for unit in units:
        if size < 1024 or unit == units[-1]:
            return f"{size:7.2f} {unit}"
        size /= 1024
    return f"{size:7.2f} {units[-1]}"


def walk_sizes(root, follow_symlinks=False):
    """Yield (path, size, is_dir) for every entry under root.

    Errors (permission denied, broken symlinks, races) are swallowed but
    counted, so a single unreadable file does not abort the walk.
    """
    errors = 0
    stack = [root]
    while stack:
        current = stack.pop()
        try:
            entries = list(os.scandir(current))
        except (PermissionError, FileNotFoundError, OSError):
            errors += 1
            continue
        for entry in entries:
            try:
                if entry.is_dir(follow_symlinks=follow_symlinks):
                    stack.append(Path(entry.path))
                elif entry.is_file(follow_symlinks=follow_symlinks):
                    yield Path(entry.path), entry.stat(follow_symlinks=False).st_size, False
            except (PermissionError, FileNotFoundError, OSError):
                errors += 1
                continue
    if errors:
        print(f"[warn] skipped {errors} entries due to errors", file=sys.stderr)


def aggregate(root, follow_symlinks):
    """Return (per_dir, per_ext, total_bytes, total_files)."""
    per_dir = defaultdict(int)
    per_ext = defaultdict(int)
    total_bytes = 0
    total_files = 0
    root = root.resolve()

    for path, size, _ in walk_sizes(root, follow_symlinks):
        total_bytes += size
        total_files += 1
        ext = path.suffix.lower() or "(no-ext)"
        per_ext[ext] += size
        cursor = path.parent
        while True:
            per_dir[cursor] += size
            if cursor == root or cursor.parent == cursor:
                break
            cursor = cursor.parent

    return per_dir, per_ext, total_bytes, total_files


def render_table(rows, headers):
    widths = [max(len(str(r[i])) for r in rows + [headers]) for i in range(len(headers))]
    line = "  ".join(h.ljust(widths[i]) for i, h in enumerate(headers))
    print(line)
    print("  ".join("-" * w for w in widths))
    for r in rows:
        print("  ".join(str(c).ljust(widths[i]) for i, c in enumerate(r)))


def main(argv=None):
    parser = argparse.ArgumentParser(description="Find the biggest items in a directory tree.")
    parser.add_argument("path", nargs="?", default=".", help="Root directory to analyze (default: cwd).")
    parser.add_argument("--top", type=int, default=15, help="How many entries to show (default: 15).")
    parser.add_argument("--by", choices=("dir", "ext", "both"), default="both", help="Group results by directory, extension, or both.")
    parser.add_argument("--min-mb", type=float, default=0.0, help="Hide entries below this size in MB.")
    parser.add_argument("--follow-symlinks", action="store_true", help="Follow symlinks (default: off).")
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON instead of a table.")
    args = parser.parse_args(argv)

    root = Path(args.path).expanduser()
    if not root.exists() or not root.is_dir():
        print(f"error: not a directory: {root}", file=sys.stderr)
        return 2

    per_dir, per_ext, total_bytes, total_files = aggregate(root, args.follow_symlinks)
    threshold = int(args.min_mb * 1024 * 1024)

    top_dirs = sorted(
        ((p, s) for p, s in per_dir.items() if s >= threshold),
        key=lambda kv: kv[1], reverse=True,
    )[: args.top]

    top_exts = sorted(
        ((e, s) for e, s in per_ext.items() if s >= threshold),
        key=lambda kv: kv[1], reverse=True,
    )[: args.top]

    if args.json:
        print(json.dumps({
            "root": str(root.resolve()),
            "total_bytes": total_bytes,
            "total_files": total_files,
            "top_directories": [{"path": str(p), "bytes": s} for p, s in top_dirs],
            "top_extensions": [{"ext": e, "bytes": s} for e, s in top_exts],
        }, indent=2))
        return 0

    print(f"Scanned {total_files:,} files, {human(total_bytes)} under {root.resolve()}")
    if args.by in ("dir", "both"):
        print("")
        print("Top directories")
        render_table([(human(s), str(p)) for p, s in top_dirs], ["size", "path"])
    if args.by in ("ext", "both"):
        print("")
        print("Top extensions")
        render_table([(human(s), e) for e, s in top_exts], ["size", "ext"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
