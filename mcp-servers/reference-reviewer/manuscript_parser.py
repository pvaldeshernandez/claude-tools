"""Parse any markdown manuscript to extract references and citations."""

import re
from bisect import bisect_right


def parse(manuscript_path: str) -> dict:
    """Main entry: parse a manuscript and return references, citations, sections, stats.

    Args:
        manuscript_path: Path to a markdown manuscript file.

    Returns:
        dict with keys: references, citations, sections, stats
    """
    with open(manuscript_path, "r") as f:
        lines = [line.rstrip("\n") for line in f.readlines()]

    sections = _detect_sections(lines)
    references = _parse_references(lines)
    citations = _extract_citations(lines, sections)

    total_cits = sum(len(v) for v in citations.values())
    cited_refs = sum(1 for n in references if n in citations and len(citations[n]) > 0)

    stats = {
        "total_references": len(references),
        "total_citations": total_cits,
        "cited_references": cited_refs,
        "uncited_references": len(references) - cited_refs,
        "uncited_list": [n for n in sorted(references) if n not in citations or len(citations.get(n, [])) == 0],
    }

    return {
        "references": references,
        "citations": citations,
        "sections": sections,
        "stats": stats,
    }


def _detect_sections(lines: list) -> list:
    """Build (start_line, end_line, name) intervals from markdown headers.

    Uses 1-indexed line numbers. Each section extends from its header to the
    line before the next header of the same or higher level.
    """
    sections = []
    header_positions = []  # (line_num_1indexed, level, name)

    for i, line in enumerate(lines):
        stripped = line.strip()
        m = re.match(r"^(#{1,3})\s+(.+)$", stripped)
        if m:
            level = len(m.group(1))
            name = m.group(2).strip()
            # Skip the References header and everything after
            if name.lower() == "references":
                break
            header_positions.append((i + 1, level, name))

    # Build intervals
    for idx, (line_num, level, name) in enumerate(header_positions):
        if idx + 1 < len(header_positions):
            end = header_positions[idx + 1][0] - 1
        else:
            # Extend to end of file (or References section)
            end = len(lines)
        sections.append((line_num, end, name))

    return sections


def _get_section_for_line(line_num: int, sections: list) -> str:
    """Find which section a line belongs to using bisect lookup."""
    if not sections:
        return "Other"

    # Extract start positions for bisect
    starts = [s[0] for s in sections]
    idx = bisect_right(starts, line_num) - 1

    if idx < 0:
        return "Other"

    start, end, name = sections[idx]
    if start <= line_num <= end:
        return name
    return "Other"


def _classify_section(section_name: str) -> str:
    """Classify a section name into a broad category for filtering.

    Returns one of: Introduction, Methods, Results, Discussion, Other
    """
    lower = section_name.lower()

    if "introduction" in lower or "background" in lower:
        return "Introduction"
    if any(kw in lower for kw in [
        "method", "participant", "subject", "sample",
        "acquisition", "processing", "analysis", "statistical",
        "procedure", "measure", "variable", "design",
        "freesurfer", "mri", "imaging",
    ]):
        return "Methods"
    if "result" in lower:
        return "Results"
    if "discussion" in lower or "conclusion" in lower or "limitation" in lower:
        return "Discussion"
    return "Other"


def _parse_references(lines: list) -> dict:
    """Find the # References header and parse N. Author... entries."""
    refs = {}
    in_refs = False
    current_ref_num = None
    current_ref_text = ""

    for line in lines:
        stripped = line.strip()
        if stripped.lower() == "# references":
            in_refs = True
            continue
        if not in_refs:
            continue
        if not stripped:
            # Blank line in references section — finish any accumulating ref
            if current_ref_num is not None:
                refs[current_ref_num] = _parse_single_reference(current_ref_text, current_ref_num)
                current_ref_num = None
                current_ref_text = ""
            continue

        # Check for a new numbered reference start
        m = re.match(r"^(\d+)\.\s+(.+)$", stripped)
        if m:
            # Save previous ref if any
            if current_ref_num is not None:
                refs[current_ref_num] = _parse_single_reference(current_ref_text, current_ref_num)
            current_ref_num = int(m.group(1))
            current_ref_text = m.group(2)
        elif current_ref_num is not None:
            # Continuation line
            current_ref_text += " " + stripped

    # Don't forget the last reference
    if current_ref_num is not None:
        refs[current_ref_num] = _parse_single_reference(current_ref_text, current_ref_num)

    return refs


def _parse_single_reference(ref_text: str, ref_num: int) -> dict:
    """Parse a single reference line into components.

    Handles Vancouver-style references: Authors. Title. Journal. Year;Vol:Pages. doi:...
    Also supports https://doi.org/... format.
    """
    # Extract DOI — support both doi:10.xxx and https://doi.org/10.xxx
    doi = ""
    doi_match = re.search(r"doi:(10\.\S+)", ref_text)
    if doi_match:
        doi = doi_match.group(1)
    else:
        doi_match = re.search(r"https?://doi\.org/(10\.\S+)", ref_text)
        if doi_match:
            doi = doi_match.group(1)
    # Clean trailing punctuation from DOI
    doi = doi.rstrip(".,;")

    # Extract year
    year_match = re.search(r"[\.\s](\d{4})[;,]", ref_text)
    year = int(year_match.group(1)) if year_match else 0

    # Extract journal
    journal = ""
    year_vol_match = re.search(r"\.\s+(\d{4})[;,]", ref_text)
    if year_vol_match:
        before_year = ref_text[: year_vol_match.start()]
        last_sep = max(before_year.rfind(". "), before_year.rfind("? "))
        if last_sep >= 0:
            journal = before_year[last_sep + 2 :].strip()
        else:
            journal = before_year.strip()

    # Extract title and authors
    title = ""
    authors_text = ""

    year_pos_match = re.search(r"\.\s+\d{4}[;,]", ref_text)
    if year_pos_match and journal:
        journal_start = ref_text.rfind(journal, 0, year_pos_match.start() + 1)
        if journal_start > 0:
            before_journal = ref_text[:journal_start].rstrip(". ")
            best_split = -1
            for m in re.finditer(r"(?<=[A-Z])\.\s+", before_journal):
                pos = m.end()
                remaining = before_journal[pos:]
                author_continuation = re.match(
                    r"^[A-Z][a-z]+(?:\s+[A-Z](?:[A-Z\-])*)?(?:\s*,|\s*\()",
                    remaining,
                )
                if author_continuation:
                    continue
                best_split = pos

            if best_split > 0:
                authors_text = before_journal[:best_split].rstrip(". ").strip()
                title = before_journal[best_split:].strip()
            else:
                parts = before_journal.split(". ", 1)
                if len(parts) >= 2:
                    authors_text = parts[0].strip()
                    title = parts[1].strip()
                else:
                    authors_text = before_journal
                    title = before_journal
    else:
        parts = ref_text.split(". ")
        if len(parts) >= 2:
            authors_text = parts[0].strip()
            title = parts[1].strip()

    title = title.rstrip(".")

    if not authors_text:
        parts = ref_text.split(". ", 1)
        authors_text = parts[0] if parts else ref_text

    first_author = authors_text.split(",")[0].strip()
    if "," in authors_text or "et al" in authors_text:
        authors = f"{first_author} et al."
    else:
        authors = first_author

    # Clean ref text for display
    ref_display = re.sub(r"\s*doi:\S+", "", ref_text).strip()
    ref_display = re.sub(r"\s*https?://doi\.org/\S+", "", ref_display).strip()
    if ref_display.endswith("."):
        ref_display = ref_display[:-1]

    return {
        "ref": ref_display,
        "doi": doi,
        "title": title,
        "authors": authors,
        "year": year,
        "journal": journal,
    }


def _extract_citations(lines: list, sections: list) -> dict:
    """Scan for [N] and [N,M,...] brackets with context."""
    citations = {}

    for i, line in enumerate(lines):
        line_num = i + 1
        stripped = line.strip()

        # Skip empty, headers, tables, figure captions
        if not stripped or stripped.startswith("#") or stripped.startswith("|"):
            continue
        if stripped.startswith("![") or stripped.startswith("**Table"):
            continue
        if stripped.startswith("Figure ") and len(stripped) > 7 and stripped[7:8].isdigit():
            continue

        section = _get_section_for_line(line_num, sections)
        if section == "Other":
            # Check if it falls in a classified broad section
            pass  # Keep "Other" — will still be included

        # Skip lines after References header
        if stripped.lower() == "# references":
            break

        broad_section = _classify_section(section)

        bracket_pattern = re.compile(r"\[(\d+(?:,\s*\d+)*)\]")
        for match in bracket_pattern.finditer(stripped):
            ref_nums_str = match.group(1)
            ref_nums = [int(n.strip()) for n in ref_nums_str.split(",")]
            snippet = _extract_snippet(stripped, match.start(), match.end())

            for ref_num in ref_nums:
                if ref_num not in citations:
                    citations[ref_num] = []
                citations[ref_num].append(
                    {
                        "section": section,
                        "broad_section": broad_section,
                        "snippet": snippet,
                        "line": line_num,
                    }
                )

    return citations


def _extract_snippet(text: str, bracket_start: int, bracket_end: int) -> str:
    """Extract ~1 sentence around a citation bracket."""
    start = bracket_start
    while start > 0:
        if text[start - 1] in ".!?" and start >= 2 and text[start - 2] != ".":
            preceding = text[max(0, start - 6) : start]
            if "al." in preceding or "vs." in preceding or "e.g." in preceding or "i.e." in preceding:
                start -= 1
                continue
            break
        start -= 1

    end = bracket_end
    while end < len(text):
        if text[end] in ".!?":
            if "al." in text[max(0, end - 3) : end + 1]:
                end += 1
                continue
            end += 1
            break
        end += 1

    snippet = text[start:end].strip()
    snippet = re.sub(r"^[.\s]+", "", snippet)
    return snippet
