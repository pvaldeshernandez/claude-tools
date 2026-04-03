# Document Formatting Preferences

These are the user's preferred formatting conventions, extracted from their reference manuscript. The docx-generator applies these as defaults unless overridden by a journal profile.

## Page Setup
- **Page size**: Letter (8.5 x 11 in)
- **Margins**: 1 inch all sides
- **Line numbering**: Yes, continuous, every line (countBy=1, restart=continuous)

## Normal Style (body text)
- **Font**: Times New Roman
- **Size**: 12 pt
- **Alignment**: Justified
- **Line spacing**: Double (2.0)
- **Space after**: 6 pt
- **First line indent**: 0.1 in (first paragraph after heading: no indent)

## Title
- **Size**: 14 pt
- **Bold**: Yes
- **Alignment**: Center

## Heading 1 (major sections: Introduction, Methods, Results, Discussion, References)
- **Bold**: Yes
- **Italic**: No
- **Size**: Inherit from Normal (12 pt)
- **Space before**: 12 pt
- **Space after**: 12 pt
- **Keep with next**: Yes
- **Alignment**: Inherit (justified)

## Heading 2 (subsections: Participants, Measures, etc.)
- **Bold**: Yes
- **Italic**: Yes
- **Size**: Inherit from Normal (12 pt)
- **Space before**: 8 pt
- **Space after**: Inherit
- **Keep with next**: Yes

## Heading 3 (sub-subsections)
- **Bold**: No (inherit)
- **Italic**: No (inherit)
- **Size**: Inherit from Normal (12 pt)
- **Space before**: Inherit
- **Space after**: Inherit

## Authors
- **Font**: ALWAYS Times New Roman (same as Normal style) — never override with journal font
- **Author names**: Normal size (12 pt)
- **Affiliation superscripts**: 9 pt, superscript
- **Affiliations**: 9 pt, italic, List Paragraph style (left indent 0.36 in)

## Table Captions
- **Style**: Subtitle
- **Size**: 11 pt (inherited from Subtitle style)
- **"Table N."** prefix: Bold
- **Rest of caption**: Normal weight
- **Keep with next**: Yes (caption stays attached to table)
- **Space after**: 0 pt

## Tables
- **Style**: Table Grid (borders on all cells)
- **Alignment**: Center (table centered on page)
- **Cell font size**: 9 pt
- **Cell alignment**: Center (both header and data)
- **Cell spacing**: Before/after 20 twips (~1pt), single-spaced (line=240)
- **Header row**: Bold
- **No color fills** — plain black-and-white
- **Width**: Full text width (~6.6 in)

## Table Notes
- **Style**: Caption (same as figure captions)
- **Size**: 10 pt
- **"Note: "** prefix: Bold (auto-added by generator)
- **Rest of text**: Normal weight
- Placed immediately after the table data

## Figure Captions
- **Style**: Caption (Word's built-in Caption style)
- **Size**: 10 pt
- **"Figure N."** prefix: Bold
- **Rest of caption**: Normal weight
- **Space after**: 18 pt

## Figures (Grouped with Caption)
The default figure insertion uses **grouped objects** with In Line with Text wrapping, matching Word's behavior when objects are grouped:

- **Structure**: Figure image + caption text box grouped as a single `wpg:wgp` object
- **Wrapping**: In Line with Text (`wp:inline`) — this is what Word produces when you group objects
- **Group width**: Always full page width (6.5 in), so the caption spans the whole line even when the image is narrower
- **Image**: Scaled to `figure_width` (default 6.5 in), centered horizontally within the group
- **Caption text box**: Full group width (6.5 in), positioned directly below the image
  - White fill, no border, zero insets
  - Contains a single paragraph with Caption style
  - "Figure N." bold prefix + normal-weight description
- **XML structure**: `w:r` > `mc:AlternateContent` > `mc:Choice Requires="wpg"` > `w:drawing` > `wp:inline` > `a:graphic` > `wpg:wgp`
- **Backwards compatibility**: `mc:Fallback` contains inline image for processors that don't support wpg
- **Fallback**: If grouped insertion raises an exception, falls back to inline image + separate caption paragraph

## Inline Math (OMML Equations)
LaTeX math expressions in markdown (`$...$` inline, `$$...$$` display) are converted to Office Math (OMML) elements.

**Simple tokenizer** (basic inline math: Greek letters, sub/superscripts, symbols):
- Greek letters, symbols (`\times`, `\cdot`, `\pm`, etc.), accents (`\bar`, `\hat`, `\tilde`), `\text{}`
- Sub/superscripts: `x_{i}`, `x^{2}`, nested like `\gamma_{sp}`
- Spacing: `\,` (thin), `\;` (medium), `\!` (negative thin)

**Full LaTeX converter** (`mml2omml.py`, auto-selected for complex math):
- Triggered when LaTeX contains `\frac`, `\sqrt`, `\mathbf`, `\begin{pmatrix}`, `\left`, `\right`, `\tag`, `\quad`, `\operatorname`
- Pipeline: LaTeX → MathML (via `latex2mathml`) → OMML (via custom `mml2omml.py`)
- Handles fractions, matrices, square roots, accents, fenced expressions, sub/superscripts, equation tags
- Falls back to simple tokenizer on error
- **Font**: Cambria Math (standard OMML font), italic for variables, upright for operators/text

## References
- **Style**: Normal
- **Left alignment** with hanging indent (left indent 0.5 in, first line indent -0.5 in)
- **Paragraph splitting**: Each reference = one line in markdown; split on single `\n` (not `\n\n`)
- **Auto-numbering suppressed**: `w:numPr` with `numId=0` prevents Word from converting `1. ` prefixes into a numbered list

## First Paragraph After Heading
- **No first-line indent** (fi=0) — overrides the Normal style's 0.1 in indent
