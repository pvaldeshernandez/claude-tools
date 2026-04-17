# Claude Custom Tools

Custom skills and MCP servers for Claude Code.

## Skills

- **docx-manuscript-writer** — Generate submission-ready DOCX from manuscript markdown
- **alps-qc-vision-reviewer** — Vision-based QC reviewer for ALPS DTI figures
- **session-monitor** — HiPerGator session lifetime monitor and auto-save
- **analysis-reporter** — Write up analysis sessions as markdown reports
- **reference-viewer** — Interactive HTML reference viewer with AI verification

## MCP Servers

- **uf_mcp_manuscript_search** — Multi-database academic literature search (PubMed, CrossRef, Scopus, PLOS, Springer, Unpaywall)

The former `reference-reviewer` MCP server has been superseded by the
`reference-viewer` skill, which adds AI verification, content-based PDF
matching (no renaming), expanded citation-context extraction (full
sentence + continuation sentences), and OpenAlex / Semantic Scholar
fallbacks for abstract fetching.

## Setup

These are deployed at `~/.claude/skills/` and `~/.claude/mcp-servers/` respectively. This repo is the version-controlled source of truth.
