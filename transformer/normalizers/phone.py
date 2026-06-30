"""E.164 phone normalization. Returns None on unparseable input — never invents."""
from typing import Optional
import phonenumbers


def normalize_phone(raw: str, default_region: str = "US") -> Optional[str]:
    if not raw or not raw.strip():
        return None
    raw = raw.strip()
    # Try caller-specified region first, then common fallbacks for unformatted numbers
    for region in [default_region, "IN", "GB", "AU", "CA"]:
        try:
            parsed = phonenumbers.parse(raw, region)
            if phonenumbers.is_valid_number(parsed):
                return phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)
        except phonenumbers.NumberParseException:
            pass
    return None


def normalize_phones(raws: list[str], default_region: str = "US") -> list[str]:
    seen = set()
    result = []
    for r in raws:
        n = normalize_phone(r, default_region)
        if n and n not in seen:
            seen.add(n)
            result.append(n)
    return result
