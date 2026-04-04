"""Match PDFs in a literature folder to numbered manuscript references and rename them.

Public API:
    match_and_rename(literature_dir, references)
        -> (matched, unmatched, warnings)

Dependencies: fitz (pymupdf), difflib, re, pathlib
"""

import difflib
import re
from pathlib import Path

import fitz  # pymupdf

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Vancouver: "01_Author-Title.pdf"  APA: "Author-2020-Title.pdf"
_ALREADY_NAMED_RE = re.compile(r"^(\d+)_.*\.pdf$", re.IGNORECASE)
_APA_NAMED_RE = re.compile(r"^([A-Za-z\-']+)-(\d{4})-.*\.pdf$", re.IGNORECASE)
_DOI_RE = re.compile(r"(10\.\d{4,9}/[^\s]+)")
_BOILERPLATE_UPPER = {
    "ORIGINAL ARTICLE",
    "RESEARCH PAPER",
    "RESEARCH ARTICLE",
    "REVIEW ARTICLE",
    "REVIEW",
    "BRIEF COMMUNICATION",
    "SHORT COMMUNICATION",
    "LETTER TO THE EDITOR",
    "EDITORIAL",
    "COMMENTARY",
    "CORRESPONDENCE",
    "ORIGINAL RESEARCH",
    "CLINICAL ARTICLE",
    "FULL PAPER",
    "REPORT",
}
_GENERIC_TITLE_FRAGMENTS = {
    "microsoft word",
    "untitled",
    "document",
    "acrobat",
    "pdf",
}
_STOP_WORDS = {
    "a", "an", "the", "of", "in", "on", "at", "to", "for", "and", "or",
    "is", "are", "was", "were", "with", "by", "from", "as", "its", "this",
    "that", "it", "be", "do", "does", "not", "but", "if", "no", "so",
    "how", "what", "when", "where", "which", "who", "why",
}


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _clean_doi(doi_str: str) -> str:
    """Strip trailing punctuation that commonly leaks from regex matches."""
    return doi_str.rstrip(".,;:)]}\"'")


def _is_generic_title(title: str) -> bool:
    """Return True if *title* looks like metadata junk rather than a real title."""
    if not title or len(title.strip()) < 5:
        return True
    low = title.lower().strip()
    for frag in _GENERIC_TITLE_FRAGMENTS:
        if frag in low:
            return True
    return False


def _scan_already_named(literature_dir: Path) -> dict:
    """Return {ref_num: Path} for PDFs already named ``<N>_<rest>.pdf``."""
    result = {}
    for p in literature_dir.glob("*.pdf"):
        m = _ALREADY_NAMED_RE.match(p.name)
        if m:
            num = int(m.group(1))
            result[num] = p
    return result


def _scan_already_named_apa(literature_dir: Path, references: dict) -> dict:
    """Return {cite_key: Path} for PDFs already named ``Author-Year-Title.pdf``.

    Matches by checking if the filename's author+year correspond to a reference.
    """
    result = {}
    for p in literature_dir.glob("*.pdf"):
        m = _APA_NAMED_RE.match(p.name)
        if m:
            file_author = m.group(1).lower()
            file_year = int(m.group(2))
            for key, ref in references.items():
                ref_author = _make_author_last(ref.get("authors", "")).lower()
                if ref_author == file_author and ref.get("year") == file_year:
                    result[key] = p
                    break
    return result


def _extract_pdf_metadata(pdf_path: Path) -> dict:
    """Extract DOI and title from a PDF.

    Returns ``{"doi": str|None, "title": str|None}``.
    """
    doi = None
    title = None

    try:
        doc = fitz.open(str(pdf_path))
    except Exception:
        return {"doi": None, "title": None}

    # --- DOI: search document metadata first, then page text (first 3 pages)
    meta = doc.metadata or {}
    for field in ("subject", "keywords", "title", "author"):
        val = meta.get(field, "") or ""
        m = _DOI_RE.search(val)
        if m:
            doi = _clean_doi(m.group(1))
            break

    page_texts = []
    for page_idx in range(min(3, len(doc))):
        try:
            txt = doc[page_idx].get_text()
            page_texts.append(txt)
        except Exception:
            page_texts.append("")

    if doi is None:
        for txt in page_texts:
            m = _DOI_RE.search(txt)
            if m:
                doi = _clean_doi(m.group(1))
                break

    # --- Title: metadata first, then heuristic from page 1 text
    meta_title = (meta.get("title") or "").strip()
    if meta_title and not _is_generic_title(meta_title):
        title = meta_title
    else:
        # Heuristic: first text block on page 1 that looks like a title
        if page_texts:
            for line in page_texts[0].splitlines():
                line = line.strip()
                if not line:
                    continue
                if len(line) < 20 or len(line) > 300:
                    continue
                if line.upper() in _BOILERPLATE_UPPER:
                    continue
                title = line
                break

    doc.close()
    return {"doi": doi, "title": title}


def _make_short_title(full_title: str, max_words: int = 4) -> str:
    """Create a CamelCase short title from significant content words."""
    words = re.findall(r"[A-Za-z]+", full_title)
    significant = [w for w in words if w.lower() not in _STOP_WORDS]
    chosen = significant[:max_words] if significant else words[:max_words]
    return "".join(w.capitalize() for w in chosen)


def _make_author_last(authors_str: str) -> str:
    """Extract the first author's last name from an authors string."""
    # Typical formats: "Smith AJ et al.", "Smith, A.J., Jones, B.C."
    # Take the first word-like token before any comma or "et al."
    s = authors_str.strip()
    # Remove leading numbers/brackets sometimes present
    s = re.sub(r"^\[?\d+\]?\s*", "", s)
    m = re.match(r"([A-Za-z\-']+)", s)
    if m:
        return m.group(1)
    return "Unknown"


def _rename_pdf(old_path: Path, ref_key, references: dict, style: str = "vancouver") -> Path:
    """Rename a PDF based on citation style.

    Vancouver: ``<N>_<AuthorLastName>-<ShortTitle>.pdf``
    APA:       ``<AuthorLastName>-<Year>-<ShortTitle>.pdf``

    Returns the new path.
    """
    ref = references[ref_key]
    author = _make_author_last(ref.get("authors", "Unknown"))
    short_title = _make_short_title(ref.get("title", ""))
    year = ref.get("year", "")

    if style == "apa":
        new_name = f"{author}-{year}-{short_title}.pdf"
    else:
        new_name = f"{ref_key}_{author}-{short_title}.pdf"

    new_path = old_path.parent / new_name
    if new_path == old_path:
        return old_path
    # Avoid overwriting an existing file
    if new_path.exists():
        slug = new_path.stem
        for i in range(2, 100):
            candidate = old_path.parent / f"{slug}_{i}.pdf"
            if not candidate.exists():
                new_path = candidate
                break
    old_path.rename(new_path)
    return new_path


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def match_and_rename(literature_dir, references, style="vancouver"):
    """Match PDFs to manuscript references and rename them.

    Args:
        literature_dir: Path (or str) to folder containing PDFs.
        references: dict ``{ref_key: {ref, doi, title, authors, year, journal}}``.
            Keys are int (Vancouver) or str cite_keys (APA).
        style: 'vancouver' or 'apa'. Controls naming convention.

    Returns:
        matched: dict ``{ref_key: Path}`` -- matched PDFs (after rename).
        unmatched: list of ``{path, extracted_title, extracted_doi}`` -- couldn't match.
        warnings: list of str -- issues encountered.
    """
    literature_dir = Path(literature_dir)
    matched = {}
    unmatched = []
    warnings = []

    if not literature_dir.is_dir():
        warnings.append(f"Literature directory not found: {literature_dir}")
        return matched, unmatched, warnings

    # ------------------------------------------------------------------
    # Step 1: Pick up files that are already named
    # Vancouver: N_Author-Title.pdf    APA: Author-Year-Title.pdf
    # ------------------------------------------------------------------
    if style == "apa":
        already = _scan_already_named_apa(literature_dir, references)
    else:
        already = _scan_already_named(literature_dir)
    for key, path in already.items():
        if key in references:
            matched[key] = path
        else:
            warnings.append(
                f"File '{path.name}' matches naming convention but no reference '{key}' exists"
            )

    matched_nums = set(matched.keys())

    # ------------------------------------------------------------------
    # Step 2: Build lookup structures from references
    # ------------------------------------------------------------------
    doi_to_num = {}
    title_to_num = {}
    for num, ref in references.items():
        if num in matched_nums:
            continue
        doi = (ref.get("doi") or "").strip().lower()
        if doi:
            doi_to_num[doi] = num
        title = (ref.get("title") or "").strip()
        if title:
            title_to_num[title.lower()] = num

    # ------------------------------------------------------------------
    # Step 3: Process unnamed PDFs
    # ------------------------------------------------------------------
    unnamed_pdfs = [
        p for p in sorted(literature_dir.glob("*.pdf"))
        if not _ALREADY_NAMED_RE.match(p.name)
    ]

    for pdf_path in unnamed_pdfs:
        meta = _extract_pdf_metadata(pdf_path)
        pdf_doi = (_clean_doi(meta["doi"]).lower() if meta["doi"] else None)
        pdf_title = meta["title"]

        ref_num = None

        # Try DOI exact match (case-insensitive)
        if pdf_doi and pdf_doi in doi_to_num:
            ref_num = doi_to_num.pop(pdf_doi)
        elif pdf_doi:
            # Try partial DOI match (some DOIs have version suffixes)
            for ref_doi, rnum in list(doi_to_num.items()):
                if pdf_doi.startswith(ref_doi) or ref_doi.startswith(pdf_doi):
                    ref_num = rnum
                    del doi_to_num[ref_doi]
                    break

        # Try title fuzzy match
        if ref_num is None and pdf_title:
            best_ratio = 0.0
            best_num = None
            pdf_title_lower = pdf_title.lower()
            for ref_title_lower, rnum in title_to_num.items():
                ratio = difflib.SequenceMatcher(
                    None, pdf_title_lower, ref_title_lower
                ).ratio()
                if ratio > best_ratio:
                    best_ratio = ratio
                    best_num = rnum
            if best_ratio >= 0.75 and best_num is not None:
                ref_num = best_num
                # Remove from lookup to prevent double-matching
                for k, v in list(title_to_num.items()):
                    if v == ref_num:
                        del title_to_num[k]
                        break
                # Also remove from doi_to_num if present
                for k, v in list(doi_to_num.items()):
                    if v == ref_num:
                        del doi_to_num[k]
                        break

        if ref_num is not None:
            new_path = _rename_pdf(pdf_path, ref_num, references, style=style)
            matched[ref_num] = new_path
            matched_nums.add(ref_num)
        else:
            unmatched.append({
                "path": pdf_path,
                "extracted_title": pdf_title,
                "extracted_doi": pdf_doi,
            })

    return matched, unmatched, warnings
