"""Presentation rounding policy shared by UI and exports.

Engines compute in float64 and stay unrounded. Displayed money is rounded half-up to
cents through ``Decimal`` so that deterministic figures match hand calculations.
"""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

CENT = Decimal("0.01")


def to_cents(value: float) -> Decimal:
    # repr-round first so 156.79999999999998 is treated as 156.80
    return Decimal(repr(round(float(value), 9))).quantize(CENT, rounding=ROUND_HALF_UP)


def money(value: float | None, *, signed: bool = False) -> str:
    if value is None:
        return "Not supplied"
    d = to_cents(value)
    if d == 0:
        d = abs(d)
    text = f"${abs(d):,.2f}"
    if d < 0:
        return f"-{text}"
    return f"+{text}" if signed and d > 0 else text


def pct(value: float | None, digits: int = 0) -> str:
    if value is None:
        return "—"
    return f"{value * 100:.{digits}f}%"


def num(value: float, digits: int = 1) -> str:
    text = f"{value:,.{digits}f}"
    return text.rstrip("0").rstrip(".") if "." in text else text
