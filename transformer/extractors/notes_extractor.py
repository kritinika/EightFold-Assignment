"""Unstructured source: recruiter free-text notes (.txt).
Rule-based extraction — no external NLP. Extracts email, phone, URLs, name hints,
skill mentions, and passes the raw text as summary.
"""
import logging
from typing import Optional, Union
import re
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# Regex patterns
_EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")
_PHONE_RE = re.compile(
    r"(?:\+?1[\s.-]?)?(?:\(?\d{3}\)?[\s.-]?)?\d{3}[\s.-]?\d{4}"
)
_LINKEDIN_RE = re.compile(r"(?:https?://)?(?:www\.)?linkedin\.com/in/[A-Za-z0-9_\-]+/?")
_GITHUB_RE = re.compile(r"(?:https?://)?(?:www\.)?github\.com/[A-Za-z0-9_\-]+/?")
_URL_RE = re.compile(r"https?://[^\s]+")

# Skill keyword patterns (pulled from skills canonical map keys)
_SKILL_KEYWORDS = [
    "python", "javascript", "typescript", "java", "golang", "go", "rust", "c++",
    "c#", "ruby", "php", "swift", "kotlin", "scala", "sql", "react", "vue",
    "angular", "node", "django", "flask", "fastapi", "spring", "docker",
    "kubernetes", "aws", "gcp", "azure", "terraform", "git", "linux",
    "machine learning", "tensorflow", "pytorch", "pandas", "numpy",
    "rest api", "graphql", "redis", "kafka", "elasticsearch", "agile", "scrum",
]

# Name hint patterns: "Name: John Doe" / "Candidate: Jane"
_NAME_RE = re.compile(
    r"(?:name|candidate|applicant)\s*[:\-]\s*([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)",
    re.IGNORECASE,
)

# Years of experience: "5 years of experience" / "5 yrs exp"
_YOE_RE = re.compile(
    r"(\d+(?:\.\d+)?)\s*(?:\+\s*)?(?:years?|yrs?)[\s\w]{0,20}(?:experience|exp\b)",
    re.IGNORECASE,
)

# Headline/title hints: "Senior Software Engineer at Acme"
_TITLE_RE = re.compile(
    r"(?:title|role|position|currently)\s*[:\-]\s*(.+?)(?:\n|$)",
    re.IGNORECASE,
)


def extract(source: Union[str, Path]) -> dict:
    try:
        text = Path(source).read_text(encoding="utf-8")
    except Exception as e:
        logger.warning("Notes extractor: cannot read %s — %s", source, e)
        return {}

    record: dict = {"_source": "notes", "_raw_text": text}

    emails = _EMAIL_RE.findall(text)
    if emails:
        record["email"] = emails[0]

    phones = _PHONE_RE.findall(text)
    if phones:
        record["phone"] = phones[0]

    linkedin = _LINKEDIN_RE.search(text)
    if linkedin:
        url = linkedin.group(0)
        if not url.startswith("http"):
            url = "https://" + url
        record["linkedin"] = url

    github = _GITHUB_RE.search(text)
    if github:
        url = github.group(0)
        if not url.startswith("http"):
            url = "https://" + url
        record["github"] = url

    name_match = _NAME_RE.search(text)
    if name_match:
        record["full_name"] = name_match.group(1).strip()

    yoe_match = _YOE_RE.search(text)
    if yoe_match:
        record["years_experience"] = float(yoe_match.group(1))

    title_match = _TITLE_RE.search(text)
    if title_match:
        record["headline"] = title_match.group(1).strip()[:120]

    text_lower = text.lower()
    found_skills = [kw.title() for kw in _SKILL_KEYWORDS if kw in text_lower]
    record["skills"] = found_skills

    record["summary"] = text.strip()[:2000]

    return record
