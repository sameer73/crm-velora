import re
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from app.errors import AppError

MAX_PAISE = 10**12


def today_ist() -> str:
    return datetime.now(ZoneInfo("Asia/Kolkata")).date().isoformat()


def shift_date(value: str, days: int) -> str:
    parsed = datetime.strptime(parse_date(value), "%Y-%m-%d").date()
    return (parsed + timedelta(days=days)).isoformat()


def parse_date(value: str) -> str:
    try:
        return datetime.strptime((value or "").strip(), "%Y-%m-%d").date().isoformat()
    except ValueError:
        raise AppError("Enter a valid date") from None


def check_paise(paise: int, label: str = "Amount") -> int:
    if not isinstance(paise, int) or isinstance(paise, bool):
        raise AppError(f"{label} must be a whole number of paise")
    if paise < 0:
        raise AppError(f"{label} cannot be negative")
    if paise > MAX_PAISE:
        raise AppError(f"{label} is too large")
    return paise


def parse_rupees(value: str, label: str = "Amount") -> int:
    text = (value or "").strip().replace(",", "").replace("₹", "").replace(" ", "")
    if not text:
        raise AppError(f"Enter {label.lower()}")
    if not re.fullmatch(r"\d+(\.\d{1,2})?", text):
        raise AppError(f"{label} should look like 150 or 150.50")
    whole, _, frac = text.partition(".")
    paise = int(whole) * 100 + int((frac + "00")[:2])
    return check_paise(paise, label)


def parse_whole(value: str, label: str) -> int:
    text = (value or "").strip()
    if not re.fullmatch(r"-?\d+", text):
        raise AppError(f"{label} must be a whole number")
    return int(text)


def format_inr(paise: int) -> str:
    sign = "-" if int(paise) < 0 else ""
    rupees, frac = divmod(abs(int(paise)), 100)
    digits = str(rupees)
    if len(digits) > 3:
        head, tail = digits[:-3], digits[-3:]
        parts: list[str] = []
        while head:
            parts.append(head[-2:])
            head = head[:-2]
        digits = ",".join(reversed(parts)) + "," + tail
    return f"{sign}₹{digits}.{frac:02d}"


def paise_to_input(paise: int) -> str:
    rupees, frac = divmod(abs(int(paise)), 100)
    return f"{rupees}.{frac:02d}"


def pretty_date(value: str) -> str:
    return datetime.strptime(value, "%Y-%m-%d").strftime("%d %b %Y")
