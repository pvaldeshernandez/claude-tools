#!/usr/bin/env python3
"""Generate an interactive HTML reference viewer from a manuscript markdown file.

Parses manuscript sections and references, matches literature PDFs, extracts
supporting snippets, fetches abstracts from CrossRef, and produces a
self-contained interactive HTML viewer.
"""

import argparse
import re
import sys
from pathlib import Path

# Ensure sibling modules are importable
sys.path.insert(0, str(Path(__file__).resolve().parent))


# ---------------------------------------------------------------------------
# 1. parse_sections
# ---------------------------------------------------------------------------

def parse_sections(lines):
    """Return a list of section dicts for every markdown heading.

    Each dict has keys:
        line  – 1-based line number
        level – heading level (1-4)
        heading – heading text (without leading '#' characters)

    Parameters
    ----------
    lines : list[str]
        Lines of the manuscript (no trailing newline expected, but tolerated).
    """
    heading_re = re.compile(r'^(#{1,4})\s+(.+)$')
    sections = []
    for i, raw in enumerate(lines, start=1):
        line = raw.rstrip('\n')
        m = heading_re.match(line)
        if m:
            sections.append({
                'line': i,
                'level': len(m.group(1)),
                'heading': m.group(2).strip(),
            })
    return sections


# ---------------------------------------------------------------------------
# 2. build_section_hierarchy
# ---------------------------------------------------------------------------

def build_section_hierarchy(sections):
    """Map each level-2 heading to its child sub-headings.

    Returns
    -------
    dict[str, list[str]]
        Keys are level-2 heading texts; values are lists of child headings
        (level 3 or 4) that appear before the next level-2 heading.
    """
    hierarchy = {}
    current_l2 = None
    for sec in sections:
        if sec['level'] == 2:
            current_l2 = sec['heading']
            hierarchy[current_l2] = []
        elif sec['level'] >= 3 and current_l2 is not None:
            hierarchy[current_l2].append(sec['heading'])
    return hierarchy


# ---------------------------------------------------------------------------
# 3. section_at_line
# ---------------------------------------------------------------------------

def section_at_line(sections, line_num):
    """Return the most specific (deepest) heading that contains *line_num*.

    If *line_num* falls before the first heading, returns None.
    """
    best = None
    for sec in sections:
        if sec['line'] <= line_num:
            best = sec
        else:
            break
    return best['heading'] if best else None


# ---------------------------------------------------------------------------
# 3b. classify_section (from MCP — broad category mapping)
# ---------------------------------------------------------------------------

def classify_section(section_name):
    """Classify a section name into a broad category.

    Returns one of: Introduction, Methods, Results, Discussion, Other
    """
    lower = (section_name or "").lower()
    if "introduction" in lower or "background" in lower:
        return "Introduction"
    if any(kw in lower for kw in [
        "method", "participant", "subject", "sample", "acquisition",
        "processing", "analysis", "statistical", "procedure", "measure",
        "variable", "design", "freesurfer", "mri", "imaging",
    ]):
        return "Methods"
    if "result" in lower:
        return "Results"
    if "discussion" in lower or "conclusion" in lower or "limitation" in lower:
        return "Discussion"
    return "Other"


# ---------------------------------------------------------------------------
# 4. parse_references
# ---------------------------------------------------------------------------

_DOI_RE = re.compile(r'https?://doi\.org/(10\.\S+)')
_YEAR_RE = re.compile(r'\b(\d{4})\b')
_JOURNAL_RE = re.compile(r'\*([^*]+)\*')


def parse_references(lines):
    """Extract numbered references from the ``## References`` block.

    Returns
    -------
    dict[int, dict]
        Keyed by reference number. Each value has keys:
        ref, doi, title, authors, year, journal.
    """
    # Find the start of the References section
    ref_start = None
    for i, raw in enumerate(lines):
        stripped = raw.strip()
        if re.match(r'^#{1,3}\s+references\s*$', stripped, re.IGNORECASE):
            ref_start = i + 1  # lines after the heading
            break
    if ref_start is None:
        return {}

    ref_re = re.compile(r'^(\d+)\.\s+(.+)$')
    refs = {}
    for raw in lines[ref_start:]:
        line = raw.strip()
        if not line:
            continue
        # Stop if we hit another heading
        if line.startswith('#'):
            break
        m = ref_re.match(line)
        if not m:
            continue

        num = int(m.group(1))
        text = m.group(2)

        # DOI — strip trailing period
        doi_m = _DOI_RE.search(text)
        doi = doi_m.group(1).rstrip('.') if doi_m else None

        # Journal — first *italic* span
        journal_m = _JOURNAL_RE.search(text)
        journal = journal_m.group(1) if journal_m else None

        # Title — text between first ". " and first "*"
        # (authors end with ". ", then title, then *Journal*)
        title = None
        first_dot_space = text.find('. ')
        if first_dot_space != -1:
            after_authors = text[first_dot_space + 2:]
            first_star = after_authors.find('*')
            if first_star > 0:
                title = after_authors[:first_star].strip().rstrip('.')
            elif first_star == -1:
                # No italic journal (e.g., a book) — take rest as title
                title = after_authors.strip().rstrip('.')
        # Special case: if title starts with '*', the first ". " was
        # inside authors and title is actually in the italic span.
        # Handle book-style refs where title IS the italic text.
        if title is not None and title.startswith('*'):
            title = None
        if title is None and journal is not None:
            # Fallback: for books where the title is the italic text
            title = journal

        # Year — first 4-digit number in valid range
        year = None
        for year_m in _YEAR_RE.finditer(text):
            candidate = int(year_m.group(1))
            if 1800 <= candidate <= 2100:
                year = candidate
                break

        # Authors — everything before first ". "
        if first_dot_space != -1:
            raw_authors = text[:first_dot_space]
        else:
            raw_authors = text
        if ',' in raw_authors:
            # Shorten to "FirstAuthor et al."
            first_author = raw_authors.split(',')[0].strip()
            authors = f'{first_author} et al.'
        else:
            authors = raw_authors.strip()

        refs[num] = {
            'ref': text,
            'doi': doi,
            'title': title,
            'authors': authors,
            'year': year,
            'journal': journal,
        }
    return refs


# ---------------------------------------------------------------------------
# 5. find_citations
# ---------------------------------------------------------------------------

_CITE_RE = re.compile(r'\[([0-9,\s\u2013\u2014\-\u2010\u2011–—]+)\]')


def _expand_citation(text):
    """Expand a citation body (e.g. '13–23' or '1,2') into a set of ints."""
    nums = set()
    # Split on commas first
    for part in text.split(','):
        part = part.strip()
        # Check for range (en-dash, em-dash, hyphen variants)
        range_m = re.match(r'(\d+)\s*[\u2013\u2014\-\u2010\u2011–—]\s*(\d+)', part)
        if range_m:
            lo, hi = int(range_m.group(1)), int(range_m.group(2))
            nums.update(range(lo, hi + 1))
        else:
            # Single number
            digit_m = re.match(r'(\d+)', part)
            if digit_m:
                nums.add(int(digit_m.group(1)))
    return nums


def find_citations(lines, sections):
    """Find all citation instances in the manuscript body.

    Returns
    -------
    dict[int, list[dict]]
        Keyed by reference number. Each value is a list of dicts with
        keys: section, snippet, line.
    """
    # Determine where References section starts so we can skip it
    ref_line = None
    for sec in sections:
        if sec['heading'].lower() == 'references':
            ref_line = sec['line']
            break

    citations = {}  # ref_num -> list of {section, snippet, line}
    seen = set()    # (ref_num, line_num, section) for dedup

    for i, raw in enumerate(lines, start=1):
        # Skip lines at or after the References section
        if ref_line is not None and i >= ref_line:
            break

        line_text = raw.rstrip('\n')

        for m in _CITE_RE.finditer(line_text):
            ref_nums = _expand_citation(m.group(1))
            # Build snippet: ~300 chars centred on the match
            start_char = max(0, m.start() - 150)
            end_char = min(len(line_text), m.end() + 150)
            snippet = line_text[start_char:end_char]
            if start_char > 0:
                snippet = '...' + snippet
            if end_char < len(line_text):
                snippet = snippet + '...'

            sec_name = section_at_line(sections, i)

            for n in ref_nums:
                key = (n, i, sec_name)
                if key in seen:
                    continue
                seen.add(key)
                citations.setdefault(n, []).append({
                    'section': sec_name,
                    'snippet': snippet,
                    'line': i,
                })

    return citations


# ---------------------------------------------------------------------------
# 6. generate_viewer — programmatic entry point for skill
# ---------------------------------------------------------------------------

def generate_viewer(
    manuscript_path,
    literature_dir=None,
    output_path=None,
    state_path=None,
    verification_results=None,
    abstracts=None,
):
    """Generate the HTML reference viewer.

    This is the main entry point when called from the skill (by Claude).
    Abstracts and verification results are passed in (fetched by Claude via MCPs).

    Args:
        manuscript_path: Path to markdown manuscript.
        literature_dir: Optional path to literature PDFs folder.
        output_path: Where to write HTML. Defaults to same dir as manuscript.
        state_path: Path to state JSON. Defaults to alongside HTML.
        verification_results: dict {ref_num: {verdict, reason}} from AI verification.
        abstracts: dict {ref_num: abstract_text} fetched by Claude via external MCPs.

    Returns dict with generation stats.
    """
    manuscript_path = Path(manuscript_path).resolve()
    lines = manuscript_path.read_text(encoding='utf-8').splitlines()

    # Parse
    sections = parse_sections(lines)
    hierarchy = build_section_hierarchy(sections)
    references = parse_references(lines)
    raw_citations = find_citations(lines, sections)
    raw_citations = {k: v for k, v in raw_citations.items() if k in references}

    # Defaults
    if output_path is None:
        output_path = manuscript_path.parent / 'reference_viewer.html'
    else:
        output_path = Path(output_path).resolve()

    if state_path is None:
        state_path = output_path.parent / 'ref_review_state.json'
    else:
        state_path = Path(state_path).resolve()

    if abstracts is None:
        # Auto-fetch abstracts if not provided by caller
        from abstract_fetcher import fetch_abstracts as _fetch_abstracts
        abstracts, _ = _fetch_abstracts(references, verbose=True)
    if verification_results is None:
        verification_results = {}

    # Subtitle from first line
    subtitle = ''
    for raw_line in lines:
        stripped = raw_line.strip()
        if stripped:
            subtitle = stripped.lstrip('#').strip()
            break

    # PDF matching and snippet extraction
    citations = {}
    matched_pdfs = {}
    unmatched_pdfs = []

    if literature_dir:
        from pdf_matcher import match_and_rename
        from snippet_extractor import extract_snippets

        lit_dir = Path(literature_dir)
        if lit_dir.is_dir():
            matched_pdfs, unmatched_pdfs, warnings = match_and_rename(lit_dir, references)

            n_matched = len(matched_pdfs)
            for idx, (ref_num, pdf_path) in enumerate(sorted(matched_pdfs.items()), 1):
                inst_list = raw_citations.get(ref_num, [])
                if inst_list:
                    groups = extract_snippets(pdf_path, inst_list)
                    citations[ref_num] = groups
                else:
                    citations[ref_num] = []

    # Wrap refs without PDFs
    for ref_num in references:
        if ref_num in citations:
            continue
        inst_list = raw_citations.get(ref_num, [])
        groups = []
        for inst in inst_list:
            groups.append({
                'instances': [{'section': inst['section'], 'line': inst['line']}],
                'manuscript_context': inst['snippet'],
                'pdf_snippets': [],
            })
        citations[ref_num] = groups

    # Load existing state (preserves user reviews)
    import state_manager
    state = state_manager.load_state(str(state_path))

    # Merge verification results into state
    for ref_num, vr in verification_results.items():
        state_manager.save_verification_result(
            str(state_path), int(ref_num), vr['verdict'], vr['reason'],
            vr.get('details'),
        )

    # Reload state after verification writes
    if verification_results:
        state = state_manager.load_state(str(state_path))

    # Generate HTML
    from html_template import generate
    total_refs = len(references)

    generate(
        title='Manuscript Reference Viewer',
        subtitle=subtitle,
        sections=sections,
        hierarchy=hierarchy,
        references=references,
        citations=citations,
        abstracts=abstracts,
        total_refs=total_refs,
        output_path=output_path,
        state=state,
    )

    return {
        'output_path': str(output_path),
        'state_path': str(state_path),
        'total_references': total_refs,
        'cited': len(raw_citations),
        'pdfs_matched': len(matched_pdfs),
        'pdfs_unmatched': len(unmatched_pdfs),
        'abstracts': len(abstracts),
        'verified': len(verification_results),
    }


# ---------------------------------------------------------------------------
# 7. main — CLI entry point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description='Generate an interactive HTML reference viewer from a '
                    'manuscript markdown file.',
    )
    parser.add_argument(
        'manuscript',
        help='Path to the manuscript markdown file.',
    )
    parser.add_argument(
        '--literature-dir',
        default=None,
        help='Directory containing literature PDFs (optional).',
    )
    parser.add_argument(
        '--output',
        default=None,
        help='Path for the output HTML file (default: alongside manuscript).',
    )
    # --email and --skip-crossref removed: abstract fetching now handled by
    # Claude via external MCPs when using the skill.
    args = parser.parse_args()

    manuscript_path = Path(args.manuscript).resolve()
    if not manuscript_path.is_file():
        print(f'Error: manuscript not found: {manuscript_path}', file=sys.stderr)
        sys.exit(1)

    # Smart default for output path: same directory as manuscript
    if args.output is None:
        output_path = manuscript_path.parent / 'reference_viewer.html'
    else:
        output_path = Path(args.output).resolve()

    # ------------------------------------------------------------------
    # Step 1: Parse manuscript
    # ------------------------------------------------------------------
    print('Parsing manuscript...')
    lines = manuscript_path.read_text(encoding='utf-8').splitlines()

    sections = parse_sections(lines)
    hierarchy = build_section_hierarchy(sections)
    references = parse_references(lines)
    raw_citations = find_citations(lines, sections)

    # Filter citations to only valid reference numbers
    raw_citations = {k: v for k, v in raw_citations.items() if k in references}

    total_refs = len(references)
    total_instances = sum(len(v) for v in raw_citations.values())
    print(f'  {total_refs} references, {len(raw_citations)} cited, '
          f'{total_instances} citation instances')

    # Extract subtitle from the first line of the manuscript
    subtitle = ''
    for raw_line in lines:
        stripped = raw_line.strip()
        if stripped:
            subtitle = stripped.lstrip('#').strip()
            break

    # ------------------------------------------------------------------
    # Step 2: Match PDFs and extract snippets
    # ------------------------------------------------------------------
    # citations dict: ref_num -> list of grouped dicts with
    #   instances, manuscript_context, pdf_snippets
    citations = {}
    matched_pdfs = {}

    if args.literature_dir:
        from pdf_matcher import match_and_rename
        from snippet_extractor import extract_snippets

        lit_dir = Path(args.literature_dir)
        print(f'Matching PDFs in {lit_dir}...')
        matched_pdfs, unmatched, warnings = match_and_rename(lit_dir, references)
        print(f'  {len(matched_pdfs)} matched, {len(unmatched)} unmatched')

        # Print warnings
        for w in warnings:
            print(f'  WARNING: {w}')

        # Print unmatched PDFs
        if unmatched:
            print(f'  Unmatched PDFs:')
            for u in unmatched:
                title = u.get('extracted_title', '?') or '?'
                print(f'    {Path(u["path"]).name}  (title: {title[:60]})')

        # Extract snippets for matched refs
        n_matched = len(matched_pdfs)
        for idx, (ref_num, pdf_path) in enumerate(sorted(matched_pdfs.items()), 1):
            if idx % 10 == 1 or idx == n_matched:
                print(f'  Extracting snippets... {idx}/{n_matched}', end='\r')
            inst_list = raw_citations.get(ref_num, [])
            if inst_list:
                groups = extract_snippets(pdf_path, inst_list)
                citations[ref_num] = groups
            else:
                # Reference has a PDF but is not cited in text
                citations[ref_num] = []
        if n_matched:
            print(f'  Extracting snippets... {n_matched}/{n_matched} done')

    # For refs WITHOUT PDFs: wrap each raw citation instance into the
    # grouped format (one entry per instance, empty pdf_snippets)
    for ref_num in references:
        if ref_num in citations:
            continue
        inst_list = raw_citations.get(ref_num, [])
        groups = []
        for inst in inst_list:
            groups.append({
                'instances': [{'section': inst['section'], 'line': inst['line']}],
                'manuscript_context': inst['snippet'],
                'pdf_snippets': [],
            })
        citations[ref_num] = groups

    # ------------------------------------------------------------------
    # Step 3: Abstracts (multi-source cascade: CrossRef → PubMed → Scopus)
    # ------------------------------------------------------------------
    from abstract_fetcher import fetch_abstracts as _fetch_abstracts
    print('Fetching abstracts...')
    abstracts, abstract_failures = _fetch_abstracts(references, email=None)
    if abstract_failures:
        print(f'  Could not fetch abstracts for: '
              f'{[f["ref_num"] for f in abstract_failures]}')

    # ------------------------------------------------------------------
    # Step 4: Generate HTML
    # ------------------------------------------------------------------
    from html_template import generate

    print(f'Generating HTML viewer...')
    generate(
        title='Manuscript Reference Viewer',
        subtitle=subtitle,
        sections=sections,
        hierarchy=hierarchy,
        references=references,
        citations=citations,
        abstracts=abstracts,
        total_refs=total_refs,
        output_path=output_path,
    )

    # ------------------------------------------------------------------
    # Step 5: Summary
    # ------------------------------------------------------------------
    pdf_snippet_count = 0
    for ref_num, groups in citations.items():
        for g in groups:
            pdf_snippet_count += len(g.get('pdf_snippets', []))

    print()
    print('=' * 60)
    print('REFERENCE VIEWER GENERATED')
    print('=' * 60)
    print(f'  Manuscript     : {manuscript_path}')
    print(f'  Output         : {output_path}')
    print(f'  References     : {total_refs}')
    print(f'  Cited in text  : {len(raw_citations)}')
    print(f'  Instances      : {total_instances}')
    print(f'  PDFs matched   : {len(matched_pdfs)}')
    print(f'  PDF snippets   : {pdf_snippet_count}')
    print(f'  Abstracts      : {len(abstracts)}')
    print('=' * 60)


if __name__ == '__main__':
    main()
