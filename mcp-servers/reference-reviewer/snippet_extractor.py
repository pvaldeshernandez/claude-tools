"""Extract supporting passages from full-text documents that relate to citation contexts."""

import re

# Common English stopwords for keyword extraction
_STOPWORDS = frozenset({
    "the", "a", "an", "of", "in", "to", "and", "or", "for", "with", "on",
    "is", "are", "was", "were", "by", "from", "at", "as", "this", "that",
    "its", "it", "be", "been", "being", "have", "has", "had", "do", "does",
    "did", "will", "would", "could", "should", "may", "might", "can",
    "shall", "not", "no", "but", "if", "than", "then", "so", "very",
    "also", "about", "up", "out", "into", "over", "after", "before",
    "between", "through", "during", "without", "within", "among", "each",
    "both", "all", "any", "more", "most", "other", "some", "such",
    "only", "own", "same", "these", "those", "which", "who", "whom",
    "what", "when", "where", "how", "why", "there", "here", "our",
    "their", "your", "my", "his", "her", "we", "they", "you", "he",
    "she", "them", "us", "me", "him", "per", "however", "therefore",
    "thus", "while", "since", "although", "though", "whether",
})


def extract(ref_num: int, full_text: str, citation_contexts: list) -> str:
    """Find and format supporting passages from a full-text document.

    Args:
        ref_num: Reference number.
        full_text: Full text of the paper (markdown or plain text).
        citation_contexts: List of citation dicts with 'snippet' key.

    Returns:
        HTML-formatted string of the top supporting passages, with keywords bolded.
    """
    if not full_text or not citation_contexts:
        return ""

    # Extract keywords from all citation contexts for this reference
    keywords = set()
    for ctx in citation_contexts:
        snippet = ctx.get("snippet", "")
        keywords.update(_extract_keywords(snippet))

    if not keywords:
        return ""

    # Split text into paragraphs and score each
    paragraphs = _split_paragraphs(full_text)
    scored = []
    for para in paragraphs:
        score = _score_paragraph(para, keywords)
        if score > 0:
            scored.append((score, para))

    # Sort by score descending, take top 3-5
    scored.sort(key=lambda x: -x[0])
    top = scored[:5]

    if not top:
        return ""

    return _format_passages([para for _, para in top], keywords)


def _extract_keywords(snippet: str) -> set:
    """Extract informative keywords from a citation snippet.

    Removes stopwords, keeps 3-5 rarest/longest terms.
    """
    words = re.findall(r"[a-zA-Z]{3,}", snippet)
    # Filter stopwords and very common short words
    candidates = [w.lower() for w in words if w.lower() not in _STOPWORDS and len(w) >= 3]

    # Prefer longer, rarer words — sort by length descending
    candidates = sorted(set(candidates), key=lambda w: -len(w))

    # Return top 5 keywords
    return set(candidates[:5])


def _split_paragraphs(text: str) -> list:
    """Split text into paragraphs on double-newlines.

    Filters out very short fragments (headers, page numbers, etc.).
    """
    # Split on double newlines or markdown section breaks
    raw = re.split(r"\n\s*\n", text)
    paragraphs = []
    for p in raw:
        cleaned = p.strip()
        # Skip very short fragments, headers, page numbers
        if len(cleaned) < 80:
            continue
        # Skip lines that are mostly non-alpha (tables, figures)
        alpha_ratio = sum(1 for c in cleaned if c.isalpha()) / max(len(cleaned), 1)
        if alpha_ratio < 0.5:
            continue
        paragraphs.append(cleaned)
    return paragraphs


def _score_paragraph(paragraph: str, keywords: set) -> float:
    """Score a paragraph by keyword overlap.

    Returns fraction of keywords found in the paragraph.
    """
    para_lower = paragraph.lower()
    found = sum(1 for kw in keywords if kw in para_lower)
    return found / len(keywords) if keywords else 0


def _format_passages(passages: list, keywords: set) -> str:
    """Format top passages as HTML with keyword highlighting."""
    parts = []
    for i, para in enumerate(passages):
        highlighted = para
        # Bold keywords (case-insensitive)
        for kw in sorted(keywords, key=lambda w: -len(w)):  # longest first to avoid partial matches
            pattern = re.compile(re.escape(kw), re.IGNORECASE)
            highlighted = pattern.sub(lambda m: f"<b>{m.group()}</b>", highlighted)

        # Clean up markdown artifacts
        highlighted = re.sub(r"#+\s*", "", highlighted)  # remove markdown headers
        highlighted = highlighted.replace("\n", " ").strip()

        if i > 0:
            parts.append("<hr style='border:none;border-top:1px solid #eee;margin:8px 0;'>")
        parts.append(f"<p style='margin:4px 0;'>{highlighted}</p>")

    return "\n".join(parts)
