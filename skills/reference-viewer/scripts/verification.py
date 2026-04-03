"""Evidence-gathering for AI reference verification.

Assembles evidence packages from parsed manuscript data so Claude can
evaluate whether each reference actually supports the claims made.

Two verification layers:
1. Bibliographic: Cross-check title/authors/year/journal against external sources.
2. Content: Snippet extraction from PDF confirms the PDF-reference link.
"""

import re


def gather_evidence(
    ref_num: int,
    reference: dict,
    citation_contexts: list,
    abstract: str = "",
    paper_snippets: list = None,
    pdf_full_text: str = "",
) -> dict:
    """Assemble all available evidence for one reference.

    Args:
        ref_num: Reference number in the manuscript.
        reference: Reference dict with keys: ref, doi, title, authors, year, journal.
        citation_contexts: List of citation dicts with section, snippet, line.
        abstract: Abstract text (from external MCP fetching).
        paper_snippets: List of supporting passage strings from snippet_extractor.
        pdf_full_text: Raw full text of the matched PDF (if available).

    Returns dict with structured evidence for Claude to evaluate.
    """
    if paper_snippets is None:
        paper_snippets = []

    claims = extract_claims(citation_contexts)

    # Take a manageable excerpt from full text
    full_text_excerpt = ""
    if pdf_full_text:
        full_text_excerpt = pdf_full_text[:4000].strip()
        if len(pdf_full_text) > 4000:
            full_text_excerpt += "\n\n[... truncated ...]"

    evidence_text = format_evidence_package(
        ref_num=ref_num,
        reference=reference,
        claims=claims,
        abstract=abstract,
        paper_snippets=paper_snippets,
        full_text_excerpt=full_text_excerpt,
    )

    return {
        "ref_num": ref_num,
        "reference": reference,
        "citation_contexts": citation_contexts,
        "abstract": abstract or None,
        "paper_snippets": paper_snippets or None,
        "full_text_excerpt": full_text_excerpt or None,
        "claims_made": claims,
        "evidence_summary": evidence_text,
        "pdf_available": bool(pdf_full_text),
    }


def extract_claims(citation_contexts: list) -> list:
    """Parse each citation snippet to isolate the specific assertion being supported."""
    claims = []
    for ctx in citation_contexts:
        snippet = ctx.get("snippet", "").strip()
        if not snippet:
            continue
        # Remove bracket citations
        claim = re.sub(
            r"\[\d+(?:[,\s\u2013\u2014\-\u2010\u2011\u2012\u2013\u2014]*\d+)*\]",
            "", snippet,
        ).strip()
        claim = claim.strip("., ")
        if claim and len(claim) > 10:
            section = ctx.get("section", "Unknown")
            claims.append(f"[{section}] {claim}")
    return claims


def format_evidence_package(
    ref_num: int,
    reference: dict,
    claims: list,
    abstract: str = "",
    paper_snippets: list = None,
    full_text_excerpt: str = "",
) -> str:
    """Format a structured evidence package as text for Claude to evaluate."""
    if paper_snippets is None:
        paper_snippets = []

    lines = []

    lines.append(f"=== REFERENCE [{ref_num}] ===")
    lines.append(f"Authors: {reference.get('authors', 'N/A')}")
    lines.append(f"Year: {reference.get('year', 'N/A')}")
    lines.append(f"Title: {reference.get('title', 'N/A')}")
    lines.append(f"Journal: {reference.get('journal', 'N/A')}")
    lines.append(f"DOI: {reference.get('doi', 'N/A')}")
    lines.append(f"Full ref: {reference.get('ref', 'N/A')}")
    lines.append("")

    lines.append(f"=== CLAIMS IN MANUSCRIPT ({len(claims)}) ===")
    if claims:
        for i, claim in enumerate(claims, 1):
            lines.append(f"  {i}. {claim}")
    else:
        lines.append("  (No citation contexts found)")
    lines.append("")

    lines.append("=== ABSTRACT ===")
    if abstract:
        clean = re.sub(r"<[^>]+>", "", abstract)
        lines.append(clean)
    else:
        lines.append("(Abstract not available)")
    lines.append("")

    lines.append("=== SUPPORTING PASSAGES FROM PAPER ===")
    if paper_snippets:
        for i, snip in enumerate(paper_snippets, 1):
            lines.append(f"  --- Passage {i} ---")
            lines.append(f"  {snip[:500]}")
    else:
        lines.append("(Full document not available)")
    lines.append("")

    if full_text_excerpt:
        lines.append("=== FULL TEXT EXCERPT (first ~4000 chars) ===")
        lines.append(full_text_excerpt)
        lines.append("")

    return "\n".join(lines)
