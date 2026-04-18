"""duplicate_file_finder.py

Find duplicate files anywhere on disk by comparing content hashes.

Two-stage algorithm for speed:
  1. Group files by size (stat only - no reads).
  2. For each multi-file size group, hash the contents and group by hash.

Only groups of size > 1 are reported. This avoids hashing singletons,
which is what makes the tool fast on large trees.

Usage:
    python duplicate_file_finder.py <root> [--min-size BYTES] [--json]

Examples:
    python duplicate_file_finder.py ~/Downloads
    python duplicate_file_finder.py /data --min-size 1048576 --json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from collections import defaultdict
from pathlib import Path
from typing import Dict, Iterable, List


CHUNK_SIZE = 1024 * 1024  # 1 MiB read chunks


def iter_files(root: Path, min_size: int) -> Iterable[Path]:
    """Yield regular files under root, skipping symlinks and small files."""
    for dirpath, _dirnames, filenames in os.walk(root, followlinks=False):
        for name in filenames:
            p = Path(dirpath) / name
            try:
                if p.is_symlink():
                    continue
                if p.stat().st_size < min_size:
                    continue
            except OSError:
                continue
            yield p


def group_by_size(paths: Iterable[Path]) -> Dict[int, List[Path]]:
    groups: Dict[int, List[Path]] = defaultdict(list)
    for p in paths:
        try:
            groups[p.stat().st_size].append(p)
        except OSError:
            continue
    return groups


def hash_file(path: Path) -> str:
    """Return sha256 hex digest of the file's contents."""
    h = hashlib.sha256()
    with path.open("rb") as f:
        while True:
            chunk = f.read(CHUNK_SIZE)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def find_duplicates(root: Path, min_size: int = 1) -> Dict[str, List[Path]]:
    """Return a dict mapping content hash -> list of duplicate paths.

    Only entries with 2+ paths are included.
    """
    by_size = group_by_size(iter_files(root, min_size))

    dupes: Dict[str, List[Path]] = {}
    for _size, paths in by_size.items():
        if len(paths) < 2:
            continue
        by_hash: Dict[str, List[Path]] = defaultdict(list)
        for p in paths:
            try:
                by_hash[hash_file(p)].append(p)
            except OSError as exc:
                print(f"warn: skipping {p}: {exc}", file=sys.stderr)
        for digest, members in by_hash.items():
            if len(members) >= 2:
                dupes[digest] = sorted(members)
    return dupes


def human_bytes(n: float) -> str:
    step = 1024.0
    for unit in ("B", "KiB", "MiB", "GiB", "TiB"):
        if n < step:
            return f"{n:.1f} {unit}" if unit != "B" else f"{int(n)} {unit}"
        n /= step
    return f"{n:.1f} PiB"


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Find duplicate files by content hash.")
    parser.add_argument("root", type=Path, help="Directory to scan")
    parser.add_argument("--min-size", type=int, default=1, help="Skip files smaller than this (bytes)")
    parser.add_argument("--json", action="store_true", help="Emit JSON instead of text")
    args = parser.parse_args(argv)

    if not args.root.is_dir():
        parser.error(f"{args.root} is not a directory")

    dupes = find_duplicates(args.root, min_size=args.min_size)

    if args.json:
        payload = {d: [str(p) for p in paths] for d, paths in dupes.items()}
        json.dump(payload, sys.stdout, indent=2)
        sys.stdout.write("\n")
        return 0

    if not dupes:
        print("No duplicates found.")
        return 0

    wasted = 0
    for digest, paths in dupes.items():
        size = paths[0].stat().st_size
        wasted += size * (len(paths) - 1)
        print(f"\n{digest[:12]}  {human_bytes(size)}  x{len(paths)}")
        for p in paths:
            print(f"    {p}")

    total_files = sum(len(v) for v in dupes.values())
    print(f"\nTotal wasted space: {human_bytes(wasted)} across {total_files} files.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
