"""Evidence-gathering module for AI reference verification.

Assembles evidence packages from parsed manuscript data so Claude can
evaluate whether each reference actually supports the claims made.

Verification has two complementary layers:
1. **Primary (bibliographic)**: Cross-check title, authors, year, journal against
   PubMed or web sources. This catches wrong author lists, wrong titles, and
   fabricated references. Independent of the PDF.
2. **Secondary (content)**: Successful snippet extraction from the PDF confirms
   the PDF exists, is readable, and contains content matching the reference.
   This is not fully independent (same source as the reference itself), but it
   confirms the PDF-reference link and that the cited content is real.

The two layers are complementary, not circular: PubMed verification checks
metadata accuracy; snippet extraction checks content relevance.
"""

import re


def gather_evidence(
    ref_num: int,
    reference: dict,
    citation_contexts: list,
    abstract: str = "",
    paper_snippets_html: str = "",
    pdf_full_text: str = "",
) -> dict:
    """Assemble all available evidence for one reference.

    Args:
        ref_num: Reference number in the manuscript.
        reference: Reference dict with keys: ref, doi, title, authors, year, journal.
        citation_contexts: List of citation dicts with section, snippet, line keys.
        abstract: Abstract text (from PubMed/CrossRef or pre-loaded JSON).
        paper_snippets_html: HTML-formatted relevant passages from snippet_extractor.
        pdf_full_text: Raw full text of the PDF (if available).

    Returns:
        dict with structured evidence for Claude to evaluate.
    """
    claims = extract_claims(citation_contexts)

    # Strip HTML from paper snippets for plain-text evidence
    snippets_text = ""
    if paper_snippets_html:
        snippets_text = re.sub(r"<[^>]+>", "", paper_snippets_html).strip()

    # Take a manageable excerpt from full text (first ~4000 chars)
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
        snippets_text=snippets_text,
        full_text_excerpt=full_text_excerpt,
    )

    # Secondary verification: if a snippet was extracted from the PDF,
    # the PDF exists, is readable, and contains relevant content.
    pdf_verified = bool(snippets_text)

    return {
        "ref_num": ref_num,
        "reference": reference,
        "citation_contexts": citation_contexts,
        "abstract": abstract or None,
        "paper_snippets_html": paper_snippets_html or None,
        "full_text_excerpt": full_text_excerpt or None,
        "claims_made": claims,
        "evidence_summary": evidence_text,
        "pdf_verified": pdf_verified,
    }


def extract_claims(citation_contexts: list) -> list:
    """Parse each citation snippet to isolate the specific assertion being supported.

    Args:
        citation_contexts: List of citation dicts with 'snippet' and 'section' keys.

    Returns:
        List of claim strings extracted from the citation contexts.
    """
    claims = []
    for ctx in citation_contexts:
        snippet = ctx.get("snippet", "").strip()
        if not snippet:
            continue

        # Remove the bracket citation itself (e.g., [3], [3,4,5])
        claim = re.sub(r"\[\d+(?:,\s*\d+)*\]", "", snippet).strip()

        # Clean up trailing/leading punctuation artifacts
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
    snippets_text: str = "",
    full_text_excerpt: str = "",
) -> str:
    """Format a structured evidence package as text for Claude to evaluate.

    Args:
        ref_num: Reference number.
        reference: Reference dict.
        claims: List of claim strings from extract_claims.
        abstract: Abstract text.
        snippets_text: Plain-text relevant passages from the full document.
        full_text_excerpt: First portion of the PDF full text.

    Returns:
        Formatted text block with labeled sections.
    """
    lines = []

    # Section 1: Reference info
    lines.append(f"=== REFERENCE [{ref_num}] ===")
    lines.append(f"Authors: {reference.get('authors', 'N/A')}")
    lines.append(f"Year: {reference.get('year', 'N/A')}")
    lines.append(f"Title: {reference.get('title', 'N/A')}")
    lines.append(f"Journal: {reference.get('journal', 'N/A')}")
    lines.append(f"DOI: {reference.get('doi', 'N/A')}")
    lines.append(f"Full ref: {reference.get('ref', 'N/A')}")
    lines.append("")

    # Section 2: Claims made in the manuscript
    lines.append(f"=== CLAIMS IN MANUSCRIPT ({len(claims)}) ===")
    if claims:
        for i, claim in enumerate(claims, 1):
            lines.append(f"  {i}. {claim}")
    else:
        lines.append("  (No citation contexts found)")
    lines.append("")

    # Section 3: Abstract
    lines.append("=== ABSTRACT ===")
    if abstract:
        # Strip HTML tags from abstract (PubMed sometimes returns <b>Label:</b>)
        clean_abstract = re.sub(r"<[^>]+>", "", abstract)
        lines.append(clean_abstract)
    else:
        lines.append("(Abstract not available)")
    lines.append("")

    # Section 4: Relevant passages from full document
    lines.append("=== RELEVANT PASSAGES FROM FULL DOCUMENT ===")
    if snippets_text:
        lines.append(snippets_text)
    else:
        lines.append("(Full document not available)")
    lines.append("")

    # Section 5: Full text excerpt
    if full_text_excerpt:
        lines.append("=== FULL TEXT EXCERPT (first ~4000 chars) ===")
        lines.append(full_text_excerpt)
        lines.append("")

    return "\n".join(lines)
