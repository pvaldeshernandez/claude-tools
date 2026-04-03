"""Springer Nature API client — covers Springer, Nature, BMC, Palgrave Macmillan."""

import os
from pathlib import Path
from typing import Any

import httpx

BASE_URL = "https://api.springernature.com"
TIMEOUT = 30.0

_META_KEY_FILE = Path.home() / ".springer" / "api_key.txt"
_OA_KEY_FILE = Path.home() / ".springer" / "oa_key.txt"


def _get_meta_key() -> str:
    key = os.environ.get("SPRINGER_API_KEY", "").strip()
    if key:
        return key
    if _META_KEY_FILE.exists():
        key = _META_KEY_FILE.read_text(encoding="utf-8").strip()
        if key:
            return key
    raise RuntimeError(
        "No Springer Nature Meta API key found. Set SPRINGER_API_KEY env var "
        f"or put your key in {_META_KEY_FILE}. "
        "Get a free key at https://dev.springernature.com/"
    )


def _get_oa_key() -> str:
    key = os.environ.get("SPRINGER_OA_KEY", "").strip()
    if key:
        return key
    if _OA_KEY_FILE.exists():
        key = _OA_KEY_FILE.read_text(encoding="utf-8").strip()
        if key:
            return key
    # Fall back to meta key if no separate OA key
    return _get_meta_key()


def _get(path: str, params: dict[str, Any], use_oa_key: bool = False) -> dict[str, Any]:
    url = f"{BASE_URL}{path}"
    params["api_key"] = _get_oa_key() if use_oa_key else _get_meta_key()
    resp = httpx.get(url, params=params, timeout=TIMEOUT)
    resp.raise_for_status()
    return resp.json()


def _parse_record(rec: dict[str, Any]) -> dict[str, Any]:
    """Normalize a Springer Nature record into a consistent shape."""
    creators = rec.get("creators", [])
    authors = [c.get("creator", "") for c in creators if c.get("creator")]

    urls = rec.get("url", [])
    url_map = {u.get("format", ""): u.get("value", "") for u in urls}

    return {
        "title": rec.get("title", ""),
        "abstract": rec.get("abstract", ""),
        "authors": authors,
        "doi": rec.get("doi", ""),
        "publisher": rec.get("publisher", ""),
        "journal": rec.get("publicationName", ""),
        "issn": rec.get("issn", ""),
        "eissn": rec.get("eIssn", ""),
        "volume": rec.get("volume", ""),
        "issue": rec.get("number", ""),
        "start_page": rec.get("startingPage", ""),
        "end_page": rec.get("endingPage", ""),
        "pub_date": rec.get("publicationDate", ""),
        "type": rec.get("contentType", ""),
        "open_access": rec.get("openaccess", "false") == "true",
        "urls": url_map,
    }


def springer_search(
    query: str,
    count: int = 10,
    start: int = 1,
    subject: str = "",
    date_from: str = "",
    date_to: str = "",
) -> dict[str, Any]:
    """Search Springer Nature metadata.

    Query supports: keyword, subject:, doi:, title:, orgname:, isbn:, issn:
    Date format: YYYY-MM-DD
    """
    q_parts = [query]
    if subject:
        q_parts.append(f"subject:{subject}")
    if date_from or date_to:
        df = date_from or "1900-01-01"
        dt = date_to or "2099-12-31"
        q_parts.append(f"onlinedatefrom:{df} onlinedateto:{dt}")

    params: dict[str, Any] = {
        "q": " ".join(q_parts),
        "s": start,
        "p": min(count, 50),
    }
    data = _get("/meta/v2/json", params)

    records = data.get("records", [])
    result_info = data.get("result", [{}])
    total = result_info[0].get("total", "0") if result_info else "0"

    return {
        "total_results": int(total),
        "returned": len(records),
        "articles": [_parse_record(r) for r in records],
    }


def springer_open_access(
    query: str,
    count: int = 10,
    start: int = 1,
) -> dict[str, Any]:
    """Search Springer Nature for open access articles only.

    Returns articles with full text available.
    """
    params: dict[str, Any] = {
        "q": query,
        "s": start,
        "p": min(count, 50),
    }
    data = _get("/openaccess/json", params, use_oa_key=True)

    records = data.get("records", [])
    result_info = data.get("result", [{}])
    total = result_info[0].get("total", "0") if result_info else "0"

    return {
        "total_results": int(total),
        "returned": len(records),
        "articles": [_parse_record(r) for r in records],
    }


def springer_by_doi(doi: str) -> dict[str, Any]:
    """Get Springer Nature article metadata by DOI."""
    params: dict[str, Any] = {
        "q": f"doi:{doi}",
        "p": 1,
    }
    data = _get("/meta/v2/json", params)
    records = data.get("records", [])
    if not records:
        return {"error": f"No article found for DOI: {doi}"}
    return _parse_record(records[0])


def springer_api_status() -> dict[str, Any]:
    """Check Springer Nature API key configuration and connectivity."""
    try:
        key = _get_meta_key()
        masked = key[:4] + "..." + key[-4:] if len(key) > 8 else "****"
        result = springer_search("test", count=1)
        return {
            "configured": True,
            "key": masked,
            "connected": True,
            "test_total_results": result.get("total_results", "?"),
        }
    except RuntimeError as e:
        return {"configured": False, "error": str(e)}
    except Exception as e:
        return {"configured": True, "connected": False, "error": str(e)}
