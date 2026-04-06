"""Extract supporting text snippets from PDFs for each citation instance.

Given a PDF and a list of citation instances (from manuscript parsing),
this module finds the actual passages in the PDF that support each claim
made in the manuscript where the citation appears.

Two extraction strategies:
1. **Claim-aware**: extracts numbers, effect sizes, directional claims,
   and named entities from the manuscript context, then searches for
   paragraphs containing those specific values.
2. **Keyword TF-IDF**: weighted keyword overlap (fallback when claim-aware
   extraction finds nothing).

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
_APA_CITE_RE = re.compile(
    r'\([^()]*?[A-Z][A-Za-z\-\']+[^()]*?\d{4}[a-z]?(?:\s*;[^()]*?)*\)'
)
_LATEX_INLINE_RE = re.compile(r'\$[^$]+\$')
_LATEX_CMD_RE = re.compile(r'\\[a-zA-Z]+')
_WORD_SPLIT_RE = re.compile(r'[^a-z0-9]+')
_HYPHEN_REJOIN_RE = re.compile(r'([a-z])-\n([a-z])')

# Claim-aware patterns
_NUMBER_RE = re.compile(
    r'(?<![a-zA-Z])'           # not preceded by letter
    r'[-−]?'                   # optional minus
    r'\d+\.?\d*'               # integer or decimal
    r'(?:\s*[-–—]\s*'          # optional range (dash)
    r'[-−]?\d+\.?\d*)?'        # second number
    r'(?=%|$|\s|[,;)\]])'     # followed by %, end, space, punctuation
)
_EFFECT_SIZE_RE = re.compile(
    r'(?:r|R|d|g|η|beta|β|B|OR|HR|RR|AUC|ICC|κ|kappa)\s*'
    r'[=≈~]\s*'
    r'[-−]?\d+\.?\d*',
    re.IGNORECASE
)
_PVALUE_RE = re.compile(
    r'[pP]\s*[<>=≤≥]\s*0?\.\d+',
)
_NVALUE_RE = re.compile(
    r'[Nn]\s*=\s*[\d,]+',
)


# ---------------------------------------------------------------------------
# Text extraction and processing
# ---------------------------------------------------------------------------

def _extract_full_text(pdf_path):
    """Read all pages with pymupdf and return the full text."""
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
    """Count word frequencies across the entire PDF text."""
    words = _WORD_SPLIT_RE.split(full_text.lower())
    freqs = {}
    for w in words:
        if w and len(w) > 1:
            freqs[w] = freqs.get(w, 0) + 1
    return freqs


# ---------------------------------------------------------------------------
# Claim-aware extraction
# ---------------------------------------------------------------------------

def _extract_claim_numbers(manuscript_snippet):
    """Extract specific numeric values from the manuscript claim.

    Returns a list of strings like '0.30', '971', '0.50', '50–88'.
    """
    text = manuscript_snippet
    # Remove citations
    text = _BRACKET_RE.sub('', text)
    text = _APA_CITE_RE.sub('', text)
    text = _LATEX_INLINE_RE.sub('', text)

    numbers = []
    for m in _NUMBER_RE.finditer(text):
        val = m.group().strip()
        if val and len(val) <= 15:
            numbers.append(val)

    # Also grab effect sizes, p-values, N-values as complete strings
    for pattern in (_EFFECT_SIZE_RE, _PVALUE_RE, _NVALUE_RE):
        for m in pattern.finditer(text):
            numbers.append(m.group().strip())

    return numbers


def _extract_claim_phrases(manuscript_snippet):
    """Extract short meaningful phrases (2-4 words) from the claim.

    Targets noun phrases, directional claims, and technical terms.
    """
    text = manuscript_snippet
    text = _BRACKET_RE.sub('', text)
    text = _APA_CITE_RE.sub('', text)
    text = _LATEX_INLINE_RE.sub('', text)
    text = _LATEX_CMD_RE.sub('', text)

    phrases = []

    # Directional/comparative phrases
    directional = re.findall(
        r'(?:more|less|greater|stronger|weaker|higher|lower|increased?|decreased?|reduced?|'
        r'impaired?|enhanced?|amplified?|blunted?|loss\s+of|associated\s+with|'
        r'predicts?|predicted|mediates?|moderates?)'
        r'\s+[a-z]+(?:\s+[a-z]+)?',
        text.lower()
    )
    phrases.extend(directional)

    # Technical compound terms (capitalized or hyphenated)
    technical = re.findall(
        r'[A-Z][a-z]+(?:[-\s][A-Z]?[a-z]+)+',
        _BRACKET_RE.sub('', _APA_CITE_RE.sub('', manuscript_snippet))
    )
    phrases.extend(t.lower() for t in technical)

    return phrases


def _score_paragraph_claims(paragraph, numbers, phrases, keywords, word_freqs):
    """Score a paragraph using claim-aware features.

    Scoring hierarchy:
    1. Exact numeric match: +5 per number found
    2. Phrase match: +3 per phrase found
    3. Keyword TF-IDF: as before (fallback)
    """
    para_lower = paragraph.lower()
    para_words = set(_WORD_SPLIT_RE.split(para_lower))
    score = 0.0

    # Numeric matches — high value
    for num in numbers:
        # Normalize dashes for range matching
        normalized = num.replace('–', '-').replace('—', '-').replace('−', '-')
        para_normalized = para_lower.replace('–', '-').replace('—', '-').replace('−', '-')
        if normalized in para_normalized:
            score += 5.0

    # Phrase matches
    for phrase in phrases:
        if phrase in para_lower:
            score += 3.0

    # Keyword TF-IDF (fallback weight)
    for kw in keywords:
        if kw in para_words:
            freq = word_freqs.get(kw, 0)
            score += 1.0 / math.log2(2 + freq)

    return score


# ---------------------------------------------------------------------------
# Keyword extraction (original, used as fallback)
# ---------------------------------------------------------------------------

def _extract_claim_keywords(manuscript_snippet):
    """Extract content keywords from a manuscript citation context."""
    text = manuscript_snippet
    text = _BRACKET_RE.sub('', text)
    text = _APA_CITE_RE.sub('', text)
    text = _LATEX_INLINE_RE.sub('', text)
    text = _LATEX_CMD_RE.sub('', text)
    words = _WORD_SPLIT_RE.split(text.lower())

    seen = set()
    keywords = []
    for w in words:
        if not w or len(w) < 3:
            continue
        if w in _STOPWORDS:
            continue
        if w in seen:
            continue
        if w.isdigit():
            continue
        seen.add(w)
        keywords.append(w)

    return keywords


def _truncate_to_words(text, max_words=150):
    """Truncate to ~max_words words, cutting at sentence boundary if possible."""
    words = text.split()
    if len(words) <= max_words:
        return text

    candidate = " ".join(words[:max_words])
    search_start = len(" ".join(words[:max(0, max_words - 20)]))
    last_period = candidate.rfind('. ', search_start)
    if last_period != -1:
        return candidate[:last_period + 1]
    return candidate + "..."


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def extract_snippets(pdf_path, citation_instances):
    """Extract supporting snippets from a PDF for each citation instance.

    Uses claim-aware extraction (numbers, phrases) first, falling back
    to keyword TF-IDF if no claim-specific matches are found.

    Args:
        pdf_path: Path to the matched PDF.
        citation_instances: list of {section, snippet, line} -- from
            manuscript parser (find_citations output for one reference).

    Returns:
        list of dicts, each with:
            instances        -- [{section: str, line: int}, ...]  (grouped)
            manuscript_context -- str (the manuscript text)
            pdf_snippets     -- [str, str, str]  (up to 3 supporting passages)
    """
    pdf_path = Path(pdf_path)

    full_text = _extract_full_text(pdf_path)
    paragraphs = _split_paragraphs(full_text)
    word_freqs = _compute_word_freqs(full_text)

    instance_results = []
    for inst in citation_instances:
        snippet = inst["snippet"]
        keywords = _extract_claim_keywords(snippet)
        numbers = _extract_claim_numbers(snippet)
        phrases = _extract_claim_phrases(snippet)

        # Score all paragraphs with claim-aware scoring
        scored = []
        for para in paragraphs:
            score = _score_paragraph_claims(
                para, numbers, phrases, keywords, word_freqs
            )
            if score > 0:
                scored.append((score, para))

        # Sort descending, take top 3
        scored.sort(key=lambda x: -x[0])
        top_paras = [_truncate_to_words(para) for _, para in scored[:3]]

        instance_results.append({
            "section": inst["section"],
            "line": inst["line"],
            "manuscript_context": snippet,
            "pdf_snippets": top_paras,
        })

    # Grouping: merge instances that have identical top snippet texts
    groups = []
    snippet_key_to_group = {}

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
