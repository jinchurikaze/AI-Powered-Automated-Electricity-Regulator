"""Bill Check (SRS Feature 11): reading bill text and comparing a bill with recorded use.

The phone reads the photo with ML Kit (on device) and sends only the text; the web version can
also read an uploaded photo with Tesseract if it is installed on the server (optional).
"""
from __future__ import annotations

import re
from datetime import date

MONTHS = {m: i + 1 for i, m in enumerate(["jan", "feb", "mar", "apr", "may", "jun",
                                          "jul", "aug", "sep", "oct", "nov", "dec"])}


def _num(s: str):
    try:
        return float(s.replace(",", ""))
    except ValueError:
        return None


def parse_bill_text(text: str) -> dict:
    """Best-effort extraction of period, kWh used, and amount due. The user always confirms the values."""
    out = {"start": None, "end": None, "kwh": None, "amount": None}
    low = text.lower()
    m = re.search(r"(kwh\s*(used|consumed|consumption)|total\s*kwh|consumption)[^\d]{0,20}([\d,]+(\.\d+)?)", low)
    if m:
        out["kwh"] = _num(m.group(3))
    else:
        m = re.search(r"([\d,]+(\.\d+)?)\s*kwh", low)
        if m:
            out["kwh"] = _num(m.group(1))
    m = re.search(r"(total\s*amount\s*due|amount\s*due|total\s*due|total)[^\d]{0,20}([\d,]+\.\d{2})", low)
    if m:
        out["amount"] = _num(m.group(2))
    named = None
    for m in re.finditer(r"([a-z]{3})[a-z]*\.?\s+(\d{1,2})(,?\s*(\d{4}))?\s*(-|–|to)\s*([a-z]{3})[a-z]*\.?\s+(\d{1,2}),?\s*(\d{4})", low):
        if m.group(1) in MONTHS and m.group(6) in MONTHS:
            named = m
            break
    if named:
        y2 = int(named.group(8))
        m1, m2 = MONTHS[named.group(1)], MONTHS[named.group(6)]
        y1 = int(named.group(4)) if named.group(4) else (y2 - 1 if m1 > m2 else y2)
        out["start"] = date(y1, m1, int(named.group(2)))
        out["end"] = date(y2, m2, int(named.group(7)))
    else:
        m = re.search(r"(\d{1,2})/(\d{1,2})/(\d{4})\s*(-|–|to)\s*(\d{1,2})/(\d{1,2})/(\d{4})", low)
        if m:
            out["start"] = date(int(m.group(3)), int(m.group(1)), int(m.group(2)))
            out["end"] = date(int(m.group(7)), int(m.group(5)), int(m.group(6)))
    return out


def validate_bill(start, end, kwh, amount) -> dict:
    """REQ-BIL-3. Returns field errors; empty when valid."""
    e = {}
    if start is None or end is None or not end > start:
        e["period"] = "Enter a period where the end date is after the start date."
    if kwh is None or kwh <= 0:
        e["kwh"] = "Enter the kWh used, greater than 0."
    if amount is None or amount <= 0:
        e["amount"] = "Enter the total amount, greater than 0."
    return e


def compare(bill_kwh: float, recorded_kwh: float, amount: float) -> dict:
    """REQ-BIL-4: coverage = recorded ÷ billed × 100%; missing kWh and pesos; all-in rate = amount ÷ kWh."""
    rate = amount / bill_kwh if bill_kwh > 0 else 0.0
    gap = bill_kwh - recorded_kwh
    return {"billK": bill_kwh, "appK": recorded_kwh, "gapK": gap, "coverage": recorded_kwh / bill_kwh * 100 if bill_kwh else 0,
            "eff": rate, "gapPeso": gap * rate}


def ocr_image(path: str) -> str | None:
    """Optional: read a bill photo with Tesseract when pytesseract and the tesseract program are installed."""
    try:
        import pytesseract
        from PIL import Image
        return pytesseract.image_to_string(Image.open(path))
    except Exception:
        return None
