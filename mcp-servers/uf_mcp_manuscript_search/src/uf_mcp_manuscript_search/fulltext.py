"""Full-text retrieval and PDF download — tries multiple sources in cascade.

Sources tried (in order):
1. Elsevier API (for 10.1016/... DOIs)
2. PLOS API (for 10.1371/... DOIs)
3. Springer Nature OA API (for 10.1007/... and 10.1038/... DOIs)
4. Unpaywall (OA copies for any DOI)
5. CrossRef TDM links (full-text URLs registered by publishers)
"""

import logging
import os
import re
from pathlib import Path
from typing import Any

import httpx

logger = logging.getLogger("uf_mcp_manuscript_search")

TIMEOUT = 60.0

# ── Helpers ────────────────────────────────────────────────────────


def _elsevier_headers(accept: str = "application/json") -> dict[str, str]:
    """Build Elsevier API headers."""
    from uf_mcp_manuscript_search.api import _get_api_key, _get_inst_token

    h = {"X-ELS-APIKey": _get_api_key(), "Accept": accept}
    inst = _get_inst_token()
    if inst:
        h["X-ELS-Insttoken"] = inst
    return h


def _unpaywall_email() -> str | None:
    email = os.environ.get("UNPAYWALL_EMAIL", "").strip()
    if email:
        return email
    f = Path.home() / ".unpaywall" / "email.txt"
    if f.exists():
        email = f.read_text(encoding="utf-8").strip()
        if email:
            return email
    return None


def _crossref_headers() -> dict[str, str]:
    email = os.environ.get("CROSSREF_EMAIL", "").strip()
    if not email:
        f = Path.home() / ".crossref" / "email.txt"
        if f.exists():
            email = f.read_text(encoding="utf-8").strip()
    h: dict[str, str] = {"Accept": "application/json"}
    if email:
        h["User-Agent"] = f"uf-mcp-manuscript-search/0.2.0 (mailto:{email})"
    return h


def _http_headers() -> dict[str, str]:
    """Generic headers for fetching from publisher sites."""
    return {
        "User-Agent": "Mozilla/5.0 (compatible; uf-mcp-manuscript-search/0.2.0; academic research)",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    }


def _safe_text_fetch(url: str, timeout: float = TIMEOUT) -> str | None:
    """Fetch text content from a URL, following redirects."""
    try:
        resp = httpx.get(url, headers=_http_headers(), timeout=timeout, follow_redirects=True)
        resp.raise_for_status()
        ct = resp.headers.get("content-type", "")
        if "pdf" in ct:
            return None  # Binary PDF, not text
        return resp.text
    except Exception as e:
        logger.debug(f"Failed to fetch text from {url}: {e}")
        return None


def _safe_pdf_fetch(url: str, timeout: float = TIMEOUT) -> bytes | None:
    """Fetch PDF bytes from a URL, following redirects."""
    try:
        headers = _http_headers()
        headers["Accept"] = "application/pdf,*/*"
        resp = httpx.get(url, headers=headers, timeout=timeout, follow_redirects=True)
        resp.raise_for_status()
        ct = resp.headers.get("content-type", "")
        # Verify we got a PDF
        if "pdf" in ct or resp.content[:5] == b"%PDF-":
            return resp.content
        return None
    except Exception as e:
        logger.debug(f"Failed to fetch PDF from {url}: {e}")
        return None


def _strip_html(text: str) -> str:
    """Remove HTML/XML tags."""
    return re.sub(r"<[^>]+>", " ", text).strip()


def _truncate(text: str, max_chars: int = 100_000) -> str:
    """Truncate text to avoid oversized MCP responses."""
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + f"\n\n[... truncated at {max_chars} chars, total {len(text)}]"


# ── Source: Elsevier ───────────────────────────────────────────────


def _fetch_elsevier_fulltext(doi: str) -> dict[str, Any] | None:
    """Try Elsevier's full-text API (works for 10.1016/... DOIs)."""
    try:
        # Try XML first (structured full text)
        headers = _elsevier_headers(accept="text/xml")
        url = f"https://api.elsevier.com/content/article/doi/{doi}"
        resp = httpx.get(url, headers=headers, timeout=TIMEOUT)
        if resp.status_code == 200:
            text = _strip_html(resp.text)
            if len(text) > 500:  # Meaningful content
                return {
                    "source": "elsevier_api",
                    "format": "xml_stripped",
                    "content": _truncate(text),
                    "chars": len(text),
                }
        # Try plain text
        headers = _elsevier_headers(accept="text/plain")
        resp = httpx.get(url, headers=headers, timeout=TIMEOUT)
        if resp.status_code == 200 and len(resp.text) > 500:
            return {
                "source": "elsevier_api",
                "format": "plain_text",
                "content": _truncate(resp.text),
                "chars": len(resp.text),
            }
    except Exception as e:
        logger.debug(f"Elsevier full-text failed for {doi}: {e}")
    return None


def _fetch_elsevier_pdf(doi: str) -> bytes | None:
    """Try Elsevier's PDF API."""
    try:
        headers = _elsevier_headers(accept="application/pdf")
        url = f"https://api.elsevier.com/content/article/doi/{doi}"
        resp = httpx.get(url, headers=headers, timeout=TIMEOUT)
        if resp.status_code == 200 and (
            "pdf" in resp.headers.get("content-type", "")
            or resp.content[:5] == b"%PDF-"
        ):
            return resp.content
    except Exception as e:
        logger.debug(f"Elsevier PDF failed for {doi}: {e}")
    return None


# ── Source: PLOS ───────────────────────────────────────────────────


def _fetch_plos_fulltext(doi: str) -> dict[str, Any] | None:
    """Try PLOS API (works for 10.1371/... DOIs)."""
    try:
        params = {
            "q": f'id:"{doi}"',
            "fl": "id,title_display,body",
            "rows": 1,
            "wt": "json",
        }
        resp = httpx.get("https://api.plos.org/search", params=params, timeout=TIMEOUT)
        resp.raise_for_status()
        docs = resp.json().get("response", {}).get("docs", [])
        if docs and docs[0].get("body"):
            body = docs[0]["body"]
            return {
                "source": "plos_api",
                "format": "full_text",
                "content": _truncate(body),
                "chars": len(body),
            }
    except Exception as e:
        logger.debug(f"PLOS full-text failed for {doi}: {e}")
    return None


# ── Source: Springer Nature ────────────────────────────────────────


def _fetch_springer_fulltext(doi: str) -> dict[str, Any] | None:
    """Try Springer Nature OA API for full text."""
    try:
        from uf_mcp_manuscript_search.springer import _get_oa_key

        key = _get_oa_key()
        params = {"q": f"doi:{doi}", "p": 1, "api_key": key}
        resp = httpx.get(
            "https://api.springernature.com/openaccess/json",
            params=params,
            timeout=TIMEOUT,
        )
        resp.raise_for_status()
        records = resp.json().get("records", [])
        if records:
            # Check for body/full-text in the record
            rec = records[0]
            body = rec.get("body", "") or rec.get("abstract", "")
            urls = rec.get("url", [])
            url_map = {u.get("format", ""): u.get("value", "") for u in urls}

            # Try fetching HTML full text from the URL
            html_url = url_map.get("html", "")
            if html_url:
                text = _safe_text_fetch(html_url)
                if text and len(text) > 1000:
                    return {
                        "source": "springer_oa",
                        "format": "html_stripped",
                        "content": _truncate(_strip_html(text)),
                        "chars": len(text),
                    }

            if body and len(body) > 200:
                return {
                    "source": "springer_oa",
                    "format": "api_body",
                    "content": _truncate(body),
                    "chars": len(body),
                }
    except Exception as e:
        logger.debug(f"Springer full-text failed for {doi}: {e}")
    return None


def _fetch_springer_pdf_url(doi: str) -> str | None:
    """Get Springer Nature PDF URL if available."""
    try:
        from uf_mcp_manuscript_search.springer import _get_oa_key

        key = _get_oa_key()
        params = {"q": f"doi:{doi}", "p": 1, "api_key": key}
        resp = httpx.get(
            "https://api.springernature.com/openaccess/json",
            params=params,
            timeout=TIMEOUT,
        )
        resp.raise_for_status()
        records = resp.json().get("records", [])
        if records:
            urls = records[0].get("url", [])
            for u in urls:
                if u.get("format", "").lower() == "pdf":
                    return u.get("value", "")
    except Exception as e:
        logger.debug(f"Springer PDF URL failed for {doi}: {e}")
    return None


# ── Source: Unpaywall ──────────────────────────────────────────────


def _fetch_unpaywall_info(doi: str) -> dict[str, Any] | None:
    """Get OA URLs from Unpaywall."""
    email = _unpaywall_email()
    if not email:
        return None
    try:
        resp = httpx.get(
            f"https://api.unpaywall.org/v2/{doi}",
            params={"email": email},
            timeout=TIMEOUT,
        )
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        logger.debug(f"Unpaywall lookup failed for {doi}: {e}")
        return None


def _fetch_unpaywall_fulltext(doi: str) -> dict[str, Any] | None:
    """Try Unpaywall OA URLs for full text."""
    data = _fetch_unpaywall_info(doi)
    if not data or not data.get("is_oa"):
        return None

    # Try all OA locations
    for loc in data.get("oa_locations", []):
        # Try landing page for HTML full text
        landing = loc.get("url_for_landing_page", "") or loc.get("url", "")
        if landing:
            text = _safe_text_fetch(landing)
            if text and len(text) > 2000:
                return {
                    "source": "unpaywall_oa",
                    "format": "html_stripped",
                    "url": landing,
                    "content": _truncate(_strip_html(text)),
                    "chars": len(text),
                    "oa_status": data.get("oa_status", ""),
                    "version": loc.get("version", ""),
                }
    return None


def _get_unpaywall_pdf_url(doi: str) -> str | None:
    """Get best PDF URL from Unpaywall."""
    data = _fetch_unpaywall_info(doi)
    if not data or not data.get("is_oa"):
        return None

    best = data.get("best_oa_location", {})
    if best:
        pdf_url = best.get("url_for_pdf", "")
        if pdf_url:
            return pdf_url

    for loc in data.get("oa_locations", []):
        pdf_url = loc.get("url_for_pdf", "")
        if pdf_url:
            return pdf_url
    return None


# ── Source: CrossRef TDM ───────────────────────────────────────────


def _fetch_crossref_tdm_links(doi: str) -> list[dict[str, str]]:
    """Get TDM/full-text links from CrossRef metadata."""
    try:
        resp = httpx.get(
            f"https://api.crossref.org/works/{doi}",
            headers=_crossref_headers(),
            timeout=TIMEOUT,
        )
        resp.raise_for_status()
        message = resp.json().get("message", {})
        links = message.get("link", [])
        return [
            {
                "url": l.get("URL", ""),
                "content_type": l.get("content-type", ""),
                "intended_application": l.get("intended-application", ""),
            }
            for l in links
            if l.get("URL")
        ]
    except Exception as e:
        logger.debug(f"CrossRef TDM links failed for {doi}: {e}")
        return []


def _fetch_crossref_fulltext(doi: str) -> dict[str, Any] | None:
    """Try CrossRef TDM links for full text."""
    links = _fetch_crossref_tdm_links(doi)
    for link in links:
        ct = link.get("content_type", "")
        url = link["url"]
        if "xml" in ct or "html" in ct or "plain" in ct:
            text = _safe_text_fetch(url)
            if text and len(text) > 1000:
                return {
                    "source": "crossref_tdm",
                    "format": ct,
                    "url": url,
                    "content": _truncate(_strip_html(text)),
                    "chars": len(text),
                }
    return None


def _get_crossref_pdf_url(doi: str) -> str | None:
    """Get PDF URL from CrossRef TDM links."""
    links = _fetch_crossref_tdm_links(doi)
    for link in links:
        if "pdf" in link.get("content_type", ""):
            return link["url"]
    return None


# ── Public API ─────────────────────────────────────────────────────


def fetch_fulltext(doi: str) -> dict[str, Any]:
    """Fetch full-text content for a DOI, trying multiple sources.

    Cascade order:
    1. Elsevier API (10.1016/...)
    2. PLOS API (10.1371/...)
    3. Springer Nature OA (10.1007/..., 10.1038/...)
    4. Unpaywall OA locations
    5. CrossRef TDM links

    Returns dict with 'source', 'format', 'content', 'chars' on success,
    or 'error' with 'tried_sources' on failure.
    """
    doi = doi.strip()
    tried: list[str] = []

    # 1. Elsevier
    if doi.startswith("10.1016/"):
        tried.append("elsevier_api")
        result = _fetch_elsevier_fulltext(doi)
        if result:
            result["doi"] = doi
            return result

    # 2. PLOS
    if doi.startswith("10.1371/"):
        tried.append("plos_api")
        result = _fetch_plos_fulltext(doi)
        if result:
            result["doi"] = doi
            return result

    # 3. Springer Nature
    if doi.startswith(("10.1007/", "10.1038/", "10.1186/")):
        tried.append("springer_oa")
        result = _fetch_springer_fulltext(doi)
        if result:
            result["doi"] = doi
            return result

    # 4. Unpaywall
    tried.append("unpaywall")
    result = _fetch_unpaywall_fulltext(doi)
    if result:
        result["doi"] = doi
        return result

    # 5. CrossRef TDM
    tried.append("crossref_tdm")
    result = _fetch_crossref_fulltext(doi)
    if result:
        result["doi"] = doi
        return result

    return {
        "doi": doi,
        "error": "Full text not available from any source",
        "tried_sources": tried,
    }


def download_pdf(doi: str, output_dir: str = ".") -> dict[str, Any]:
    """Download a PDF for a DOI, trying multiple sources.

    Cascade order:
    1. Elsevier API (10.1016/...)
    2. Unpaywall best PDF URL
    3. CrossRef TDM PDF link
    4. Springer Nature OA PDF URL

    Returns dict with 'path', 'source', 'size_bytes' on success,
    or 'error' with 'tried_sources' on failure.
    """
    doi = doi.strip()
    tried: list[str] = []

    # Sanitize filename from DOI
    safe_name = doi.replace("/", "_").replace("\\", "_") + ".pdf"
    out_path = Path(output_dir).expanduser()
    out_path.mkdir(parents=True, exist_ok=True)
    filepath = out_path / safe_name

    # 1. Elsevier
    if doi.startswith("10.1016/"):
        tried.append("elsevier_api")
        pdf_bytes = _fetch_elsevier_pdf(doi)
        if pdf_bytes:
            filepath.write_bytes(pdf_bytes)
            return {
                "doi": doi,
                "source": "elsevier_api",
                "path": str(filepath),
                "size_bytes": len(pdf_bytes),
            }

    # 2. Unpaywall
    tried.append("unpaywall")
    pdf_url = _get_unpaywall_pdf_url(doi)
    if pdf_url:
        pdf_bytes = _safe_pdf_fetch(pdf_url)
        if pdf_bytes:
            filepath.write_bytes(pdf_bytes)
            return {
                "doi": doi,
                "source": "unpaywall",
                "url": pdf_url,
                "path": str(filepath),
                "size_bytes": len(pdf_bytes),
            }

    # 3. CrossRef TDM
    tried.append("crossref_tdm")
    pdf_url = _get_crossref_pdf_url(doi)
    if pdf_url:
        pdf_bytes = _safe_pdf_fetch(pdf_url)
        if pdf_bytes:
            filepath.write_bytes(pdf_bytes)
            return {
                "doi": doi,
                "source": "crossref_tdm",
                "url": pdf_url,
                "path": str(filepath),
                "size_bytes": len(pdf_bytes),
            }

    # 4. Springer Nature
    if doi.startswith(("10.1007/", "10.1038/", "10.1186/")):
        tried.append("springer_oa")
        pdf_url = _fetch_springer_pdf_url(doi)
        if pdf_url:
            pdf_bytes = _safe_pdf_fetch(pdf_url)
            if pdf_bytes:
                filepath.write_bytes(pdf_bytes)
                return {
                    "doi": doi,
                    "source": "springer_oa",
                    "url": pdf_url,
                    "path": str(filepath),
                    "size_bytes": len(pdf_bytes),
                }

    return {
        "doi": doi,
        "error": "PDF not available from any source",
        "tried_sources": tried,
    }
