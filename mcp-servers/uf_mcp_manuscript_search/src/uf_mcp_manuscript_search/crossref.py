"""CrossRef API client — DOI metadata for all publishers.

Covers Frontiers, Science/AAAS, Wiley, Taylor & Francis, Springer, Elsevier,
PLOS, IEEE, and virtually every publisher that assigns DOIs.
"""

import os
from pathlib import Path
from typing import Any

import httpx

BASE_URL = "https://api.crossref.org"
TIMEOUT = 30.0

_EMAIL_FILE = Path.home() / ".crossref" / "email.txt"


def _get_email() -> str | None:
    """Email for CrossRef polite pool (faster rate limits)."""
    email = os.environ.get("CROSSREF_EMAIL", "").strip()
    if email:
        return email
    if _EMAIL_FILE.exists():
        email = _EMAIL_FILE.read_text(encoding="utf-8").strip()
        if email:
            return email
    return None


def _headers() -> dict[str, str]:
    h: dict[str, str] = {"Accept": "application/json"}
    email = _get_email()
    if email:
        h["User-Agent"] = f"uf-mcp-manuscript-search/0.1.0 (mailto:{email})"
    return h


def _get(path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    url = f"{BASE_URL}{path}"
    resp = httpx.get(url, headers=_headers(), params=params, timeout=TIMEOUT)
    resp.raise_for_status()
    return resp.json()


def _parse_work(item: dict[str, Any]) -> dict[str, Any]:
    """Normalize a CrossRef work item."""
    # Authors
    authors = []
    for a in item.get("author", []):
        name_parts = []
        if a.get("given"):
            name_parts.append(a["given"])
        if a.get("family"):
            name_parts.append(a["family"])
        entry: dict[str, str] = {"name": " ".join(name_parts)}
        affils = a.get("affiliation", [])
        if affils and affils[0].get("name"):
            entry["affiliation"] = affils[0]["name"]
        if name_parts:
            authors.append(entry)

    # Title
    titles = item.get("title", [])
    title = titles[0] if titles else ""

    # Abstract
    abstract = item.get("abstract", "")
    # CrossRef abstracts sometimes have JATS XML tags
    if abstract.startswith("<jats:"):
        import re
        abstract = re.sub(r"<[^>]+>", "", abstract).strip()

    # Container (journal)
    containers = item.get("container-title", [])
    journal = containers[0] if containers else ""

    # Dates
    issued = item.get("issued", {}).get("date-parts", [[]])
    date_parts = issued[0] if issued else []
    pub_date = "-".join(str(p) for p in date_parts) if date_parts else ""

    # ISSN
    issns = item.get("ISSN", [])

    # References count
    ref_count = item.get("references-count", 0)
    cited_count = item.get("is-referenced-by-count", 0)

    return {
        "doi": item.get("DOI", ""),
        "title": title,
        "abstract": abstract,
        "authors": authors,
        "journal": journal,
        "publisher": item.get("publisher", ""),
        "type": item.get("type", ""),
        "pub_date": pub_date,
        "issn": issns,
        "volume": item.get("volume", ""),
        "issue": item.get("issue", ""),
        "page": item.get("page", ""),
        "cited_by_count": cited_count,
        "references_count": ref_count,
        "open_access": item.get("is-oa", False) if "is-oa" in item else None,
        "url": item.get("URL", ""),
    }


def crossref_search(
    query: str,
    count: int = 10,
    offset: int = 0,
    sort: str = "relevance",
    order: str = "desc",
    filter_from_date: str = "",
    filter_to_date: str = "",
    filter_type: str = "",
) -> dict[str, Any]:
    """Search CrossRef works (articles, books, etc.) across all publishers.

    Sort options: relevance, published, deposited, indexed, is-referenced-by-count
    filter_type: journal-article, book-chapter, proceedings-article, etc.
    Date format: YYYY-MM-DD
    """
    params: dict[str, Any] = {
        "query": query,
        "rows": min(count, 100),
        "offset": offset,
        "sort": sort,
        "order": order,
    }

    filters: list[str] = []
    if filter_from_date:
        filters.append(f"from-pub-date:{filter_from_date}")
    if filter_to_date:
        filters.append(f"until-pub-date:{filter_to_date}")
    if filter_type:
        filters.append(f"type:{filter_type}")
    if filters:
        params["filter"] = ",".join(filters)

    data = _get("/works", params)
    message = data.get("message", {})

    return {
        "total_results": message.get("total-results", 0),
        "returned": len(message.get("items", [])),
        "articles": [_parse_work(item) for item in message.get("items", [])],
    }


def crossref_work(doi: str) -> dict[str, Any]:
    """Get metadata for a specific DOI from CrossRef.

    Works for any publisher that registers DOIs — Frontiers, Science, Wiley, etc.
    """
    data = _get(f"/works/{doi}")
    message = data.get("message", {})
    return _parse_work(message)


def crossref_journal(issn: str, count: int = 10, offset: int = 0) -> dict[str, Any]:
    """Get journal info and recent articles by ISSN."""
    # Journal metadata
    journal_data = _get(f"/journals/{issn}")
    journal_info = journal_data.get("message", {})

    # Recent works from this journal
    works_data = _get(f"/journals/{issn}/works", {
        "rows": min(count, 50),
        "offset": offset,
        "sort": "published",
        "order": "desc",
    })
    works_msg = works_data.get("message", {})

    return {
        "journal": {
            "title": journal_info.get("title", ""),
            "publisher": journal_info.get("publisher", ""),
            "issn": journal_info.get("ISSN", []),
            "subjects": journal_info.get("subjects", []),
            "total_dois": journal_info.get("counts", {}).get("total-dois", 0),
        },
        "recent_articles": [_parse_work(item) for item in works_msg.get("items", [])],
        "total_articles": works_msg.get("total-results", 0),
    }


def crossref_funder_works(
    funder_id: str, query: str = "", count: int = 10
) -> dict[str, Any]:
    """Search for works funded by a specific funder (by CrossRef funder ID).

    Example funder IDs: 100000002 (NIH), 501100000266 (EPSRC), 100000001 (NSF)
    """
    params: dict[str, Any] = {"rows": min(count, 50)}
    if query:
        params["query"] = query
    data = _get(f"/funders/{funder_id}/works", params)
    message = data.get("message", {})

    return {
        "total_results": message.get("total-results", 0),
        "articles": [_parse_work(item) for item in message.get("items", [])],
    }


def crossref_api_status() -> dict[str, Any]:
    """Check CrossRef API connectivity and polite pool status."""
    email = _get_email()
    result: dict[str, Any] = {
        "polite_pool": email is not None,
        "email": email or "(not configured — set CROSSREF_EMAIL or ~/.crossref/email.txt)",
    }
    try:
        data = crossref_search("test", count=1)
        result["connected"] = True
        result["test_total_results"] = data.get("total_results", "?")
    except Exception as e:
        result["connected"] = False
        result["error"] = str(e)
    return result
