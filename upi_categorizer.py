"""
UPI Transaction Categorizer
============================
Auto-categorizes UPI transactions from any major Indian bank's CSV statement
into Food / Groceries / Transport / Bills / Shopping / Investments / Health /
Entertainment buckets, then prints a monthly pivot.

Usage:
    python upi_categorizer.py statement.csv

Outputs:
    - upi_summary.csv (monthly pivot of debits by category)
    - prints the pivot to stdout

See the writeup: https://dev.to/automate-archit/build-a-upi-transaction-categorizer-in-95-lines-of-python-2g8f
"""
import re
import sys
from pathlib import Path
import pandas as pd

CATEGORIES = {
    "Food": [
        "zomato", "swiggy", "dunzo", "eatfit", "faasos", "behrouz",
        "dominos", "pizzahut", "kfc", "mcdonalds", "starbucks", "cafe",
    ],
    "Groceries": [
        "bigbasket", "blinkit", "grofers", "zepto", "dmart", "instamart",
        "reliancefresh", "natures", "spencer", "more-retail",
    ],
    "Transport": [
        "uber", "olacabs", "rapido", "irctc", "redbus", "abhibus",
        "namma-yatri", "blusmart", "yulu", "vogo",
    ],
    "Bills": [
        "airtel", "jio", "vodafone", "vi-mobile", "bsnl", "tatapower",
        "bescom", "adani-electricity", "torrent-power", "mahanagargas",
        "act-fibernet", "hathway",
    ],
    "Shopping": [
        "amazon", "flipkart", "myntra", "ajio", "nykaa", "meesho",
        "tatacliq", "firstcry", "lenskart", "boat-lifestyle",
    ],
    "Investments": [
        "zerodha", "groww", "upstox", "kuvera", "paytmmoney",
        "indmoney", "angelone", "smallcase",
    ],
    "Health": [
        "pharmeasy", "1mg", "netmeds", "apollo", "practo",
        "cult-fit", "healthifyme",
    ],
    "Entertainment": [
        "netflix", "hotstar", "primevideo", "sonyliv", "zee5",
        "spotify", "gaana", "bookmyshow", "pvr", "inox",
    ],
}

UPI_PATTERN = re.compile(r"upi[/-]([a-z0-9.\-_@]+)", re.IGNORECASE)


def extract_merchant(narration: str) -> str:
    """Pull the merchant slug out of a UPI narration string."""
    if not isinstance(narration, str):
        return ""
    match = UPI_PATTERN.search(narration.lower())
    return match.group(1) if match else narration.lower()


def categorize(narration: str) -> str:
    merchant = extract_merchant(narration)
    for category, keywords in CATEGORIES.items():
        for keyword in keywords:
            if keyword in merchant:
                return category
    return "Other"


def load_statement(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    df.columns = [c.strip().lower() for c in df.columns]
    rename_map = {
        "transaction date": "date", "txn date": "date", "value date": "date",
        "narration": "narration", "description": "narration", "details": "narration",
        "withdrawal amt.": "debit", "withdrawal": "debit", "debit": "debit",
        "deposit amt.": "credit", "deposit": "credit", "credit": "credit",
    }
    df = df.rename(columns={k: v for k, v in rename_map.items() if k in df.columns})
    df["debit"] = pd.to_numeric(df.get("debit", 0), errors="coerce").fillna(0)
    df["date"] = pd.to_datetime(df["date"], errors="coerce", dayfirst=True)
    return df.dropna(subset=["date"])


def summarize(df: pd.DataFrame) -> pd.DataFrame:
    df = df[df["debit"] > 0].copy()
    df["category"] = df["narration"].apply(categorize)
    df["month"] = df["date"].dt.to_period("M")
    pivot = df.pivot_table(
        index="month", columns="category", values="debit",
        aggfunc="sum", fill_value=0,
    )
    pivot["Total"] = pivot.sum(axis=1)
    return pivot.round(0)


if __name__ == "__main__":
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("statement.csv")
    summary = summarize(load_statement(path))
    print(summary.to_string())
    summary.to_csv("upi_summary.csv")
    print("\nSaved upi_summary.csv")
