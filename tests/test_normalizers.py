
"""Tests for all normalizers."""
import pytest
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from transformer.normalizers.phone import normalize_phone, normalize_phones
from transformer.normalizers.date import normalize_date
from transformer.normalizers.location import normalize_location
from transformer.normalizers.skills import canonicalize_skill, canonicalize_skills


# ── Phone ──────────────────────────────────────────────────────────────────────

class TestNormalizePhone:
    def test_e164_us(self):
        assert normalize_phone("+1-415-555-0101") == "+14155550101"

    def test_us_local(self):
        assert normalize_phone("415.555.0202") == "+14155550202"

    def test_us_parens(self):
        assert normalize_phone("(650) 555-0303") == "+16505550303"

    def test_international_mexico(self):
        assert normalize_phone("+52-55-1234-5678") == "+525512345678"

    def test_international_korea(self):
        assert normalize_phone("+82-10-9876-5432") == "+821098765432"

    def test_empty_returns_none(self):
        assert normalize_phone("") is None

    def test_garbage_returns_none(self):
        assert normalize_phone("not-a-phone") is None

    def test_dedup(self):
        result = normalize_phones(["+14155550101", "415-555-0101", "+14155550202"])
        assert result == ["+14155550101", "+14155550202"]


# ── Date ───────────────────────────────────────────────────────────────────────

class TestNormalizeDate:
    def test_already_yyyy_mm(self):
        assert normalize_date("2021-03") == "2021-03"

    def test_yyyy_only(self):
        assert normalize_date("2018") == "2018-01"

    def test_full_date(self):
        assert normalize_date("March 2021") == "2021-03"

    def test_present_returns_none(self):
        assert normalize_date("Present") is None
        assert normalize_date("current") is None

    def test_empty_returns_none(self):
        assert normalize_date("") is None

    def test_iso_date(self):
        assert normalize_date("2020-01-15") == "2020-01"


# ── Location ───────────────────────────────────────────────────────────────────

class TestNormalizeLocation:
    def test_full_us(self):
        result = normalize_location("San Francisco, CA, USA")
        assert result["country"] == "US"
        assert result["city"] == "San Francisco"

    def test_country_code(self):
        result = normalize_location("Mexico City, MX")
        assert result["country"] == "MX"

    def test_empty(self):
        result = normalize_location("")
        assert result == {"city": None, "region": None, "country": None}

    def test_korea(self):
        result = normalize_location("Seoul, KR")
        assert result["country"] == "KR"

    def test_uk_alias(self):
        result = normalize_location("London, UK")
        assert result["country"] == "GB"


# ── Skills ─────────────────────────────────────────────────────────────────────

class TestCanonicalizeSkill:
    def test_exact_match(self):
        assert canonicalize_skill("python") == "Python"

    def test_alias(self):
        assert canonicalize_skill("golang") == "Go"
        assert canonicalize_skill("reactjs") == "React"
        assert canonicalize_skill("k8s") == "Kubernetes"

    def test_case_insensitive(self):
        assert canonicalize_skill("PYTHON") == "Python"
        assert canonicalize_skill("TypeScript") == "TypeScript"

    def test_unknown_skill_titlecased(self):
        result = canonicalize_skill("some obscure lib")
        assert result == "Some Obscure Lib"

    def test_empty_returns_none(self):
        assert canonicalize_skill("") is None

    def test_dedup(self):
        result = canonicalize_skills(["python", "Python", "py", "JavaScript", "js"])
        assert result.count("Python") == 1
        assert result.count("JavaScript") == 1
