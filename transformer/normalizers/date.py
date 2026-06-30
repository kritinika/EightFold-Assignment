"""Date normalization to YYYY-MM. Returns None on unparseable input."""
from typing import Optional
import re
from dateutil import parser as dateutil_parser


def normalize_date(raw: str) -> Optional[str]:
    if not raw or not str(raw).strip():
        return None
    raw = str(raw).strip()

    # already YYYY-MM
    if re.fullmatch(r"\d{4}-\d{2}", raw):
        return raw

    # YYYY only
    if re.fullmatch(r"\d{4}", raw):
        return f"{raw}-01"

    # "Present" / "Current" / "Now"
    if raw.lower() in ("present", "current", "now", "ongoing", "today"):
        return None  # caller interprets None end date as current

    try:
        dt = dateutil_parser.parse(raw, default=dateutil_parser.parse("1900-01-01"))
        return dt.strftime("%Y-%m")
    except (ValueError, OverflowError):
        return None
