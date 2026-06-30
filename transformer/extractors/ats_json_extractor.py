"""Structured source: ATS JSON blob.
ATS systems use their own field names — we map them to our canonical keys.
Supports both a single object and a list of objects.
"""
import json
import logging
from pathlib import Path
from typing import Any, Optional, Union

logger = logging.getLogger(__name__)

# Known ATS field aliases -> our internal keys
_FIELD_MAP = {
    # name variants
    "name": "full_name", "full_name": "full_name", "candidate_name": "full_name",
    "firstName": "first_name", "first_name": "first_name",
    "lastName": "last_name", "last_name": "last_name",
    # contact
    "email": "email", "emailAddress": "email", "email_address": "email",
    "phone": "phone", "phoneNumber": "phone", "phone_number": "phone", "mobile": "phone",
    # job info
    "currentTitle": "title", "current_title": "title", "title": "title", "jobTitle": "title",
    "currentCompany": "company", "current_company": "company", "company": "company", "employer": "company",
    # location
    "location": "location", "city": "location", "address": "location",
    # links
    "linkedinUrl": "linkedin", "linkedin_url": "linkedin", "linkedin": "linkedin",
    "githubUrl": "github", "github_url": "github", "github": "github",
    "portfolioUrl": "portfolio", "portfolio": "portfolio",
    # content
    "summary": "summary", "bio": "summary", "about": "summary", "headline": "headline",
    "skills": "skills", "skillSet": "skills", "skill_set": "skills",
    # experience
    "experience": "experience", "workHistory": "experience", "work_history": "experience",
    "positions": "experience",
    # education
    "education": "education", "educationHistory": "education",
    # years of experience
    "yearsOfExperience": "years_experience", "years_experience": "years_experience",
    "totalExperience": "years_experience",
}

# Field maps for experience entries
_EXP_MAP = {
    "company": "company", "companyName": "company", "employer": "company",
    "title": "title", "jobTitle": "title", "position": "title", "designation": "title",
    "startDate": "start", "start_date": "start", "start": "start",
    "endDate": "end", "end_date": "end", "end": "end",
    "summary": "summary", "description": "summary",
    "years": "years", "duration": "duration",
}

# Field maps for education entries
_EDU_MAP = {
    "institution": "institution", "school": "institution", "university": "institution", "college": "institution",
    "degree": "degree", "degreeType": "degree",
    "field": "field", "fieldOfStudy": "field", "major": "field",
    "endYear": "end_year", "end_year": "end_year", "graduationYear": "end_year",
}


def _remap(obj: dict, field_map: dict) -> dict:
    result = {}
    for k, v in obj.items():
        canonical = field_map.get(k)
        if canonical and v is not None:
            result[canonical] = v
    return result


def _parse_duration(duration: Any) -> Optional[float]:
    """Parse '3 years', '18 months', '1.5' etc. → float years. Returns None on failure."""
    import re
    if duration is None:
        return None
    s = str(duration).strip().lower()
    # plain number
    try:
        return float(s)
    except ValueError:
        pass
    # "3 years", "3 yrs", "3.5 years"
    m = re.search(r"(\d+(?:\.\d+)?)\s*(?:years?|yrs?)", s)
    if m:
        return float(m.group(1))
    # "18 months"
    m = re.search(r"(\d+(?:\.\d+)?)\s*months?", s)
    if m:
        return round(float(m.group(1)) / 12, 1)
    return None


def _parse_experience(raw: Any) -> list[dict]:
    if not isinstance(raw, list):
        return []
    result = []
    for entry in raw:
        if not isinstance(entry, dict):
            continue
        mapped = _remap(entry, _EXP_MAP)
        # Resolve duration → years
        if "duration" in mapped:
            parsed_yrs = _parse_duration(mapped.pop("duration"))
            if parsed_yrs is not None:
                mapped["years"] = parsed_yrs
        if mapped:
            result.append(mapped)
    return result


def _parse_education(raw: Any) -> list[dict]:
    # Accept both a single object and a list
    if isinstance(raw, dict):
        raw = [raw]
    if not isinstance(raw, list):
        return []
    result = []
    for entry in raw:
        if not isinstance(entry, dict):
            continue
        mapped = _remap(entry, _EDU_MAP)
        if mapped:
            result.append(mapped)
    return result


def _parse_skills(raw: Any) -> list[str]:
    if isinstance(raw, list):
        return [str(s).strip() for s in raw if s]
    if isinstance(raw, str):
        return [s.strip() for s in raw.split(",") if s.strip()]
    return []


def _parse_record(obj: dict) -> dict:
    mapped = _remap(obj, _FIELD_MAP)

    # Reconstruct full_name from first/last if needed
    if "full_name" not in mapped:
        first = mapped.pop("first_name", "")
        last = mapped.pop("last_name", "")
        if first or last:
            mapped["full_name"] = f"{first} {last}".strip()
    else:
        mapped.pop("first_name", None)
        mapped.pop("last_name", None)

    # Parse sub-structures
    if "experience" in mapped:
        mapped["experience"] = _parse_experience(mapped["experience"])
        # If no explicit years_experience, sum up "years" fields from experience entries
        if "years_experience" not in mapped:
            total = sum(
                float(e["years"]) for e in mapped["experience"] if e.get("years") is not None
            )
            if total > 0:
                mapped["years_experience"] = total
        # Remove "years" from individual experience entries (not in canonical schema)
        for e in mapped["experience"]:
            e.pop("years", None)
    if "education" in mapped:
        mapped["education"] = _parse_education(mapped["education"])
    if "skills" in mapped:
        mapped["skills"] = _parse_skills(mapped["skills"])
    else:
        mapped["skills"] = []

    mapped["_source"] = "ats_json"
    return mapped


def extract(source: Union[str, Path]) -> list[dict]:
    try:
        path = Path(source)
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        logger.warning("ATS JSON extractor: cannot read %s — %s", source, e)
        return []

    records = []
    items = data if isinstance(data, list) else [data]
    for i, item in enumerate(items):
        if not isinstance(item, dict):
            logger.warning("ATS JSON extractor: skipping non-object at index %d", i)
            continue
        try:
            records.append(_parse_record(item))
        except Exception as e:
            logger.warning("ATS JSON extractor: error at index %d — %s", i, e)

    return records
