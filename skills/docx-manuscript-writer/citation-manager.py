#!/usr/bin/env python3
"""
Scientific Writer — Citation Manager
Search and format references from BibTeX files or Mendeley exports.

Usage:
    # Search a .bib file
    python3.13 citation-manager.py search library.bib "pain sleep gait"

    # Search with filters
    python3.13 citation-manager.py search library.bib "processing speed" --author "Smith" --year-min 2015

    # Format references for a citation style
    python3.13 citation-manager.py format library.bib key1,key2,key3 --style vancouver

    # List all entries
    python3.13 citation-manager.py list library.bib

    # Show details of a specific entry
    python3.13 citation-manager.py show library.bib entry_key
"""
import sys
import os
import argparse
import re

import bibtexparser
from bibtexparser.bparser import BibTexParser
from bibtexparser.customization import convert_to_unicode


def load_bib(bib_path):
    """Load and parse a BibTeX file."""
    with open(bib_path) as f:
        parser = BibTexParser(common_strings=True)
        parser.customization = convert_to_unicode
        return bibtexparser.load(f, parser=parser)


def clean_text(text):
    """Remove LaTeX artifacts from text."""
    text = re.sub(r'[{}]', '', text)
    text = re.sub(r'\\textendash\s*', '–', text)
    text = re.sub(r'\\textemdash\s*', '—', text)
    text = re.sub(r'\\&', '&', text)
    text = re.sub(r'~', ' ', text)
    text = re.sub(r'\\[a-zA-Z]+\s*', '', text)
    return text.strip()


def match_score(entry, query_terms, author_filter=None,
                year_min=None, year_max=None):
    """Score how well an entry matches the search query.

    Returns 0 if filtered out, positive int for match quality.
    """
    # Apply filters first
    if author_filter:
        author_field = clean_text(entry.get('author', '')).lower()
        if author_filter.lower() not in author_field:
            return 0

    year_str = entry.get('year', '')
    if year_str:
        try:
            year = int(year_str)
            if year_min and year < year_min:
                return 0
            if year_max and year > year_max:
                return 0
        except ValueError:
            pass

    # Score based on query terms
    searchable = ' '.join([
        clean_text(entry.get('title', '')),
        clean_text(entry.get('abstract', '')),
        clean_text(entry.get('keywords', '')),
    ]).lower()

    score = 0
    for term in query_terms:
        term_lower = term.lower()
        # Title matches worth more
        if term_lower in clean_text(entry.get('title', '')).lower():
            score += 3
        if term_lower in searchable:
            score += 1

    return score


def format_entry_short(entry):
    """Format an entry as a one-line summary."""
    author = clean_text(entry.get('author', 'Unknown'))
    # Shorten to first author + et al.
    authors = author.split(' and ')
    if len(authors) > 2:
        author_short = f"{authors[0].strip()} et al."
    elif len(authors) == 2:
        author_short = f"{authors[0].strip()} and {authors[1].strip()}"
    else:
        author_short = authors[0].strip()

    year = entry.get('year', '?')
    title = clean_text(entry.get('title', 'Untitled'))
    journal = clean_text(entry.get('journal', entry.get('booktitle', '')))
    key = entry.get('ID', '?')

    return f"[{key}] {author_short} ({year}). {title}. {journal}"


def format_entry_detail(entry):
    """Format an entry with full details."""
    lines = []
    key = entry.get('ID', '?')
    lines.append(f"Key: {key}")
    lines.append(f"Type: {entry.get('ENTRYTYPE', '?')}")
    lines.append(f"Title: {clean_text(entry.get('title', 'Untitled'))}")
    lines.append(f"Authors: {clean_text(entry.get('author', 'Unknown'))}")
    lines.append(f"Year: {entry.get('year', '?')}")
    lines.append(f"Journal: {clean_text(entry.get('journal', entry.get('booktitle', '?')))}")
    if entry.get('volume'):
        vol = entry['volume']
        pages = entry.get('pages', '')
        lines.append(f"Volume: {vol}" + (f", Pages: {pages}" if pages else ''))
    if entry.get('doi'):
        lines.append(f"DOI: {entry['doi']}")
    if entry.get('abstract'):
        abstract = clean_text(entry['abstract'])
        if len(abstract) > 300:
            abstract = abstract[:300] + '...'
        lines.append(f"Abstract: {abstract}")
    if entry.get('keywords'):
        lines.append(f"Keywords: {clean_text(entry['keywords'])}")
    return '\n'.join(lines)


def format_reference_vancouver(entry, number=None):
    """Format a reference in Vancouver/AMA numbered style."""
    author = clean_text(entry.get('author', 'Unknown'))
    authors = [a.strip() for a in author.split(' and ')]
    # Vancouver: list all authors, last name first initial
    author_str = ', '.join(authors)

    title = clean_text(entry.get('title', 'Untitled'))
    # Remove trailing period from title if present
    title = title.rstrip('.')

    journal = clean_text(entry.get('journal', entry.get('booktitle', '')))
    year = entry.get('year', '?')
    volume = entry.get('volume', '')
    pages = entry.get('pages', '').replace('--', '-')
    doi = entry.get('doi', '')

    ref = f"{author_str}. {title}. {journal}. {year}"
    if volume:
        ref += f";{volume}"
        if pages:
            ref += f":{pages}"
    ref += '.'
    if doi:
        ref += f" doi:{doi}"

    if number is not None:
        ref = f"{number}. {ref}"
    return ref


def format_reference_apa(entry, number=None):
    """Format a reference in APA author-year style."""
    author = clean_text(entry.get('author', 'Unknown'))
    authors = [a.strip() for a in author.split(' and ')]
    if len(authors) > 7:
        author_str = ', '.join(authors[:6]) + ', ... ' + authors[-1]
    else:
        if len(authors) > 1:
            author_str = ', '.join(authors[:-1]) + ', & ' + authors[-1]
        else:
            author_str = authors[0]

    title = clean_text(entry.get('title', 'Untitled'))
    journal = clean_text(entry.get('journal', entry.get('booktitle', '')))
    year = entry.get('year', '?')
    volume = entry.get('volume', '')
    pages = entry.get('pages', '').replace('--', '-')
    doi = entry.get('doi', '')

    ref = f"{author_str} ({year}). {title}. {journal}"
    if volume:
        ref += f", {volume}"
        if pages:
            ref += f", {pages}"
    ref += '.'
    if doi:
        ref += f" https://doi.org/{doi}"

    if number is not None:
        ref = f"{number}. {ref}"
    return ref


FORMATTERS = {
    'vancouver': format_reference_vancouver,
    'vancouver-numbered': format_reference_vancouver,
    'apa': format_reference_apa,
    'numbered-superscript': format_reference_vancouver,
}


def cmd_search(args):
    bib = load_bib(args.bib_file)
    query_terms = args.query.split()

    results = []
    for entry in bib.entries:
        score = match_score(entry, query_terms,
                            author_filter=args.author,
                            year_min=args.year_min,
                            year_max=args.year_max)
        if score > 0:
            results.append((score, entry))

    results.sort(key=lambda x: -x[0])
    max_results = args.max_results or 20

    print(f"Found {len(results)} matches for \"{args.query}\"" +
          (f" (showing top {max_results})" if len(results) > max_results else ""))
    print()
    for score, entry in results[:max_results]:
        print(f"  [{score}] {format_entry_short(entry)}")


def cmd_list(args):
    bib = load_bib(args.bib_file)
    print(f"Library: {args.bib_file} ({len(bib.entries)} entries)")
    print()
    for entry in bib.entries:
        print(f"  {format_entry_short(entry)}")


def cmd_show(args):
    bib = load_bib(args.bib_file)
    for entry in bib.entries:
        if entry.get('ID') == args.key:
            print(format_entry_detail(entry))
            return
    print(f"Entry '{args.key}' not found.")
    sys.exit(1)


def cmd_format(args):
    bib = load_bib(args.bib_file)
    keys = [k.strip() for k in args.keys.split(',')]
    style = args.style or 'vancouver'
    formatter = FORMATTERS.get(style, format_reference_vancouver)

    entries = []
    for key in keys:
        for entry in bib.entries:
            if entry.get('ID') == key:
                entries.append(entry)
                break
        else:
            print(f"Warning: entry '{key}' not found, skipping.", file=sys.stderr)

    print(f"References ({style} style):")
    print()
    for i, entry in enumerate(entries, 1):
        print(formatter(entry, number=i))


def main():
    parser = argparse.ArgumentParser(description='Citation Manager')
    subparsers = parser.add_subparsers(dest='command')

    # search
    sp = subparsers.add_parser('search', help='Search a .bib file')
    sp.add_argument('bib_file', help='Path to .bib file')
    sp.add_argument('query', help='Search query (space-separated terms)')
    sp.add_argument('--author', help='Filter by author name')
    sp.add_argument('--year-min', type=int, help='Minimum year')
    sp.add_argument('--year-max', type=int, help='Maximum year')
    sp.add_argument('--max-results', type=int, default=20, help='Max results')

    # list
    sp = subparsers.add_parser('list', help='List all entries')
    sp.add_argument('bib_file', help='Path to .bib file')

    # show
    sp = subparsers.add_parser('show', help='Show entry details')
    sp.add_argument('bib_file', help='Path to .bib file')
    sp.add_argument('key', help='BibTeX entry key')

    # format
    sp = subparsers.add_parser('format', help='Format references')
    sp.add_argument('bib_file', help='Path to .bib file')
    sp.add_argument('keys', help='Comma-separated BibTeX keys')
    sp.add_argument('--style', default='vancouver',
                    choices=list(FORMATTERS.keys()),
                    help='Citation style')

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        sys.exit(1)

    {'search': cmd_search, 'list': cmd_list,
     'show': cmd_show, 'format': cmd_format}[args.command](args)


if __name__ == '__main__':
    main()
