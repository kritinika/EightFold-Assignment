"""Schema validation for canonical profiles and projected output.
Validates types, required fields, and formats. Returns a list of violation messages.
"""
from __future__ import annotations

import re
from typing import Any

_EMAIL_RE = re.compile(r"[^@]+@[^@]+\.[^@]+")
_E164_RE = re.compile(r"^\+[1-9]\d{6,14}$")


def _check_type(value: Any, expected: str, path: str) -> list[str]:
    errs = []
    if expected == "string" and not isinstance(value, str):
        errs.append(f"{path}: expected string, got {type(value).__name__}")
    elif expected == "string[]":
        if not isinstance(value, list):
            errs.append(f"{path}: expected list, got {type(value).__name__}")
        else:
            for i, v in enumerate(value):
                if not isinstance(v, str):
                    errs.append(f"{path}[{i}]: expected string, got {type(v).__name__}")
    elif expected == "number" and not isinstance(value, (int, float)):
        errs.append(f"{path}: expected number, got {type(value).__name__}")
    elif expected == "object" and not isinstance(value, dict):
        errs.append(f"{path}: expected object, got {type(value).__name__}")
    return errs


def validate_canonical(profile: dict) -> list[str]:
    """Validate the canonical profile against the default schema. Returns list of issues."""
    errs: list[str] = []

    if not isinstance(profile, dict):
        return ["Profile is not a dict"]

    # candidate_id
    if not profile.get("candidate_id"):
        errs.append("candidate_id: missing or empty")

    # emails: list of valid-looking email strings
    emails = profile.get("emails", [])
    if not isinstance(emails, list):
        errs.append("emails: must be a list")
    else:
        for i, e in enumerate(emails):
            if not isinstance(e, str) or not _EMAIL_RE.match(e):
                errs.append(f"emails[{i}]: invalid email format: {e!r}")

    # phones: list of E.164 strings
    phones = profile.get("phones", [])
    if not isinstance(phones, list):
        errs.append("phones: must be a list")
    else:
        for i, p in enumerate(phones):
            if not isinstance(p, str) or not _E164_RE.match(p):
                errs.append(f"phones[{i}]: not E.164 format: {p!r}")

    # location: object with city/region/country
    location = profile.get("location")
    if location is not None:
        if not isinstance(location, dict):
            errs.append("location: must be an object")
        else:
            for key in ("city", "region", "country"):
                v = location.get(key)
                if v is not None and not isinstance(v, str):
                    errs.append(f"location.{key}: must be string or null")

    # skills: list of objects with name/confidence/sources
    skills = profile.get("skills", [])
    if not isinstance(skills, list):
        errs.append("skills: must be a list")
    else:
        for i, s in enumerate(skills):
            if not isinstance(s, dict):
                errs.append(f"skills[{i}]: must be an object")
            elif not s.get("name"):
                errs.append(f"skills[{i}]: missing name")

    # experience: list of objects
    experience = profile.get("experience", [])
    if not isinstance(experience, list):
        errs.append("experience: must be a list")

    # education: list of objects
    education = profile.get("education", [])
    if not isinstance(education, list):
        errs.append("education: must be a list")

    # overall_confidence: number 0-1
    oc = profile.get("overall_confidence")
    if oc is not None:
        if not isinstance(oc, (int, float)):
            errs.append("overall_confidence: must be a number")
        elif not (0.0 <= float(oc) <= 1.0):
            errs.append(f"overall_confidence: out of range [0,1]: {oc}")

    return errs


def validate_projected(output: dict, config: dict) -> list[str]:
    """Validate projected output against the field specs in config."""
    errs: list[str] = []
    fields = config.get("fields", [])
    on_missing = config.get("on_missing", "null")

    for spec in fields:
        path = spec.get("path")
        if not path:
            continue
        required = spec.get("required", False)
        type_hint = spec.get("type")
        value = output.get(path)

        if value is None:
            if required and on_missing != "omit":
                errs.append(f"{path}: required field is null/missing")
        elif type_hint:
            errs.extend(_check_type(value, type_hint, path))

    return errs
