#!/usr/bin/env python3
"""
Multi-Source Candidate Data Transformer — CLI

Usage:
  python cli.py [OPTIONS]

Source options (at least one structured + one unstructured required):
  --csv PATH           Recruiter CSV export
  --ats-json PATH      ATS JSON blob
  --github URL         GitHub profile URL (repeatable)
  --notes PATH         Recruiter notes .txt file (repeatable)

Output options:
  --config PATH        Runtime output config JSON (optional)
  --out PATH           Write JSON output to file (default: stdout)
  --pretty             Pretty-print JSON (default: compact)
  --validate-only      Run pipeline but exit non-zero on validation errors

Environment:
  GITHUB_TOKEN         GitHub personal access token (optional; raises rate limit)

Examples:
  python cli.py --csv sample_inputs/candidates.csv --notes sample_inputs/notes.txt
  python cli.py --csv sample_inputs/candidates.csv --ats-json sample_inputs/ats_data.json \\
                --notes sample_inputs/notes.txt --config sample_inputs/config.json --pretty
"""
import argparse
import json
import logging
import sys
from pathlib import Path

from transformer.pipeline import Pipeline


def _load_config(path: str) -> dict:
    try:
        return json.loads(Path(path).read_text())
    except Exception as e:
        print(f"[ERROR] Cannot load config {path}: {e}", file=sys.stderr)
        sys.exit(1)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Multi-Source Candidate Data Transformer",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--csv", metavar="PATH", help="Recruiter CSV export")
    parser.add_argument("--ats-json", metavar="PATH", help="ATS JSON blob")
    parser.add_argument("--github", metavar="URL", action="append", default=[], help="GitHub profile URL (repeatable)")
    parser.add_argument("--notes", metavar="PATH", action="append", default=[], help="Recruiter notes .txt (repeatable)")
    parser.add_argument("--config", metavar="PATH", help="Output config JSON")
    parser.add_argument("--out", metavar="PATH", help="Write output to file (default: stdout)")
    parser.add_argument("--pretty", action="store_true", help="Pretty-print JSON")
    parser.add_argument("--validate-only", action="store_true", help="Exit non-zero if validation errors")
    parser.add_argument("--log-level", default="WARNING", choices=["DEBUG", "INFO", "WARNING", "ERROR"])
    args = parser.parse_args()

    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(levelname)s %(name)s: %(message)s",
    )

    # Require at least one source
    if not any([args.csv, args.ats_json, args.github, args.notes]):
        parser.error("Provide at least one source: --csv, --ats-json, --github, or --notes")

    config = _load_config(args.config) if args.config else {}
    pipeline = Pipeline(config=config)

    profiles = pipeline.run(
        csv_path=args.csv,
        ats_json_path=args.ats_json,
        github_urls=args.github,
        notes_paths=args.notes,
    )

    indent = 2 if args.pretty else None
    output_json = json.dumps(profiles, indent=indent, ensure_ascii=False, default=str)

    if args.out:
        Path(args.out).write_text(output_json, encoding="utf-8")
        print(f"Wrote {len(profiles)} profile(s) to {args.out}", file=sys.stderr)
    else:
        print(output_json)

    if args.validate_only and not profiles:
        sys.exit(1)


if __name__ == "__main__":
    main()
