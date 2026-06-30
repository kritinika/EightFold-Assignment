"""Unstructured source: GitHub profile URL.
Uses GitHub REST API (unauthenticated, rate-limited to 60 req/hr; token via env var for higher limits).
Extracts: name, bio, location, email, repos, top languages, company.
"""
import logging
import os
import re
from typing import Any, Dict, List, Optional, Union

import requests

logger = logging.getLogger(__name__)

GITHUB_API = "https://api.github.com"
_TIMEOUT = 10


def _headers() -> dict:
    token = os.environ.get("GITHUB_TOKEN")
    h = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}
    if token:
        h["Authorization"] = f"Bearer {token}"
    return h


def _extract_username(url: str) -> Optional[str]:
    url = url.strip().rstrip("/")
    # https://github.com/username  or  github.com/username
    m = re.search(r"github\.com/([A-Za-z0-9_-]+)/?$", url)
    return m.group(1) if m else None


def _get(path: str) -> Optional[Union[dict, list]]:
    try:
        resp = requests.get(f"{GITHUB_API}{path}", headers=_headers(), timeout=_TIMEOUT)
        if resp.status_code == 404:
            logger.warning("GitHub: 404 for %s", path)
            return None
        if resp.status_code == 403:
            logger.warning("GitHub: rate limited")
            return None
        resp.raise_for_status()
        return resp.json()
    except requests.RequestException as e:
        logger.warning("GitHub API error for %s: %s", path, e)
        return None


def _top_languages(username: str, max_repos: int = 10) -> list[str]:
    repos = _get(f"/users/{username}/repos?per_page={max_repos}&sort=pushed")
    if not repos or not isinstance(repos, list):
        return []
    lang_count: dict[str, int] = {}
    for repo in repos:
        if isinstance(repo, dict) and repo.get("language"):
            lang = repo["language"]
            lang_count[lang] = lang_count.get(lang, 0) + 1
    return sorted(lang_count, key=lambda l: lang_count[l], reverse=True)


def extract(url: str) -> dict:
    """Return a raw candidate dict extracted from a GitHub profile URL."""
    username = _extract_username(url)
    if not username:
        logger.warning("GitHub extractor: cannot parse username from URL: %s", url)
        return {}

    user = _get(f"/users/{username}")
    if not user or not isinstance(user, dict):
        return {}

    record: dict = {"_source": "github", "_source_url": url}

    if user.get("name"):
        record["full_name"] = user["name"]
    if user.get("email"):
        record["email"] = user["email"]
    if user.get("bio"):
        record["summary"] = user["bio"]
    if user.get("company"):
        record["company"] = user["company"].lstrip("@")
    if user.get("location"):
        record["location"] = user["location"]
    if user.get("blog"):
        record["portfolio"] = user["blog"]

    record["github"] = f"https://github.com/{username}"
    record["skills"] = _top_languages(username)

    # repos as a proxy for activity
    record["_github_public_repos"] = user.get("public_repos", 0)
    record["_github_followers"] = user.get("followers", 0)

    return record
