"""PLOS API client — all PLOS journals, fully open access.

Covers PLOS ONE, PLOS Medicine, PLOS Biology, PLOS Genetics,
PLOS Computational Biology, PLOS Pathogens, PLOS Neglected Tropical Diseases.
"""

from typing import Any

import httpx

BASE_URL = "https://api.plos.org/search"
TIMEOUT = 30.0

# Field list for search results
_DEFAULT_FIELDS = (
    "id,doi,title_display,abstract,author_display,journal,publication_date,"
    "volume,issue,pagecount,article_type,subject,score"
)


def _get(params: dict[str, Any]) -> dict[str, Any]:
    params["wt"] = "json"
    resp = httpx.get(BASE_URL, params=params, timeout=TIMEOUT)
    resp.raise_for_status()
    return resp.json()


def _parse_doc(doc: dict[str, Any]) -> dict[str, Any]:
    """Normalize a PLOS Solr document."""
    return {
        "id": doc.get("id", ""),
        "doi": doc.get("doi", ""),
        "title": doc.get("title_display", ""),
        "abstract": (doc.get("abstract", [""])[0] if isinstance(doc.get("abstract"), list)
                      else doc.get("abstract", "")),
        "authors": doc.get("author_display", []),
        "journal": doc.get("journal", ""),
        "pub_date": doc.get("publication_date", ""),
        "volume": doc.get("volume", ""),
        "issue": doc.get("issue", ""),
        "article_type": doc.get("article_type", ""),
        "subjects": doc.get("subject", []),
        "score": doc.get("score", 0),
    }


def plos_search(
    query: str,
    count: int = 10,
    start: int = 0,
    journal: str = "",
    article_type: str = "",
    subject: str = "",
    date_from: str = "",
    date_to: str = "",
) -> dict[str, Any]:
    """Search PLOS journals using Solr query syntax.

    Query supports field-specific searches:
    - title:"term" — title only
    - abstract:"term" — abstract only
    - author:"name" — author search
    - everything:"term" — full text search
    - subject:"term" — subject area
    - Default searches across title, abstract, body.

    Journal filter values:
    - PLoS ONE, PLoS Medicine, PLoS Biology, PLoS Genetics,
      PLoS Computational Biology, PLoS Pathogens, PLoS Neglected Tropical Diseases

    Article types: Research Article, Review, Editorial, etc.

    Date format: YYYY-MM-DDT00:00:00Z (or just YYYY-MM-DD, will be normalized)
    """
    params: dict[str, Any] = {
        "q": query,
        "fl": _DEFAULT_FIELDS,
        "rows": min(count, 100),
        "start": start,
    }

    fq_parts: list[str] = []
    if journal:
        fq_parts.append(f'journal:"{journal}"')
    if article_type:
        fq_parts.append(f'article_type:"{article_type}"')
    if subject:
        fq_parts.append(f'subject:"{subject}"')
    if date_from or date_to:
        df = date_from if "T" in date_from else f"{date_from}T00:00:00Z" if date_from else "*"
        dt = date_to if "T" in date_to else f"{date_to}T23:59:59Z" if date_to else "*"
        fq_parts.append(f"publication_date:[{df} TO {dt}]")

    if fq_parts:
        params["fq"] = " AND ".join(fq_parts)

    data = _get(params)
    response = data.get("response", {})

    return {
        "total_results": response.get("numFound", 0),
        "returned": len(response.get("docs", [])),
        "articles": [_parse_doc(doc) for doc in response.get("docs", [])],
    }


def plos_article(doi: str) -> dict[str, Any]:
    """Get a PLOS article by DOI.

    Example: "10.1371/journal.pone.0001234"
    """
    # PLOS DOIs double as IDs
    params: dict[str, Any] = {
        "q": f'id:"{doi}"',
        "fl": _DEFAULT_FIELDS + ",body",
        "rows": 1,
    }
    data = _get(params)
    docs = data.get("response", {}).get("docs", [])
    if not docs:
        return {"error": f"No article found for DOI: {doi}"}

    result = _parse_doc(docs[0])
    # Include body text if available
    body = docs[0].get("body", "")
    if body:
        result["full_text"] = body
    return result


def plos_api_status() -> dict[str, Any]:
    """Check PLOS API connectivity. No API key required."""
    result: dict[str, Any] = {"requires_key": False}
    try:
        data = plos_search("test", count=1)
        result["connected"] = True
        result["test_total_results"] = data.get("total_results", "?")
    except Exception as e:
        result["connected"] = False
        result["error"] = str(e)
    return result
