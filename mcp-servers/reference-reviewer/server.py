#!/usr/bin/env python3
"""MCP server for generating interactive HTML reference viewers from markdown manuscripts."""

import json
import sys
import os

# Ensure this directory is on the path for local imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from mcp.server.fastmcp import FastMCP

import manuscript_parser
import abstract_fetcher
import pdf_processor
import snippet_extractor
import html_generator
import verification
import state_manager

mcp = FastMCP("reference-reviewer")


@mcp.tool()
def parse_manuscript(manuscript_path: str) -> str:
    """Parse a markdown manuscript to extract references, citations, and section structure.

    Args:
        manuscript_path: Absolute path to the markdown manuscript file.

    Returns:
        JSON with references (numbered dict), citations (ref_num -> contexts),
        sections (detected from headers), and stats (counts).
    """
    result = manuscript_parser.parse(manuscript_path)
    # Convert for JSON serialization
    return json.dumps(result, indent=2, default=str)


@mcp.tool()
def fetch_abstracts(dois: list[str], email: str) -> str:
    """Fetch abstracts for a list of DOIs from PubMed and CrossRef.

    Args:
        dois: List of DOI strings (e.g., ["10.1234/example", "10.5678/other"]).
        email: Your email address (required for PubMed Entrez API).

    Returns:
        JSON mapping DOI -> abstract text (or null if not found).
    """
    results = abstract_fetcher.fetch_all(dois, email)
    return json.dumps(results, indent=2)


@mcp.tool()
def process_pdfs(pdfs_folder: str, references_json: str) -> str:
    """Extract text from PDFs in a folder and match them to manuscript references.

    Args:
        pdfs_folder: Path to folder containing PDF files.
        references_json: JSON string of the references dict (from parse_manuscript).

    Returns:
        JSON mapping ref_num -> extracted markdown text, plus "_unmatched" list.
    """
    references = json.loads(references_json)
    # Convert string keys back to ints
    references = {int(k): v for k, v in references.items()}
    results = pdf_processor.process(pdfs_folder, references)
    return json.dumps(results, indent=2, default=str)


@mcp.tool()
def extract_snippets(ref_num: int, full_text: str, citation_contexts_json: str) -> str:
    """Find supporting passages in a full-text document for a specific reference.

    Args:
        ref_num: The reference number.
        full_text: Full text of the paper (markdown or plain text).
        citation_contexts_json: JSON string of citation context list (from parse_manuscript).

    Returns:
        HTML-formatted string of top supporting passages with keyword highlighting.
    """
    contexts = json.loads(citation_contexts_json)
    result = snippet_extractor.extract(ref_num, full_text, contexts)
    return result


@mcp.tool()
def generate_viewer(
    manuscript_path: str,
    output_path: str,
    title: str = "",
    pdfs_folder: str = "",
    abstracts_json: str = "",
    email: str = "",
) -> str:
    """Generate a complete interactive HTML reference viewer for a markdown manuscript.

    This is the main one-shot tool that orchestrates the full pipeline:
    parse manuscript -> fetch abstracts -> process PDFs -> extract snippets -> build HTML.

    IMPORTANT: Always ask the user for pdfs_folder if not provided. When PDFs
    are available, the pipeline extracts abstracts and key snippets automatically.
    Snippet extraction also serves as secondary verification — confirming each
    PDF exists, is readable, and contains content relevant to its citation.

    Args:
        manuscript_path: Absolute path to the markdown manuscript file.
        output_path: Where to write the HTML file.
        title: Optional title override (auto-detected from first # heading if empty).
        pdfs_folder: Path to folder with reference PDFs. Always provide when available.
        abstracts_json: Optional path to pre-existing abstracts JSON file (DOI -> abstract).
        email: Email for PubMed Entrez API (needed for abstract fetching).

    Returns:
        JSON with generation stats (reference count, citation count, etc.).
    """
    return html_generator.generate(
        manuscript_path=manuscript_path,
        output_path=output_path,
        title=title,
        pdfs_folder=pdfs_folder,
        abstracts_json=abstracts_json,
        email=email,
    )


@mcp.tool()
def verify_reference(
    manuscript_path: str,
    ref_num: int,
    pdfs_folder: str = "",
    abstracts_json: str = "",
    email: str = "",
) -> str:
    """Gather evidence for verifying a single reference against the manuscript claims.

    This tool does NOT make a judgment — it assembles an evidence package
    (citation contexts, claims, abstract, PDF snippets) and returns it.
    Claude reads the evidence, reasons about it, then calls save_verification
    to record the verdict.

    Verification has two complementary layers:
    1. Primary (bibliographic): PubMed/web cross-check of metadata (independent).
    2. Secondary (content): Successful snippet extraction from PDF confirms the
       PDF-reference link and content relevance. The returned evidence includes
       a pdf_verified flag indicating whether snippets were extracted.

    Args:
        manuscript_path: Absolute path to the markdown manuscript file.
        ref_num: The reference number to verify (e.g., 3 for [3]).
        pdfs_folder: Optional path to folder with reference PDFs.
        abstracts_json: Optional path to pre-existing abstracts JSON file (ref_num -> abstract).
        email: Email for PubMed Entrez API (needed for abstract fetching).

    Returns:
        JSON evidence package with citation contexts, claims, abstract, and PDF excerpts.
    """
    # Parse manuscript
    parsed = manuscript_parser.parse(manuscript_path)
    references = parsed["references"]
    citations = parsed["citations"]

    if ref_num not in references:
        return json.dumps({"error": f"Reference [{ref_num}] not found in manuscript."})

    reference = references[ref_num]
    citation_contexts = citations.get(ref_num, [])

    # Load or fetch abstract
    abstract = ""
    if abstracts_json and os.path.isfile(abstracts_json):
        with open(abstracts_json, "r") as f:
            raw = json.load(f)
        abstracts_dict = {int(k): v for k, v in raw.items()}
        abstract = abstracts_dict.get(ref_num, "")

    if not abstract and reference.get("doi") and email:
        doi_result = abstract_fetcher.fetch_all([reference["doi"]], email)
        abstract = doi_result.get(reference["doi"], "") or ""

    # Process PDF if available
    paper_snippets_html = ""
    pdf_full_text = ""
    if pdfs_folder and os.path.isdir(pdfs_folder):
        pdf_results = pdf_processor.process(pdfs_folder, {ref_num: reference})
        pdf_results.pop("_unmatched", None)
        pdf_results.pop("_error", None)
        if ref_num in pdf_results:
            pdf_full_text = pdf_results[ref_num]
            snippet_html = snippet_extractor.extract(ref_num, pdf_full_text, citation_contexts)
            if snippet_html:
                paper_snippets_html = snippet_html

    # Assemble evidence
    evidence = verification.gather_evidence(
        ref_num=ref_num,
        reference=reference,
        citation_contexts=citation_contexts,
        abstract=abstract,
        paper_snippets_html=paper_snippets_html,
        pdf_full_text=pdf_full_text,
    )

    return json.dumps(evidence, indent=2, default=str)


@mcp.tool()
def save_verification(
    state_path: str,
    ref_num: int,
    verdict: str,
    reason: str,
    details_json: str = "",
) -> str:
    """Record an AI verification verdict for a reference.

    Call this after reviewing the evidence from verify_reference.

    Args:
        state_path: Absolute path to the state JSON file (e.g., ref_review_state.json).
        ref_num: The reference number being verified.
        verdict: One of "pass", "flag", or "warning".
            - pass: Abstract/text clearly supports the claims.
            - warning: Support is indirect, partial, or tangential.
            - flag: Text does not appear to support the claim, or there is a mismatch.
        reason: Text explanation of the verdict (1-3 sentences).
        details_json: Optional JSON string with additional details.

    Returns:
        JSON with the updated review entry.
    """
    details = None
    if details_json:
        details = json.loads(details_json)

    entry = state_manager.save_verification_result(
        state_path=state_path,
        ref_num=ref_num,
        verdict=verdict,
        reason=reason,
        details=details,
    )

    return json.dumps({"ref_num": ref_num, "entry": entry}, indent=2, default=str)


if __name__ == "__main__":
    mcp.run(transport="stdio")
