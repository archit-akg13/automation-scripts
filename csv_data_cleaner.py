#!/usr/bin/env python3
"""
csv_data_cleaner.py — Automated CSV data cleaning pipeline.

Handles common data quality issues: duplicates, missing values, type coercion,
whitespace normalization, outlier detection, and column renaming. Outputs a
clean CSV alongside a JSON report summarizing every transformation applied.

Usage:
    python csv_data_cleaner.py input.csv -o cleaned.csv --drop-duplicates --fill-strategy median
        python csv_data_cleaner.py data.csv --strip-whitespace --normalize-headers --report report.json
        """

from __future__ import annotations

import argparse
import csv
import json
import logging
import re
import statistics
import sys
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

logging.basicConfig(
      level=logging.INFO,
      format="%(asctime)s [%(levelname)s] %(message)s",
      datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


@dataclass
class CleaningReport:
      """Tracks all transformations applied during cleaning."""

    input_file: str
    output_file: str
    original_rows: int = 0
    final_rows: int = 0
    original_cols: int = 0
    final_cols: int = 0
    duplicates_removed: int = 0
    nulls_filled: dict[str, int] = field(default_factory=dict)
    whitespace_trimmed: int = 0
    headers_renamed: dict[str, str] = field(default_factory=dict)
    outliers_flagged: dict[str, int] = field(default_factory=dict)
    type_coercions: dict[str, str] = field(default_factory=dict)
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> dict[str, Any]:
              return {
                            "input_file": self.input_file,
                            "output_file": self.output_file,
                            "original_rows": self.original_rows,
                            "final_rows": self.final_rows,
                            "original_cols": self.original_cols,
                            "final_cols": self.final_cols,
                            "duplicates_removed": self.duplicates_removed,
                            "nulls_filled": self.nulls_filled,
                            "whitespace_trimmed": self.whitespace_trimmed,
                            "headers_renamed": self.headers_renamed,
                            "outliers_flagged": self.outliers_flagged,
                            "type_coercions": self.type_coercions,
                            "timestamp": self.timestamp,
              }


def normalize_header(name: str) -> str:
      """Convert header to snake_case, stripping special chars."""
      name = name.strip().lower()
      name = re.sub(r"[^\w\s]", "", name)
      name = re.sub(r"\s+", "_", name)
      return name


def detect_numeric(value: str) -> float | None:
      """Try to parse a string as a number."""
      try:
                return float(value.replace(",", ""))
except (ValueError, AttributeError):
        return None


def fill_missing(rows: list[dict], strategy: str, report: CleaningReport) -> list[dict]:
      """Fill missing/empty values using the chosen strategy."""
      if not rows:
                return rows

      columns = list(rows[0].keys())
      for col in columns:
                values = [r[col] for r in rows if r[col].strip()]
                missing_count = sum(1 for r in rows if not r[col].strip())

          if missing_count == 0:
                        continue

        fill_value = ""
        if strategy == "median":
                      nums = [detect_numeric(v) for v in values]
                      nums = [n for n in nums if n is not None]
                      if nums:
                                        fill_value = str(statistics.median(nums))
        elif strategy == "mean":
                      nums = [detect_numeric(v) for v in values]
                      nums = [n for n in nums if n is not None]
                      if nums:
                                        fill_value = str(round(statistics.mean(nums), 4))
elif strategy == "mode":
            if values:
                counter = Counter(values)
                              fill_value = counter.most_common(1)[0][0]
elif strategy == "drop":
            rows = [r for r in rows if r[col].strip()]
            report.nulls_filled[col] = missing_count
            continue
else:
            fill_value = strategy  # literal fill value

        if fill_value:
                      for r in rows:
                                        if not r[col].strip():
                                                              r[col] = fill_value
                                                      report.nulls_filled[col] = missing_count
                                    logger.info("Filled %d missing values in '%s' with %s=%s", missing_count, col, strategy, fill_value)

    return rows


def detect_outliers_iqr(rows: list[dict], report: CleaningReport, threshold: float = 1.5) -> list[dict]:
      """Flag outliers using IQR method, adds _outlier column."""
    if not rows:
              return rows

    columns = list(rows[0].keys())
    for col in columns:
              nums = []
        for r in rows:
                      n = detect_numeric(r[col])
            if n is not None:
                              nums.append(n)

        if len(nums) < 4:
                      continue

        sorted_nums = sorted(nums)
        q1 = sorted_nums[len(sorted_nums) // 4]
        q3 = sorted_nums[3 * len(sorted_nums) // 4]
        iqr = q3 - q1
        lower = q1 - threshold * iqr
        upper = q3 + threshold * iqr

        outlier_count = 0
        flag_col = f"{col}_outlier"
        for r in rows:
                      n = detect_numeric(r[col])
            if n is not None and (n < lower or n > upper):
                              r[flag_col] = "true"
                              outlier_count += 1
else:
                r[flag_col] = "false"

        if outlier_count > 0:
                      report.outliers_flagged[col] = outlier_count
            logger.info("Flagged %d outliers in '%s' (IQR bounds: %.2f–%.2f)", outlier_count, col, lower, upper)

    return rows


def clean_csv(
      input_path: Path,
      output_path: Path,
      *,
      drop_duplicates: bool = False,
      fill_strategy: str | None = None,
      strip_whitespace: bool = False,
      normalize_headers: bool = False,
      detect_outliers: bool = False,
      report_path: Path | None = None,
) -> CleaningReport:
      """Main cleaning pipeline — reads, transforms, writes."""

    report = CleaningReport(
              input_file=str(input_path),
              output_file=str(output_path),
    )

    # --- Read ---
    with open(input_path, newline="", encoding="utf-8-sig") as f:
              reader = csv.DictReader(f)
        original_headers = reader.fieldnames or []
        rows = list(reader)

    report.original_rows = len(rows)
    report.original_cols = len(original_headers)
    logger.info("Loaded %d rows x %d cols from %s", len(rows), len(original_headers), input_path)

    # --- Normalize headers ---
    if normalize_headers:
              new_headers = {h: normalize_header(h) for h in original_headers}
        report.headers_renamed = {k: v for k, v in new_headers.items() if k != v}
        rows = [{new_headers[k]: v for k, v in row.items()} for row in rows]
        if report.headers_renamed:
                      logger.info("Renamed %d headers", len(report.headers_renamed))

    # --- Strip whitespace ---
    if strip_whitespace:
              trimmed = 0
        for row in rows:
                                    for key in row:
                                                      original = row[key]
                                                      row[key] = row[key].strip()
                                                      if row[key] != original:
                                                                            trimmed += 1
                                                                report.whitespace_trimmed = trimmed
                                              logger.info("Trimmed whitespace in %d cells", trimmed)

    # --- Drop duplicates ---
    if drop_duplicates:
              seen: set[tuple[str, ...]] = set()
        unique_rows = []
        for row in rows:
                      key = tuple(sorted(row.items()))
            if key not in seen:
                              seen.add(key)
                unique_rows.append(row)
        report.duplicates_removed = len(rows) - len(unique_rows)
        rows = unique_rows
        logger.info("Removed %d duplicate rows", report.duplicates_removed)

    # --- Fill missing values ---
    if fill_strategy:
              rows = fill_missing(rows, fill_strategy, report)

    # --- Outlier detection ---
    if detect_outliers:
              rows = detect_outliers_iqr(rows, report)

    # --- Write ---
    if rows:
              fieldnames = list(rows[0].keys())
else:
        fieldnames = original_headers

    report.final_rows = len(rows)
    report.final_cols = len(fieldnames)

    with open(output_path, "w", newline="", encoding="utf-8") as f:
              writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    logger.info("Wrote %d rows x %d cols to %s", len(rows), len(fieldnames), output_path)

    # --- Report ---
    if report_path:
              with open(report_path, "w", encoding="utf-8") as f:
                            json.dump(report.to_dict(), f, indent=2)
        logger.info("Cleaning report saved to %s", report_path)

    return report


def build_parser() -> argparse.ArgumentParser:
      parser = argparse.ArgumentParser(
                description="Automated CSV data cleaning pipeline",
                formatter_class=argparse.RawDescriptionHelpFormatter,
      )
    parser.add_argument("input", type=Path, help="Path to input CSV file")
    parser.add_argument("-o", "--output", type=Path, default=None, help="Output CSV path (default: input_cleaned.csv)")
    parser.add_argument("--drop-duplicates", action="store_true", help="Remove duplicate rows")
    parser.add_argument(
              "--fill-strategy",
              choices=["median", "mean", "mode", "drop"],
              default=None,
              help="Strategy for filling missing values",
    )
    parser.add_argument("--strip-whitespace", action="store_true", help="Trim leading/trailing whitespace in all cells")
    parser.add_argument("--normalize-headers", action="store_true", help="Convert headers to snake_case")
    parser.add_argument("--detect-outliers", action="store_true", help="Flag outliers using IQR method")
    parser.add_argument("--report", type=Path, default=None, help="Path to save JSON cleaning report")
    return parser


def main() -> None:
      parser = build_parser()
    args = parser.parse_args()

    if not args.input.exists():
              logger.error("Input file not found: %s", args.input)
        sys.exit(1)

    output = args.output or args.input.with_stem(args.input.stem + "_cleaned")

    report = clean_csv(
              args.input,
              output,
              drop_duplicates=args.drop_duplicates,
              fill_strategy=args.fill_strategy,
              strip_whitespace=args.strip_whitespace,
              normalize_headers=args.normalize_headers,
              detect_outliers=args.detect_outliers,
              report_path=args.report,
    )

    summary = report.to_dict()
    logger.info(
              "Done — %d→%d rows | %d dupes removed | %d nulls filled | %d outliers flagged",
              summary["original_rows"],
              summary["final_rows"],
              summary["duplicates_removed"],
              sum(summary["nulls_filled"].values()),
              sum(summary["outliers_flagged"].values()),
    )


if __name__ == "__main__":
      main()
