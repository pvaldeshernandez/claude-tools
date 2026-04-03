"""Fetch abstracts for references via PubMed (Entrez) and CrossRef (habanero)."""

import time
import sys


def fetch_all(dois: list, email: str = "") -> dict:
    """Batch-fetch abstracts for a list of DOIs.

    Tries PubMed first, then CrossRef as fallback. Respects NCBI rate limits
    (max 3 requests/sec without API key).

    Args:
        dois: List of DOI strings (e.g., "10.1234/example").
        email: Email for NCBI Entrez (required for PubMed).

    Returns:
        dict mapping DOI -> abstract text (or None if not found).
    """
    results = {}
    for doi in dois:
        if not doi:
            continue
        abstract = _fetch_pubmed(doi, email)
        if not abstract:
            abstract = _fetch_crossref(doi)
        results[doi] = abstract
        time.sleep(0.34)  # NCBI rate limit: ~3/sec
    return results


def _fetch_pubmed(doi: str, email: str) -> str:
    """Fetch abstract from PubMed via Entrez using a DOI search."""
    try:
        from Bio import Entrez
    except ImportError:
        print("Warning: biopython not installed, PubMed fetching disabled.", file=sys.stderr)
        return None

    if not email:
        return None

    Entrez.email = email
    try:
        # Search for the DOI in PubMed
        handle = Entrez.esearch(db="pubmed", term=f"{doi}[DOI]", retmax=1)
        record = Entrez.read(handle)
        handle.close()

        id_list = record.get("IdList", [])
        if not id_list:
            return None

        # Fetch the article XML
        handle = Entrez.efetch(db="pubmed", id=id_list[0], rettype="xml", retmode="xml")
        records = Entrez.read(handle)
        handle.close()

        # Navigate XML structure to find AbstractText
        articles = records.get("PubmedArticle", [])
        if not articles:
            return None

        article = articles[0]
        medline = article.get("MedlineCitation", {})
        art_data = medline.get("Article", {})
        abstract_data = art_data.get("Abstract", {})
        abstract_texts = abstract_data.get("AbstractText", [])

        if not abstract_texts:
            return None

        # AbstractText can be a list of labeled sections or plain strings
        parts = []
        for text in abstract_texts:
            label = getattr(text, "attributes", {}).get("Label", "")
            content = str(text)
            if label:
                parts.append(f"<b>{label}:</b> {content}")
            else:
                parts.append(content)

        return " ".join(parts)

    except Exception:
        return None


def _fetch_crossref(doi: str) -> str:
    """Fetch abstract from CrossRef via habanero."""
    try:
        from habanero import Crossref
    except ImportError:
        print("Warning: habanero not installed, CrossRef fetching disabled.", file=sys.stderr)
        return None

    try:
        cr = Crossref()
        result = cr.works(ids=doi)
        message = result.get("message", {})
        abstract = message.get("abstract", "")
        if abstract:
            # CrossRef abstracts sometimes have JATS XML tags
            import re
            abstract = re.sub(r"<[^>]+>", "", abstract).strip()
            return abstract
        return None
    except Exception:
        return None
