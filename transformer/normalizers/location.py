"""Location normalization: best-effort city/region extraction + ISO-3166-1 alpha-2 country."""
from typing import Optional
import re
import pycountry


# Common country name aliases not in pycountry
_ALIASES: dict[str, str] = {
    "usa": "US", "us": "US", "united states": "US", "u.s.": "US", "u.s.a.": "US",
    "uk": "GB", "united kingdom": "GB", "england": "GB",
    "uae": "AE", "emirates": "AE",
}


def _lookup_country(token: str) -> Optional[str]:
    token_clean = token.strip().lower().rstrip(".")
    if token_clean in _ALIASES:
        return _ALIASES[token_clean]
    # pycountry alpha-2 lookup
    if len(token_clean) == 2:
        c = pycountry.countries.get(alpha_2=token_clean.upper())
        if c:
            return c.alpha_2
    # pycountry name fuzzy
    try:
        results = pycountry.countries.search_fuzzy(token_clean)
        if results:
            return results[0].alpha_2
    except LookupError:
        pass
    return None


def normalize_location(raw: str) -> dict:
    """Return {city, region, country} — any field may be None."""
    if not raw or not raw.strip():
        return {"city": None, "region": None, "country": None}

    parts = [p.strip() for p in re.split(r"[,/|]", raw) if p.strip()]
    # If still one part (no delimiters), try splitting by spaces — last token may be country/state
    if len(parts) == 1 and " " in parts[0]:
        tokens = parts[0].split()
        parts = []
        buf = []
        for t in tokens:
            c = _lookup_country(t)
            if c and not parts:
                if buf:
                    parts.append(" ".join(buf))
                    buf = []
                parts.append(t)  # will be resolved as country below
            else:
                buf.append(t)
        if buf:
            parts.insert(0, " ".join(buf))
    country = None
    region = None
    city = None

    # Try to identify country from last token backwards
    for i in range(len(parts) - 1, -1, -1):
        c = _lookup_country(parts[i])
        if c:
            country = c
            parts.pop(i)
            break

    if len(parts) >= 2:
        city = parts[0]
        region = parts[1]
    elif len(parts) == 1:
        city = parts[0]

    return {"city": city, "region": region, "country": country}
