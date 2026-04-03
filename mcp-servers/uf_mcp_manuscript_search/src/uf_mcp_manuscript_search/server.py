"""Academic literature MCP server.

Elsevier (12): scopus_search, scopus_abstract, scopus_abstract_by_doi,
scopus_author, scopus_author_search, scopus_affiliation_search, scidir_search,
scidir_article, scidir_article_by_pii, serial_search, serial_title, api_key_status.

PubMed (6): pubmed_search, pubmed_fetch, pubmed_summary, pubmed_related,
pmc_lookup, pubmed_api_status.

Springer Nature (4): springer_search, springer_open_access, springer_by_doi,
springer_api_status.

CrossRef (5): crossref_search, crossref_work, crossref_journal,
crossref_funder_works, crossref_api_status.

PLOS (3): plos_search, plos_article, plos_api_status.

Unpaywall (3): unpaywall_lookup, unpaywall_batch, unpaywall_api_status.
"""

import logging
import sys
from typing import Any

from mcp.server.fastmcp import FastMCP

from uf_mcp_manuscript_search import api, crossref, fulltext, plos, pubmed, springer, unpaywall

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger("uf_mcp_manuscript_search")

mcp = FastMCP("uf_mcp_manuscript_search")


def _safe(func: Any, *args: Any, **kwargs: Any) -> dict[str, Any]:
    try:
        return func(*args, **kwargs)
    except Exception as e:
        logger.exception(f"Error in {func.__name__}")
        return {"error": str(e)}


# ── Scopus Tools ────────────────────────────────────────────────────


@mcp.tool()
def scopus_search(
    query: str,
    count: int = 10,
    start: int = 0,
    sort: str = "-citedby-count",
) -> dict[str, Any]:
    """Search Scopus for academic articles.

    Uses Scopus search syntax. Common field codes:
    - TITLE-ABS-KEY(term) — title, abstract, or keyword
    - TITLE(term) — title only
    - AUTH(name) — author name
    - SRCTITLE(journal) — source/journal title
    - SUBJAREA(MEDI) — subject area
    - PUBYEAR > 2020 — publication year filter
    - AND, OR, AND NOT — boolean operators

    Examples:
      "TITLE-ABS-KEY(gait analysis) AND PUBYEAR > 2020"
      "TITLE(machine learning) AND SUBJAREA(MEDI)"

    Args:
        query: Scopus search query string
        count: Number of results (max 25)
        start: Offset for pagination
        sort: Sort order (default: most cited first)
    """
    return _safe(api.scopus_search, query, count, start, sort)


@mcp.tool()
def scopus_abstract(scopus_id: str) -> dict[str, Any]:
    """Get full abstract and metadata for a paper by Scopus ID.

    Returns: title, abstract, authors, citations, keywords, references, DOI, etc.
    """
    return _safe(api.scopus_abstract, scopus_id)


@mcp.tool()
def scopus_abstract_by_doi(doi: str) -> dict[str, Any]:
    """Get full abstract and metadata for a paper by DOI.

    Example: "10.1016/j.gaitpost.2023.01.001"
    """
    return _safe(api.scopus_abstract_by_doi, doi)


@mcp.tool()
def scopus_author(author_id: str) -> dict[str, Any]:
    """Get author profile from Scopus — name, affiliation, h-index, publication count, etc."""
    return _safe(api.scopus_author, author_id)


@mcp.tool()
def scopus_author_search(query: str, count: int = 10) -> dict[str, Any]:
    """Search for authors in Scopus.

    Examples:
      "AUTHLASTNAME(smith) AND AUTHFIRST(john)"
      "AFFIL(university of florida)"
    """
    return _safe(api.scopus_author_search, query, count)


@mcp.tool()
def scopus_affiliation_search(query: str, count: int = 10) -> dict[str, Any]:
    """Search for institutions/affiliations in Scopus.

    Example: "AFFIL(university florida)"
    """
    return _safe(api.scopus_affiliation_search, query, count)


# ── ScienceDirect Tools ────────────────────────────────────────────


@mcp.tool()
def scidir_search(query: str, count: int = 10, start: int = 0) -> dict[str, Any]:
    """Search ScienceDirect for full-text articles by keyword.

    Searches across Elsevier's full-text journal and book content.
    """
    return _safe(api.scidir_search, query, count, start)


@mcp.tool()
def scidir_article(doi: str) -> dict[str, Any]:
    """Get a ScienceDirect article by DOI. Returns full text if your institution has access."""
    return _safe(api.scidir_article, doi)


@mcp.tool()
def scidir_article_by_pii(pii: str) -> dict[str, Any]:
    """Get a ScienceDirect article by PII (Publisher Item Identifier)."""
    return _safe(api.scidir_article_by_pii, pii)


# ── Journal/Serial Tools ───────────────────────────────────────────


@mcp.tool()
def serial_search(title: str, count: int = 10) -> dict[str, Any]:
    """Search for journals by title keyword. Returns ISSN, publisher, impact metrics."""
    return _safe(api.serial_search, title, count)


@mcp.tool()
def serial_title(issn: str) -> dict[str, Any]:
    """Get journal metadata by ISSN — title, publisher, SJR, SNIP, subject areas."""
    return _safe(api.serial_title, issn)


# ── Utility ─────────────────────────────────────────────────────────


@mcp.tool()
def api_key_status() -> dict[str, Any]:
    """Check if the Elsevier API key is configured and working."""
    try:
        key = api._get_api_key()
        masked = key[:4] + "..." + key[-4:] if len(key) > 8 else "****"
        # Quick test call
        result = api.scopus_search("test", count=1)
        total = result.get("search-results", {}).get("opensearch:totalResults", "?")
        return {"configured": True, "key": masked, "test_query_results": total}
    except Exception as e:
        return {"configured": False, "error": str(e)}


# ── PubMed Tools ──────────────────────────────────────────────────


@mcp.tool()
def pubmed_search(
    query: str,
    count: int = 10,
    start: int = 0,
    sort: str = "relevance",
    min_date: str = "",
    max_date: str = "",
) -> dict[str, Any]:
    """Search PubMed for biomedical articles.

    Uses PubMed query syntax with field tags:
    - [TI] — title
    - [TIAB] — title + abstract
    - [AU] — author
    - [MH] — MeSH term
    - [TA] — journal abbreviation
    - [DP] — date of publication
    - AND, OR, NOT — boolean operators

    Examples:
      "gait analysis[TIAB] AND aging[MH]"
      "smith j[AU] AND rehabilitation[TIAB]"
      "COVID-19[MH] AND vaccine[TI]"

    Args:
        query: PubMed search query
        count: Number of results (max 200)
        start: Offset for pagination
        sort: relevance, pub_date, Author, or JournalName
        min_date: Filter start date (YYYY/MM/DD or YYYY)
        max_date: Filter end date (YYYY/MM/DD or YYYY)
    """
    return _safe(pubmed.pubmed_search, query, count, start, sort, min_date, max_date)


@mcp.tool()
def pubmed_fetch(pmids: list[str]) -> dict[str, Any]:
    """Get full article records for PubMed IDs.

    Returns title, abstract, authors, MeSH terms, keywords, journal info, DOI.
    Accepts up to 50 PMIDs per call.
    """
    return _safe(pubmed.pubmed_fetch, pmids)


@mcp.tool()
def pubmed_summary(pmids: list[str]) -> dict[str, Any]:
    """Get brief metadata summaries for PubMed IDs (faster than full fetch).

    Returns title, authors, journal, date, DOI.
    Accepts up to 200 PMIDs per call.
    """
    return _safe(pubmed.pubmed_summary, pmids)


@mcp.tool()
def pubmed_related(pmid: str, count: int = 10) -> dict[str, Any]:
    """Find articles related to a given PubMed ID, ranked by similarity score."""
    return _safe(pubmed.pubmed_related, pmid, count)


@mcp.tool()
def pmc_lookup(ids: list[str], id_type: str = "pmid") -> dict[str, Any]:
    """Convert between PMID, PMCID, and DOI using the PMC ID Converter.

    Args:
        ids: List of identifiers to convert
        id_type: Type of input IDs — 'pmid', 'pmcid', or 'doi'

    Returns PMID, PMCID, and DOI for each input ID (where available).
    """
    return _safe(pubmed.pmc_lookup, ids, id_type)


@mcp.tool()
def pubmed_api_status() -> dict[str, Any]:
    """Check PubMed/NCBI API key configuration and connectivity.

    API key is optional but increases rate limit from 3/sec to 10/sec.
    Set NCBI_API_KEY env var or put key in ~/.ncbi/api_key.txt
    """
    return _safe(pubmed.pubmed_api_status)


# ── Springer Nature Tools ────────────────────────────────────────


@mcp.tool()
def springer_search(
    query: str,
    count: int = 10,
    start: int = 1,
    subject: str = "",
    date_from: str = "",
    date_to: str = "",
) -> dict[str, Any]:
    """Search Springer Nature for articles (covers Springer, Nature, BMC, Palgrave).

    Query supports keywords and field prefixes:
    - subject:Chemistry, doi:10.1007/..., title:..., orgname:...

    Args:
        query: Search query
        count: Number of results (max 50)
        start: Start index (1-based)
        subject: Filter by subject area
        date_from: Start date (YYYY-MM-DD)
        date_to: End date (YYYY-MM-DD)
    """
    return _safe(springer.springer_search, query, count, start, subject, date_from, date_to)


@mcp.tool()
def springer_open_access(query: str, count: int = 10, start: int = 1) -> dict[str, Any]:
    """Search Springer Nature for open access articles only (full text available)."""
    return _safe(springer.springer_open_access, query, count, start)


@mcp.tool()
def springer_by_doi(doi: str) -> dict[str, Any]:
    """Get Springer Nature article metadata by DOI."""
    return _safe(springer.springer_by_doi, doi)


@mcp.tool()
def springer_api_status() -> dict[str, Any]:
    """Check Springer Nature API key and connectivity.

    Get a free key at https://dev.springernature.com/
    Set SPRINGER_API_KEY env var or put key in ~/.springer/api_key.txt
    """
    return _safe(springer.springer_api_status)


# ── CrossRef Tools ───────────────────────────────────────────────


@mcp.tool()
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
    """Search CrossRef for articles across ALL publishers.

    Covers Frontiers, Science/AAAS, Wiley, Taylor & Francis, IEEE, Springer,
    Elsevier, PLOS, and any publisher that registers DOIs.

    Args:
        query: Search query
        count: Number of results (max 100)
        offset: Pagination offset
        sort: relevance, published, deposited, indexed, is-referenced-by-count
        order: asc or desc
        filter_from_date: Start date (YYYY-MM-DD)
        filter_to_date: End date (YYYY-MM-DD)
        filter_type: journal-article, book-chapter, proceedings-article, etc.
    """
    return _safe(
        crossref.crossref_search, query, count, offset, sort, order,
        filter_from_date, filter_to_date, filter_type,
    )


@mcp.tool()
def crossref_work(doi: str) -> dict[str, Any]:
    """Get metadata for any DOI from CrossRef.

    Works for Frontiers, Science, Nature, Wiley, IEEE — any publisher with DOIs.
    Returns title, authors, abstract, journal, citations, references count.
    """
    return _safe(crossref.crossref_work, doi)


@mcp.tool()
def crossref_journal(issn: str, count: int = 10, offset: int = 0) -> dict[str, Any]:
    """Get journal info and recent articles by ISSN from CrossRef."""
    return _safe(crossref.crossref_journal, issn, count, offset)


@mcp.tool()
def crossref_funder_works(funder_id: str, query: str = "", count: int = 10) -> dict[str, Any]:
    """Search for works by funder ID in CrossRef.

    Example funder IDs: 100000002 (NIH), 100000001 (NSF), 501100000266 (EPSRC).
    """
    return _safe(crossref.crossref_funder_works, funder_id, query, count)


@mcp.tool()
def crossref_api_status() -> dict[str, Any]:
    """Check CrossRef API connectivity and polite pool status.

    No key needed. Set CROSSREF_EMAIL or ~/.crossref/email.txt for faster rate limits.
    """
    return _safe(crossref.crossref_api_status)


# ── PLOS Tools ───────────────────────────────────────────────────


@mcp.tool()
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
    """Search PLOS journals (all open access).

    Covers PLOS ONE, PLOS Medicine, PLOS Biology, PLOS Genetics,
    PLOS Computational Biology, PLOS Pathogens, PLOS NTD.

    Uses Solr query syntax:
    - title:"term", abstract:"term", author:"name", everything:"term"
    - Default searches title + abstract + body

    Args:
        query: Search query (Solr syntax)
        count: Number of results (max 100)
        start: Pagination offset
        journal: Filter by journal name (e.g. "PLoS ONE")
        article_type: Filter by type (e.g. "Research Article")
        subject: Filter by subject area
        date_from: Start date (YYYY-MM-DD)
        date_to: End date (YYYY-MM-DD)
    """
    return _safe(
        plos.plos_search, query, count, start, journal, article_type, subject,
        date_from, date_to,
    )


@mcp.tool()
def plos_article(doi: str) -> dict[str, Any]:
    """Get a PLOS article by DOI, including full text.

    Example: "10.1371/journal.pone.0001234"
    """
    return _safe(plos.plos_article, doi)


@mcp.tool()
def plos_api_status() -> dict[str, Any]:
    """Check PLOS API connectivity. No API key required — all PLOS content is open access."""
    return _safe(plos.plos_api_status)


# ── Unpaywall Tools ──────────────────────────────────────────────


@mcp.tool()
def unpaywall_lookup(doi: str) -> dict[str, Any]:
    """Find open access full text for an article by DOI.

    Returns OA status (gold/green/hybrid/bronze/closed), PDF URLs,
    and all available OA locations (publisher, repository, preprint).

    Example: "10.1016/j.gaitpost.2023.01.001"
    """
    return _safe(unpaywall.unpaywall_lookup, doi)


@mcp.tool()
def unpaywall_batch(dois: list[str]) -> dict[str, Any]:
    """Check multiple DOIs for open access availability (up to 25).

    Returns OA status and best PDF URL for each DOI.
    """
    return _safe(unpaywall.unpaywall_batch, dois)


@mcp.tool()
def unpaywall_api_status() -> dict[str, Any]:
    """Check Unpaywall connectivity. Requires email only (no key).

    Set UNPAYWALL_EMAIL env var or put email in ~/.unpaywall/email.txt
    """
    return _safe(unpaywall.unpaywall_api_status)


# ── Full-Text & PDF Tools ───────────────────────────────────────


@mcp.tool()
def fetch_fulltext(doi: str) -> dict[str, Any]:
    """Fetch full-text content of an article by DOI.

    Tries multiple sources in cascade:
    1. Elsevier API (for Elsevier/ScienceDirect DOIs)
    2. PLOS API (for PLOS DOIs — always open access)
    3. Springer Nature OA API (for Springer/Nature/BMC DOIs)
    4. Unpaywall (finds open access copies from any publisher)
    5. CrossRef TDM links (text-mining URLs registered by publishers)

    Returns the full text content as a string, plus source and format metadata.

    Example: "10.1016/j.neuroscience.2023.01.001"
    """
    return _safe(fulltext.fetch_fulltext, doi)


@mcp.tool()
def download_pdf(doi: str, output_dir: str = ".") -> dict[str, Any]:
    """Download the PDF of an article by DOI.

    Tries multiple sources in cascade:
    1. Elsevier API (direct PDF for Elsevier DOIs with institutional access)
    2. Unpaywall (best open access PDF URL)
    3. CrossRef TDM links (PDF URLs registered by publishers)
    4. Springer Nature OA (PDF for open access Springer/Nature articles)

    Args:
        doi: Article DOI (e.g. "10.1016/j.pain.2023.01.001")
        output_dir: Directory to save the PDF (default: current directory)

    Returns path to downloaded file, source, and file size.
    """
    return _safe(fulltext.download_pdf, doi, output_dir)


def main() -> None:
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
