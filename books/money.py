import re
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from books.errors import AppError

MAX_PAISE = 10**12


def today_ist() -> date:
    return datetime.now(ZoneInfo("Asia/Kolkata")).date()


def shift_date(value: date, days: int) -> date:
    return value + timedelta(days=days)


def parse_date(value: str) -> date:
    try:
        return datetime.strptime((value or "").strip(), "%Y-%m-%d").date()
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


def pretty_date(value) -> str:
    if isinstance(value, str):
        value = datetime.strptime(value, "%Y-%m-%d").date()
    return value.strftime("%d %b %Y")
