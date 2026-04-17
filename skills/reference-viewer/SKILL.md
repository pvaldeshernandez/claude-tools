---
name: reference-viewer
description: Generate an interactive HTML reference viewer with AI verification from a manuscript markdown file and literature PDFs. Parses references, matches PDFs, extracts supporting snippets, auto-fetches abstracts, verifies each reference, and produces a self-contained reference_viewer.html with verdict badges and review workflow.
---

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
Search for `.md` files that contain a `## References` section. Check `docs/` first, then the working directory. If multiple or none found, ask the user.

### 2. Find the literature folder
Look for a `literature/` or `papers/` directory relative to the manuscript's parent directory (e.g., if manuscript is `project/docs/manuscript.md`, check `project/literature/`). If not found, ask the user for the path.

### 3. Parse, fetch abstracts, match PDFs, extract snippets

All handled automatically by `generate_viewer()`:

```python
import sys, os
sys.path.insert(0, os.path.expanduser('~/.claude/skills/reference-viewer/scripts'))
from generate_reference_viewer import generate_viewer
```

- **Abstracts**: Built-in cascade (CrossRef → PubMed E-utilities → Scopus). No MCP calls needed.
- **PDF matching**: Matches literature PDFs by content (DOI extracted from PDF metadata or first 3 pages; fuzzy title match). Filenames are preserved — the skill never renames PDFs.
- **Snippet extraction**: Finds supporting passages from each PDF for each citation context.

### 4. Run AI verification

For each reference, Claude judges whether the paper supports the manuscript's claims. This is the **only step that requires Claude** — everything else is automated.

```python
from verification import gather_evidence
from state_manager import save_verification_result
```

For each reference:
1. Call `gather_evidence(ref_num, reference, citation_contexts, abstract, paper_snippets, pdf_full_text)`
2. Read the evidence summary — this includes claim-aware snippets that target specific numbers, effect sizes, and directional assertions from the manuscript
3. Assign a single verdict: **pass**, **warning**, or **flag**
4. Write an **AI analysis summary** explaining WHY the reference supports (or fails to support) each specific claim. This should:
   - Match each manuscript assertion to specific evidence in the paper (quote numbers, findings, conclusions)
   - Flag if a specific numeric claim (e.g., "effect sizes of 0.30–0.50") cannot be found in the paper
   - Note if the paper is an animal study being cited without qualification
   - Note if the paper's actual finding differs from how it's characterized in the manuscript
5. Call `save_verification_result(state_path, ref_num, verdict, reason, details={"summary": ai_summary_text})`

The verdict covers everything — metadata correctness AND content support. There is no separate "metadata check" step. If metadata is wrong (wrong paper, wrong year), that's a **flag**. If the paper doesn't support the claim, that's a **flag** or **warning**.

Process in batches of ~10 to manage context. Verdicts:
- **pass**: Paper clearly supports the claims; metadata correct
- **warning**: Support is indirect, partial, or tangential
- **flag**: Paper does not support the claim, or metadata mismatch (wrong paper cited)

The AI summary is stored in `claude_summary` in the state file and rendered in the HTML viewer as a collapsible "AI Analysis Summary" section under each reference's verdict.

### 5. Generate HTML

```python
stats = generate_viewer(
    manuscript_path=manuscript_path,
    literature_dir=literature_dir,
    output_path=output_path,
    state_path=state_path,
    verification_results=verification_results,
)
```

### 6. Report results
Report: total references, PDFs matched, abstracts fetched, verification summary (pass/warning/flag counts), output file path.

**Note**: PDF filenames are never changed. The matcher reads each PDF's content (DOI + title from the first 3 pages) and matches it to a manuscript reference regardless of what the file is called.

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

## Error Handling

- If `pymupdf` not installed: tell user to run `conda install pymupdf`
- If PDF has no extractable text: warn and skip (abstracts-only mode)

## Notes

- The HTML output is self-contained — no server, no external resources. Open in any browser.
- Each reference has one AI badge (Pass/Warning/Flag) — no separate metadata checkbox.
- Review state is stored in browser localStorage AND in the JSON state file. The HTML embeds AI verdicts from the state at generation time.
- Re-running generates fresh HTML but preserves user review state in the JSON file.
- The state file uses v3 schema: `{version: 3, savedAt: ISO, reviews: {refNum: {satisfied, comment, claude_verdict, claude_reason, claude_timestamp}}}`.
