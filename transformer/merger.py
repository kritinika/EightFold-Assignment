"""Merge multiple raw source records for the same candidate into one canonical profile.

Conflict-resolution policy:
  1. Source priority order (highest first): csv > ats_json > github > notes
  2. For scalar fields: highest-priority non-null value wins.
  3. For list fields: union with dedup, preserving priority order.
  4. For structured lists (experience, education): merge by identity (company+title+dates).
  5. Provenance: every field carries its source and method.
"""
from __future__ import annotations

import hashlib
import logging
import re
import uuid
from typing import Any, Optional

from .normalizers import (
    normalize_phones,
    normalize_date,
    normalize_location,
    canonicalize_skills,
)

logger = logging.getLogger(__name__)

# Source priority: lower index = higher authority
SOURCE_PRIORITY = ["csv", "ats_json", "github", "notes"]
SOURCE_CONFIDENCE = {"csv": 0.90, "ats_json": 0.85, "github": 0.80, "notes": 0.55}

# Fields that are lists of scalars
_LIST_FIELDS = {"skills", "emails", "phones"}


def _source_rank(source: str) -> int:
    try:
        return SOURCE_PRIORITY.index(source)
    except ValueError:
        return len(SOURCE_PRIORITY)


def _provenance(field: str, source: str, method: str) -> dict:
    return {"field": field, "source": source, "method": method}


def _name_key(name: str) -> str:
    """Normalized name for dedup matching."""
    return re.sub(r"\s+", " ", name.strip().lower())


def _email_key(email: str) -> str:
    return email.strip().lower()


def _pick_scalar(
    field: str,
    records: list[dict],
) -> tuple[Optional[Any], Optional[str]]:
    """Return (best_value, source) for a scalar field using priority ordering."""
    for source in SOURCE_PRIORITY:
        for r in records:
            if r.get("_source") == source and r.get(field):
                return r[field], source
    # Fallback: any non-null
    for r in records:
        if r.get(field):
            return r[field], r.get("_source", "unknown")
    return None, None


def _merge_list_field(field: str, records: list[dict]) -> tuple[list, list[str]]:
    """Return (merged_list, [sources])."""
    seen: set = set()
    result: list = []
    sources: list[str] = []
    for source in SOURCE_PRIORITY:
        for r in records:
            if r.get("_source") != source:
                continue
            items = r.get(field, [])
            if not isinstance(items, list):
                items = [items] if items else []
            for item in items:
                key = str(item).lower().strip()
                if key and key not in seen:
                    seen.add(key)
                    result.append(item)
                    if source not in sources:
                        sources.append(source)
    return result, sources


def _merge_experience(records: list[dict]) -> list[dict]:
    """Merge experience entries across sources. Dedup by (company, title)."""
    seen: set[tuple] = set()
    result: list[dict] = []
    for source in SOURCE_PRIORITY:
        for r in records:
            if r.get("_source") != source:
                continue
            for exp in r.get("experience", []):
                key = (
                    str(exp.get("company", "")).lower().strip(),
                    str(exp.get("title", "")).lower().strip(),
                )
                if key not in seen:
                    seen.add(key)
                    result.append(exp)
    return result


def _merge_education(records: list[dict]) -> list[dict]:
    seen: set[tuple] = set()
    result: list[dict] = []
    for source in SOURCE_PRIORITY:
        for r in records:
            if r.get("_source") != source:
                continue
            for edu in r.get("education", []):
                key = (
                    str(edu.get("institution", "")).lower().strip(),
                    str(edu.get("degree", "")).lower().strip(),
                )
                if key not in seen:
                    seen.add(key)
                    result.append(edu)
    return result


def _compute_confidence(field: str, sources: list[str], values_agree: bool) -> float:
    """
    Confidence = base confidence of the winning source.
    Bonus +0.08 if 2+ sources agree; penalty −0.15 if sources conflict.
    Clamped to [0.0, 1.0].
    """
    if not sources:
        return 0.0
    base = SOURCE_CONFIDENCE.get(sources[0], 0.5)
    if len(sources) >= 2:
        base += 0.08 if values_agree else -0.15
    return round(max(0.0, min(1.0, base)), 3)


def _overall_confidence(field_confidences: list[float]) -> float:
    if not field_confidences:
        return 0.0
    return round(sum(field_confidences) / len(field_confidences), 3)


def _candidate_id(emails: list[str], name: str) -> str:
    key = (emails[0] if emails else name or "unknown").lower().strip()
    return "cand_" + hashlib.md5(key.encode()).hexdigest()[:12]


def merge(records: list[dict]) -> dict:
    """Merge a list of source records (same candidate) into one canonical profile."""
    if not records:
        return {}

    provenance: list[dict] = []
    field_confidences: list[float] = []

    # ── full_name ──────────────────────────────────────────────
    name_val, name_src = _pick_scalar("full_name", records)
    # Check agreement
    name_values = [r["full_name"] for r in records if r.get("full_name")]
    names_agree = len(set(_name_key(n) for n in name_values)) == 1

    # ── emails ─────────────────────────────────────────────────
    raw_emails: list[str] = []
    email_sources: list[str] = []
    for source in SOURCE_PRIORITY:
        for r in records:
            if r.get("_source") != source:
                continue
            email = r.get("email", "")
            if email and _email_key(email) not in [_email_key(e) for e in raw_emails]:
                raw_emails.append(email.strip().lower())
                if source not in email_sources:
                    email_sources.append(source)

    # ── phones ─────────────────────────────────────────────────
    raw_phones: list[str] = []
    phone_sources: list[str] = []
    for source in SOURCE_PRIORITY:
        for r in records:
            if r.get("_source") != source:
                continue
            phone = r.get("phone", "")
            if phone:
                raw_phones.append(phone)
                if source not in phone_sources:
                    phone_sources.append(source)
    phones = normalize_phones(raw_phones)

    # ── location ───────────────────────────────────────────────
    loc_raw, loc_src = _pick_scalar("location", records)
    location = normalize_location(loc_raw) if loc_raw else {"city": None, "region": None, "country": None}

    # ── links ──────────────────────────────────────────────────
    linkedin, li_src = _pick_scalar("linkedin", records)
    github, gh_src = _pick_scalar("github", records)
    portfolio, pf_src = _pick_scalar("portfolio", records)

    # ── headline ───────────────────────────────────────────────
    headline, hl_src = _pick_scalar("headline", records)
    if not headline:
        title_val, title_src = _pick_scalar("title", records)
        if title_val:
            company_val, _ = _pick_scalar("company", records)
            headline = f"{title_val} at {company_val}" if company_val else title_val
            hl_src = title_src

    # ── years_experience ──────────────────────────────────────
    yoe_val, yoe_src = _pick_scalar("years_experience", records)
    if yoe_val is not None:
        try:
            yoe_val = float(yoe_val)
        except (TypeError, ValueError):
            yoe_val = None

    # ── skills ─────────────────────────────────────────────────
    raw_skill_lists = [(r.get("skills", []), r.get("_source", "unknown")) for r in records]
    all_skills_raw: list[str] = []
    skill_sources: list[str] = []
    for skills_list, source in sorted(raw_skill_lists, key=lambda x: _source_rank(x[1])):
        for s in skills_list:
            if s not in all_skills_raw:
                all_skills_raw.append(s)
                if source not in skill_sources:
                    skill_sources.append(source)
    canonical_skills = canonicalize_skills(all_skills_raw)
    skills_with_meta = [
        {"name": s, "confidence": SOURCE_CONFIDENCE.get(skill_sources[0] if skill_sources else "notes", 0.5),
         "sources": skill_sources}
        for s in canonical_skills
    ]

    # ── experience ─────────────────────────────────────────────
    experience_raw = _merge_experience(records)
    experience = []
    for exp in experience_raw:
        experience.append({
            "company": exp.get("company"),
            "title": exp.get("title"),
            "start": normalize_date(exp.get("start")) if exp.get("start") else None,
            "end": normalize_date(exp.get("end")) if exp.get("end") else None,
            "summary": exp.get("summary"),
        })

    # ── education ──────────────────────────────────────────────
    education_raw = _merge_education(records)
    education = []
    for edu in education_raw:
        end_year = edu.get("end_year")
        if end_year:
            try:
                end_year = int(str(end_year)[:4])
            except (ValueError, TypeError):
                end_year = None
        education.append({
            "institution": edu.get("institution"),
            "degree": edu.get("degree"),
            "field": edu.get("field"),
            "end_year": end_year,
        })

    # ── summary ────────────────────────────────────────────────
    summary_val, summary_src = _pick_scalar("summary", records)

    # ── provenance ─────────────────────────────────────────────
    def add_prov(field, src, method="direct"):
        if src:
            provenance.append(_provenance(field, src, method))

    add_prov("full_name", name_src)
    add_prov("emails", email_sources[0] if email_sources else None)
    add_prov("phones", phone_sources[0] if phone_sources else None)
    add_prov("location", loc_src)
    add_prov("linkedin", li_src)
    add_prov("github", gh_src)
    add_prov("headline", hl_src)
    add_prov("skills", skill_sources[0] if skill_sources else None, "union")
    add_prov("years_experience", yoe_src)
    add_prov("summary", summary_src)

    # ── field confidences ──────────────────────────────────────
    def fc(sources, agree=True):
        c = _compute_confidence("", sources, agree)
        field_confidences.append(c)
        return c

    profile: dict = {
        "candidate_id": _candidate_id(raw_emails, name_val or ""),
        "full_name": name_val,
        "emails": raw_emails,
        "phones": phones,
        "location": location,
        "links": {
            "linkedin": linkedin,
            "github": github,
            "portfolio": portfolio,
            "other": [],
        },
        "headline": headline,
        "years_experience": yoe_val,
        "skills": skills_with_meta,
        "experience": experience,
        "education": education,
        "summary": summary_val,
        "provenance": provenance,
        "overall_confidence": 0.0,  # filled below
        "_sources_used": list({r.get("_source", "unknown") for r in records}),
    }

    # Compute overall confidence from key fields
    fc(email_sources)
    fc([name_src] if name_src else [], names_agree)
    fc(phone_sources)
    fc([loc_src] if loc_src else [])
    fc(skill_sources)
    profile["overall_confidence"] = _overall_confidence(field_confidences)

    return profile
