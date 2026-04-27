"""
Split a GST-inclusive amount into base + tax components.

For intra-state invoices, GST splits into CGST (half) + SGST (half).
For inter-state invoices, the full GST goes into IGST.

Usage:
    >>> split_gst(118.0, rate=18, inter_state=False)
    {'base': 100.0, 'cgst': 9.0, 'sgst': 9.0, 'igst': 0.0, 'total': 118.0}
    >>> split_gst(118.0, rate=18, inter_state=True)
    {'base': 100.0, 'cgst': 0.0, 'sgst': 0.0, 'igst': 18.0, 'total': 118.0}
"""
from decimal import Decimal, ROUND_HALF_UP
from typing import Dict


def _round2(x: Decimal) -> float:
    return float(x.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def split_gst(total: float, rate: float = 18.0, inter_state: bool = False) -> Dict[str, float]:
    """Split a GST-inclusive total into its base and tax components.

    Args:
        total: The GST-inclusive invoice amount in INR.
        rate: GST rate as a percentage (5, 12, 18, 28). Defaults to 18.
        inter_state: True for IGST (inter-state), False for CGST+SGST.

    Returns:
        Dict with 'base', 'cgst', 'sgst', 'igst', and 'total' keys.
    """
    if total < 0:
        raise ValueError("total must be non-negative")
    if rate not in (0, 5, 12, 18, 28):
        raise ValueError(f"unsupported GST rate: {rate}")

    t = Decimal(str(total))
    r = Decimal(str(rate))
    base = t * Decimal("100") / (Decimal("100") + r)
    tax = t - base

    if inter_state:
        cgst = sgst = Decimal("0")
        igst = tax
    else:
        cgst = sgst = tax / Decimal("2")
        igst = Decimal("0")

    return {
        "base": _round2(base),
        "cgst": _round2(cgst),
        "sgst": _round2(sgst),
        "igst": _round2(igst),
        "total": _round2(t),
    }


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python gst_split.py <amount> [rate] [--inter-state]")
        sys.exit(1)
    amount = float(sys.argv[1])
    rate = float(sys.argv[2]) if len(sys.argv) > 2 and not sys.argv[2].startswith("--") else 18.0
    inter = "--inter-state" in sys.argv
    result = split_gst(amount, rate=rate, inter_state=inter)
    for key, value in result.items():
        print(f"{key:>6}: Rs {value:,.2f}")
