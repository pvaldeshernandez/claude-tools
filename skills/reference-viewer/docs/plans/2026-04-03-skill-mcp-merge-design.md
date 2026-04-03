# Reference Viewer Skill — MCP Merge & Verification Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Merge the best features from the reference-reviewer MCP server into the reference-viewer skill, add AI verification, and delegate paper fetching to external MCPs.

**Architecture:** Flat scripts in `~/.claude/skills/reference-viewer/scripts/`. Skill's Python code handles parsing, PDF matching, snippet extraction, verification, state management, and HTML generation. Claude orchestrates abstract/metadata fetching via external MCPs (uf_mcp_manuscript_search, PubMed plugin, paper-search). The monolithic CLI is refactored into importable functions. The MCP server is retired after migration.

**Tech Stack:** Python 3.13, pymupdf (fitz), no new dependencies. External MCPs for paper fetching.

---

## Decisions (from brainstorming)

1. **Single trigger** (`/reference-viewer`), intent detected from natural language
2. **Three intents**: generate viewer (with AI verification baked in), address user comments, regenerate viewer
3. **Abstract fetching**: delegated to external MCPs, `crossref_fetcher.py` removed
4. **PDF rename**: kept (skill version wins)
5. **Snippet extraction**: skill's TF-IDF version wins, add keyword highlighting from MCP
6. **Verification**: adopted from MCP — both individual and batch mode
7. **State file**: JSON alongside HTML, loaded by HTML viewer for AI badges + user reviews
8. **Flat file layout**: no package restructuring

---

### Task 1: Add `state_manager.py` (from MCP)

**Files:**
- Create: `~/.claude/skills/reference-viewer/scripts/state_manager.py`

**Step 1: Create state_manager.py**

Adopt the MCP's `state_manager.py` wholesale. It handles JSON state file I/O with schema migration (v1→v3), stores both user reviews (satisfied/comment) and AI verification results (verdict/reason/timestamp).

```python
"""State file I/O for reference review state with schema migration.

Manages a JSON state file that stores both user reviews (satisfied/comment)
and AI verification results (claude_verdict, claude_reason, claude_timestamp).
"""

import json
import os
from datetime import datetime, timezone

CURRENT_VERSION = 3


def load_state(state_path: str) -> dict:
    """Read JSON state file, migrating from older versions if needed.

    Returns dict with keys: version, savedAt, reviews.
    Each review entry has: satisfied, comment, claude_verified,
    claude_verdict, claude_reason, claude_timestamp.
    """
    if not os.path.isfile(state_path):
        return {
            "version": CURRENT_VERSION,
            "savedAt": _now_iso(),
            "reviews": {},
        }

    with open(state_path, "r") as f:
        data = json.load(f)

    version = data.get("version", 1)

    # Handle bare dict (v1: no version key)
    if "version" not in data:
        data = {"version": 1, "savedAt": _now_iso(), "reviews": data}
        version = 1

    # Migrate v1/v2 -> v3: add claude_* fields as None
    if version < CURRENT_VERSION:
        reviews = data.get("reviews", {})
        for ref_num, review in reviews.items():
            for field in ("claude_verified", "claude_verdict", "claude_reason", "claude_timestamp"):
                if field not in review:
                    review[field] = None
        data["version"] = CURRENT_VERSION

    return data


def save_state(state_path: str, state: dict) -> None:
    """Write state to JSON file."""
    state["version"] = CURRENT_VERSION
    state["savedAt"] = _now_iso()
    os.makedirs(os.path.dirname(os.path.abspath(state_path)), exist_ok=True)
    with open(state_path, "w") as f:
        json.dump(state, f, indent=2)


def save_verification_result(
    state_path: str,
    ref_num: int,
    verdict: str,
    reason: str,
    details: dict = None,
) -> dict:
    """Update one reference's AI verification in the state file.

    Args:
        state_path: Absolute path to the state JSON file.
        ref_num: Reference number.
        verdict: One of "pass", "flag", "warning".
        reason: Text explanation of the verdict.
        details: Optional extra details dict.

    Returns the updated review entry.
    """
    if verdict not in ("pass", "flag", "warning"):
        raise ValueError(f"verdict must be 'pass', 'flag', or 'warning', got '{verdict}'")

    state = load_state(state_path)
    reviews = state.get("reviews", {})
    ref_key = str(ref_num)

    if ref_key not in reviews:
        reviews[ref_key] = {"satisfied": False, "comment": ""}

    entry = reviews[ref_key]
    entry["claude_verified"] = True
    entry["claude_verdict"] = verdict
    entry["claude_reason"] = reason
    entry["claude_timestamp"] = _now_iso()
    if details:
        entry["claude_details"] = details

    reviews[ref_key] = entry
    state["reviews"] = reviews
    save_state(state_path, state)
    return entry


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
```

**Step 2: Verify it runs**

Run: `python -c "import sys; sys.path.insert(0, '$HOME/.claude/skills/reference-viewer/scripts'); import state_manager; print(state_manager.load_state('/tmp/test_state.json'))"`

Expected: `{'version': 3, 'savedAt': '...', 'reviews': {}}`

---

### Task 2: Add `verification.py` (from MCP)

**Files:**
- Create: `~/.claude/skills/reference-viewer/scripts/verification.py`

**Step 1: Create verification.py**

Adopt the MCP's evidence-gathering and claim extraction logic. This module assembles evidence packages that Claude reads and judges.

```python
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
        claim = re.sub(r"\[\d+(?:[,\s\u2013\u2014\-\u2010\u2011\u2012\u2013\u2014]*\d+)*\]", "", snippet).strip()
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
```

**Step 2: Verify it runs**

Run: `python -c "import sys; sys.path.insert(0, '$HOME/.claude/skills/reference-viewer/scripts'); from verification import extract_claims; print(extract_claims([{'snippet': 'Pain disrupts sleep architecture [7].', 'section': 'Introduction'}]))"`

Expected: `['[Introduction] Pain disrupts sleep architecture']`

---

### Task 3: Refactor `generate_reference_viewer.py` into importable functions

**Files:**
- Modify: `~/.claude/skills/reference-viewer/scripts/generate_reference_viewer.py`

**Step 1: Refactor**

The current `main()` is monolithic. Refactor so that:
- All parsing functions (`parse_sections`, `build_section_hierarchy`, `parse_references`, `find_citations`) stay as-is (they're already importable)
- Add `classify_section()` from MCP for broad category mapping
- Add a new `generate_viewer()` function that accepts pre-computed data (abstracts, verification results, state) and delegates to `html_template.generate()`
- Remove the abstract-fetching step from `main()` (now done by Claude via MCPs)
- Keep the CLI for quick standalone runs but make it call `generate_viewer()`

Key changes to `generate_reference_viewer.py`:

1. Add after line 90 (after `section_at_line`):

```python
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
```

2. Add a new orchestration function (before `main()`):

```python
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
    from pathlib import Path
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
        abstracts = {}
    if verification_results is None:
        verification_results = {}

    # PDF matching and snippet extraction
    citations = {}
    matched_pdfs = {}

    if literature_dir:
        from pdf_matcher import match_and_rename
        from snippet_extractor import extract_snippets

        lit_dir = Path(literature_dir)
        matched_pdfs, unmatched, warnings = match_and_rename(lit_dir, references)

        for ref_num, pdf_path in sorted(matched_pdfs.items()):
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
            str(state_path), ref_num, vr['verdict'], vr['reason'],
            vr.get('details'),
        )

    # Reload state after verification writes
    state = state_manager.load_state(str(state_path))

    # Generate HTML
    from html_template import generate
    total_refs = len(references)

    generate(
        title='Manuscript Reference Viewer',
        subtitle=lines[0].lstrip('#').strip() if lines else '',
        sections=sections,
        hierarchy=hierarchy,
        references=references,
        citations=citations,
        abstracts=abstracts,
        total_refs=total_refs,
        output_path=output_path,
        state=state,  # NEW: pass state for AI verification badges
    )

    return {
        'output_path': str(output_path),
        'state_path': str(state_path),
        'total_references': total_refs,
        'cited': len(raw_citations),
        'pdfs_matched': len(matched_pdfs),
        'abstracts': len(abstracts),
        'verified': len(verification_results),
    }
```

3. Simplify `main()` to call `generate_viewer()` and remove the CrossRef fetching block (lines 402-414).

**Step 2: Verify import works**

Run: `python -c "import sys; sys.path.insert(0, '$HOME/.claude/skills/reference-viewer/scripts'); from generate_reference_viewer import parse_sections, classify_section; print(classify_section('Statistical Analysis'))"`

Expected: `Methods`

---

### Task 4: Update `html_template.py` to display AI verification state

**Files:**
- Modify: `~/.claude/skills/reference-viewer/scripts/html_template.py`

**Step 1: Update `generate()` signature**

Add a `state` parameter to the `generate()` function. The state dict contains verification verdicts that get embedded in the HTML as a JS constant (`AI_VERDICTS`).

Changes to `generate()`:
- Add parameter `state=None` to the function signature
- After the existing JS data blocks (REFERENCES, CITATIONS, etc.), add:

```javascript
const AI_VERDICTS = {json.dumps(ai_verdicts, indent=2)};
```

Where `ai_verdicts` is built from `state['reviews']`:
```python
ai_verdicts = {}
if state:
    for ref_key, review in state.get('reviews', {}).items():
        if review.get('claude_verified'):
            ai_verdicts[ref_key] = {
                'verdict': review.get('claude_verdict', ''),
                'reason': review.get('claude_reason', ''),
            }
```

**Step 2: Add AI verdict badges to card rendering**

In the JS `renderCards()` function, after the existing badge rendering, add:

```javascript
// AI verification badge
var aiV = AI_VERDICTS[String(num)];
if (aiV) {
  var aiBadge = document.createElement('span');
  aiBadge.className = 'badge badge-ai-' + aiV.verdict;
  aiBadge.textContent = aiV.verdict === 'pass' ? 'AI: Pass' :
                         aiV.verdict === 'warning' ? 'AI: Warning' : 'AI: Flag';
  aiBadge.title = aiV.reason || '';
  badges.appendChild(aiBadge);
}
```

**Step 3: Add CSS for AI verdict badges**

```css
.badge-ai-pass { background: #c6f6d5; color: #276749; }
.badge-ai-warning { background: #fefcbf; color: #975a16; }
.badge-ai-flag { background: #fed7d7; color: #c53030; }
```

**Step 4: Add AI verdict filter buttons**

Add to the compile bar:
```html
<button onclick="filterByReviewStatus('ai-flagged')">Show AI Flagged</button>
<button onclick="filterByReviewStatus('ai-unverified')">Show AI Unverified</button>
```

Update `filterByReviewStatus()` to handle these:
```javascript
} else if (status === 'ai-flagged') {
  var aiV = AI_VERDICTS[String(refNum)];
  card.style.display = (aiV && (aiV.verdict === 'flag' || aiV.verdict === 'warning')) ? '' : 'none';
} else if (status === 'ai-unverified') {
  card.style.display = (!AI_VERDICTS[String(refNum)]) ? '' : 'none';
}
```

**Step 5: Show AI reason in review panel**

In the review panel rendering, after the Claude-verified checkbox, display the AI verdict reason as a read-only text area (populated from `AI_VERDICTS`, not just localStorage):

```javascript
var aiV = AI_VERDICTS[String(num)];
if (aiV) {
  rpHTML += '<div style="margin-top:6px;font-size:0.82rem;color:#553c9a;padding:6px 10px;background:#f5f0ff;border:1px solid #d6bcfa;border-radius:4px;">' +
    '<strong>AI verdict: ' + aiV.verdict.toUpperCase() + '</strong> — ' + escapeHtml(aiV.reason) + '</div>';
}
```

**Step 6: Update state save/load to include AI verdicts**

The `saveStateToFile()` function should merge `AI_VERDICTS` into the export so the state file has both user reviews and AI verdicts:

```javascript
function saveStateToFile() {
  var data = getAllReviews();
  // Merge AI verdicts
  for (var refNum in AI_VERDICTS) {
    if (!data[refNum]) data[refNum] = { satisfied: false, comment: '' };
    data[refNum].claude_verified = true;
    data[refNum].claude_verdict = AI_VERDICTS[refNum].verdict;
    data[refNum].claude_reason = AI_VERDICTS[refNum].reason;
  }
  var wrapper = { version: 3, savedAt: new Date().toISOString(), reviews: data };
  var blob = new Blob([JSON.stringify(wrapper, null, 2)], { type: 'application/json' });
  var a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = STATE_FILENAME;
  a.click();
  URL.revokeObjectURL(a.href);
}
```

And `loadStateFromFile()` should handle the v3 wrapper format:

```javascript
function loadStateFromFile(input) {
  var file = input.files[0];
  if (!file) return;
  var reader = new FileReader();
  reader.onload = function(e) {
    try {
      var raw = JSON.parse(e.target.result);
      var data = raw.reviews || raw;  // Handle both v3 wrapper and bare dict
      localStorage.setItem(STORAGE_KEY, JSON.stringify(data));
      renderCards();
      alert('State loaded successfully!');
    } catch(err) {
      alert('Error loading state file: ' + err.message);
    }
  };
  reader.readAsText(file);
  input.value = '';
}
```

---

### Task 5: Delete `crossref_fetcher.py`

**Files:**
- Delete: `~/.claude/skills/reference-viewer/scripts/crossref_fetcher.py`

**Step 1: Remove the file**

```bash
rm ~/.claude/skills/reference-viewer/scripts/crossref_fetcher.py
```

**Step 2: Remove the import from `generate_reference_viewer.py`**

In `main()`, remove the `from crossref_fetcher import fetch_abstracts` line and the entire "Step 3: Fetch abstracts from CrossRef" block. Replace with a comment:

```python
# Abstracts are fetched by Claude via external MCPs and passed to generate_viewer().
# When running standalone (CLI), no abstracts are fetched.
abstracts = {}
```

---

### Task 6: Rewrite `SKILL.md`

**Files:**
- Modify: `~/.claude/skills/reference-viewer/SKILL.md`

**Step 1: Rewrite with new workflow**

```markdown
# Reference Viewer

## When to Invoke

- User asks to generate or regenerate a reference viewer
- User says `/reference-viewer`
- User mentions checking citations against PDFs
- User wants to review manuscript references interactively
- User asks to address comments/flags from the reference viewer

## Intent Detection

Detect which workflow the user wants from natural language:

- **Generate**: "generate reference viewer", "review my references", "make the HTML", "reference viewer" (default)
- **Address comments**: "check my comments", "address the flagged references", "fix the flagged refs", "update based on review"
- **Regenerate**: "regenerate the viewer", "redo the HTML", "update the reference viewer"

## Workflow: Generate Viewer

### 1. Find the manuscript
Search for `.md` files in `docs/` that contain a `## References` section. If multiple or none found, ask the user.

### 2. Find the literature folder
Look for a `literature/` directory relative to the manuscript's parent directory. If not found, ask the user.

### 3. Parse the manuscript

```python
import sys
sys.path.insert(0, os.path.expanduser('~/.claude/skills/reference-viewer/scripts'))
from generate_reference_viewer import parse_sections, parse_references, find_citations, build_section_hierarchy
```

Parse the manuscript to get references (with DOIs), citation contexts, and sections.

### 4. Fetch abstracts via external MCPs

For each reference that has a DOI, fetch the abstract. Use this cascade:

1. **uf_mcp_manuscript_search** tools (preferred — has Scopus, Elsevier, CrossRef, PubMed, Springer, PLOS access with institutional API keys):
   - `crossref_work(doi)` — works for any publisher, returns abstract
   - `scopus_abstract_by_doi(doi)` — Elsevier/Scopus articles
   - `pubmed_search(query)` then `pubmed_fetch(pmids)` — for PubMed-indexed articles

2. **PubMed plugin** (cloud MCP):
   - `mcp__claude_ai_PubMed__search_articles(query)` — search by title/DOI
   - `mcp__claude_ai_PubMed__get_article_metadata(pmids)` — get abstract

3. **paper-search** (for preprints):
   - `search_biorxiv(query)`, `search_medrxiv(query)`, `search_arxiv(query)`

Process references in batches. Build a dict: `{ref_num: abstract_text}`.

### 5. Match PDFs and extract snippets

This happens inside `generate_viewer()` automatically.

### 6. Run AI verification

For each reference, build an evidence package and judge it:

```python
from verification import gather_evidence
from state_manager import save_verification_result
```

For each reference:
1. Call `gather_evidence(ref_num, reference, citation_contexts, abstract, paper_snippets, pdf_full_text)`
2. Read the evidence summary
3. Judge: does the reference support the claims? Assign verdict: pass / warning / flag
4. Call `save_verification_result(state_path, ref_num, verdict, reason)`

Process in batches of ~10 to manage context.

### 7. Generate HTML

```python
from generate_reference_viewer import generate_viewer

stats = generate_viewer(
    manuscript_path=manuscript_path,
    literature_dir=literature_dir,
    output_path=output_path,
    state_path=state_path,
    verification_results=verification_results,
    abstracts=abstracts,
)
```

### 8. Report results
Report: total references, PDFs matched, abstracts fetched, verification summary (pass/warning/flag counts), output file path.

**IMPORTANT**: The tool renames PDFs in the literature folder to `N_AuthorLastName-ShortTitle.pdf`. This is non-destructive (rename, not delete) but irreversible without git. Warn the user on first run.

## Workflow: Address Comments

1. Find the state file (`ref_review_state.json`) alongside the manuscript
2. Read it with `state_manager.load_state(state_path)`
3. Find all entries where `comment` is non-empty and `satisfied` is False
4. For each flagged reference, read the comment and act on it:
   - Fix the manuscript directly (wrong year, typo, rewrite claim, etc.)
   - If the comment asks to find a better reference, use external MCPs to search
5. Report what was changed

## Workflow: Regenerate Viewer

Same as Generate, but:
- Existing user reviews (satisfied checkboxes, comments) in the state file are preserved
- AI verification is re-run fresh (verdicts may change if manuscript was updated)

## Notes

- The HTML output is self-contained — no server, no external resources. Open in any browser.
- Review state is stored in browser localStorage AND in the JSON state file. The HTML loads the state file on generation to embed AI verdicts.
- Re-running generates fresh HTML but preserves user review state in the JSON file.
```

---

### Task 7: Integration test — full pipeline

**Step 1: Test with the Sleep-Pain manuscript**

Run the full pipeline against the active manuscript:

```bash
cd /orange/cruzalmeida/pvaldeshernandez/Sleep-Pain_Coupling/UPLOAD2
python ~/.claude/skills/reference-viewer/scripts/generate_reference_viewer.py \
    docs/manuscript_pain.md \
    --literature-dir literature/ \
    --output docs/reference_viewer.html
```

Verify:
- All 56+ references parsed
- PDFs matched and renamed
- HTML opens in browser with reference cards
- No Python errors

**Step 2: Test generate_viewer() programmatically**

```python
import sys
sys.path.insert(0, os.path.expanduser('~/.claude/skills/reference-viewer/scripts'))
from generate_reference_viewer import generate_viewer

stats = generate_viewer(
    manuscript_path='docs/manuscript_pain.md',
    literature_dir='literature/',
    abstracts={1: 'Test abstract for ref 1'},
    verification_results={1: {'verdict': 'pass', 'reason': 'Abstract supports claims'}},
)
print(stats)
```

Verify the HTML has the AI badge on reference 1.

**Step 3: Test state round-trip**

1. Generate viewer (creates state JSON with AI verdicts)
2. Open HTML — verify AI badges show
3. Add a comment in the HTML, save state
4. Read state file with `state_manager.load_state()` — verify user comment AND AI verdict coexist
5. Regenerate — verify user comment preserved, AI verdict refreshed

---

### Task 8: Clean up MCP server (optional, after verification)

**Step 1: Remove MCP from settings**

After confirming the skill works end-to-end, remove the `reference-reviewer` entry from `~/.claude/settings.json` under `mcpServers`.

**Step 2: Archive or delete the MCP server directory**

```bash
# Archive first, delete later if desired
mv ~/.claude/mcp-servers/reference-reviewer ~/.claude/mcp-servers/reference-reviewer.archived
```
