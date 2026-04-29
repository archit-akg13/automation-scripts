"""GST Invoice PDF Extractor

Walks a folder of PDF invoices, extracts vendor/buyer GSTINs, invoice number,
date, and total amount, and writes a clean CSV.

Usage:
    pip install pdfplumber
    python gst_invoice_extractor.py ./invoices

Valid GSTIN format: <2-digit state><5-letter PAN><4-digit><1-letter><1 alnum>Z<1 alnum>
State codes 1-38 cover every Indian state and union territory.
"""
import re
import sys
import csv
from pathlib import Path

import pdfplumber

GSTIN_RE = re.compile(r'\b(\d{2}[A-Z]{5}\d{4}[A-Z][A-Z\d]Z[A-Z\d])\b')
INV_NUM_RE = re.compile(
    r'Invoice\s*(?:No\.?|Number|#)\s*[:\-]?\s*([A-Z0-9\-/]+)', re.I
)
DATE_RE = re.compile(r'(\d{2}[\-/]\d{2}[\-/]\d{4})')
AMOUNT_RE = re.compile(
    r'(?:Grand\s*Total|Total|Amount)[^\d]*(?:Rs\.?|INR)?\s*([\d,]+\.\d{0,2})',
    re.I,
)


def is_valid_gstin(gstin: str) -> bool:
    """Sanity check the 15-character GSTIN format and state code."""
    if len(gstin) != 15:
        return False
    state = int(gstin[:2])
    return 1 <= state <= 38


def extract_from_pdf(path: Path) -> dict:
    """Pull GSTINs, invoice number, date, and total from one PDF."""
    text = ''
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            text += (page.extract_text() or '') + '\n'
    gstins = [g for g in GSTIN_RE.findall(text) if is_valid_gstin(g)]
    inv = INV_NUM_RE.search(text)
    date = DATE_RE.search(text)
    amounts = [float(a.replace(',', '')) for a in AMOUNT_RE.findall(text)]
    return {
        'file': path.name,
        'vendor_gstin': gstins[0] if gstins else '',
        'buyer_gstin': gstins[1] if len(gstins) > 1 else '',
        'invoice_no': inv.group(1) if inv else '',
        'date': date.group(1) if date else '',
        'total_inr': max(amounts, default=0.0),
    }


def main(folder: str) -> None:
    rows = [extract_from_pdf(p) for p in sorted(Path(folder).glob('*.pdf'))]
    if not rows:
        print('No PDFs found.')
        return
    out = Path(folder) / 'invoices_extracted.csv'
    with out.open('w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
    print(f'Processed {len(rows)} invoices then wrote {out}')


if __name__ == '__main__':
    main(sys.argv[1] if len(sys.argv) > 1 else '.')
