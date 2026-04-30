"""password_generator.py — secure password generator with policy controls.

Generates cryptographically-strong passwords using `secrets`. Supports length,
character classes (lower, upper, digits, symbols), exclusion of ambiguous
characters (0/O, 1/l/I), and a guarantee that at least one character from each
enabled class appears in the result.

Usage:
    python password_generator.py                  # 1 password, length 16
        python password_generator.py -n 5 -l 24       # 5 passwords, length 24
            python password_generator.py --no-symbols     # alphanumeric only
                python password_generator.py --no-ambiguous   # avoid look-alike chars
                """

from __future__ import annotations

import argparse
import secrets
import string
import sys

AMBIGUOUS = set("0O1lI|`'\";:,.")


def build_alphabet(
      use_lower: bool,
      use_upper: bool,
      use_digits: bool,
      use_symbols: bool,
      no_ambiguous: bool,
) -> list[str]:
      """Return per-class alphabets after filtering ambiguous chars if requested."""
      classes: list[str] = []
      if use_lower:
                classes.append(string.ascii_lowercase)
            if use_upper:
                      classes.append(string.ascii_uppercase)
                  if use_digits:
                            classes.append(string.digits)
                        if use_symbols:
                                  classes.append("!@#$%^&*()-_=+[]{}<>?/")
                              if not classes:
                                        raise ValueError("At least one character class must be enabled.")
                                    if no_ambiguous:
                                              classes = ["".join(c for c in cls if c not in AMBIGUOUS) for cls in classes]
                                              if any(not cls for cls in classes):
                                                            raise ValueError("Ambiguous filter removed all chars from a class.")
                                                    return classes


def generate(length: int, classes: list[str]) -> str:
      """Generate a password guaranteed to include >=1 char from each class."""
    if length < len(classes):
              raise ValueError(f"length must be >= {len(classes)} to cover all classes.")
    # Seed with one char from each class, then fill from the union.
    pool = "".join(classes)
    chars = [secrets.choice(cls) for cls in classes]
    chars += [secrets.choice(pool) for _ in range(length - len(classes))]
    # Fisher-Yates shuffle using secrets for unbiased ordering.
    for i in range(len(chars) - 1, 0, -1):
              j = secrets.randbelow(i + 1)
        chars[i], chars[j] = chars[j], chars[i]
    return "".join(chars)


def main(argv: list[str] | None = None) -> int:
      parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("-l", "--length", type=int, default=16, help="password length")
    parser.add_argument("-n", "--count", type=int, default=1, help="how many to make")
    parser.add_argument("--no-lower", action="store_true")
    parser.add_argument("--no-upper", action="store_true")
    parser.add_argument("--no-digits", action="store_true")
    parser.add_argument("--no-symbols", action="store_true")
    parser.add_argument(
              "--no-ambiguous",
              action="store_true",
              help="exclude look-alike chars (0/O, 1/l/I, quotes, etc.)",
    )
    args = parser.parse_args(argv)

    try:
              classes = build_alphabet(
                            use_lower=not args.no_lower,
                            use_upper=not args.no_upper,
                            use_digits=not args.no_digits,
                            use_symbols=not args.no_symbols,
                            no_ambiguous=args.no_ambiguous,
              )
        for _ in range(args.count):
                      print(generate(args.length, classes))
except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
      raise SystemExit(main())
