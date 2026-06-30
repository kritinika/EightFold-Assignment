"""Integration tests: full pipeline end-to-end."""
import json
import pytest
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from transformer.pipeline import Pipeline

SAMPLE_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "sample_inputs")
CSV_PATH = os.path.join(SAMPLE_DIR, "candidates.csv")
ATS_PATH = os.path.join(SAMPLE_DIR, "ats_data.json")
NOTES_JANE = os.path.join(SAMPLE_DIR, "notes_jane.txt")
NOTES_BOB = os.path.join(SAMPLE_DIR, "notes_bob.txt")


class TestPipelineBasic:
    def test_csv_only(self):
        pipeline = Pipeline()
        results = pipeline.run(csv_path=CSV_PATH)
        assert len(results) == 4
        names = [r["full_name"] for r in results]
        assert "Jane Smith" in names

    def test_notes_only(self):
        pipeline = Pipeline()
        results = pipeline.run(notes_paths=[NOTES_JANE])
        assert len(results) == 1
        assert results[0]["emails"] == ["jane.smith@email.com"]

    def test_csv_plus_ats_merges_same_candidate(self):
        pipeline = Pipeline()
        results = pipeline.run(csv_path=CSV_PATH, ats_json_path=ATS_PATH)
        # Both sources have Jane — should be merged into one
        jane_profiles = [r for r in results if r.get("full_name") == "Jane Smith"]
        assert len(jane_profiles) == 1
        jane = jane_profiles[0]
        # Should have experience from ATS
        assert len(jane["experience"]) >= 1

    def test_multi_source_pipeline(self):
        pipeline = Pipeline()
        results = pipeline.run(
            csv_path=CSV_PATH,
            ats_json_path=ATS_PATH,
            notes_paths=[NOTES_JANE, NOTES_BOB],
        )
        assert len(results) >= 4

    def test_missing_source_is_skipped_gracefully(self):
        pipeline = Pipeline()
        results = pipeline.run(
            csv_path="/nonexistent/path.csv",
            notes_paths=[NOTES_JANE],
        )
        # notes still processed
        assert len(results) >= 1

    def test_empty_all_sources_returns_empty(self):
        pipeline = Pipeline()
        results = pipeline.run()
        assert results == []


class TestPipelineOutput:
    def test_canonical_fields_present(self):
        pipeline = Pipeline()
        results = pipeline.run(csv_path=CSV_PATH)
        for r in results:
            assert "candidate_id" in r
            assert "emails" in r
            assert "phones" in r
            assert "skills" in r
            assert "provenance" in r
            assert "overall_confidence" in r

    def test_phones_e164(self):
        pipeline = Pipeline()
        results = pipeline.run(csv_path=CSV_PATH)
        for r in results:
            for phone in r["phones"]:
                assert phone.startswith("+"), f"Phone not E.164: {phone}"

    def test_custom_config_projection(self):
        config = {
            "fields": [
                {"path": "full_name", "type": "string", "required": True},
                {"path": "primary_email", "from": "emails[0]", "type": "string"},
                {"path": "skills", "from": "skills[].name", "type": "string[]"},
            ],
            "include_confidence": True,
            "include_provenance": False,
            "on_missing": "null",
        }
        pipeline = Pipeline(config=config)
        results = pipeline.run(csv_path=CSV_PATH)
        for r in results:
            assert "full_name" in r
            assert "primary_email" in r
            assert "skills" in r
            assert "provenance" not in r
            assert "overall_confidence" in r

    def test_confidence_range(self):
        pipeline = Pipeline()
        results = pipeline.run(csv_path=CSV_PATH, ats_json_path=ATS_PATH)
        for r in results:
            oc = r.get("overall_confidence")
            if oc is not None:
                assert 0.0 <= oc <= 1.0


class TestEdgeCases:
    def test_garbage_notes_file(self, tmp_path):
        garbage = tmp_path / "garbage.txt"
        garbage.write_text("!@#$%^&*() no useful information here 123")
        pipeline = Pipeline()
        results = pipeline.run(notes_paths=[str(garbage)])
        # Should produce a record with mostly null fields, not crash
        assert isinstance(results, list)

    def test_empty_csv(self, tmp_path):
        empty_csv = tmp_path / "empty.csv"
        empty_csv.write_text("full_name,email,phone\n")
        pipeline = Pipeline()
        results = pipeline.run(csv_path=str(empty_csv))
        assert results == []

    def test_malformed_json(self, tmp_path):
        bad_json = tmp_path / "bad.json"
        bad_json.write_text("{not valid json}")
        pipeline = Pipeline()
        results = pipeline.run(ats_json_path=str(bad_json), notes_paths=[NOTES_JANE])
        # Notes should still be processed
        assert len(results) >= 1
