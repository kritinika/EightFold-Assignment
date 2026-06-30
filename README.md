LIVE LINK OF PROJECT - https://candidate-data-transformer-1n54.onrender.com/
VIDEO LINK - https://jam.dev/c/00cb3eef-8903-45d2-ba8d-09b142bcf1eb

# Multi-Source Candidate Data Transformer

> A deterministic pipeline that merges candidate data from multiple structured and unstructured sources into one canonical profile — with provenance, confidence scoring, and a configurable output layer.

![Python](https://img.shields.io/badge/Python-3.9+-blue?style=flat-square&logo=python)
![Tests](https://img.shields.io/badge/tests-63%20passing-brightgreen?style=flat-square)
![Flask](https://img.shields.io/badge/UI-Flask%20%2B%20localhost-lightgrey?style=flat-square&logo=flask)
![License](https://img.shields.io/badge/license-MIT-green?style=flat-square)

Eightfold AI take-home assignment. Ingests candidate data from CSVs, ATS JSON blobs, GitHub profiles, and recruiter notes — deduplicates, normalises (E.164 phones, YYYY-MM dates, ISO 3166 countries, canonical skill names), merges with source-priority conflict resolution, and emits schema-valid JSON with full field-level provenance and confidence scores. Output shape is controlled by a runtime config with no code changes.

---

## Quick start

```bash
# 1. Clone the repo
git clone https://github.com/yourusername/eightfold-assignment.git
cd eightfold-assignment

# 2. Install dependencies
pip3 install phonenumbers pycountry python-dateutil requests flask

# 3. Run the web UI
python3 app.py
# Open http://localhost:8080 in your browser
```

Or use the CLI directly:

```bash
# Run on all sample inputs (default output schema)
python3 cli.py \
  --csv sample_inputs/candidates.csv \
  --ats-json sample_inputs/ats_data.json \
  --notes sample_inputs/notes_jane.txt \
  --notes sample_inputs/notes_bob.txt \
  --pretty

# Run with a custom output config
python3 cli.py \
  --csv sample_inputs/candidates.csv \
  --ats-json sample_inputs/ats_data.json \
  --notes sample_inputs/notes_jane.txt \
  --config sample_inputs/config_custom.json \
  --pretty \
  --out sample_outputs/custom_output.json

# Run tests
python3 -m pytest tests/ -v
```

## Web UI

```bash
python3 app.py
```

Open **http://localhost:8080** — upload your files, paste a config, click Run.

![Web UI](https://img.shields.io/badge/UI-localhost%3A8080-blue?style=flat-square)

---

## CLI reference

```
python3 cli.py [OPTIONS]

Source options (mix freely; at least one required):
  --csv PATH           Recruiter CSV export
  --ats-json PATH      ATS JSON blob
  --github URL         GitHub profile URL (repeatable; calls GitHub REST API)
  --notes PATH         Recruiter free-text notes .txt (repeatable)

Output options:
  --config PATH        Runtime output config JSON (see §Config below)
  --out PATH           Write JSON to file (default: stdout)
  --pretty             Pretty-print JSON
  --log-level LEVEL    DEBUG | INFO | WARNING | ERROR (default: WARNING)

Environment:
  GITHUB_TOKEN         GitHub personal access token (optional; avoids 60 req/hr rate limit)
```

---

## Pipeline stages

```
Detect → Extract → Group → Normalize → Merge → Project → Validate
```

| Stage | What it does |
|---|---|
| **Detect** | Identifies source type from CLI args |
| **Extract** | Parses each source into raw dicts; any failure logs a warning and continues |
| **Group** | Clusters records by candidate identity (shared email, or ≥75% name-token overlap) |
| **Normalize** | Phones → E.164, dates → YYYY-MM, country → ISO 3166-1 alpha-2, skills → canonical |
| **Merge** | Conflict resolution by source priority (csv > ats_json > github > notes); lists unioned |
| **Project** | Applies runtime config: field selection, renaming, per-field normalization |
| **Validate** | Checks canonical profile and projected output; logs warnings, never crashes |

---

## Sources supported

| Source | Type | Format |
|---|---|---|
| Recruiter CSV | Structured | Flexible column names (case-insensitive alias map) |
| ATS JSON blob | Structured | Any field naming convention (camelCase or snake_case); single object or array |
| GitHub profile URL | Unstructured | GitHub REST API — name, bio, company, location, top languages |
| Recruiter notes | Unstructured | Free-text .txt — rule-based extraction of email, phone, URLs, skills, YOE |

> **LinkedIn** and **PDF/DOCX resume** parsing are architecturally slotted but not implemented (see [Assumptions](#assumptions--descoped)).

---

## Runtime config

The `--config` flag accepts a JSON file that reshapes the output without changing any pipeline logic.

```json
{
  "fields": [
    { "path": "full_name",      "type": "string",   "required": true },
    { "path": "primary_email",  "from": "emails[0]","type": "string",   "required": true },
    { "path": "phone",          "from": "phones[0]","normalize": "E164" },
    { "path": "skills",         "from": "skills[].name", "normalize": "canonical" },
    { "path": "location_country", "from": "location.country" }
  ],
  "include_confidence": true,
  "include_provenance": false,
  "on_missing": "null"
}
```

**Path notation:**
- `emails[0]` — index into array
- `location.country` — nested object field
- `skills[].name` — slice-map: extract `name` from every element in `skills`

**`on_missing`:** `"null"` (default) | `"omit"` | `"error"`

---

## Project structure

```
transformer/
  extractors/
    csv_extractor.py        # Structured: recruiter CSV
    ats_json_extractor.py   # Structured: ATS JSON blob
    github_extractor.py     # Unstructured: GitHub REST API
    notes_extractor.py      # Unstructured: free-text notes
  normalizers/
    phone.py                # E.164 via `phonenumbers`
    date.py                 # YYYY-MM via `dateutil`
    location.py             # ISO 3166-1 via `pycountry`
    skills.py               # Canonical alias map
  merger.py                 # Conflict resolution + confidence scoring
  projector.py              # Runtime config projection
  validator.py              # Schema validation
  pipeline.py               # Orchestrator

cli.py                      # Command-line interface
tests/
  test_normalizers.py       # 22 tests
  test_merger.py            # 13 tests
  test_projector.py         # 11 tests
  test_pipeline.py          # 17 tests  (63 total, all passing)
sample_inputs/
  candidates.csv
  ats_data.json
  notes_jane.txt
  notes_bob.txt
  config_default.json
  config_custom.json
sample_outputs/
  default_output.json
  custom_output.json
```

---

## Confidence scoring

```
field_confidence = base_confidence(winning_source)
                 + 0.08  if ≥2 sources agree
                 − 0.15  if sources conflict
                 clamped to [0.0, 1.0]

overall_confidence = mean(field_confidences)
```

Source base confidences: `csv=0.90`, `ats_json=0.85`, `github=0.80`, `notes=0.55`

A missing value is always `null` — never invented from partial signals.

---

## Running tests

```bash
python3 -m pytest tests/ -v
# 63 passed in ~0.2s
```

Edge cases covered: missing source files, malformed JSON, unparseable phones, "Present" as end date, same candidate across multiple sources, garbage free-text, empty CSV.

---

## Assumptions & descoped

- **LinkedIn API**: Requires OAuth approval; not implemented. LinkedIn URLs are stored in `links.linkedin` from CSV/ATS/notes inputs.
- **PDF/DOCX resume parsing**: The extractor slot is ready (same interface as `NotesExtractor`); `pdfplumber`/`python-docx` integration is left out to avoid heavyweight dependencies.
- **ML-based dedup**: Name matching uses 75% token overlap. "Jon Smith" vs "Jonathan Smith" would not merge — an embedding-based approach would catch this but adds an LLM dependency not justified at this scope.
- **Streaming/batching**: The pipeline is in-memory. Scales to thousands of candidates; for millions, a chunked design is needed at the grouping stage.
- **ATS field coverage**: The ATS field alias map covers common systems (Greenhouse, Lever, Workday naming patterns). Unmapped fields are silently skipped — provenance makes this auditable.

---

## Demo output (Jane Smith — merged from CSV + ATS + notes)

```json
{
  "full_name": "Jane Smith",
  "primary_email": "jane.smith@email.com",
  "phone": "+14155550101",
  "linkedin": "https://linkedin.com/in/janesmith",
  "github": "https://github.com/janesmith",
  "headline": "Senior Software Engineer at Acme Corp",
  "years_experience": 7.0,
  "skills": ["Python", "Django", "SQL", "Docker", "AWS", "REST API", "Git"],
  "current_company": "Acme Corp",
  "location_country": "US",
  "overall_confidence": 0.932
}
```
