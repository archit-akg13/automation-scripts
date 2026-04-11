#!/usr/bin/env python3
"""
PDF Merger & Splitter Tool
--------------------------
Merge multiple PDFs into one or split a PDF into individual pages.
Supports page range selection, rotation, and metadata preservation.

Usage:
    python pdf_merger.py merge file1.pdf file2.pdf -o combined.pdf
        python pdf_merger.py split input.pdf -o output_dir/
            python pdf_merger.py merge file1.pdf file2.pdf --pages 1-3,5,7-10 -o output.pdf

            Requirements:
                pip install PyPDF2
                """

import argparse
import os
import sys
from pathlib import Path

try:
      from PyPDF2 import PdfReader, PdfWriter, PdfMerger
except ImportError:
      print("Error: PyPDF2 is required. Install with: pip install PyPDF2")
      sys.exit(1)


def parse_page_ranges(page_str: str, max_pages: int) -> list[int]:
      """Parse page range string like '1-3,5,7-10' into list of page indices (0-based)."""
      pages = []
      for part in page_str.split(","):
                part = part.strip()
                if "-" in part:
                              start, end = part.split("-", 1)
                              start = max(1, int(start))
                              end = min(max_pages, int(end))
                              pages.extend(range(start - 1, end))
else:
            page_num = int(part)
              if 1 <= page_num <= max_pages:
                                pages.append(page_num - 1)
                    return pages


def merge_pdfs(
      input_files: list[str],
      output_path: str,
      page_ranges: str | None = None,
      rotate: int = 0,
) -> None:
      """Merge multiple PDF files into a single PDF.

              Args:
                      input_files: List of paths to PDF files to merge.
                              output_path: Path for the merged output PDF.
                                      page_ranges: Optional comma-separated page ranges (e.g., '1-3,5').
                                              rotate: Rotation angle in degrees (0, 90, 180, 270).
                                                  """
    writer = PdfWriter()
    total_pages_added = 0

    for filepath in input_files:
              if not os.path.exists(filepath):
                            print(f"Warning: '{filepath}' not found, skipping.")
                            continue

              reader = PdfReader(filepath)
              num_pages = len(reader.pages)
              print(f"Processing: {filepath} ({num_pages} pages)")

        if page_ranges:
                      selected = parse_page_ranges(page_ranges, num_pages)
else:
            selected = list(range(num_pages))

        for page_idx in selected:
                      page = reader.pages[page_idx]
                      if rotate:
                                        page.rotate(rotate)
                                    writer.add_page(page)
            total_pages_added += 1

    if total_pages_added == 0:
              print("Error: No pages were added. Check your input files and page ranges.")
        sys.exit(1)

    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    with open(output_path, "wb") as f:
              writer.write(f)

    print(f"Merged {total_pages_added} pages into '{output_path}'")


def split_pdf(input_file: str, output_dir: str, pages: str | None = None) -> None:
      """Split a PDF into individual page files.

              Args:
                      input_file: Path to the PDF file to split.
                              output_dir: Directory to save individual page PDFs.
                                      pages: Optional page ranges to extract (e.g., '1-3,5').
                                          """
    if not os.path.exists(input_file):
              print(f"Error: '{input_file}' not found.")
        sys.exit(1)

    reader = PdfReader(input_file)
    num_pages = len(reader.pages)
    base_name = Path(input_file).stem

    if pages:
              selected = parse_page_ranges(pages, num_pages)
else:
        selected = list(range(num_pages))

    os.makedirs(output_dir, exist_ok=True)

    for page_idx in selected:
              writer = PdfWriter()
        writer.add_page(reader.pages[page_idx])
        out_path = os.path.join(output_dir, f"{base_name}_page_{page_idx + 1}.pdf")
        with open(out_path, "wb") as f:
                      writer.write(f)
        print(f"  Saved: {out_path}")

    print(f"Split {len(selected)} pages from '{input_file}' into '{output_dir}'")


def get_pdf_info(input_file: str) -> None:
      """Display metadata and page information for a PDF file."""
    if not os.path.exists(input_file):
              print(f"Error: '{input_file}' not found.")
        sys.exit(1)

    reader = PdfReader(input_file)
    meta = reader.metadata

    print(f"File: {input_file}")
    print(f"Pages: {len(reader.pages)}")
    if meta:
              print(f"Title: {meta.title or 'N/A'}")
        print(f"Author: {meta.author or 'N/A'}")
        print(f"Creator: {meta.creator or 'N/A'}")

    for i, page in enumerate(reader.pages):
              box = page.mediabox
        w = float(box.width)
        h = float(box.height)
        print(f"  Page {i + 1}: {w:.0f} x {h:.0f} pts ({w/72:.1f} x {h/72:.1f} in)")


def main():
      parser = argparse.ArgumentParser(
                description="PDF Merger & Splitter — merge, split, and inspect PDF files.",
                formatter_class=argparse.RawDescriptionHelpFormatter,
      )
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Merge command
    merge_parser = subparsers.add_parser("merge", help="Merge multiple PDFs into one")
    merge_parser.add_argument("files", nargs="+", help="PDF files to merge")
    merge_parser.add_argument("-o", "--output", default="merged.pdf", help="Output file path")
    merge_parser.add_argument("--pages", help="Page ranges to include (e.g., '1-3,5,7-10')")
    merge_parser.add_argument("--rotate", type=int, default=0, choices=[0, 90, 180, 270], help="Rotate pages")

    # Split command
    split_parser = subparsers.add_parser("split", help="Split a PDF into individual pages")
    split_parser.add_argument("file", help="PDF file to split")
    split_parser.add_argument("-o", "--output", default="./split_output", help="Output directory")
    split_parser.add_argument("--pages", help="Page ranges to extract (e.g., '1-3,5')")

    # Info command
    info_parser = subparsers.add_parser("info", help="Show PDF metadata and page info")
    info_parser.add_argument("file", help="PDF file to inspect")

    args = parser.parse_args()

    if args.command == "merge":
              merge_pdfs(args.files, args.output, args.pages, args.rotate)
elif args.command == "split":
        split_pdf(args.file, args.output, args.pages)
elif args.command == "info":
        get_pdf_info(args.file)
else:
        parser.print_help()



if __name__ == "__main__":
    main()

if __name__ == "__main__":
      main()
