"""Telegram expense tracker bot — log spends by chat message, report by month.

Messages of the form ``<amount> <note>`` are appended to a CSV ledger. A
``/total [YYYY-MM]`` command replies with that month's spend grouped by note.
Each Telegram chat gets its own ledger slice, so one CSV serves many users.

Usage:
    # Run the bot (long-polls Telegram; Ctrl-C to stop)
    python telegram_expense_bot.py --serve

    # Report offline, straight from the ledger
    python telegram_expense_bot.py --report
    python telegram_expense_bot.py --report 2026-07 --json
    python telegram_expense_bot.py --report --chat-id 12345 --ledger spends.csv

Message formats accepted by the bot:
    450 lunch                    -> 450.00  lunch
    Rs 89.50 auto rickshaw       ->  89.50  auto rickshaw
    INR 2500 electricity bill    -> 2500.00 electricity bill

Environment:
    TELEGRAM_TOKEN   Bot token from @BotFather. Required for --serve only.

Exit codes:
    0  success
    1  ran but found nothing to report
    2  usage / setup error
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
import sys
import time
from collections import defaultdict
from datetime import datetime

DEFAULT_LEDGER = "expenses.csv"
ENTRY = re.compile(r"^(?:rs\.?|inr|₹)?\s*(\d+(?:\.\d{1,2})?)\s+(.{1,40}?)$", re.I)
HELP_TEXT = (
    "Send: <amount> <note>\n"
    "e.g.  450 lunch  |  Rs 1200 groceries\n"
    "Commands: /total [YYYY-MM]"
)


def log_expense(ledger: str, chat_id, amount: float, note: str) -> None:
    """Append one expense row, writing the header if the file is new."""
    fresh = not os.path.exists(ledger)
    with open(ledger, "a", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        if fresh:
            writer.writerow(["date", "chat_id", "amount", "note"])
        writer.writerow(
            [datetime.now().strftime("%Y-%m-%d"), chat_id, f"{amount:.2f}", note]
        )


def month_totals(ledger: str, month: str, chat_id=None) -> dict[str, float]:
    """Sum amounts by note for ``month`` (YYYY-MM), optionally one chat only."""
    totals: dict[str, float] = defaultdict(float)
    if not os.path.exists(ledger):
        return dict(totals)
    with open(ledger, encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            if chat_id is not None and row["chat_id"] != str(chat_id):
                continue
            if not row["date"].startswith(month):
                continue
            totals[row["note"].lower()] += float(row["amount"])
    return dict(totals)


def format_report(month: str, totals: dict[str, float]) -> str:
    """Render totals as a fixed-width text table suitable for a chat message."""
    if not totals:
        return f"Nothing logged for {month} yet."
    rows = sorted(totals.items(), key=lambda kv: -kv[1])
    out = [f"Spend for {month}", "-" * 30]
    out += [f"{note[:17]:<17} Rs {amount:>9,.2f}" for note, amount in rows]
    out += ["-" * 30, f"{'TOTAL':<17} Rs {sum(totals.values()):>9,.2f}"]
    return "\n".join(out)


def serve(token: str, ledger: str) -> None:
    """Long-poll Telegram and handle messages until interrupted."""
    import requests  # imported here so --report stays stdlib-only

    api = f"https://api.telegram.org/bot{token}"

    def send(chat_id, text: str) -> None:
        requests.post(
            f"{api}/sendMessage", json={"chat_id": chat_id, "text": text}, timeout=20
        )

    def handle(message: dict) -> None:
        chat_id = message["chat"]["id"]
        text = (message.get("text") or "").strip()
        if text.startswith("/total"):
            parts = text.split(maxsplit=1)
            month = parts[1].strip() if len(parts) > 1 else datetime.now().strftime("%Y-%m")
            send(chat_id, format_report(month, month_totals(ledger, month, chat_id)))
            return
        match = ENTRY.match(text)
        if not match:
            send(chat_id, HELP_TEXT)
            return
        amount, note = float(match.group(1)), match.group(2).strip()
        log_expense(ledger, chat_id, amount, note)
        send(chat_id, f"Logged Rs {amount:,.2f} - {note}")

    offset = 0
    print(f"Polling Telegram; ledger={ledger}. Ctrl-C to stop.", file=sys.stderr)
    while True:
        try:
            resp = requests.get(
                f"{api}/getUpdates",
                params={"offset": offset, "timeout": 50},
                timeout=60,
            )
            for update in resp.json().get("result", []):
                offset = update["update_id"] + 1
                if "message" in update:
                    handle(update["message"])
        except KeyboardInterrupt:
            raise
        except Exception as exc:  # network blips should not kill the daemon
            print(f"poll error: {exc}", file=sys.stderr)
            time.sleep(3)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=__doc__.splitlines()[0],
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--serve", action="store_true", help="run the Telegram bot")
    mode.add_argument(
        "--report",
        nargs="?",
        const="",
        metavar="YYYY-MM",
        help="print a month report (default: current month)",
    )
    parser.add_argument("--ledger", default=DEFAULT_LEDGER, help="CSV ledger path")
    parser.add_argument("--chat-id", help="restrict a report to one Telegram chat")
    parser.add_argument("--json", action="store_true", help="emit JSON instead of text")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    if args.serve:
        token = os.environ.get("TELEGRAM_TOKEN")
        if not token:
            print("TELEGRAM_TOKEN is not set; get one from @BotFather.", file=sys.stderr)
            return 2
        try:
            serve(token, args.ledger)
        except KeyboardInterrupt:
            print("stopped", file=sys.stderr)
        return 0

    month = args.report or datetime.now().strftime("%Y-%m")
    if not re.fullmatch(r"\d{4}-\d{2}", month):
        print(f"--report expects YYYY-MM, got {month!r}", file=sys.stderr)
        return 2

    totals = month_totals(args.ledger, month, args.chat_id)
    if args.json:
        print(json.dumps({"month": month, "totals": totals, "total": sum(totals.values())}, indent=2))
    else:
        print(format_report(month, totals))
    return 0 if totals else 1


if __name__ == "__main__":
    sys.exit(main())
