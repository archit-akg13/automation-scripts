import re
import sys
from pathlib import Path
from datetime import datetime
import pdfplumber

DATE_RE = re.compile(r"(\d{1,2})[\-/\s]([A-Za-z]{3,9}|\d{1,2})[\-/\s](\d{2,4})")
GSTIN_RE = re.compile(r"\b\d{2}[A-Z]{5}\d{4}[A-Z][A-Z\d]Z[A-Z\d]\b")
INV_RE = re.compile(r"(?:Invoice\s*(?:No\.?|#|Number)\s*[:\-]?\s*)([A-Z0-9\-/]+)", re.I)
AMT_RE = re.compile(r"(?:Total|Grand\s*Total|Amount\s*Payable)[^\d₹]{0,15}₹?\s*([\d,]+\.?\d{0,2})", re.I)


def parse_date(text):
    m = DATE_RE.search(text)
    if not m:
        return None
    raw = m.group(0)
    for fmt in ("%d-%m-%Y", "%d/%m/%Y", "%d %b %Y", "%d %B %Y", "%d-%b-%Y"):
        try:
            return datetime.strptime(raw, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return None


def vendor_from_gstin(text):
    m = GSTIN_RE.search(text)
    if not m:
        return None
    line = next((l for l in text.splitlines() if m.group(0) in l), "")
    parts = [p.strip() for p in line.split(m.group(0)) if p.strip()]
    return re.sub(r"[^A-Za-z0-9]+", "", parts[0])[:20] if parts else None


def extract(pdf_path):
    with pdfplumber.open(pdf_path) as pdf:
        text = "\n".join((p.extract_text() or "") for p in pdf.pages[:2])
    inv = INV_RE.search(text)
    amt = AMT_RE.search(text)
    return {
        "date": parse_date(text) or "NoDate",
        "vendor": vendor_from_gstin(text) or "UnknownVendor",
        "invoice": (inv.group(1) if inv else "NoInv").replace("/", "-"),
        "amount": (amt.group(1).replace(",", "").split(".")[0] if amt else "0"),
    }


def safe_rename(src, new_name):
    dest = src.with_name(f"{new_name}.pdf")
    n = 1
    while dest.exists() and dest != src:
        dest = src.with_name(f"{new_name}_{n}.pdf")
        n += 1
    src.rename(dest)
    return dest.name


def main(folder):
    folder = Path(folder)
    for pdf in folder.glob("*.pdf"):
        try:
            f = extract(pdf)
            new = f"{f['date']}_{f['vendor']}_{f['invoice']}_{f['amount']}"
            renamed = safe_rename(pdf, new)
            print(f"OK {pdf.name} -> {renamed}")
        except Exception as e:
            print(f"FAIL {pdf.name}: {e}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else ".")
