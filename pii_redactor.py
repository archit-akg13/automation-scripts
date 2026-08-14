#!/usr/bin/env python3
"""Permanently redact Indian PII (PAN, Aadhaar, GSTIN) from PDF files.

Unlike drawing a black rectangle in a PDF viewer, this removes the characters
from the content stream, so the values cannot be recovered by copy-paste or
text extraction.

Aadhaar candidates are validated with the UIDAI Verhoeff checksum, so ordinary
12-digit numbers (order IDs, reference numbers) are left alone.

Usage:
    # Preview what would be redacted -- writes nothing (default)
    python pii_redactor.py ./kyc_packets

    # Actually write redacted copies
    python pii_redactor.py ./kyc_packets --apply --output ./clean

    # Machine-readable report
    python pii_redactor.py ./kyc_packets --json

    # Only redact Aadhaar, leave PAN and GSTIN intact
    python pii_redactor.py ./kyc_packets --types aadhaar --apply

Exit codes:
    0  success, nothing suspicious
    1  ran, but found issues (a PDF with no text layer may hide unredacted PII)
    2  usage or setup error (bad path, PyMuPDF not installed)
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

# Verhoeff multiplication (D5) and permutation tables -- UIDAI's Aadhaar checksum.
_D = (
    (0, 1, 2, 3, 4, 5, 6, 7, 8, 9), (1, 2, 3, 4, 0, 6, 7, 8, 9, 5),
    (2, 3, 4, 0, 1, 7, 8, 9, 5, 6), (3, 4, 0, 1, 2, 8, 9, 5, 6, 7),
    (4, 0, 1, 2, 3, 9, 5, 6, 7, 8), (5, 9, 8, 7, 6, 0, 4, 3, 2, 1),
    (6, 5, 9, 8, 7, 1, 0, 4, 3, 2), (7, 6, 5, 9, 8, 2, 1, 0, 4, 3),
    (8, 7, 6, 5, 9, 3, 2, 1, 0, 4), (9, 8, 7, 6, 5, 4, 3, 2, 1, 0),
)
_P = (
    (0, 1, 2, 3, 4, 5, 6, 7, 8, 9), (1, 5, 7, 6, 2, 8, 3, 0, 9, 4),
    (5, 8, 0, 3, 7, 9, 6, 1, 4, 2), (8, 9, 1, 6, 0, 4, 3, 5, 2, 7),
    (9, 4, 5, 3, 1, 2, 6, 8, 7, 0), (4, 2, 8, 6, 5, 7, 3, 9, 0, 1),
    (2, 7, 9, 3, 8, 0, 6, 4, 1, 5), (7, 0, 4, 6, 9, 1, 3, 2, 5, 8),
)

PATTERNS = {
    "pan": re.compile(r"\b[A-Z]{5}[0-9]{4}[A-Z]\b"),
    "aadhaar": re.compile(r"\b[2-9][0-9]{3}[ -]?[0-9]{4}[ -]?[0-9]{4}\b"),
    "gstin": re.compile(r"\b[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][A-Z0-9]Z[A-Z0-9]\b"),
}


def verhoeff_ok(digits: str) -> bool:
    """True if `digits` carries a valid Verhoeff check digit."""
    checksum = 0
    for i, char in enumerate(reversed(digits)):
        checksum = _D[checksum][_P[i % 8][int(char)]]
    return checksum == 0


def find_pii(text: str, types: set[str]) -> dict[str, set[str]]:
    """Return {type: {matched strings}} for the requested PII types."""
    found: dict[str, set[str]] = {}
    for kind in types:
        hits = set()
        for match in PATTERNS[kind].finditer(text):
            raw = match.group()
            # Reject 12-digit numbers that fail the Aadhaar checksum.
            if kind == "aadhaar" and not verhoeff_ok(re.sub(r"[ -]", "", raw)):
                continue
            hits.add(raw)
        if hits:
            found[kind] = hits
    return found


def _contains(outer, inner) -> bool:
    """True if rect `outer` fully encloses rect `inner` (1pt tolerance)."""
    return (outer[0] - 1 <= inner[0] and outer[1] - 1 <= inner[1]
            and outer[2] + 1 >= inner[2] and outer[3] + 1 >= inner[3])


def locate(page, found: dict[str, set[str]]) -> list[tuple[str, object]]:
    """Map matches to page rectangles, longest match wins on overlap.

    page.search_for() is a plain substring search and ignores the word
    boundaries the regexes rely on, so a PAN pattern also matches inside a
    GSTIN (29ABCDE1234F1Z5 contains ABCDE1234F). Without this pass the same
    ink gets counted twice and the report overstates what was found.
    """
    candidates = [(kind, value) for kind, values in found.items() for value in values]
    candidates.sort(key=lambda pair: len(pair[1]), reverse=True)

    claimed: list[tuple[str, object]] = []
    for kind, value in candidates:
        for box in page.search_for(value):
            if not any(_contains(prev, box) for _, prev in claimed):
                claimed.append((kind, box))
    return claimed


def scan_pdf(pymupdf, path: Path, types: set[str], dest: Path | None) -> dict:
    """Scan one PDF; redact into `dest` when dest is not None."""
    doc = pymupdf.open(path)
    counts: dict[str, int] = {}
    empty_pages = 0
    for page in doc:
        text = page.get_text()
        if not text.strip():
            empty_pages += 1
            continue
        for kind, box in locate(page, find_pii(text, types)):
            counts[kind] = counts.get(kind, 0) + 1
            if dest is not None:
                page.add_redact_annot(box, fill=(0, 0, 0))
        if dest is not None:
            page.apply_redactions()

    if dest is not None:
        dest.parent.mkdir(parents=True, exist_ok=True)
        # garbage=4 drops the orphaned pre-redaction content streams.
        doc.save(dest, garbage=4, deflate=True)
    pages = doc.page_count
    doc.close()

    return {
        "file": str(path),
        "pages": pages,
        "redactions": counts,
        "total": sum(counts.values()),
        # A page with no extractable text is almost always a scan. PII on it is
        # invisible to this tool -- the caller needs to know.
        "pages_without_text": empty_pages,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Permanently redact PAN, Aadhaar and GSTIN from PDFs.",
        epilog="Previews by default; pass --apply to write redacted copies.",
    )
    parser.add_argument("source", type=Path, help="PDF file or directory of PDFs")
    parser.add_argument(
        "--output", type=Path, default=None,
        help="output directory (default: <source>/redacted)",
    )
    parser.add_argument(
        "--types", nargs="+", choices=sorted(PATTERNS), default=sorted(PATTERNS),
        help="PII types to redact (default: all)",
    )
    parser.add_argument(
        "--apply", action="store_true",
        help="write redacted files (without this, only reports what it would do)",
    )
    parser.add_argument("--json", action="store_true", help="emit a JSON report")
    args = parser.parse_args(argv)

    try:
        import pymupdf
    except ImportError:
        print("error: PyMuPDF is required -- pip install pymupdf", file=sys.stderr)
        return 2

    if not args.source.exists():
        print(f"error: no such path: {args.source}", file=sys.stderr)
        return 2

    if args.source.is_dir():
        pdfs = sorted(args.source.glob("*.pdf"))
        out_dir = args.output or args.source / "redacted"
    else:
        pdfs = [args.source]
        out_dir = args.output or args.source.parent / "redacted"

    if not pdfs:
        print(f"error: no PDFs found in {args.source}", file=sys.stderr)
        return 2

    types = set(args.types)
    reports = [
        scan_pdf(pymupdf, pdf, types, out_dir / pdf.name if args.apply else None)
        for pdf in pdfs
    ]

    total = sum(r["total"] for r in reports)
    blind = sum(r["pages_without_text"] for r in reports)

    if args.json:
        print(json.dumps(
            {"applied": args.apply, "files": reports,
             "total_redactions": total, "pages_without_text": blind},
            indent=2,
        ))
    else:
        for r in reports:
            detail = ", ".join(f"{k}={v}" for k, v in sorted(r["redactions"].items()))
            print(f"{Path(r['file']).name}: {r['total']} match(es)"
                  + (f" ({detail})" if detail else ""))
            if r["pages_without_text"]:
                print(f"  warning: {r['pages_without_text']} page(s) have no text "
                      f"layer -- run OCR first or PII may survive")
        verb = "redacted" if args.apply else "would redact"
        print(f"\n{verb} {total} value(s) across {len(reports)} file(s)")
        if args.apply:
            print(f"output: {out_dir}")
        else:
            print("preview only -- re-run with --apply to write files")

    # Blind pages mean we cannot promise the file is clean.
    return 1 if blind else 0


if __name__ == "__main__":
    sys.exit(main())

