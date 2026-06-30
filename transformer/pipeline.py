"""Main pipeline orchestrator.

Pipeline stages:
  1. Detect  — resolve which sources are present
  2. Extract — parse each source into raw records
  3. Group   — cluster raw records by candidate identity (email match, then name similarity)
  4. Normalize — normalize raw fields before merging
  5. Merge   — merge records per candidate into a canonical profile
  6. Project — apply runtime config to reshape output
  7. Validate — check canonical and projected output; log warnings on violations
"""
from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any, Optional

from .extractors import CsvExtractor, AtsJsonExtractor, GitHubExtractor, NotesExtractor
from .merger import merge
from .projector import project, ProjectionError
from .validator import validate_canonical, validate_projected

logger = logging.getLogger(__name__)


# ── Source detection ────────────────────────────────────────────────────────────

def _is_github_url(s: str) -> bool:
    return bool(re.match(r"https?://(?:www\.)?github\.com/", s.strip()))


def _is_linkedin_url(s: str) -> bool:
    return bool(re.match(r"https?://(?:www\.)?linkedin\.com/", s.strip()))


# ── Identity grouping ───────────────────────────────────────────────────────────

def _name_tokens(name: str) -> set[str]:
    return set(re.sub(r"[^a-z\s]", "", name.lower()).split())


def _records_match(a: dict, b: dict) -> bool:
    """Two records are for the same candidate if they share an email, or strong name overlap."""
    emails_a = {(a.get("email") or "").lower().strip()}
    emails_b = {(b.get("email") or "").lower().strip()}
    emails_a.discard("")
    emails_b.discard("")
    if emails_a and emails_b and emails_a & emails_b:
        return True

    name_a = a.get("full_name", "")
    name_b = b.get("full_name", "")
    if name_a and name_b:
        ta, tb = _name_tokens(name_a), _name_tokens(name_b)
        if ta and tb:
            overlap = len(ta & tb) / max(len(ta), len(tb))
            if overlap >= 0.75:
                return True
    return False


def _has_identity(record: dict) -> bool:
    """A record must have at least an email or a name to be a standalone candidate."""
    return bool(record.get("email") or record.get("full_name"))


def _group_records(records: list[dict]) -> list[list[dict]]:
    """Union-find grouping of records by identity.
    Records with no email AND no name are merged into the best-matching group
    if one exists, otherwise discarded — they cannot stand alone as a candidate.
    """
    groups: list[list[dict]] = []
    no_identity = []

    for record in records:
        if not _has_identity(record):
            no_identity.append(record)
            continue
        placed = False
        for group in groups:
            if any(_records_match(record, existing) for existing in group):
                group.append(record)
                placed = True
                break
        if not placed:
            groups.append([record])

    # Try to attach anonymous records (e.g. generic notes) to an existing group
    # by merging into the first group from the same source batch — or drop them.
    for record in no_identity:
        # If there's exactly one candidate group, it's almost certainly about them
        if len(groups) == 1:
            groups[0].append(record)
        # Otherwise we can't know who it belongs to — drop it to avoid phantom candidates
        else:
            logger.warning(
                "Dropping anonymous record from source '%s' — no email or name to match on",
                record.get("_source", "unknown"),
            )
    return groups


# ── Pipeline ────────────────────────────────────────────────────────────────────

class Pipeline:
    def __init__(self, config: Optional[dict] = None):
        self.config = config or {}

    def run(
        self,
        csv_path: Optional[str] = None,
        ats_json_path: Optional[str] = None,
        github_urls: Optional[list[str]] = None,
        notes_paths: Optional[list[str]] = None,
    ) -> list[dict]:
        """
        Run the full pipeline and return a list of projected output profiles.
        Any missing or malformed source is skipped gracefully.
        """
        all_records: list[dict] = []

        # ── Stage 1: Extract ───────────────────────────────────
        if csv_path:
            logger.info("Extracting CSV: %s", csv_path)
            records = CsvExtractor.extract(csv_path)
            logger.info("  → %d records", len(records))
            all_records.extend(records)

        if ats_json_path:
            logger.info("Extracting ATS JSON: %s", ats_json_path)
            records = AtsJsonExtractor.extract(ats_json_path)
            logger.info("  → %d records", len(records))
            all_records.extend(records)

        for url in (github_urls or []):
            logger.info("Extracting GitHub: %s", url)
            record = GitHubExtractor.extract(url)
            if record:
                all_records.append(record)

        for path in (notes_paths or []):
            logger.info("Extracting notes: %s", path)
            record = NotesExtractor.extract(path)
            if record:
                all_records.append(record)

        if not all_records:
            logger.warning("No records extracted from any source.")
            return []

        # ── Stage 2: Group by candidate identity ───────────────
        groups = _group_records(all_records)
        logger.info("Grouped %d raw records into %d candidate(s)", len(all_records), len(groups))

        # ── Stage 3: Merge + Project per candidate ─────────────
        results: list[dict] = []
        for i, group in enumerate(groups):
            try:
                canonical = merge(group)
            except Exception as e:
                logger.error("Merge failed for group %d: %s", i, e)
                continue

            # Validate canonical
            errs = validate_canonical(canonical)
            for err in errs:
                logger.warning("Canonical validation [%s]: %s", canonical.get("candidate_id", f"group_{i}"), err)

            # Project
            try:
                output = project(canonical, self.config)
            except ProjectionError as e:
                logger.error("Projection error for %s: %s", canonical.get("candidate_id"), e)
                output = canonical  # fall back to full canonical

            # Validate projected
            if self.config.get("fields"):
                proj_errs = validate_projected(output, self.config)
                for err in proj_errs:
                    logger.warning("Projected validation [%s]: %s", canonical.get("candidate_id"), err)

            results.append(output)

        return results
