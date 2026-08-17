#!/usr/bin/env python3
"""Validate and decode Indian GSTINs offline — no API, no network, no rate limits.

A GSTIN embeds its own check character: the 15th character is a base-36 weighted
modular function of the first 14. That means single-character typos and most
transpositions are detectable without ever calling the GST portal.

What this script checks:
  1. Length is exactly 15
  2. Structure matches the GSTIN pattern (state / PAN / entity / Z / checksum)
  3. State code is a real, currently-assigned code
  4. The check character matches the computed checksum

On success it also decodes the embedded PAN, the state name, the entity type
(from the PAN's 4th character) and the per-state registration counter.

What this script CANNOT tell you: whether a GSTIN is registered, active, or
belongs to the vendor who gave it to you. Only the GST portal knows that. Use
this as a cheap pre-filter so you spend portal lookups only on numbers that
survive the arithmetic.

Usage:
  # Check one or more GSTINs on the command line
  python gstin_validator.py --check 27AAPFU0939F1ZV 29AAGCB7383J1Z4

  # Check a CSV column and write an annotated copy
  python gstin_validator.py vendors.csv --output checked.csv
  python gstin_validator.py vendors.csv --output checked.csv --column gst_no

  # Machine-readable report
  python gstin_validator.py vendors.csv --json

Exit codes:
  0  all GSTINs valid
  1  ran successfully but found invalid GSTINs
  2  usage / setup error (missing file, missing column)
"""

import argparse
import csv
import json
import re
import sys

CHARSET = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"
GSTIN_RE = re.compile(r"^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][0-9A-Z][Z][0-9A-Z]$")

STATE_CODES = {
    "01": "Jammu & Kashmir", "02": "Himachal Pradesh", "03": "Punjab",
    "04": "Chandigarh", "05": "Uttarakhand", "06": "Haryana", "07": "Delhi",
    "08": "Rajasthan", "09": "Uttar Pradesh", "10": "Bihar", "11": "Sikkim",
    "12": "Arunachal Pradesh", "13": "Nagaland", "14": "Manipur",
    "15": "Mizoram", "16": "Tripura", "17": "Meghalaya", "18": "Assam",
    "19": "West Bengal", "20": "Jharkhand", "21": "Odisha",
    "22": "Chhattisgarh", "23": "Madhya Pradesh", "24": "Gujarat",
    "26": "Dadra & Nagar Haveli and Daman & Diu", "27": "Maharashtra",
    "29": "Karnataka", "30": "Goa", "31": "Lakshadweep", "32": "Kerala",
    "33": "Tamil Nadu", "34": "Puducherry", "35": "Andaman & Nicobar Islands",
    "36": "Telangana", "37": "Andhra Pradesh", "38": "Ladakh",
    "97": "Other Territory", "99": "Centre Jurisdiction",
}

PAN_ENTITY = {
    "A": "Association of Persons (AOP)",
    "B": "Body of Individuals (BOI)",
    "C": "Company",
    "F": "Partnership Firm / LLP",
    "G": "Government",
    "H": "Hindu Undivided Family (HUF)",
    "J": "Artificial Juridical Person",
    "L": "Local Authority",
    "P": "Individual / Proprietor",
    "T": "Trust",
}


def compute_checksum(first14: str) -> str:
    """Return the expected 15th character for the first 14 characters of a GSTIN."""
    total = 0
    for index, char in enumerate(first14):
        product = CHARSET.index(char) * (2 if index % 2 else 1)
        total += product // 36 + product % 36
    return CHARSET[(36 - total % 36) % 36]


def validate(raw: str) -> dict:
    """Validate a single GSTIN. Always returns a dict with a 'valid' boolean."""
    gstin = (raw or "").strip().upper().replace(" ", "").replace("-", "")
    result = {"gstin": gstin, "valid": False, "error": ""}

    if not gstin:
        result["error"] = "empty value"
        return result
    if len(gstin) != 15:
        result["error"] = f"length {len(gstin)}, expected 15"
        return result
    if not GSTIN_RE.match(gstin):
        result["error"] = "structure does not match GSTIN pattern"
        return result
    if gstin[:2] not in STATE_CODES:
        result["error"] = f"unknown or unassigned state code {gstin[:2]}"
        return result

    expected = compute_checksum(gstin[:14])
    if expected != gstin[14]:
        result["error"] = f"checksum mismatch (expected {expected}, got {gstin[14]})"
        return result

    result.update(
        valid=True,
        state_code=gstin[:2],
        state=STATE_CODES[gstin[:2]],
        pan=gstin[2:12],
        entity_type=PAN_ENTITY.get(gstin[5], "Unknown"),
        registration_no=gstin[12],
    )
    return result


def _report(rows: list, as_json: bool) -> None:
    invalid = [r for r in rows if not r["valid"]]
    if as_json:
        print(json.dumps({"checked": len(rows), "invalid": len(invalid),
                          "results": rows}, indent=2))
        return
    for row in rows:
        if row["valid"]:
            print(f"  OK   {row['gstin']}  {row['state']}  "
                  f"PAN {row['pan']}  {row['entity_type']}")
        else:
            print(f"  BAD  {row['gstin'] or '(empty)'}  -> {row['error']}")
    print(f"\n{len(rows)} checked | {len(invalid)} invalid")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Validate and decode Indian GSTINs offline.",
        epilog="Exit codes: 0 all valid, 1 invalid found, 2 usage error.",
    )
    parser.add_argument("csvfile", nargs="?", help="CSV file containing a GSTIN column")
    parser.add_argument("--check", nargs="+", metavar="GSTIN",
                        help="validate GSTINs passed directly on the command line")
    parser.add_argument("--column", default="gstin",
                        help="CSV column holding the GSTIN (default: gstin)")
    parser.add_argument("--output", help="write an annotated copy of the CSV here")
    parser.add_argument("--json", action="store_true", dest="as_json",
                        help="emit a JSON report instead of text")
    args = parser.parse_args(argv)

    if not args.csvfile and not args.check:
        parser.error("provide a CSV file or --check GSTIN [GSTIN ...]")

    if args.check:
        rows = [validate(value) for value in args.check]
        _report(rows, args.as_json)
        return 1 if any(not r["valid"] for r in rows) else 0

    try:
        with open(args.csvfile, newline="", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            if reader.fieldnames is None:
                print(f"error: {args.csvfile} is empty", file=sys.stderr)
                return 2
            if args.column not in reader.fieldnames:
                print(f"error: column '{args.column}' not found. "
                      f"Available: {', '.join(reader.fieldnames)}", file=sys.stderr)
                return 2
            source = list(reader)
    except FileNotFoundError:
        print(f"error: no such file: {args.csvfile}", file=sys.stderr)
        return 2
    except OSError as exc:
        print(f"error: could not read {args.csvfile}: {exc}", file=sys.stderr)
        return 2

    rows = [{**row, **validate(row.get(args.column, ""))} for row in source]

    if args.output:
        fields = list(dict.fromkeys(key for row in rows for key in row))
        try:
            with open(args.output, "w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(handle, fieldnames=fields)
                writer.writeheader()
                writer.writerows(rows)
        except OSError as exc:
            print(f"error: could not write {args.output}: {exc}", file=sys.stderr)
            return 2

    _report(rows, args.as_json)
    if args.output and not args.as_json:
        print(f"wrote {args.output}")
    return 1 if any(not r["valid"] for r in rows) else 0


if __name__ == "__main__":
    sys.exit(main())
