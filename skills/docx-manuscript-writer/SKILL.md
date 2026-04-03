---
name: docx-manuscript-writer
description: Use when the user asks to write, draft, or revise a scientific abstract, manuscript section (Introduction, Methods, Results, Discussion), or needs help with scientific writing including finding citations and formatting for a specific journal. Generates formatted Word (.docx) documents.
---

# DOCX Manuscript Writer

Draft scientific abstracts and manuscript sections as formatted Word documents (.docx), with journal-specific styles, study-design-aware language, and a reusable author database.

## Workflow

### Phase 1: Setup

Ask three questions (one at a time, prefer multiple choice):

1. **Study design** — Cross-sectional, longitudinal, or RCT?
   Read `language-rules.md` in this skill directory and apply the matching ruleset throughout all writing.

2. **Output type** — Abstract or manuscript section?
   If manuscript section: which one (Introduction, Methods, Results, Discussion)?

3. **Target journal/conference** — List available profiles from `journals/` directory.
   If none match, ask the user for formatting details and offer to create a new profile.

### Phase 2: Content Input

Two modes — let the user choose or infer from context:

- **CSV mode**: User points to a results file. Read it, identify significant effects, ask which to report and in what units.
- **Conversational**: User describes findings. Organize into target sections, ask for missing stats (N, effect sizes, CIs, p-values).

### Phase 3: Literature (optional)

When writing Background, Introduction, or Discussion:
- Ask: "Should I search for supporting citations?"
- **If user has a .bib file** (Mendeley export or other): use the citation manager to search it:

   ```bash
   /apps/conda/25.3.1/bin/python3.13 ~/.claude/skills/docx-manuscript-writer/citation-manager.py search /path/to/library.bib "search terms"
   ```

   Show details: `citation-manager.py show library.bib entry_key`
   Format refs: `citation-manager.py format library.bib key1,key2 --style vancouver`

- **If no .bib file**: use web search to find relevant papers
- Present candidates (title, authors, year, journal) for approval
- **Never insert a citation the user hasn't approved**
- **Never invent a citation**
- Format approved references using the journal profile's `citation_style`

### Phase 4: Generate .docx

Two-step pipeline: parse markdown → generate docx.

**Step 1: Parse markdown to JSON** (if starting from a .md manuscript):

   ```bash
   python ~/.claude/skills/docx-manuscript-writer/markdown-to-json.py manuscript.md \
       --journal journal-of-pain \
       --authors valdes-hernandez,montesino-goicolea,fillingim,cruz-almeida \
       --page-break-before "Abstract,Introduction"
   ```

   This produces `manuscript_input.json` in the same directory. The parser handles:
   - Title/author/affiliation extraction from the header block
   - Section headings (##/###/####) with body text
   - Markdown tables (pipe-delimited → tab-separated)
   - Table captions, table notes
   - Figure placeholders with captions
   - Page break insertion points

**Step 2: Generate docx from JSON**:

   ```bash
   python ~/.claude/skills/docx-manuscript-writer/docx-generator.py manuscript_input.json
   ```

   The generator handles:
   - Plain Table 2 style, 11pt, autofit, centered tables
   - Inline LaTeX math ($...$) rendered as OMML equations (in body text AND table cells)
   - Markdown formatting (**bold**, *italic*, ***bold+italic***) including in tables
   - Page breaks before specified headings
   - Figures as grouped objects with In Line with Text wrapping

1. Read `authors.yaml` — user specifies which collaborators and their order
2. If a collaborator is missing, ask for details and add them to `authors.yaml`
3. Read `domain-conventions.md` and apply reporting rules
4. Report word counts per section and total vs. limit
5. User reviews and requests revisions — regenerate the same .docx

### Phase 5: Adding a New Journal

When the user targets a journal without a profile:
1. Ask for: font, font size, spacing, alignment, word limit, required sections, citation style
2. Check the journal's author guidelines via web search if the user doesn't know specifics
3. Save as a new YAML in `journals/`

### Phase 6: Reference Viewer

After the manuscript is complete, generate an interactive HTML reference viewer using the **reference-reviewer MCP server** (configured at `~/.claude/mcp-servers/reference-reviewer/`).

**IMPORTANT:** Always use the reference-reviewer MCP tools — never call standalone Python scripts for this.

MCP tools available:
- `parse_manuscript(manuscript_path)` — Parse markdown to extract references, citations, sections
- `generate_viewer(manuscript_path, output_path)` — Generate interactive HTML viewer
- `fetch_abstracts(dois, email)` — Fetch abstracts from PubMed/CrossRef
- `process_pdfs(pdfs_folder, references_json)` — Extract text from reference PDFs
- `verify_references(references_json, email)` — Verify references against PubMed

Features: search, section filters, expand/collapse, review checkboxes, Claude-verified badges, save/load state (JSON)

## Key Rules

- Apply language rules from the study design throughout — never use causal language in cross-sectional work unless the user overrides
- Follow domain conventions in `domain-conventions.md`
- Each revision overwrites the same .docx — no file proliferation
- Word counts are reported after every generation

## LaTeX Math Support

The generator converts LaTeX math (`$...$` inline, `$$...$$` display) to Word OMML equations using a two-tier system:

- **Simple math** (Greek letters, sub/superscripts, symbols): handled by built-in tokenizer
- **Complex math** (`\frac`, `\sqrt`, `\begin{pmatrix}`, `\mathbf`, `\left/\right`, `\tag`): handled by `mml2omml.py` via LaTeX → MathML (`latex2mathml`) → OMML
- Display math (`$$...$$`) gets its own centered paragraph
- Requires `latex2mathml` package (`pip install latex2mathml`)

## Figure Formatting

Figures are inserted as **grouped objects** (image + caption text box) with In Line with Text wrapping:

- Image and caption are wrapped in a DrawingML group (`wpg:wgp`) inside an inline element (`wp:inline`)
- Group is always full page width (6.5 in) so captions span the whole line even when the image is narrower
- Image is centered horizontally within the group
- Caption uses Word's built-in Caption style with "Figure N." bold prefix
- XML: `w:r` > `mc:AlternateContent` > `mc:Choice Requires="wpg"` > `w:drawing` > `wp:inline` > `wpg:wgp`
- Falls back to inline insertion if grouping fails
- See `formatting.md` for full details
