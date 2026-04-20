backup_manager.py"""
backup_manager.py
-----------------
Lightweight, dependency-free backup utility for files and directories.

Features:
  * Timestamped tar.gz archives
  * Configurable retention (keep N most recent)
  * Optional include/exclude glob patterns
  * Dry-run mode for safe previews
  * Single-file CLI usable from cron / launchd

Usage:
    python backup_manager.py /path/to/source /path/to/backups
    python backup_manager.py ~/projects ~/backups --keep 5 --exclude "*.log,node_modules"
    python backup_manager.py ~/notes ~/backups --dry-run
"""

from __future__ import annotations

import argparse
import fnmatch
import logging
import os
import sys
import tarfile
from datetime import datetime
from pathlib import Path
from typing import Iterable, List, Sequence

logger = logging.getLogger("backup_manager")


def _matches_any(name: str, patterns: Sequence[str]) -> bool:
    return any(fnmatch.fnmatch(name, pat) for pat in patterns)


def _iter_files(
    source: Path,
    include: Sequence[str] = (),
    exclude: Sequence[str] = (),
) -> Iterable[Path]:
    """Yield files under `source` honoring include/exclude globs."""
    for root, dirs, files in os.walk(source):
        # Prune excluded directories in place so os.walk does not descend
        dirs[:] = [d for d in dirs if not _matches_any(d, exclude)]
        for fname in files:
            if exclude and _matches_any(fname, exclude):
                continue
            if include and not _matches_any(fname, include):
                continue
            yield Path(root) / fname


def make_archive(
    source: Path,
    dest_dir: Path,
    *,
    name_prefix: str | None = None,
    include: Sequence[str] = (),
    exclude: Sequence[str] = (),
    dry_run: bool = False,
) -> Path:
    """Create a timestamped .tar.gz archive of `source` inside `dest_dir`.

    Returns the resulting archive path. In dry-run mode, no file is written
    and the returned path describes what would have been created.
    """
    source = source.expanduser().resolve()
    dest_dir = dest_dir.expanduser().resolve()
    if not source.exists():
        raise FileNotFoundError(f"source does not exist: {source}")

    dest_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    prefix = name_prefix or source.name or "backup"
    archive_path = dest_dir / f"{prefix}-{stamp}.tar.gz"

    files = list(_iter_files(source, include, exclude)) if source.is_dir() else [source]
    logger.info("Backing up %d files from %s", len(files), source)

    if dry_run:
        for f in files:
            logger.debug("would add: %s", f.relative_to(source) if source.is_dir() else f.name)
        logger.info("[dry-run] would write %s", archive_path)
        return archive_path

    with tarfile.open(archive_path, "w:gz") as tar:
        for f in files:
            arcname = f.relative_to(source.parent) if source.is_dir() else f.name
            tar.add(f, arcname=str(arcname))

    logger.info("Wrote %s (%d bytes)", archive_path, archive_path.stat().st_size)
    return archive_path


def prune_old(dest_dir: Path, *, keep: int, prefix: str | None = None) -> List[Path]:
    """Delete oldest archives in `dest_dir` so that at most `keep` remain.

    Only files matching `{prefix}-*.tar.gz` are considered when prefix is set.
    Returns the list of removed paths.
    """
    if keep < 0:
        raise ValueError("keep must be >= 0")
    pattern = f"{prefix}-*.tar.gz" if prefix else "*.tar.gz"
    archives = sorted(
        dest_dir.glob(pattern),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    to_remove = archives[keep:]
    for path in to_remove:
        logger.info("Pruning old archive: %s", path)
        path.unlink()
    return to_remove


def _split_csv(value: str | None) -> List[str]:
    if not value:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="backup_manager",
        description="Create timestamped tar.gz backups with retention.",
    )
    p.add_argument("source", type=Path, help="File or directory to back up")
    p.add_argument("dest", type=Path, help="Directory where archives are stored")
    p.add_argument("--prefix", help="Override the archive name prefix")
    p.add_argument("--keep", type=int, default=7, help="Keep N most recent archives (default: 7)")
    p.add_argument("--include", help="Comma-separated glob patterns to include")
    p.add_argument("--exclude", help="Comma-separated glob patterns to exclude")
    p.add_argument("--dry-run", action="store_true", help="Show what would happen without writing")
    p.add_argument("-v", "--verbose", action="store_true", help="Verbose logging")
    return p


def main(argv: Sequence[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )

    archive = make_archive(
        args.source,
        args.dest,
        name_prefix=args.prefix,
        include=_split_csv(args.include),
        exclude=_split_csv(args.exclude),
        dry_run=args.dry_run,
    )
    if not args.dry_run and args.keep is not None:
        prune_old(args.dest, keep=args.keep, prefix=args.prefix or args.source.name)
    print(archive)
    return 0


if __name__ == "__main__":
    sys.exit(main())
