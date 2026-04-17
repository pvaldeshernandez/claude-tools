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
# 4. parse_references (Vancouver + APA)
# ---------------------------------------------------------------------------

_DOI_RE = re.compile(r'(?:https?://(?:dx\.)?doi\.org/|doi:\s*)(10\.\d{4,9}/\S+)', re.IGNORECASE)

# Matches the end of a Vancouver author block. Captures the period that
# terminates the last author's initials (e.g., "Smith AB, Jones CD. Title...")
# Requires 1-4 uppercase letters followed by ". " to avoid false hits on
# mid-title abbreviations like "U.S."
_AUTHORS_END_RE = re.compile(r'\b[A-Z]{1,4}\.\s')


def _find_authors_end(text):
    """Return the index of the period that ends the author block, or -1."""
    m = _AUTHORS_END_RE.search(text)
    return (m.end() - 2) if m else -1
_YEAR_RE = re.compile(r'\b(\d{4})\b')
_JOURNAL_RE = re.compile(r'\*([^*]+)\*')

# APA reference patterns
# e.g. "Cruz-Almeida, Y., & Valdes-Hernandez, P. A. (2025). Title. *Journal*, 1(2), 3-4."
_APA_REF_RE = re.compile(
    r'^(.+?)\s*\((\d{4}[a-z]?)\)\.\s*(.+)$'
)
# Vancouver: "1. Author. Title. Journal..."
_VANCOUVER_REF_RE = re.compile(r'^(\d+)\.\s+(.+)$')


def _find_ref_section_start(lines):
    """Return the line index after the References heading, or None."""
    for i, raw in enumerate(lines):
        stripped = raw.strip()
        if re.match(r'^#{1,3}\s+references\s*$', stripped, re.IGNORECASE):
            return i + 1
    return None


def detect_citation_style(lines):
    """Detect whether the manuscript uses Vancouver [N] or APA (Author, Year).

    Scans the body (before References) and returns 'vancouver' or 'apa'.
    """
    ref_start = _find_ref_section_start(lines)
    body_end = ref_start if ref_start else len(lines)
    body = '\n'.join(lines[:body_end])

    vancouver_hits = len(re.findall(r'\[\d[\d,\s\u2013\u2014\-–—]*\]', body))
    apa_hits = len(re.findall(
        r'(?:\([A-Z][A-Za-z\-\']+(?:\s+(?:et\s+al\.|&\s+[A-Z]))[^)]*,\s*\d{4}[a-z]?\))|'
        r'(?:[A-Z][A-Za-z\-\']+\s+(?:et\s+al\.\s*)?\(\d{4}[a-z]?\))',
        body
    ))
    return 'apa' if apa_hits > vancouver_hits else 'vancouver'


def parse_references(lines):
    """Extract references from the ``## References`` block.

    Auto-detects Vancouver (numbered) vs APA (author-date) format.
    Tries Vancouver first on the reference list itself, falling back to APA
    only if Vancouver yields no results. This handles manuscripts with APA
    in-text citations but Vancouver-formatted reference lists.

    Returns
    -------
    dict[int|str, dict]
        Vancouver: keyed by int reference number.
        APA: keyed by str citation key (e.g. 'Cruz-Almeida2025').
        Each value has keys: ref, doi, title, authors, year, journal, cite_key.
    """
    # Try Vancouver first (works for numbered ref lists regardless of body style)
    refs = _parse_references_vancouver(lines)
    if refs:
        return refs
    # Try unnumbered Vancouver (APA in-text but Vancouver ref list without numbers)
    refs = _parse_references_unnumbered_vancouver(lines)
    if refs:
        return refs
    # Fall back to APA-formatted reference list
    return _parse_references_apa(lines)


def _parse_references_vancouver(lines):
    """Parse numbered Vancouver-style references."""
    ref_start = _find_ref_section_start(lines)
    if ref_start is None:
        return {}

    refs = {}
    for raw in lines[ref_start:]:
        line = raw.strip()
        if not line:
            continue
        if line.startswith('#'):
            break
        m = _VANCOUVER_REF_RE.match(line)
        if not m:
            continue

        num = int(m.group(1))
        text = m.group(2)

        doi_m = _DOI_RE.search(text)
        doi = doi_m.group(1).rstrip('.,;') if doi_m else None

        journal_m = _JOURNAL_RE.search(text)
        journal = journal_m.group(1) if journal_m else None

        # Parse author block, title, and journal from plain-text Vancouver refs.
        # Vancouver layout (authors end with a period after initials):
        #   "Smith AB, Jones CD, Doe EF. Title of the article. Journal Abbrev. 2020;..."
        # The authors block ends at the first ". " that follows an uppercase-initial
        # token (e.g. "EF."). After that, the title runs until the next ". ".
        author_end = _find_authors_end(text)
        if author_end == -1:
            # Fallback: first ". " anywhere
            author_end = text.find('. ')

        if author_end != -1:
            raw_authors = text[:author_end]
            rest = text[author_end + 2:]
        else:
            raw_authors = text
            rest = ''

        title = None
        if rest:
            # First, try italic-journal marker (*Journal*)
            first_star = rest.find('*')
            if first_star > 0:
                title = rest[:first_star].strip().rstrip('.')
            else:
                # Plain text: title ends at next ". " (before the journal name)
                title_end = rest.find('. ')
                if title_end != -1:
                    title = rest[:title_end].strip().rstrip('.')
                else:
                    title = rest.strip().rstrip('.')
        if title is not None and title.startswith('*'):
            title = None
        if title is None and journal is not None:
            title = journal

        year = None
        for year_m in _YEAR_RE.finditer(text):
            candidate = int(year_m.group(1))
            if 1800 <= candidate <= 2100:
                year = candidate
                break
        if ',' in raw_authors:
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
            'cite_key': str(num),
        }
    return refs


def _parse_references_unnumbered_vancouver(lines):
    """Parse unnumbered Vancouver-style references (one per line, no leading number).

    Handles reference lists where each line is a full Vancouver entry like:
        Smith MT, Jones AB. Title. *Journal* 2020;1:2-3. https://doi.org/...
    Assigns sequential numbers starting from 1.
    """
    ref_start = _find_ref_section_start(lines)
    if ref_start is None:
        return {}

    refs = {}
    num = 0
    for raw in lines[ref_start:]:
        line = raw.strip()
        if not line:
            continue
        if line.startswith('#'):
            break
        # Skip lines that don't look like references (too short, or table/note lines)
        if len(line) < 30:
            continue
        # A Vancouver ref line starts with an author name (capital letter)
        # and contains a year and typically a DOI or journal in italics
        if not line[0].isupper():
            continue
        # Must contain a 4-digit year
        year_m = _YEAR_RE.search(line)
        if not year_m:
            continue

        num += 1
        text = line

        doi_m = _DOI_RE.search(text)
        doi = doi_m.group(1).rstrip('.') if doi_m else None

        journal_m = _JOURNAL_RE.search(text)
        journal = journal_m.group(1) if journal_m else None

        title = None
        first_dot_space = text.find('. ')
        if first_dot_space != -1:
            after_authors = text[first_dot_space + 2:]
            first_star = after_authors.find('*')
            if first_star > 0:
                title = after_authors[:first_star].strip().rstrip('.')
            elif first_star == -1:
                title = after_authors.strip().rstrip('.')
        if title is not None and title.startswith('*'):
            title = None
        if title is None and journal is not None:
            title = journal

        year = None
        for ym in _YEAR_RE.finditer(text):
            candidate = int(ym.group(1))
            if 1800 <= candidate <= 2100:
                year = candidate
                break

        if first_dot_space != -1:
            raw_authors = text[:first_dot_space]
        else:
            raw_authors = text
        if ',' in raw_authors:
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
            'cite_key': str(num),
        }

    return refs


def _make_cite_key(authors_str, year):
    """Build a citation key like 'CruzAlmeida2025' from authors and year."""
    # Extract first author last name
    s = authors_str.strip()
    # Handle "Last, F." or "Last, F. M." or "Last F"
    m = re.match(r"([A-Za-z\-']+)", s)
    last = m.group(1) if m else 'Unknown'
    # Remove hyphens for the key
    key_name = last.replace('-', '')
    return f'{key_name}{year}' if year else key_name


def _parse_references_apa(lines):
    """Parse APA-style references (author-date, not numbered).

    Handles formats like:
        Cruz-Almeida, Y., & Valdes-Hernandez, P. A. (2025). Title. *Journal*, ...
        Headache Classification Committee ... (2018). The International ...
    """
    ref_start = _find_ref_section_start(lines)
    if ref_start is None:
        return {}

    refs = {}
    ref_lines = []
    # Collect reference lines, joining continuation lines
    for raw in lines[ref_start:]:
        line = raw.strip()
        if line.startswith('#'):
            break
        if not line:
            continue
        # A new APA ref typically starts with a capital letter or has (Year)
        # Continuation lines are indented or don't match the APA pattern
        if ref_lines and not _APA_REF_RE.match(line):
            # Continuation of previous reference
            ref_lines[-1] += ' ' + line
        else:
            ref_lines.append(line)

    for text in ref_lines:
        m = _APA_REF_RE.match(text)
        if not m:
            continue

        raw_authors = m.group(1).strip()
        year_str = m.group(2)
        rest = m.group(3)

        year = int(year_str[:4])  # handle '2025a' -> 2025

        doi_m = _DOI_RE.search(text)
        doi = doi_m.group(1).rstrip('.') if doi_m else None

        journal_m = _JOURNAL_RE.search(rest)
        journal = journal_m.group(1) if journal_m else None

        # Title: text before first *Journal* or before first period+space
        title = None
        first_star = rest.find('*')
        if first_star > 0:
            title = rest[:first_star].strip().rstrip('.')
        else:
            dot_pos = rest.find('. ')
            if dot_pos > 0:
                title = rest[:dot_pos].strip()
            else:
                title = rest.strip().rstrip('.')

        # Shorten authors
        if ',' in raw_authors:
            first_author = raw_authors.split(',')[0].strip()
            authors = f'{first_author} et al.'
        else:
            authors = raw_authors.strip()

        cite_key = _make_cite_key(raw_authors, year)
        # Handle duplicate keys (e.g., same author, same year)
        base_key = cite_key
        suffix_idx = 0
        while cite_key in refs:
            suffix_idx += 1
            cite_key = f'{base_key}{chr(96 + suffix_idx)}'  # a, b, c...

        refs[cite_key] = {
            'ref': text,
            'doi': doi,
            'title': title,
            'authors': authors,
            'year': year,
            'journal': journal,
            'cite_key': cite_key,
            'raw_authors': raw_authors,  # kept for citation matching
        }
    return refs


# ---------------------------------------------------------------------------
# 5. find_citations
# ---------------------------------------------------------------------------

_CITE_RE = re.compile(r'\[([0-9,\s\u2013\u2014\-\u2010\u2011–—]+)\]')

# APA citation patterns
# Parenthetical: (Smith et al., 2020), (Smith & Jones, 2020; Brown, 2021)
# Narrative: Smith et al. (2020), Smith and Jones (2020)
_APA_PAREN_CITE_RE = re.compile(
    r'\(([^()]*?[A-Z][A-Za-z\-\']+[^()]*?\d{4}[a-z]?(?:\s*;[^()]*?)*)\)'
)
_APA_NARRATIVE_CITE_RE = re.compile(
    r'([A-Z][A-Za-z\-\']+(?:\s+(?:et\s+al\.|and\s+[A-Z][A-Za-z\-\']+|&\s+[A-Z][A-Za-z\-\']+))?)\s*\((\d{4}[a-z]?)\)'
)


def _balance_dollars(text):
    """Ensure balanced $ delimiters in a snippet by trimming truncated edges.

    If the snippet starts or ends mid-LaTeX-expression (odd $ count),
    strip from the boundary inward to the nearest $ to restore balance.
    """
    count = text.count('$')
    if count == 0 or count % 2 == 0:
        return text
    # Odd count — one $ is orphaned from truncation
    first = text.index('$')
    before_first = text[:first]
    # If text before first $ has LaTeX fragments (backslash commands),
    # it's a truncated opening — strip up to and including that $
    if re.search(r'\\[a-zA-Z]', before_first) or re.search(r'[a-z]{1,5}$', before_first.rstrip()):
        text = '...' + text[first + 1:]
    else:
        # Last $ is the orphan — strip it
        last = text.rindex('$')
        text = text[:last] + text[last + 1:]
    # Re-check: if still odd (nested truncation), strip again
    if text.count('$') % 2 == 1:
        # Fallback: strip all $ to prevent rendering issues
        text = text.replace('$', '')
    return text


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


# Candidate sentence-break: punctuation followed by whitespace and a capital.
_SENTENCE_BREAK_RE = re.compile(r'([.!?])(\s+)(?=[A-Z\[\"(])')

# Abbreviations that, when they *precede* a candidate break, indicate the
# period is part of the abbreviation and not an actual sentence terminator.
# We test the ~8 chars before the break position.
_ABBREV_PAT = re.compile(
    r'(?:\b(?:et\s+al|e\.g|i\.e|cf|vs|Dr|Mr|Mrs|Ms|St|Fig|No|Eq|Ref|Refs)|'
    r'\b[A-Z])$',
    re.IGNORECASE,
)

# Markers that signal a sentence continues discussion of the preceding citation
# without introducing a new one. These are matched case-insensitively at or
# near the start of the sentence. "et al." catches "Smith et al. found..."
# patterns; pronouns and demonstratives catch "They found..." / "Their study..."
# / "This analysis..." etc.
_CONTINUATION_MARKERS = (
    r'\bet\s+al\.?',                    # "Smith et al. reported..."
    r'\bthey\b', r'\btheir\b', r'\bthem\b',
    r'\bthe\s+authors?\b',
    r'\bthese\s+authors?\b',
    r'\bthis\s+(?:study|work|paper|analysis|cohort|sample|group|report|'
    r'finding|observation|result|approach|dataset)\b',
    r'\bthat\s+(?:study|work|paper|analysis|cohort|sample|group|report|'
    r'finding|observation|result|approach|dataset)\b',
    r'\bin\s+(?:their|that|this)\s+',   # "In their sample..."
    r'\bthe\s+(?:study|analysis|cohort|sample|authors?)\s+',
)
_CONTINUATION_RE = re.compile(
    r'^[\s"\'\(]*(?:' + '|'.join(_CONTINUATION_MARKERS) + r')',
    re.IGNORECASE,
)

_CITE_ANY_RE = re.compile(
    r'\[\d+(?:\s*[,\u2013\u2014\-]\s*\d+)*(?:\s*,\s*\d+)*\]'
)


def _split_sentences(text):
    """Split paragraph-ish text into sentences, preserving original order.

    Skips candidate splits where the word immediately preceding the period
    is a known abbreviation ("et al.", "e.g.", "Fig.", "Dr.", initials, etc.).
    """
    flat = re.sub(r'\s+', ' ', text).strip()
    if not flat:
        return []
    sentences = []
    last_end = 0
    for m in _SENTENCE_BREAK_RE.finditer(flat):
        # The punctuation is captured in group 1; the position just before
        # it is where the abbreviation test applies.
        before = flat[last_end:m.start()]
        # Look at the last ~8 characters of the preceding run for an abbrev
        tail = before[-8:]
        if _ABBREV_PAT.search(tail):
            continue  # not a real sentence break
        sentence = before + m.group(1)  # include the period
        sentences.append(sentence.strip())
        last_end = m.end()
    tail = flat[last_end:].strip()
    if tail:
        sentences.append(tail)
    return sentences


def _cite_refs_in(sentence):
    """Return the set of reference numbers cited in *sentence* (Vancouver)."""
    nums = set()
    for m in _CITE_ANY_RE.finditer(sentence):
        # reuse _expand_citation to parse numbers and ranges
        body_m = re.match(r'\[(.+)\]', m.group(0))
        if body_m:
            nums |= _expand_citation(body_m.group(1))
    return nums


def _is_continuation(sentence, target_ref):
    """True if *sentence* appears to continue discussion of *target_ref*
    without citing a different reference.
    """
    other_refs = _cite_refs_in(sentence) - {target_ref}
    if other_refs:
        return False
    # Recite of the same ref is a strong continuation signal
    if target_ref in _cite_refs_in(sentence):
        return True
    return bool(_CONTINUATION_RE.search(sentence))


def _build_snippet(line_text, match, sections, line_num, target_ref=None):
    """Build a snippet around a citation match.

    Returns the full sentence containing the match, plus:
      * up to 3 following sentences that continue discussing the same
        reference (author surname + "et al.", pronouns, demonstratives, or
        a repeat of the same citation number; stopping at any citation to
        a different reference or lack of continuation markers); and
      * 1 preceding sentence if it sets up the citation without itself
        citing a different reference.

    The result is trimmed to ~900 chars so the AI verification prompt
    doesn't explode on long expansions.
    """
    sentences = _split_sentences(line_text)
    if not sentences:
        return _balance_dollars(line_text)

    # Locate which sentence contains the citation match
    offsets = []
    pos = 0
    flat = re.sub(r'\s+', ' ', line_text).strip()
    for s in sentences:
        idx = flat.find(s, pos)
        if idx < 0:
            idx = pos
        offsets.append(idx)
        pos = idx + len(s)
    match_text = match.group(0)
    match_sent_idx = 0
    for i, s in enumerate(sentences):
        if match_text in s:
            match_sent_idx = i
            break

    collected = [sentences[match_sent_idx]]

    # Pull 1 preceding sentence for lead-in (only if it does not cite a
    # different reference)
    if match_sent_idx > 0:
        prev = sentences[match_sent_idx - 1]
        if target_ref is None or \
                not (_cite_refs_in(prev) - {target_ref}):
            collected.insert(0, prev)

    # Walk forward through continuation sentences (max 3)
    added = 0
    i = match_sent_idx + 1
    while i < len(sentences) and added < 3:
        s = sentences[i]
        if target_ref is None:
            # Without a target, include the next sentence only if it clearly
            # continues (pronoun/demonstrative) AND does not introduce a new
            # citation.
            if _cite_refs_in(s):
                break
            if not _CONTINUATION_RE.search(s):
                break
        else:
            if not _is_continuation(s, target_ref):
                break
        collected.append(s)
        added += 1
        i += 1

    snippet = ' '.join(collected)
    if len(snippet) > 900:
        snippet = snippet[:897].rstrip() + '...'
    return _balance_dollars(snippet)


def _match_apa_cite_to_refs(author_fragment, year_str, references):
    """Match an APA citation (author fragment + year) to reference keys.

    Handles letter-disambiguated years (``2022a``, ``2022b``) by matching
    the suffix to the Nth same-author same-year entry in the reference list
    (sorted by key).  Works for both int-keyed (Vancouver) and str-keyed
    (APA) reference dicts.

    Returns a list of matching cite_keys.
    """
    year = int(year_str[:4])
    year_suffix = year_str[4:] if len(year_str) > 4 else ''
    author_clean = author_fragment.strip().rstrip(',').strip()
    # Extract the last name (first word)
    m = re.match(r"([A-Za-z\-']+)", author_clean)
    if not m:
        return []
    last_name = m.group(1).lower()

    # Collect all refs matching this author + year
    candidates = []
    for key, ref in references.items():
        if ref.get('year') != year:
            continue
        ref_authors = (ref.get('raw_authors') or ref.get('authors', '')).lower()
        ref_last = re.match(r"([a-z\-']+)", ref_authors)
        if ref_last and ref_last.group(1) == last_name:
            candidates.append(key)

    if not candidates:
        return []

    # Sort candidates by key so a/b/c order is stable
    candidates.sort(key=lambda k: (k if isinstance(k, int) else str(k)))

    if year_suffix:
        # 'a' -> index 0, 'b' -> index 1, etc.
        # First try: check if cite_key string ends with the suffix
        for ck in candidates:
            if str(ck).endswith(year_suffix):
                return [ck]
        # Fall back: use alphabetical index for int-keyed (Vancouver) refs
        suffix_idx = ord(year_suffix[0]) - ord('a')
        if 0 <= suffix_idx < len(candidates):
            return [candidates[suffix_idx]]
        return []

    # No suffix: return all candidates (or single if only one)
    return candidates


def find_citations(lines, sections, references=None):
    """Find all citation instances in the manuscript body.

    Auto-detects Vancouver vs APA based on citation style.
    For APA, *references* dict is needed to match citations to keys.

    In Vancouver mode, also scans for inline author-date mentions
    (e.g. ``Smith et al. (2020)``) and matches them to references,
    so manually typed citations are not missed.

    Returns
    -------
    dict[int|str, list[dict]]
        Keyed by reference number (Vancouver) or cite_key (APA).
        Each value is a list of dicts with keys: section, snippet, line.
    """
    style = detect_citation_style(lines)
    if style == 'apa' and references is not None:
        return _find_citations_apa(lines, sections, references)

    citations = _find_citations_vancouver(lines, sections)

    # Also pick up inline author-date mentions in Vancouver mode
    if references:
        apa_cites = _find_citations_apa(lines, sections, references)
        for key, instances in apa_cites.items():
            for inst in instances:
                # Deduplicate: skip if same ref on same line already found
                existing = citations.get(key, [])
                if any(e['line'] == inst['line'] for e in existing):
                    continue
                citations.setdefault(key, []).append(inst)

    return citations


def _find_citations_vancouver(lines, sections):
    """Find Vancouver-style [N] citations."""
    ref_line = None
    for sec in sections:
        if sec['heading'].lower() == 'references':
            ref_line = sec['line']
            break

    citations = {}
    seen = set()

    for i, raw in enumerate(lines, start=1):
        if ref_line is not None and i >= ref_line:
            break

        line_text = raw.rstrip('\n')

        for m in _CITE_RE.finditer(line_text):
            ref_nums = _expand_citation(m.group(1))
            sec_name = section_at_line(sections, i)

            for n in ref_nums:
                key = (n, i, sec_name)
                if key in seen:
                    continue
                seen.add(key)
                # Build a per-reference snippet so continuation logic can
                # treat the target reference specially (repeat cites of the
                # same ref extend the window; cites to other refs close it).
                snippet = _build_snippet(line_text, m, sections, i,
                                         target_ref=n)
                citations.setdefault(n, []).append({
                    'section': sec_name,
                    'snippet': snippet,
                    'line': i,
                })

    return citations


def _find_citations_apa(lines, sections, references):
    """Find APA-style (Author, Year) and Author (Year) citations."""
    ref_line = None
    for sec in sections:
        if sec['heading'].lower() == 'references':
            ref_line = sec['line']
            break

    citations = {}
    seen = set()

    for i, raw in enumerate(lines, start=1):
        if ref_line is not None and i >= ref_line:
            break

        line_text = raw.rstrip('\n')
        sec_name = section_at_line(sections, i)

        # Parenthetical: (Smith et al., 2020; Jones & Brown, 2019)
        for m in _APA_PAREN_CITE_RE.finditer(line_text):
            inner = m.group(1)
            snippet = _build_snippet(line_text, m, sections, i)
            # Split on semicolons for multiple citations
            for part in inner.split(';'):
                part = part.strip()
                # Handle compressed years: "Author et al., 2025, 2024, 2023"
                # Find ALL years in this part, then extract the author from
                # the text before the first year.
                all_years = list(re.finditer(r'(\d{4}[a-z]?)', part))
                if not all_years:
                    continue
                author_part = part[:all_years[0].start()].rstrip(',').strip()
                for ym in all_years:
                    matched_keys = _match_apa_cite_to_refs(
                        author_part, ym.group(1), references
                    )
                    for ck in matched_keys:
                        dedup_key = (ck, i, sec_name)
                        if dedup_key in seen:
                            continue
                        seen.add(dedup_key)
                        citations.setdefault(ck, []).append({
                            'section': sec_name,
                            'snippet': snippet,
                            'line': i,
                        })

        # Narrative: Smith et al. (2020), Smith and Jones (2020)
        for m in _APA_NARRATIVE_CITE_RE.finditer(line_text):
            author_part = m.group(1)
            year_str = m.group(2)
            snippet = _build_snippet(line_text, m, sections, i)
            matched_keys = _match_apa_cite_to_refs(
                author_part, year_str, references
            )
            for ck in matched_keys:
                dedup_key = (ck, i, sec_name)
                if dedup_key in seen:
                    continue
                seen.add(dedup_key)
                citations.setdefault(ck, []).append({
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
    raw_citations = find_citations(lines, sections, references=references)
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

        citation_style = detect_citation_style(lines)
        lit_dir = Path(literature_dir)
        if lit_dir.is_dir():
            matched_pdfs, unmatched_pdfs, warnings = match_and_rename(
                lit_dir, references, style=citation_style)

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
