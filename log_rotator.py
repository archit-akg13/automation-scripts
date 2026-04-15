#!/usr/bin/env python3
"""
Log Rotator — compress, archive, and prune old log files.

Features:
  - Scans a directory for log files matching a glob pattern
    - Compresses logs older than a threshold (gzip)
      - Moves compressed logs to an archive directory
        - Deletes archives older than a retention period
          - Supports dry-run mode for safe previewing
            - Generates a rotation summary report

            Usage:
              python log_rotator.py /var/log/myapp --pattern "*.log" --compress-after 1 --delete-after 30
                python log_rotator.py ./logs --dry-run
                """

import argparse
import gzip
import os
import shutil
import sys
from datetime import datetime, timedelta
from pathlib import Path
from dataclasses import dataclass, field
from typing import List


@dataclass
class RotationResult:
      """Tracks what happened during a rotation run."""
      compressed: List[str] = field(default_factory=list)
      archived: List[str] = field(default_factory=list)
      deleted: List[str] = field(default_factory=list)
      errors: List[str] = field(default_factory=list)
      bytes_saved: int = 0

    @property
    def summary(self) -> str:
              lines = [
                            f"Compressed : {len(self.compressed)} files",
                            f"Archived   : {len(self.archived)} files",
                            f"Deleted    : {len(self.deleted)} files",
                            f"Errors     : {len(self.errors)}",
                            f"Space saved: {self.bytes_saved / 1024 / 1024:.2f} MB",
              ]
              return "\n".join(lines)


def file_age_days(path: Path) -> float:
      """Return age of a file in days based on modification time."""
      mtime = datetime.fromtimestamp(path.stat().st_mtime)
      return (datetime.now() - mtime).total_seconds() / 86400


def compress_file(src: Path, dest_dir: Path, dry_run: bool = False) -> int:
      """Gzip-compress a file into dest_dir. Returns bytes saved."""
      dest = dest_dir / (src.name + ".gz")
      original_size = src.stat().st_size

    if dry_run:
              print(f"  [DRY-RUN] Would compress {src.name} -> {dest}")
              return 0

    try:
              with open(src, "rb") as f_in, gzip.open(dest, "wb") as f_out:
                            shutil.copyfileobj(f_in, f_out)
                        compressed_size = dest.stat().st_size
        src.unlink()
        saved = original_size - compressed_size
        print(f"  Compressed {src.name} ({original_size:,}B -> {compressed_size:,}B, saved {saved:,}B)")
        return max(saved, 0)
except OSError as exc:
        raise RuntimeError(f"Failed to compress {src}: {exc}") from exc


def rotate_logs(
      log_dir: Path,
      pattern: str = "*.log",
      archive_subdir: str = "archive",
      compress_after_days: float = 1.0,
      delete_after_days: float = 30.0,
      dry_run: bool = False,
) -> RotationResult:
      """
          Main rotation logic.

              1. Find log files matching *pattern* in *log_dir*.
                  2. Compress any older than *compress_after_days* into the archive subdir.
                      3. Delete compressed archives older than *delete_after_days*.
                          """
    result = RotationResult()
    archive_dir = log_dir / archive_subdir

    if not log_dir.is_dir():
              result.errors.append(f"Log directory does not exist: {log_dir}")
        return result

    if not dry_run:
              archive_dir.mkdir(parents=True, exist_ok=True)

    # --- Compress old uncompressed logs ---
    for log_file in sorted(log_dir.glob(pattern)):
              if not log_file.is_file():
                            continue
                        age = file_age_days(log_file)
        if age >= compress_after_days:
                      try:
                                        saved = compress_file(log_file, archive_dir, dry_run=dry_run)
                                        result.compressed.append(str(log_file))
                                        result.archived.append(str(archive_dir / (log_file.name + ".gz")))
                                        result.bytes_saved += saved
except RuntimeError as exc:
                                  result.errors.append(str(exc))

    # --- Prune old compressed archives ---
    if archive_dir.is_dir():
              for gz_file in sorted(archive_dir.glob("*.gz")):
                            if not gz_file.is_file():
                                              continue
                                          age = file_age_days(gz_file)
            if age >= delete_after_days:
                              if dry_run:
                                                    print(f"  [DRY-RUN] Would delete {gz_file.name} (age: {age:.1f}d)")
            else:
                    gz_file.unlink()
                    print(f"  Deleted {gz_file.name} (age: {age:.1f} days)")
                result.deleted.append(str(gz_file))

    return result


def build_parser() -> argparse.ArgumentParser:
      parser = argparse.ArgumentParser(
                description="Rotate, compress, and prune log files.",
                formatter_class=argparse.RawDescriptionHelpFormatter,
      )
    parser.add_argument("log_dir", type=Path, help="Directory containing log files")
    parser.add_argument("--pattern", default="*.log", help="Glob pattern for log files (default: *.log)")
    parser.add_argument("--archive-subdir", default="archive", help="Subdirectory for compressed archives")
    parser.add_argument("--compress-after", type=float, default=1.0, help="Compress logs older than N days (default: 1)")
    parser.add_argument("--delete-after", type=float, default=30.0, help="Delete archives older than N days (default: 30)")
    parser.add_argument("--dry-run", action="store_true", help="Preview changes without modifying files")
    return parser


def main() -> None:
      parser = build_parser()
    args = parser.parse_args()

    print(f"Log Rotator — {datetime.now():%Y-%m-%d %H:%M:%S}")
    print(f"Directory : {args.log_dir.resolve()}")
    print(f"Pattern   : {args.pattern}")
    print(f"Compress  : after {args.compress_after} day(s)")
    print(f"Delete    : after {args.delete_after} day(s)")
    if args.dry_run:
              print("Mode      : DRY-RUN (no changes will be made)\n")
else:
        print()

    result = rotate_logs(
              log_dir=args.log_dir,
              pattern=args.pattern,
              archive_subdir=args.archive_subdir,
              compress_after_days=args.compress_after,
              delete_after_days=args.delete_after,
              dry_run=args.dry_run,
    )

    print(f"\n--- Rotation Summary ---\n{result.summary}")
    if result.errors:
              print("\nErrors:")
        for err in result.errors:
                      print(f"  ! {err}")
        sys.exit(1)


if __name__ == "__main__":
      main()
