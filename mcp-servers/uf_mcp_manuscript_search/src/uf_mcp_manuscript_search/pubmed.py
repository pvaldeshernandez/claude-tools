"""PubMed E-Utilities API client."""

import os
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

import httpx

BASE_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
PMC_ID_CONVERTER = "https://pmc.ncbi.nlm.nih.gov/tools/idconv/api/v1/articles/"
TIMEOUT = 30.0
TOOL_NAME = "uf-mcp-manuscript-search"

_KEY_FILE = Path.home() / ".ncbi" / "api_key.txt"
_EMAIL_FILE = Path.home() / ".ncbi" / "email.txt"


def _get_api_key() -> str | None:
    key = os.environ.get("NCBI_API_KEY", "").strip()
    if key:
        return key
    if _KEY_FILE.exists():
        key = _KEY_FILE.read_text(encoding="utf-8").strip()
        if key:
            return key
    return None


def _get_email() -> str:
    email = os.environ.get("NCBI_EMAIL", "").strip()
    if email:
        return email
    if _EMAIL_FILE.exists():
        email = _EMAIL_FILE.read_text(encoding="utf-8").strip()
        if email:
            return email
    return "user@example.com"


def _base_params() -> dict[str, str]:
    """Common params required by all E-Utility requests."""
    params: dict[str, str] = {
        "tool": TOOL_NAME,
        "email": _get_email(),
    }
    key = _get_api_key()
    if key:
        params["api_key"] = key
    return params


def _get(endpoint: str, params: dict[str, Any]) -> httpx.Response:
    url = f"{BASE_URL}/{endpoint}"
    all_params = {**_base_params(), **params}
    resp = httpx.get(url, params=all_params, timeout=TIMEOUT)
    resp.raise_for_status()
    return resp


# ── XML parsing helpers ──────────────────────────────────────────────


def _text(el: ET.Element | None, tag: str) -> str:
    """Get text content of a child element."""
    child = el.find(tag) if el is not None else None
    return (child.text or "").strip() if child is not None else ""


def _parse_article(article_el: ET.Element) -> dict[str, Any]:
    """Parse a PubmedArticle XML element into a dict."""
    citation = article_el.find("MedlineCitation")
    article = citation.find("Article") if citation is not None else None
    pubmed_data = article_el.find("PubmedData")

    pmid = _text(citation, "PMID")

    # Title
    title = _text(article, "ArticleTitle")

    # Abstract — may have multiple labeled sections
    abstract_parts: list[str] = []
    abstract_el = article.find("Abstract") if article is not None else None
    if abstract_el is not None:
        for at in abstract_el.findall("AbstractText"):
            label = at.get("Label", "")
            text = "".join(at.itertext()).strip()
            if label:
                abstract_parts.append(f"{label}: {text}")
            else:
                abstract_parts.append(text)
    abstract = "\n\n".join(abstract_parts)

    # Authors
    authors: list[dict[str, str]] = []
    author_list = article.find("AuthorList") if article is not None else None
    if author_list is not None:
        for au in author_list.findall("Author"):
            last = _text(au, "LastName")
            fore = _text(au, "ForeName")
            affil_el = au.find(".//Affiliation")
            affil = affil_el.text.strip() if affil_el is not None and affil_el.text else ""
            if last:
                entry: dict[str, str] = {"name": f"{fore} {last}".strip()}
                if affil:
                    entry["affiliation"] = affil
                authors.append(entry)

    # Journal
    journal_el = article.find("Journal") if article is not None else None
    journal = _text(journal_el, "Title")
    journal_abbrev = _text(journal_el, "ISOAbbreviation")
    pub_date_el = journal_el.find(".//PubDate") if journal_el is not None else None
    pub_year = _text(pub_date_el, "Year")
    pub_month = _text(pub_date_el, "Month")
    volume = _text(journal_el, ".//Volume") if journal_el is not None else ""
    issue = _text(journal_el, ".//Issue") if journal_el is not None else ""

    # IDs (DOI, PMC)
    ids: dict[str, str] = {"pmid": pmid}
    if pubmed_data is not None:
        for aid in pubmed_data.findall(".//ArticleId"):
            id_type = aid.get("IdType", "")
            if aid.text:
                ids[id_type] = aid.text.strip()

    # MeSH terms
    mesh_terms: list[str] = []
    mesh_list = citation.find("MeshHeadingList") if citation is not None else None
    if mesh_list is not None:
        for mh in mesh_list.findall("MeshHeading"):
            desc = mh.find("DescriptorName")
            if desc is not None and desc.text:
                mesh_terms.append(desc.text.strip())

    # Keywords
    keywords: list[str] = []
    if citation is not None:
        for kw_list in citation.findall("KeywordList"):
            for kw in kw_list.findall("Keyword"):
                if kw.text:
                    keywords.append(kw.text.strip())

    result: dict[str, Any] = {
        "pmid": pmid,
        "title": title,
        "abstract": abstract,
        "authors": authors,
        "journal": journal,
        "journal_abbrev": journal_abbrev,
        "pub_year": pub_year,
        "pub_month": pub_month,
        "volume": volume,
        "issue": issue,
        "ids": ids,
        "mesh_terms": mesh_terms,
        "keywords": keywords,
    }
    return result


# ── Public API functions ─────────────────────────────────────────────


def pubmed_search(
    query: str,
    count: int = 10,
    start: int = 0,
    sort: str = "relevance",
    min_date: str = "",
    max_date: str = "",
) -> dict[str, Any]:
    """Search PubMed and return matching PMIDs with summary info.

    Sort options: relevance, pub_date, Author, JournalName
    Date format: YYYY/MM/DD or YYYY
    """
    params: dict[str, Any] = {
        "db": "pubmed",
        "term": query,
        "retmax": min(count, 200),
        "retstart": start,
        "sort": sort,
        "retmode": "json",
        "usehistory": "y",
    }
    if min_date:
        params["mindate"] = min_date
        params["datetype"] = "pdat"
    if max_date:
        params["maxdate"] = max_date
        if "datetype" not in params:
            params["datetype"] = "pdat"

    resp = _get("esearch.fcgi", params)
    data = resp.json()
    result = data.get("esearchresult", {})

    return {
        "total_results": int(result.get("count", 0)),
        "returned": len(result.get("idlist", [])),
        "pmids": result.get("idlist", []),
        "query_translation": result.get("querytranslation", ""),
    }


def pubmed_fetch(pmids: list[str]) -> dict[str, Any]:
    """Fetch full article records for one or more PMIDs.

    Returns parsed article data including title, abstract, authors, MeSH terms.
    """
    if not pmids:
        return {"articles": []}

    params: dict[str, Any] = {
        "db": "pubmed",
        "id": ",".join(pmids[:50]),  # cap at 50 per request
        "retmode": "xml",
    }
    resp = _get("efetch.fcgi", params)
    root = ET.fromstring(resp.text)

    articles = []
    for art_el in root.findall("PubmedArticle"):
        articles.append(_parse_article(art_el))

    return {"articles": articles, "count": len(articles)}


def pubmed_summary(pmids: list[str]) -> dict[str, Any]:
    """Get brief summaries for PMIDs (faster than full fetch)."""
    if not pmids:
        return {"summaries": []}

    params: dict[str, Any] = {
        "db": "pubmed",
        "id": ",".join(pmids[:200]),
        "retmode": "json",
        "version": "2.0",
    }
    resp = _get("esummary.fcgi", params)
    data = resp.json()

    result_data = data.get("result", {})
    uids = result_data.get("uids", [])

    summaries = []
    for uid in uids:
        doc = result_data.get(uid, {})
        summaries.append({
            "pmid": uid,
            "title": doc.get("title", ""),
            "authors": [
                a.get("name", "") for a in doc.get("authors", [])
            ],
            "source": doc.get("source", ""),
            "pub_date": doc.get("pubdate", ""),
            "volume": doc.get("volume", ""),
            "issue": doc.get("issue", ""),
            "doi": doc.get("elocationid", ""),
        })

    return {"summaries": summaries, "count": len(summaries)}


def pubmed_related(pmid: str, count: int = 10) -> dict[str, Any]:
    """Find articles related to a given PMID."""
    params: dict[str, Any] = {
        "dbfrom": "pubmed",
        "db": "pubmed",
        "id": pmid,
        "cmd": "neighbor_score",
        "retmode": "json",
    }
    resp = _get("elink.fcgi", params)
    data = resp.json()

    linksets = data.get("linksets", [])
    related: list[dict[str, Any]] = []
    if linksets:
        for linkset_db in linksets[0].get("linksetdbs", []):
            if linkset_db.get("linkname") == "pubmed_pubmed":
                for link in linkset_db.get("links", [])[:count]:
                    related.append({
                        "pmid": link.get("id", ""),
                        "score": link.get("score", ""),
                    })
                break

    return {"source_pmid": pmid, "related": related, "count": len(related)}


def pmc_lookup(ids: list[str], id_type: str = "pmid") -> dict[str, Any]:
    """Convert between PMID, PMCID, and DOI using the PMC ID Converter.

    id_type: 'pmid', 'pmcid', or 'doi'
    """
    params: dict[str, Any] = {
        "ids": ",".join(ids[:200]),
        "format": "json",
        "tool": TOOL_NAME,
        "email": _get_email(),
    }
    if id_type != "pmid":
        params["idtype"] = id_type

    resp = httpx.get(PMC_ID_CONVERTER, params=params, timeout=TIMEOUT)
    resp.raise_for_status()
    data = resp.json()

    records = data.get("records", [])
    return {
        "records": [
            {
                "pmid": r.get("pmid", ""),
                "pmcid": r.get("pmcid", ""),
                "doi": r.get("doi", ""),
            }
            for r in records
            if "errmsg" not in r
        ],
        "count": len([r for r in records if "errmsg" not in r]),
    }


def pubmed_api_status() -> dict[str, Any]:
    """Check PubMed API configuration and connectivity."""
    key = _get_api_key()
    email = _get_email()
    result: dict[str, Any] = {
        "api_key_configured": key is not None,
        "email": email,
        "rate_limit": "10/sec" if key else "3/sec",
    }
    try:
        search = pubmed_search("test", count=1)
        result["connected"] = True
        result["test_total_results"] = search["total_results"]
    except Exception as e:
        result["connected"] = False
        result["error"] = str(e)
    return result
