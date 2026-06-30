"""Structured source: recruiter CSV export.
Expected columns (case-insensitive): name/full_name, email, phone, current_company/company, title/job_title, location, linkedin, github, skills
"""
import csv
import io
import logging
import re
from typing import Optional, Union
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# Maps known CSV column names to our internal keys
_COL_MAP = {
    "name": "full_name", "full_name": "full_name", "fullname": "full_name",
    "email": "email", "email_address": "email",
    "phone": "phone", "phone_number": "phone", "mobile": "phone",
    "current_company": "company", "company": "company", "employer": "company",
    "title": "title", "job_title": "title", "position": "title", "role": "title",
    "location": "location", "city": "location",
    "linkedin": "linkedin", "linkedin_url": "linkedin",
    "github": "github", "github_url": "github",
    "skills": "skills",
    "summary": "summary", "bio": "summary",
}


def _map_row(row: dict) -> dict:
    mapped: dict = {}
    for k, v in row.items():
        canonical = _COL_MAP.get(k.strip().lower().replace(" ", "_"))
        if canonical and v and str(v).strip():
            mapped[canonical] = str(v).strip()
    return mapped


def extract(source: Union[str, Path]) -> list[dict]:
    """Parse CSV and return list of raw candidate dicts."""
    try:
        path = Path(source)
        text = path.read_text(encoding="utf-8-sig")  # handle BOM
    except Exception as e:
        logger.warning("CSV extractor: cannot read %s — %s", source, e)
        return []

    records = []
    try:
        reader = csv.DictReader(io.StringIO(text))
        for i, row in enumerate(reader):
            try:
                mapped = _map_row(row)
                if not mapped:
                    continue
                # skills may be comma or pipe-separated inside the cell
                if "skills" in mapped:
                    raw_skills = re.split(r"[,|]", mapped["skills"])
                    mapped["skills"] = [s.strip() for s in raw_skills if s.strip()]
                else:
                    mapped["skills"] = []
                mapped["_source"] = "csv"
                mapped["_source_row"] = i
                records.append(mapped)
            except Exception as row_err:
                logger.warning("CSV extractor: skipping row %d — %s", i, row_err)
    except Exception as e:
        logger.warning("CSV extractor: parse error — %s", e)

    return records
