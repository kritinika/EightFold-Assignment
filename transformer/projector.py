"""Runtime config projector.

Config schema:
{
  "fields": [
    {
      "path": "output_field_name",        # required — output key
      "from": "canonical.path[0].sub",    # optional — source path in canonical; defaults to path
      "type": "string|string[]|number|object",  # optional — for coercion
      "normalize": "E164|canonical|...",  # optional
      "required": true|false              # optional — error if missing
    }
  ],
  "include_confidence": true|false,       # default true
  "include_provenance": true|false,       # default true
  "on_missing": "null|omit|error"         # default "null"
}
"""
from __future__ import annotations

import re
import logging
from typing import Any, Optional

from .normalizers import normalize_phone, canonicalize_skill

logger = logging.getLogger(__name__)


# ── Path resolution ────────────────────────────────────────────────────────────

_INDEX_RE = re.compile(r"^(.+?)\[(\d+)\]$")
_SLICE_RE = re.compile(r"^(.+?)\[\]\.(.+)$")


def _resolve_path(obj: Any, path: str) -> Any:
    """
    Resolve a dot-notated path with optional index and slice notation.
    Examples:
      "emails[0]"         -> first email
      "skills[].name"     -> list of skill names
      "location.country"  -> nested field
    """
    # Slice: "skills[].name"
    m = _SLICE_RE.match(path)
    if m:
        collection = _resolve_path(obj, m.group(1))
        subfield = m.group(2)
        if isinstance(collection, list):
            return [_resolve_path(item, subfield) for item in collection]
        return None

    parts = path.split(".", 1)
    key = parts[0]
    rest = parts[1] if len(parts) > 1 else None

    # Index notation: "emails[0]"
    idx_m = _INDEX_RE.match(key)
    if idx_m:
        key = idx_m.group(1)
        idx = int(idx_m.group(2))
        collection = obj.get(key) if isinstance(obj, dict) else None
        if isinstance(collection, list) and idx < len(collection):
            val = collection[idx]
        else:
            val = None
        return _resolve_path(val, rest) if rest else val

    if isinstance(obj, dict):
        val = obj.get(key)
    else:
        val = None

    return _resolve_path(val, rest) if rest and val is not None else val


# ── Type coercion ──────────────────────────────────────────────────────────────

def _coerce(value: Any, type_hint: Optional[str]) -> Any:
    if value is None or type_hint is None:
        return value
    if type_hint == "string":
        return str(value) if not isinstance(value, str) else value
    if type_hint == "string[]":
        if isinstance(value, list):
            return [str(v) for v in value]
        return [str(value)]
    if type_hint == "number":
        try:
            return float(value)
        except (TypeError, ValueError):
            return None
    if type_hint == "object":
        return value if isinstance(value, dict) else None
    return value


# ── Field-level normalization ─────────────────────────────────────────────────

def _apply_normalize(value: Any, normalize: Optional[str]) -> Any:
    if not normalize or value is None:
        return value
    if normalize == "E164":
        if isinstance(value, list):
            return [normalize_phone(v) or v for v in value]
        return normalize_phone(str(value)) or value
    if normalize == "canonical":
        if isinstance(value, list):
            return [canonicalize_skill(v) or v for v in value]
        return canonicalize_skill(str(value)) or value
    return value


# ── Projection ────────────────────────────────────────────────────────────────

class ProjectionError(Exception):
    pass


def project(canonical: dict, config: dict) -> dict:
    """Apply runtime config to the canonical profile and return the output record."""
    fields = config.get("fields")
    include_confidence = config.get("include_confidence", True)
    include_provenance = config.get("include_provenance", True)
    on_missing = config.get("on_missing", "null")

    # If no fields config provided, return the full canonical profile as-is
    if not fields:
        result = dict(canonical)
        if not include_confidence:
            result.pop("overall_confidence", None)
        if not include_provenance:
            result.pop("provenance", None)
        return result

    result: dict = {}
    errors: list[str] = []

    for field_spec in fields:
        output_path = field_spec.get("path")
        if not output_path:
            continue

        source_path = field_spec.get("from", output_path)
        type_hint = field_spec.get("type")
        normalize = field_spec.get("normalize")
        required = field_spec.get("required", False)

        value = _resolve_path(canonical, source_path)
        value = _coerce(value, type_hint)
        value = _apply_normalize(value, normalize)

        if value is None or value == [] or value == "":
            if required:
                if on_missing == "error":
                    errors.append(f"Required field '{output_path}' is missing")
                    continue
                elif on_missing == "omit":
                    continue
                else:
                    result[output_path] = None
            elif on_missing == "omit":
                continue
            else:
                result[output_path] = None
        else:
            result[output_path] = value

    if errors:
        raise ProjectionError("; ".join(errors))

    if include_confidence:
        result["overall_confidence"] = canonical.get("overall_confidence")
    if include_provenance:
        result["provenance"] = canonical.get("provenance", [])

    return result
