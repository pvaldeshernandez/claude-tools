"""Process a folder of PDFs: extract text and match to references."""

import os
import re
import sys


def process(pdfs_folder: str, references: dict) -> dict:
    """Extract text from PDFs and match them to references.

    Args:
        pdfs_folder: Path to a folder containing PDF files.
        references: dict of ref_num -> ref_dict (from manuscript_parser).

    Returns:
        dict mapping ref_num -> markdown text of the PDF, plus "_unmatched" -> list of unmatched filenames.
    """
    if not os.path.isdir(pdfs_folder):
        return {"_unmatched": [], "_error": f"Directory not found: {pdfs_folder}"}

    pdf_files = [f for f in os.listdir(pdfs_folder) if f.lower().endswith(".pdf")]
    if not pdf_files:
        return {"_unmatched": []}

    results = {}
    unmatched = []

    for filename in sorted(pdf_files):
        filepath = os.path.join(pdfs_folder, filename)
        text = _extract_text(filepath)
        if text is None:
            unmatched.append(filename)
            continue

        ref_num = _match_pdf_to_ref(filename, text, references)
        if ref_num is not None:
            results[ref_num] = text
        else:
            unmatched.append(filename)

    results["_unmatched"] = unmatched
    return results


def _extract_text(pdf_path: str) -> str:
    """Extract text from a PDF file.

    Tries pymupdf4llm first (better markdown output), falls back to pymupdf plain text.
    """
    # Try pymupdf4llm first
    try:
        import pymupdf4llm
        text = pymupdf4llm.to_markdown(pdf_path)
        if text and len(text.strip()) > 100:
            return text
    except ImportError:
        pass
    except Exception:
        pass

    # Fallback to pymupdf plain text
    try:
        import pymupdf
        doc = pymupdf.open(pdf_path)
        pages = []
        for page in doc:
            pages.append(page.get_text())
        doc.close()
        text = "\n\n".join(pages)
        if text and len(text.strip()) > 100:
            return text
    except ImportError:
        print("Warning: pymupdf not installed, PDF processing disabled.", file=sys.stderr)
    except Exception:
        pass

    return None


def _match_pdf_to_ref(filename: str, text: str, references: dict) -> int:
    """Match a PDF file to a reference using a cascade of strategies.

    1. DOI in filename (slashes replaced with underscores or hyphens)
    2. First-author lastname + year in filename
    3. Title word overlap (Jaccard > 0.4)
    """
    name_lower = filename.lower().replace(".pdf", "")

    # Strategy 1: DOI match
    for ref_num, ref in references.items():
        doi = ref.get("doi", "")
        if not doi:
            continue
        # Normalize DOI for filename comparison
        doi_normalized = doi.lower().replace("/", "_").replace("/", "-")
        doi_normalized2 = doi.lower().replace("/", "-")
        if doi_normalized in name_lower or doi_normalized2 in name_lower:
            return ref_num

    # Strategy 2: First author lastname + year in filename
    for ref_num, ref in references.items():
        authors = ref.get("authors", "")
        year = ref.get("year", 0)
        if not authors or not year:
            continue
        # Extract first author's last name
        first_author = authors.split(" et al")[0].split(",")[0].strip()
        # Take just the surname (last word if multiple words)
        surname = first_author.split()[-1].lower() if first_author else ""
        if surname and len(surname) > 2 and surname in name_lower and str(year) in name_lower:
            return ref_num

    # Strategy 3: Title word overlap (using text content, not filename)
    best_ref = None
    best_score = 0.0
    stopwords = {"the", "a", "an", "of", "in", "to", "and", "or", "for", "with", "on", "is", "are", "was", "were", "by", "from", "at", "as", "this", "that", "its", "it"}

    for ref_num, ref in references.items():
        title = ref.get("title", "")
        if not title:
            continue
        title_words = set(w.lower() for w in re.findall(r"\w+", title) if len(w) > 2) - stopwords
        if not title_words:
            continue

        # Check first ~2000 chars of PDF text for title words
        text_start = text[:2000].lower()
        text_words = set(re.findall(r"\w+", text_start)) - stopwords

        intersection = title_words & text_words
        union = title_words | text_words
        if not union:
            continue
        jaccard = len(intersection) / len(title_words)  # fraction of title words found
        if jaccard > best_score and jaccard > 0.6:
            best_score = jaccard
            best_ref = ref_num

    return best_ref
