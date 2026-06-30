"""Tests for projector: field selection, renaming, normalization, on_missing."""
import pytest
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from transformer.projector import project, ProjectionError

_CANONICAL = {
    "candidate_id": "cand_abc123",
    "full_name": "Jane Smith",
    "emails": ["jane@work.com", "jane@personal.com"],
    "phones": ["+14155550101"],
    "location": {"city": "San Francisco", "region": "CA", "country": "US"},
    "links": {"linkedin": "https://linkedin.com/in/jane", "github": None, "portfolio": None, "other": []},
    "headline": "Senior SWE at Acme",
    "years_experience": 7.0,
    "skills": [{"name": "Python", "confidence": 0.9, "sources": ["csv"]},
               {"name": "Docker", "confidence": 0.9, "sources": ["csv"]}],
    "experience": [{"company": "Acme", "title": "Senior SWE", "start": "2021-03", "end": None, "summary": None}],
    "education": [],
    "summary": "Great engineer.",
    "provenance": [{"field": "full_name", "source": "csv", "method": "direct"}],
    "overall_confidence": 0.92,
}


class TestProjectNoConfig:
    def test_passthrough_when_no_fields(self):
        result = project(_CANONICAL, {})
        assert result["full_name"] == "Jane Smith"
        assert result["overall_confidence"] == 0.92

    def test_confidence_excluded(self):
        result = project(_CANONICAL, {"include_confidence": False})
        assert "overall_confidence" not in result

    def test_provenance_excluded(self):
        result = project(_CANONICAL, {"include_provenance": False})
        assert "provenance" not in result


class TestProjectFieldSelection:
    def test_select_subset(self):
        config = {"fields": [
            {"path": "full_name"},
            {"path": "primary_email", "from": "emails[0]"},
        ], "include_confidence": False, "include_provenance": False}
        result = project(_CANONICAL, config)
        assert set(result.keys()) == {"full_name", "primary_email"}
        assert result["primary_email"] == "jane@work.com"

    def test_nested_path(self):
        config = {"fields": [{"path": "country", "from": "location.country"}],
                  "include_confidence": False, "include_provenance": False}
        result = project(_CANONICAL, config)
        assert result["country"] == "US"

    def test_slice_path(self):
        config = {"fields": [{"path": "skill_names", "from": "skills[].name"}],
                  "include_confidence": False, "include_provenance": False}
        result = project(_CANONICAL, config)
        assert result["skill_names"] == ["Python", "Docker"]

    def test_type_coercion_string(self):
        config = {"fields": [{"path": "years", "from": "years_experience", "type": "string"}],
                  "include_confidence": False, "include_provenance": False}
        result = project(_CANONICAL, config)
        assert isinstance(result["years"], str)


class TestOnMissing:
    def test_on_missing_null(self):
        config = {"fields": [{"path": "github", "from": "links.github"}],
                  "on_missing": "null", "include_confidence": False, "include_provenance": False}
        result = project(_CANONICAL, config)
        assert result["github"] is None

    def test_on_missing_omit(self):
        config = {"fields": [{"path": "github", "from": "links.github"}],
                  "on_missing": "omit", "include_confidence": False, "include_provenance": False}
        result = project(_CANONICAL, config)
        assert "github" not in result

    def test_on_missing_error_required(self):
        config = {"fields": [{"path": "github", "from": "links.github", "required": True}],
                  "on_missing": "error", "include_confidence": False, "include_provenance": False}
        with pytest.raises(ProjectionError):
            project(_CANONICAL, config)


class TestNormalizeInProjection:
    def test_e164_normalize(self):
        config = {"fields": [{"path": "phone", "from": "phones[0]", "normalize": "E164"}],
                  "include_confidence": False, "include_provenance": False}
        result = project(_CANONICAL, config)
        assert result["phone"] == "+14155550101"

    def test_canonical_skill_normalize(self):
        config = {"fields": [{"path": "skills", "from": "skills[].name", "normalize": "canonical"}],
                  "include_confidence": False, "include_provenance": False}
        result = project(_CANONICAL, config)
        assert "Python" in result["skills"]
