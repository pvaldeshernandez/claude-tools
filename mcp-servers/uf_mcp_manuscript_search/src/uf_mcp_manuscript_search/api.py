"""Elsevier API client — Scopus & ScienceDirect."""

import os
from pathlib import Path
from typing import Any

import httpx

BASE_URL = "https://api.elsevier.com"
TIMEOUT = 30.0

# API key resolution: env var > file
_KEY_FILE = Path.home() / ".elsevier" / "api_key.txt"


def _get_api_key() -> str:
    key = os.environ.get("ELSEVIER_API_KEY", "").strip()
    if key:
        return key
    if _KEY_FILE.exists():
        key = _KEY_FILE.read_text(encoding="utf-8").strip()
        if key:
            return key
    raise RuntimeError(
        "No Elsevier API key found. Set ELSEVIER_API_KEY env var "
        f"or put your key in {_KEY_FILE}"
    )


_INST_TOKEN_FILE = Path.home() / ".elsevier" / "inst_token.txt"


def _get_inst_token() -> str | None:
    token = os.environ.get("ELSEVIER_INST_TOKEN", "").strip()
    if token:
        return token
    if _INST_TOKEN_FILE.exists():
        token = _INST_TOKEN_FILE.read_text(encoding="utf-8").strip()
        if token:
            return token
    return None


def _headers() -> dict[str, str]:
    h = {
        "X-ELS-APIKey": _get_api_key(),
        "Accept": "application/json",
    }
    inst = _get_inst_token()
    if inst:
        h["X-ELS-Insttoken"] = inst
    return h


def _get(path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    """Make GET request to Elsevier API."""
    url = f"{BASE_URL}{path}"
    resp = httpx.get(url, headers=_headers(), params=params, timeout=TIMEOUT)
    resp.raise_for_status()
    return resp.json()


def _put(path: str, json_body: dict[str, Any]) -> dict[str, Any]:
    """Make PUT request to Elsevier API (used by ScienceDirect search)."""
    url = f"{BASE_URL}{path}"
    resp = httpx.put(url, headers=_headers(), json=json_body, timeout=TIMEOUT)
    resp.raise_for_status()
    return resp.json()


# ── Scopus ──────────────────────────────────────────────────────────


def scopus_search(
    query: str,
    count: int = 10,
    start: int = 0,
    sort: str = "-citedby-count",
) -> dict[str, Any]:
    """Search Scopus for articles. Query uses Scopus search syntax.

    Examples: 'TITLE-ABS-KEY(machine learning)', 'AU-ID(12345)', 'ISSN(0140-6736)'
    """
    params = {
        "query": query,
        "count": min(count, 25),
        "start": start,
        "sort": sort,
    }
    return _get("/content/search/scopus", params)


def scopus_abstract(scopus_id: str) -> dict[str, Any]:
    """Get full abstract and metadata for a Scopus document."""
    return _get(f"/content/abstract/scopus_id/{scopus_id}")


def scopus_abstract_by_doi(doi: str) -> dict[str, Any]:
    """Get full abstract and metadata by DOI."""
    return _get(f"/content/abstract/doi/{doi}")


def scopus_author(author_id: str) -> dict[str, Any]:
    """Get author profile from Scopus."""
    return _get(f"/content/author/author_id/{author_id}")


def scopus_author_search(query: str, count: int = 10) -> dict[str, Any]:
    """Search for authors. Query uses Scopus author search syntax.

    Examples: 'AUTHLASTNAME(smith) AND AUTHFIRST(john)', 'AF-ID(60007776)'
    """
    params = {"query": query, "count": min(count, 25)}
    return _get("/content/search/author", params)


def scopus_affiliation(affil_id: str) -> dict[str, Any]:
    """Get affiliation/institution details."""
    return _get(f"/content/affiliation/affiliation_id/{affil_id}")


def scopus_affiliation_search(query: str, count: int = 10) -> dict[str, Any]:
    """Search affiliations. Example: 'AF-ID(60007776)' or 'AFFIL(university florida)'."""
    params = {"query": query, "count": min(count, 25)}
    return _get("/content/search/affiliation", params)


# ── ScienceDirect ───────────────────────────────────────────────────


def scidir_search(query: str, count: int = 10, start: int = 0) -> dict[str, Any]:
    """Search ScienceDirect for articles by keyword.

    Note: Requires institutional token (insttoken) for access.
    Set ELSEVIER_INST_TOKEN env var or add to ~/.elsevier/inst_token.txt
    """
    body = {
        "qs": query,
        "display": {"offset": start, "show": min(count, 25)},
    }
    return _put("/content/search/sciencedirect", body)


def scidir_article(doi: str) -> dict[str, Any]:
    """Get ScienceDirect article content by DOI (full text if institutional access)."""
    return _get(f"/content/article/doi/{doi}")


def scidir_article_by_pii(pii: str) -> dict[str, Any]:
    """Get ScienceDirect article content by PII."""
    return _get(f"/content/article/pii/{pii}")


# ── Serial (Journal) metadata ──────────────────────────────────────


def serial_title(issn: str) -> dict[str, Any]:
    """Get journal/serial metadata by ISSN."""
    return _get(f"/content/serial/title/issn/{issn}")


def serial_search(title: str, count: int = 10) -> dict[str, Any]:
    """Search for journals by title keyword."""
    params = {"title": title, "count": min(count, 25)}
    return _get("/content/serial/title", params)
