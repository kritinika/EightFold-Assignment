"""Tests for merger: conflict resolution, provenance, confidence."""
import pytest
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from transformer.merger import merge


def _make_records(*overrides):
    """Build minimal test records."""
    return [dict(r) for r in overrides]


class TestMergeBasic:
    def test_single_record(self):
        records = [{"_source": "csv", "full_name": "Jane Doe", "email": "j@x.com", "skills": []}]
        profile = merge(records)
        assert profile["full_name"] == "Jane Doe"
        assert "j@x.com" in profile["emails"]
        assert profile["candidate_id"].startswith("cand_")

    def test_empty_returns_empty(self):
        assert merge([]) == {}


class TestConflictResolution:
    def test_csv_beats_notes(self):
        records = [
            {"_source": "csv", "full_name": "Jane Smith", "email": "j@x.com", "skills": []},
            {"_source": "notes", "full_name": "Janet Smith", "email": "j@x.com", "skills": []},
        ]
        profile = merge(records)
        # csv has higher priority
        assert profile["full_name"] == "Jane Smith"

    def test_emails_union(self):
        records = [
            {"_source": "csv", "email": "work@acme.com", "full_name": "Jane", "skills": []},
            {"_source": "notes", "email": "personal@gmail.com", "full_name": "Jane", "skills": []},
        ]
        profile = merge(records)
        assert "work@acme.com" in profile["emails"]
        assert "personal@gmail.com" in profile["emails"]

    def test_skills_union(self):
        records = [
            {"_source": "csv", "full_name": "Bob", "email": "b@x.com", "skills": ["Python", "Docker"]},
            {"_source": "ats_json", "full_name": "Bob", "email": "b@x.com", "skills": ["Go", "Kubernetes"]},
        ]
        profile = merge(records)
        skill_names = [s["name"] for s in profile["skills"]]
        assert "Python" in skill_names
        assert "Go" in skill_names


class TestProvenance:
    def test_provenance_populated(self):
        records = [{"_source": "csv", "full_name": "Alice", "email": "a@x.com", "skills": ["Python"]}]
        profile = merge(records)
        prov_fields = [p["field"] for p in profile["provenance"]]
        assert "full_name" in prov_fields
        assert "emails" in prov_fields

    def test_provenance_source_correct(self):
        records = [{"_source": "github", "full_name": "Alice", "email": "a@x.com", "skills": []}]
        profile = merge(records)
        name_prov = next(p for p in profile["provenance"] if p["field"] == "full_name")
        assert name_prov["source"] == "github"


class TestConfidence:
    def test_confidence_in_range(self):
        records = [{"_source": "csv", "full_name": "Alice", "email": "a@x.com", "skills": []}]
        profile = merge(records)
        assert 0.0 <= profile["overall_confidence"] <= 1.0

    def test_multi_source_agreement_boosts_confidence(self):
        single = merge([{"_source": "csv", "full_name": "Alice", "email": "a@x.com", "skills": []}])
        multi = merge([
            {"_source": "csv", "full_name": "Alice", "email": "a@x.com", "skills": []},
            {"_source": "ats_json", "full_name": "Alice", "email": "a@x.com", "skills": []},
        ])
        assert multi["overall_confidence"] >= single["overall_confidence"]


class TestPhoneNormalization:
    def test_phone_normalized_to_e164(self):
        records = [{"_source": "csv", "full_name": "Alice", "email": "a@x.com", "phone": "(415) 555-0101", "skills": []}]
        profile = merge(records)
        assert profile["phones"] == ["+14155550101"]

    def test_unparseable_phone_omitted(self):
        records = [{"_source": "csv", "full_name": "Alice", "email": "a@x.com", "phone": "not-a-phone", "skills": []}]
        profile = merge(records)
        assert profile["phones"] == []


class TestEdgeCases:
    def test_missing_email(self):
        records = [{"_source": "notes", "full_name": "Ghost Candidate", "skills": []}]
        profile = merge(records)
        assert profile["emails"] == []
        assert profile["candidate_id"].startswith("cand_")

    def test_all_fields_null_when_not_provided(self):
        records = [{"_source": "csv", "email": "x@y.com", "skills": []}]
        profile = merge(records)
        assert profile["full_name"] is None
        assert profile["headline"] is None
