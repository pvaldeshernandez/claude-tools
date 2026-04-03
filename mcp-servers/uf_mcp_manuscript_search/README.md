# Academic Literature MCP Server

MCP server providing 33 tools for searching and retrieving academic literature across 6 sources.

## Sources & Tools

| Source | Tools | Full Text? | Key Required? |
|--------|-------|-----------|---------------|
| **Elsevier** (Scopus + ScienceDirect) | 12 | Yes (with inst token) | Yes — free at [dev.elsevier.com](https://dev.elsevier.com/) |
| **PubMed** (NCBI E-Utilities) | 6 | Abstracts only (PMC for some OA) | Optional — free at [ncbi.nlm.nih.gov/account](https://www.ncbi.nlm.nih.gov/account/) |
| **Springer Nature** (Nature, Springer, BMC) | 4 | OA articles | Yes — free at [dev.springernature.com](https://dev.springernature.com/) |
| **CrossRef** (all publishers) | 5 | Metadata only | No |
| **PLOS** (all 7 journals) | 3 | Yes (all OA) | No |
| **Unpaywall** (OA finder) | 3 | Finds OA PDFs by DOI | Email only |

## Install

```bash
# Clone the repo
git clone <repo-url>
cd uf_mcp_manuscript_search

# Create venv and install
python -m venv .venv
# Windows:
.venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate

pip install -e .
```

## Configure API Keys

Create these files with your keys (one key per file, plain text):

```
~/.elsevier/api_key.txt       # Required — Elsevier API key
~/.elsevier/inst_token.txt     # Optional — institutional token for full text
~/.springer/api_key.txt        # Springer Nature Meta API key
~/.springer/oa_key.txt         # Springer Nature Open Access API key
~/.ncbi/api_key.txt            # Optional — PubMed (bumps rate from 3 to 10 req/sec)
~/.ncbi/email.txt              # Optional — your email for NCBI
~/.crossref/email.txt          # Optional — email for CrossRef polite pool (faster rates)
~/.unpaywall/email.txt         # Required for Unpaywall — your email address
```

Or use environment variables instead:

```bash
export ELSEVIER_API_KEY="your-key"
export ELSEVIER_INST_TOKEN="your-token"     # optional
export SPRINGER_API_KEY="your-meta-key"
export SPRINGER_OA_KEY="your-oa-key"
export NCBI_API_KEY="your-key"              # optional
export NCBI_EMAIL="you@example.com"         # optional
export CROSSREF_EMAIL="you@example.com"     # optional
export UNPAYWALL_EMAIL="you@example.com"
```

## Add to Claude Code

Add to your `~/.claude/mcp_settings.json`:

```json
{
  "mcpServers": {
    "uf_mcp_manuscript_search": {
      "command": "cmd",
      "args": ["/c", "C:\\path\\to\\uf_mcp_manuscript_search\\.venv\\Scripts\\python.exe", "-m", "uf_mcp_manuscript_search.server"]
    }
  }
}
```

On macOS/Linux:

```json
{
  "mcpServers": {
    "uf_mcp_manuscript_search": {
      "command": "/path/to/uf_mcp_manuscript_search/.venv/bin/python",
      "args": ["-m", "uf_mcp_manuscript_search.server"]
    }
  }
}
```

## Verify

After restarting Claude Code, test with:

- `api_key_status` — check Elsevier
- `pubmed_api_status` — check PubMed
- `springer_api_status` — check Springer Nature
- `crossref_api_status` — check CrossRef
- `plos_api_status` — check PLOS
- `unpaywall_api_status` — check Unpaywall

## Tool Reference

### Elsevier / Scopus
- `scopus_search` — search Scopus (citation database, all publishers)
- `scopus_abstract` — get abstract by Scopus ID
- `scopus_abstract_by_doi` — get abstract by DOI
- `scopus_author` — author profile (h-index, publications)
- `scopus_author_search` — find authors
- `scopus_affiliation_search` — find institutions

### Elsevier / ScienceDirect
- `scidir_search` — search full-text articles
- `scidir_article` — get article by DOI (full text with inst access)
- `scidir_article_by_pii` — get article by PII

### Elsevier / Serials
- `serial_search` — search journals by title
- `serial_title` — journal metadata by ISSN

### PubMed
- `pubmed_search` — search 36M+ biomedical articles
- `pubmed_fetch` — full records (abstract, MeSH, authors)
- `pubmed_summary` — brief metadata (faster)
- `pubmed_related` — find similar articles
- `pmc_lookup` — convert between PMID/PMCID/DOI

### Springer Nature
- `springer_search` — search metadata (Nature, Springer, BMC, Palgrave)
- `springer_open_access` — search OA articles only
- `springer_by_doi` — lookup by DOI

### CrossRef
- `crossref_search` — search all publishers (Frontiers, Science, Wiley, IEEE, etc.)
- `crossref_work` — metadata for any DOI
- `crossref_journal` — journal info + recent articles by ISSN
- `crossref_funder_works` — articles by funder (NIH, NSF, etc.)

### PLOS
- `plos_search` — search all 7 PLOS journals
- `plos_article` — get article with full text by DOI

### Unpaywall
- `unpaywall_lookup` — find OA full text for a DOI
- `unpaywall_batch` — check multiple DOIs for OA (up to 25)

### Status
- `api_key_status` / `pubmed_api_status` / `springer_api_status` / `crossref_api_status` / `plos_api_status` / `unpaywall_api_status`
