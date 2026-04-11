#!/usr/bin/env python3
"""
File Organizer - Automatically sort files into folders by extension.

Usage:
    python file_organizer.py /path/to/messy/folder
    python file_organizer.py /path/to/folder --dry-run
    python file_organizer.py /path/to/folder --undo

Author: Archit Mittal (@automate_archit)
"""

import argparse
import json
import logging
import os
import shutil
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

CATEGORY_MAP: Dict[str, str] = {
    ".pdf": "Documents", ".doc": "Documents", ".docx": "Documents",
    ".txt": "Documents", ".rtf": "Documents", ".odt": "Documents",
    ".xls": "Documents", ".xlsx": "Documents", ".csv": "Documents",
    ".jpg": "Images", ".jpeg": "Images", ".png": "Images",
    ".gif": "Images", ".svg": "Images", ".webp": "Images",
    ".mp4": "Videos", ".avi": "Videos", ".mkv": "Videos",
    ".mov": "Videos", ".wmv": "Videos",
    ".mp3": "Audio", ".wav": "Audio", ".flac": "Audio",
    ".zip": "Archives", ".tar": "Archives", ".gz": "Archives",
    ".rar": "Archives", ".7z": "Archives",
    ".py": "Code", ".js": "Code", ".ts": "Code",
    ".html": "Code", ".css": "Code", ".json": "Code",
}

MANIFEST_FILE = ".file_organizer_manifest.json"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


def get_category(file_path: Path) -> str:
    return CATEGORY_MAP.get(file_path.suffix.lower(), "Other")


def organize(target_dir: Path, dry_run: bool = False) -> List[Dict]:
    manifest = []
    for item in target_dir.iterdir():
        if item.is_dir() or item.name.startswith("."):
            continue
        category = get_category(item)
        dest_dir = target_dir / category
        dest_path = dest_dir / item.name
        counter = 1
        while dest_path.exists():
            dest_path = dest_dir / f"{item.stem}_{counter}{item.suffix}"
            counter += 1
        record = {"src": str(item), "dst": str(dest_path), "ts": datetime.now().isoformat()}
        if dry_run:
            logger.info("[DRY RUN] %s -> %s", item.name, dest_path)
        else:
            dest_dir.mkdir(exist_ok=True)
            shutil.move(str(item), str(dest_path))
            logger.info("Moved: %s -> %s", item.name, dest_path)
        manifest.append(record)
    if not dry_run and manifest:
        with open(target_dir / MANIFEST_FILE, "w") as f:
            json.dump(manifest, f, indent=2)
    return manifest


def undo(target_dir: Path) -> None:
    manifest_path = target_dir / MANIFEST_FILE
    if not manifest_path.exists():
        logger.error("No manifest found. Nothing to undo.")
        return
    with open(manifest_path) as f:
        manifest = json.load(f)
    for rec in reversed(manifest):
        src, dst = Path(rec["dst"]), Path(rec["src"])
        if src.exists():
            shutil.move(str(src), str(dst))
            logger.info("Restored: %s", dst.name)
    manifest_path.unlink()
    for item in target_dir.iterdir():
        if item.is_dir() and not any(item.iterdir()):
            item.rmdir()


def main() -> None:
    parser = argparse.ArgumentParser(description="Organize files by extension.")
    parser.add_argument("directory", type=Path, help="Target directory")
    parser.add_argument("--dry-run", action="store_true", help="Preview only")
    parser.add_argument("--undo", action="store_true", help="Reverse last run")
    args = parser.parse_args()
    if not args.directory.is_dir():
        raise SystemExit(f"Not a directory: {args.directory}")
    if args.undo:
        undo(args.directory)
    else:
        result = organize(args.directory, dry_run=args.dry_run)
        logger.info("Done. %d file(s) processed.", len(result))


if __name__ == "__main__":
    main()
