"""Orchestrator: parse manuscript, fetch abstracts, process PDFs, generate HTML."""

import os
import re
import json

import manuscript_parser
import abstract_fetcher
import pdf_processor
import snippet_extractor
from html_template import CSS_TEMPLATE, JS_TEMPLATE


def js_escape(s: str) -> str:
    """Escape a string for embedding in JS single-quoted strings."""
    s = s.replace("\\", "\\\\")
    s = s.replace("'", "\\'")
    s = s.replace('"', '\\"')
    s = s.replace("\n", "\\n")
    s = s.replace("\r", "")
    return s


def generate(
    manuscript_path: str,
    output_path: str,
    title: str = "",
    pdfs_folder: str = "",
    abstracts_json: str = "",
    email: str = "",
) -> str:
    """Generate an interactive reference viewer HTML file.

    Args:
        manuscript_path: Path to the markdown manuscript.
        output_path: Where to write the HTML file.
        title: Optional title (auto-detected from manuscript if empty).
        pdfs_folder: Optional folder containing reference PDFs.
        abstracts_json: Optional path to a pre-existing abstracts JSON file.
        email: Email for PubMed Entrez queries.

    Returns:
        JSON string with generation stats.
    """
    # 1. Parse manuscript
    parsed = manuscript_parser.parse(manuscript_path)
    references = parsed["references"]
    citations = parsed["citations"]
    sections = parsed["sections"]
    stats = parsed["stats"]

    # 2. Auto-detect title if not provided
    if not title:
        title = _detect_title(manuscript_path)

    # 3. Load or fetch abstracts
    abstracts = {}
    if abstracts_json and os.path.isfile(abstracts_json):
        with open(abstracts_json, "r") as f:
            raw = json.load(f)
        # Keys may be strings or ints
        abstracts = {int(k): v for k, v in raw.items()}
    else:
        # Fetch from PubMed/CrossRef
        dois = {num: ref["doi"] for num, ref in references.items() if ref.get("doi")}
        if dois and email:
            doi_to_abstract = abstract_fetcher.fetch_all(list(dois.values()), email)
            # Map back to ref numbers
            for num, doi in dois.items():
                if doi in doi_to_abstract and doi_to_abstract[doi]:
                    abstracts[num] = doi_to_abstract[doi]

    # 4. Process PDFs if folder provided
    paper_snippets = {}
    pdf_stats = {"matched": 0, "unmatched": 0}
    if pdfs_folder and os.path.isdir(pdfs_folder):
        pdf_results = pdf_processor.process(pdfs_folder, references)
        unmatched = pdf_results.pop("_unmatched", [])
        pdf_results.pop("_error", None)

        # For each matched PDF, extract relevant snippets
        for ref_num, full_text in pdf_results.items():
            contexts = citations.get(ref_num, [])
            snippet_html = snippet_extractor.extract(ref_num, full_text, contexts)
            if snippet_html:
                paper_snippets[ref_num] = snippet_html

        pdf_stats["matched"] = len(pdf_results)
        pdf_stats["unmatched"] = len(unmatched)

    # 5. Assemble HTML
    html = _build_html(
        title=title,
        references=references,
        citations=citations,
        abstracts=abstracts,
        paper_snippets=paper_snippets,
        stats=stats,
    )

    # 7. Write output
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    with open(output_path, "w") as f:
        f.write(html)

    # Return stats
    result = {
        "output_path": os.path.abspath(output_path),
        "references": stats["total_references"],
        "citations": stats["total_citations"],
        "cited_references": stats["cited_references"],
        "uncited_references": stats["uncited_references"],
        "abstracts_loaded": len(abstracts),
        "paper_snippets": len(paper_snippets),
        "pdfs_matched": pdf_stats["matched"],
        "pdfs_unmatched": pdf_stats["unmatched"],
    }
    return json.dumps(result, indent=2)


def _detect_title(manuscript_path: str) -> str:
    """Detect manuscript title from the first # heading."""
    with open(manuscript_path, "r") as f:
        for line in f:
            stripped = line.strip()
            m = re.match(r"^#\s+(.+)$", stripped)
            if m:
                return m.group(1)
    return "Manuscript Reference Viewer"


def _build_html(
    title: str,
    references: dict,
    citations: dict,
    abstracts: dict,
    paper_snippets: dict,
    stats: dict,
) -> str:
    """Assemble the complete HTML file."""

    total_refs = stats["total_references"]
    total_citations = stats["total_citations"]
    cited_refs = stats["cited_references"]
    uncited_refs = stats["uncited_references"]

    # Build REFERENCES JS object
    refs_lines = []
    for num in sorted(references.keys()):
        ref = references[num]
        refs_lines.append(
            f'  {num}: {{ref: "{js_escape(ref["ref"])}", '
            f'doi: "{js_escape(ref["doi"])}", '
            f'title: "{js_escape(ref["title"])}", '
            f'authors: "{js_escape(ref["authors"])}", '
            f'year: {ref["year"]}, '
            f'journal: "{js_escape(ref["journal"])}"}}'
        )
    refs_js = "const REFERENCES = {\n" + ",\n".join(refs_lines) + "\n};"

    # Build CITATIONS JS object
    cits_lines = []
    for num in sorted(references.keys()):
        if num in citations and len(citations[num]) > 0:
            entries = []
            for c in citations[num]:
                entries.append(
                    f'{{section:"{js_escape(c["section"])}",'
                    f'snippet:"{js_escape(c["snippet"])}",'
                    f'line:{c["line"]}}}'
                )
            cits_lines.append(f"  {num}: [{','.join(entries)}]")
    cits_js = "const CITATIONS = {\n" + ",\n".join(cits_lines) + "\n};"

    # Build ABSTRACTS JS object
    abs_lines = []
    for num in sorted(references.keys()):
        if num in abstracts:
            abs_lines.append(f'  {num}: "{js_escape(str(abstracts[num]))}"')
    abs_js = "const ABSTRACTS = {\n" + ",\n".join(abs_lines) + "\n};"

    # Build PAPER_SNIPPETS JS object
    snip_lines = []
    for num in sorted(references.keys()):
        if num in paper_snippets:
            snip_lines.append(f'  {num}: "{js_escape(paper_snippets[num])}"')
    snip_js = ("// Paper snippets: relevant passages from the full document that support claims in our manuscript.\n"
               "// null = full document not available.\n"
               "const PAPER_SNIPPETS = {\n" + ",\n".join(snip_lines) + "\n};")

    # Escape title for HTML
    html_title = title.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Manuscript Reference Viewer</title>
<style>
{CSS_TEMPLATE}
</style>
</head>
<body>

<div class="header">
  <h1>Manuscript Reference Viewer</h1>
  <p>{html_title}</p>
  <div class="stats">
    <div class="stat-box"><strong id="total-refs">{total_refs}</strong> References</div>
    <div class="stat-box"><strong id="total-citations">{total_citations}</strong> Citation instances</div>
    <div class="stat-box"><strong id="cited-count">{cited_refs}</strong> Cited</div>
    <div class="stat-box"><strong id="uncited-count">{uncited_refs}</strong> Uncited</div>
  </div>
</div>

<div class="controls">
  <input type="text" class="search-box" id="searchBox" placeholder="Search references, abstracts, or citation contexts...">
  <button class="filter-btn active" data-filter="all" title="Show all {total_refs} references">All</button>
  <button class="filter-btn" data-filter="uncited" title="Show references that are never cited as [N] in the manuscript text">Uncited</button>
  <button class="filter-btn" data-filter="intro" title="Show references cited in the Introduction section">Introduction</button>
  <button class="filter-btn" data-filter="methods" title="Show references cited in Methods (Participants, FreeSurfer, Analysis, etc.)">Methods</button>
  <button class="filter-btn" data-filter="discussion" title="Show references cited in the Discussion section">Discussion</button>
</div>

<div class="expand-all-bar">
  <button class="expand-btn" onclick="expandAll()" title="Open all reference cards to show citation contexts">Expand All</button>
  <button class="expand-btn" onclick="collapseAll()" title="Close all reference cards">Collapse All</button>
  <button class="expand-btn" onclick="expandAllPaperInfo()" title="Open the Abstract & Supporting Evidence panels inside all cards">Show All Paper Info</button>
  <button class="expand-btn" onclick="collapseAllPaperInfo()" title="Close all Abstract & Supporting Evidence panels">Hide All Paper Info</button>
</div>

<div class="compile-bar">
  <div class="review-progress">
    <span class="progress-text" id="progressText">0 / {total_refs} reviewed</span>
    <div class="progress-bar-outer">
      <div class="progress-bar-inner" id="progressBar" style="width: 0%"></div>
    </div>
  </div>
  <button class="compile-btn secondary" onclick="filterByReviewStatus('flagged')" title="Show only references with comments that are not yet marked as satisfied">Show Flagged</button>
  <button class="compile-btn secondary" onclick="filterByReviewStatus('unreviewed')" title="Show only references whose checkbox has not been checked yet">Show Unreviewed</button>
  <button class="compile-btn secondary" onclick="filterByReviewStatus('ai-flagged')" title="Show references flagged or warned by AI verification">Show AI Flagged</button>
  <button class="compile-btn secondary" onclick="filterByReviewStatus('ai-unverified')" title="Show references not yet verified by AI">Show AI Unverified</button>
  <button class="compile-btn secondary" onclick="filterByReviewStatus('all')" title="Remove review filters and show all references">Show All</button>
  <button class="compile-btn primary" onclick="compileConcerns()" title="Open a summary of all flagged concerns, with options to copy or download as text">Compile Concerns</button>
  <button class="compile-btn secondary" onclick="saveStateToFile()" title="Download a JSON file with all checkboxes and comments -- save it to this folder to auto-load next time">Save State</button>
  <button class="compile-btn secondary" onclick="document.getElementById('loadStateInput').click()" title="Import a previously saved JSON file to restore checkboxes and comments">Load State</button>
  <input type="file" id="loadStateInput" accept=".json" style="display:none" onchange="loadStateFromFile(this)">
  <button class="compile-btn danger" onclick="clearAllReviews()" title="Erase all checkboxes and comments (asks for confirmation first)">Reset All Reviews</button>
</div>

<div id="ref-container"></div>

<!-- Concerns modal -->
<div class="modal-overlay" id="concernsModal">
  <div class="modal-content">
    <div class="modal-header">
      <h2>Compiled Concerns</h2>
      <button class="modal-close" onclick="closeModal()">&times;</button>
    </div>
    <div class="modal-body" id="concernsBody"></div>
    <div class="modal-footer">
      <button class="compile-btn secondary" onclick="copyConcernsToClipboard()">Copy to Clipboard</button>
      <button class="compile-btn secondary" onclick="downloadConcerns()">Download as Text</button>
      <button class="compile-btn secondary" onclick="closeModal()">Close</button>
    </div>
  </div>
</div>

<script>
// ===== DATA =====
{refs_js}

{cits_js}

{abs_js}

{snip_js}

{JS_TEMPLATE}
</script>
</body>
</html>
"""
    return html
