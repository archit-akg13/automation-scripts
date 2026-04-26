"""UPI Payment QR Code Generator.

Generates a UPI payment link and QR code (PNG) for a given VPA + amount.
Useful for one-off invoices, donation pages, or "buy me a coffee" buttons.

Usage:
    python upi_qr_generator.py
"""
import urllib.parse
import qrcode


def build_upi_link(payee_vpa: str, payee_name: str, amount: float,
                   note: str = "", txn_ref: str = "") -> str:
    """Build a standards-compliant UPI deep link (upi://pay?...)."""
    params = {
        "pa": payee_vpa,
        "pn": payee_name,
        "am": f"{amount:.2f}",
        "cu": "INR",
    }
    if note:
        params["tn"] = note
    if txn_ref:
        params["tr"] = txn_ref
    return "upi://pay?" + urllib.parse.urlencode(params)


def make_qr_png(upi_link: str, out_path: str = "upi_qr.png") -> str:
    qr = qrcode.QRCode(version=None, box_size=10, border=4,
                       error_correction=qrcode.constants.ERROR_CORRECT_M)
    qr.add_data(upi_link)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    img.save(out_path)
    return out_path


if __name__ == "__main__":
    link = build_upi_link(
        payee_vpa="archit@upi",
        payee_name="Mittal Automation Studio",
        amount=499.00,
        note="Automation consult — 30 min",
        txn_ref="INV-2026-014",
    )
    print("UPI link:", link)
    print("QR saved to:", make_qr_png(link))
