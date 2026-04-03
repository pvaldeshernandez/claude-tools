"""Extract supporting text snippets from PDFs for each citation instance.

Given a PDF and a list of citation instances (from manuscript parsing),
this module finds the actual passages in the PDF that support each claim
made in the manuscript where the citation appears.

Public API:
    extract_snippets(pdf_path, citation_instances)
        -> list of grouped snippet dicts

Dependencies: fitz (pymupdf), re, math, pathlib
"""

import math
import re
from pathlib import Path

import fitz  # pymupdf


# ---------------------------------------------------------------------------
# Stopwords
# ---------------------------------------------------------------------------

def _build_stopwords():
    """Return a set of ~150 common English stopwords plus LaTeX tokens."""
    english = {
        "a", "about", "above", "after", "again", "against", "all", "am", "an",
        "and", "any", "are", "aren't", "as", "at", "be", "because", "been",
        "before", "being", "below", "between", "both", "but", "by", "can",
        "cannot", "could", "couldn't", "did", "didn't", "do", "does",
        "doesn't", "doing", "don't", "down", "during", "each", "few", "for",
        "from", "further", "get", "got", "had", "hadn't", "has", "hasn't",
        "have", "haven't", "having", "he", "her", "here", "hers", "herself",
        "him", "himself", "his", "how", "i", "if", "in", "into", "is",
        "isn't", "it", "its", "itself", "just", "let", "ll", "may", "me",
        "might", "more", "most", "mustn't", "my", "myself", "no", "nor",
        "not", "now", "of", "off", "on", "once", "only", "or", "other",
        "our", "ours", "ourselves", "out", "over", "own", "re", "s", "same",
        "shall", "shan't", "she", "should", "shouldn't", "so", "some",
        "such", "t", "than", "that", "the", "their", "theirs", "them",
        "themselves", "then", "there", "these", "they", "this", "those",
        "through", "to", "too", "under", "until", "up", "us", "ve", "very",
        "was", "wasn't", "we", "were", "weren't", "what", "when", "where",
        "which", "while", "who", "whom", "why", "will", "with", "won't",
        "would", "wouldn't", "you", "your", "yours", "yourself", "yourselves",
        "also", "already", "although", "among", "another", "around", "based",
        "became", "become", "besides", "can't", "compared", "d", "eg", "et",
        "etc", "even", "given", "however", "ie", "less", "like", "m",
        "made", "many", "much", "must", "neither", "never", "next",
        "none", "often", "one", "per", "rather", "respectively", "several",
        "since", "still", "therefore", "thus", "toward", "towards",
        "upon", "using", "ve", "versus", "via", "vs", "well", "whether",
        "within", "without", "yet",
    }
    # LaTeX tokens
    latex = {
        "\\", "$", "mathbf", "mathrm", "lambda", "gamma", "delta", "omega",
        "phi", "mu", "sigma", "tau", "rho", "alpha", "beta", "epsilon",
        "kappa", "theta", "pi", "psi", "chi", "eta", "zeta", "nu", "xi",
        "textbf", "textit", "emph", "cite", "ref", "frac", "sqrt", "sum",
        "int", "left", "right", "begin", "end", "displaystyle", "cdot",
        "times", "approx", "leq", "geq", "neq", "infty", "partial",
        "mathcal", "operatorname", "text",
    }
    return english | latex


_STOPWORDS = _build_stopwords()

# Pre-compiled patterns
_BRACKET_RE = re.compile(r'\[\d+(?:[,\s\u2013\u2014\-\u2010\u2011\u2012–—]*\d+)*\]')
_LATEX_INLINE_RE = re.compile(r'\$[^$]+\$')
_LATEX_CMD_RE = re.compile(r'\\[a-zA-Z]+')
_WORD_SPLIT_RE = re.compile(r'[^a-z0-9]+')
_HYPHEN_REJOIN_RE = re.compile(r'([a-z])-\n([a-z])')


# ---------------------------------------------------------------------------
# Text extraction and processing
# ---------------------------------------------------------------------------

def _extract_full_text(pdf_path):
    """Read all pages with pymupdf and return the full text.

    Cleans up artificial hyphenation at line breaks: if a word is split
    like ``word-\\ntion``, rejoin to ``wordtion`` only if the character
    before ``-\\n`` is a lowercase letter and the character after is also
    lowercase.
    """
    pdf_path = Path(pdf_path)
    try:
        doc = fitz.open(str(pdf_path))
    except Exception:
        return ""
    parts = []
    for page in doc:
        try:
            parts.append(page.get_text())
        except Exception:
            parts.append("")
    doc.close()
    text = "\n".join(parts)

    # Rejoin artificial hyphenation
    text = _HYPHEN_REJOIN_RE.sub(r'\1\2', text)

    return text


def _split_paragraphs(text):
    """Split on double newlines and filter out short fragments."""
    raw_paras = re.split(r'\n\s*\n', text)
    paras = []
    for p in raw_paras:
        cleaned = p.strip()
        if len(cleaned) >= 30:
            paras.append(cleaned)
    return paras


def _compute_word_freqs(full_text):
    """Count word frequencies across the entire PDF text.

    Returns dict {word: count}.
    """
    words = _WORD_SPLIT_RE.split(full_text.lower())
    freqs = {}
    for w in words:
        if w and len(w) > 1:
            freqs[w] = freqs.get(w, 0) + 1
    return freqs


# ---------------------------------------------------------------------------
# Keyword extraction and scoring
# ---------------------------------------------------------------------------

def _extract_claim_keywords(manuscript_snippet):
    """Extract content keywords from a manuscript citation context.

    Removes citation brackets, LaTeX, stopwords, and short tokens.
    Returns a list of unique content words.
    """
    text = manuscript_snippet

    # Remove [N], [N,M], [N-M] patterns
    text = _BRACKET_RE.sub('', text)

    # Remove LaTeX inline math
    text = _LATEX_INLINE_RE.sub('', text)

    # Remove LaTeX commands
    text = _LATEX_CMD_RE.sub('', text)

    # Lowercase and split on whitespace/punctuation
    words = _WORD_SPLIT_RE.split(text.lower())

    # Filter
    seen = set()
    keywords = []
    for w in words:
        if not w or len(w) < 3:
            continue
        if w in _STOPWORDS:
            continue
        if w in seen:
            continue
        # Skip pure numbers
        if w.isdigit():
            continue
        seen.add(w)
        keywords.append(w)

    return keywords


def _score_paragraph(paragraph, keywords, word_freqs):
    """Score a paragraph by weighted keyword overlap.

    Rarer words in the PDF count more: score per keyword =
    1 / log2(2 + word_freqs[keyword]).
    """
    para_words = set(_WORD_SPLIT_RE.split(paragraph.lower()))
    total = 0.0
    for kw in keywords:
        if kw in para_words:
            freq = word_freqs.get(kw, 0)
            total += 1.0 / math.log2(2 + freq)
    return total


def _truncate_to_words(text, max_words=150):
    """Truncate to ~max_words words, cutting at a sentence boundary if possible.

    If no sentence boundary is found within the last 20 words, cut at
    a word boundary and append '...'.
    """
    words = text.split()
    if len(words) <= max_words:
        return text

    # Try to find a sentence boundary (period followed by space) within
    # the last 20 words of the allowed range
    candidate = " ".join(words[:max_words])
    search_start = len(" ".join(words[:max(0, max_words - 20)]))
    last_period = candidate.rfind('. ', search_start)
    if last_period != -1:
        return candidate[:last_period + 1]

    # No sentence boundary found — cut at word boundary
    return candidate + "..."


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def extract_snippets(pdf_path, citation_instances):
    """Extract supporting snippets from a PDF for each citation instance.

    Args:
        pdf_path: Path to the matched PDF.
        citation_instances: list of {section, snippet, line} -- from
            manuscript parser (find_citations output for one reference).

    Returns:
        list of dicts, each with:
            instances        -- [{section: str, line: int}, ...]  (grouped)
            manuscript_context -- str (the manuscript text)
            pdf_snippets     -- [str, str]  (up to 2 supporting passages)
    """
    pdf_path = Path(pdf_path)

    # Extract and process the PDF text
    full_text = _extract_full_text(pdf_path)
    paragraphs = _split_paragraphs(full_text)
    word_freqs = _compute_word_freqs(full_text)

    # For each instance, compute top-2 snippets
    instance_results = []
    for inst in citation_instances:
        keywords = _extract_claim_keywords(inst["snippet"])

        # Score all paragraphs
        scored = []
        for para in paragraphs:
            score = _score_paragraph(para, keywords, word_freqs)
            if score > 0:
                scored.append((score, para))

        # Sort descending by score, take top 2
        scored.sort(key=lambda x: -x[0])
        top_paras = [_truncate_to_words(para) for _, para in scored[:2]]

        instance_results.append({
            "section": inst["section"],
            "line": inst["line"],
            "manuscript_context": inst["snippet"],
            "pdf_snippets": top_paras,
        })

    # Grouping: merge instances that have identical top-2 snippet texts
    groups = []
    snippet_key_to_group = {}  # tuple of snippet texts -> group index

    for ir in instance_results:
        key = tuple(ir["pdf_snippets"])
        if key in snippet_key_to_group:
            idx = snippet_key_to_group[key]
            groups[idx]["instances"].append({
                "section": ir["section"],
                "line": ir["line"],
            })
        else:
            idx = len(groups)
            snippet_key_to_group[key] = idx
            groups.append({
                "instances": [{"section": ir["section"], "line": ir["line"]}],
                "manuscript_context": ir["manuscript_context"],
                "pdf_snippets": ir["pdf_snippets"],
            })

    return groups
