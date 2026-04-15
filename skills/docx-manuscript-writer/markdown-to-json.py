#!/usr/bin/env python3
"""
Parse a scientific manuscript markdown file into structured JSON for docx-generator.py.

Handles:
  - Title, authors, affiliations, corresponding author from the header block
  - Section headings (##/###/#### for level 1/2/3)
  - Markdown tables (pipe-delimited) → tab-separated table sections
  - Table captions (**Table N.** ...) and table notes (Note: ...)
  - Figure placeholders ([INSERT FIGURE N HERE]) with captions
  - Page breaks before specified headings

Usage:
    python markdown-to-json.py manuscript.md [--output input.json]
                                             [--journal journal-of-pain]
                                             [--authors key1,key2,...]
                                             [--figures-dir /path/to/figures]
                                             [--page-break-before "Abstract,Introduction"]
"""
import argparse
import json
import os
import re
import sys


def parse_front_matter(lines):
    """Extract title, authors, affiliations, and corresponding author from
    the markdown header block (everything before the first ## heading).

    The title is the first non-empty line (plain text, no #).
    """
    title = ''
    corresponding = None
    header_end = 0

    # Find the title (first non-empty line) and the end of front matter (first ## heading)
    for i, line in enumerate(lines):
        stripped = line.strip()
        if not stripped or stripped == '---':
            continue
        if not title and not stripped.startswith('#'):
            title = stripped
        if re.match(r'^#{2,4}\s+', stripped):
            header_end = i
            break
    else:
        header_end = len(lines)

    # Corresponding author: look for "*Corresponding author:" or "\\*Corresponding"
    for i, line in enumerate(lines[:header_end]):
        if 'orresponding author' in line.lower():
            ca_lines = []
            text = re.sub(r'^[\\*]+\s*', '', line.strip())
            text = re.sub(r'^Corresponding author:\s*', '', text, flags=re.I)
            if text:
                ca_lines.append(text)
            # Grab continuation lines
            for j in range(i + 1, header_end):
                l = lines[j].strip()
                if not l or l.startswith('#') or l == '---':
                    break
                ca_lines.append(l)
            if ca_lines:
                corresponding = {'lines': ca_lines}
            break

    return title, corresponding, header_end


def parse_body(lines):
    """Parse the body (after front matter) into structured sections.

    Headings use ## = level 1, ### = level 2, #### = level 3.
    """
    sections = []
    i = 0

    while i < len(lines):
        line = lines[i].strip()

        # Skip horizontal rules and empty lines
        if not line or line == '---':
            i += 1
            continue

        # Heading
        heading_match = re.match(r'^(#{2,4})\s+(.+)', line)
        if heading_match:
            hashes = heading_match.group(1)
            heading_text = heading_match.group(2).strip()
            level = len(hashes) - 1  # ## = 1, ### = 2, #### = 3
            i += 1
            # Collect body text until next heading or special block
            body_lines = []
            while i < len(lines):
                cur = lines[i]
                cur_stripped = cur.strip()
                # Skip horizontal rules (don't absorb into text)
                if cur_stripped == '---':
                    i += 1
                    continue
                # Stop at next heading
                if re.match(r'^#{2,4}\s+', cur_stripped):
                    break
                # Stop at table caption (will be handled separately)
                if re.match(r'^\*\*Table [A-Za-z]?\d+\.\*\*', cur_stripped):
                    break
                # Stop at figure insert or markdown image
                if re.match(r'^\[INSERT FIGURE [A-Za-z]?\d+ HERE\]', cur_stripped):
                    break
                if re.match(r'^!\[', cur_stripped):
                    break
                # Stop at table note
                if re.match(r'^\*?Notes?[\.:]\*?', cur_stripped, re.I):
                    break
                # Stop at markdown table (line starting with |)
                if cur_stripped.startswith('|') and '|' in cur_stripped[1:]:
                    break
                body_lines.append(cur)
                i += 1
            text = '\n'.join(body_lines).strip()
            sections.append({
                'header': heading_text,
                'level': level,
                'text': text,
                'type': 'text'
            })
            continue

        # Table caption: **Table N.** description (must be a standalone caption,
        # not a body paragraph that happens to start with a table reference).
        # Captions are short (<200 chars) or are followed by a table within 3 lines.
        table_caption_match = re.match(
            r'^\*\*Table ([A-Za-z]?\d+)\.\*\*\s*(.*)', line)
        if table_caption_match:
            # Check if this looks like a real caption vs body text
            is_caption = len(line) < 200
            if not is_caption:
                # Long line — only treat as caption if a table follows soon
                for lookahead in range(i + 1, min(i + 4, len(lines))):
                    la = lines[lookahead].strip()
                    if la.startswith('|') and '|' in la[1:]:
                        is_caption = True
                        break
                    if la and not la.startswith('|'):
                        break
            if not is_caption:
                # Treat as regular body text instead
                table_caption_match = None
        if table_caption_match:
            caption = line
            sections.append({
                'header': '',
                'level': 0,
                'text': caption,
                'type': 'table_caption'
            })
            i += 1
            # Check if next lines are a markdown table
            if i < len(lines) and lines[i].strip().startswith('|'):
                table_lines = []
                while i < len(lines) and lines[i].strip().startswith('|'):
                    row = lines[i].strip()
                    # Skip separator rows (|---|---|): every cell between pipes
                    # contains only dashes, colons, or whitespace (and >= 1 dash)
                    if re.match(r'^\|(?:[\s\-:]*-[\s\-:]*\|)+\s*$', row):
                        i += 1
                        continue
                    # Convert pipe-delimited to tab-separated
                    cells = [c.strip() for c in row.split('|')]
                    # Strip empty first/last from pipe format
                    if cells and cells[0] == '':
                        cells = cells[1:]
                    if cells and cells[-1] == '':
                        cells = cells[:-1]
                    table_lines.append('\t'.join(cells))
                    i += 1
                if table_lines:
                    sections.append({
                        'header': '',
                        'level': 0,
                        'text': '\n'.join(table_lines),
                        'type': 'table'
                    })
            # Check for table note (skip blank lines first)
            while i < len(lines) and not lines[i].strip():
                i += 1
            if i < len(lines):
                note_line = lines[i].strip()
                if re.match(r'^(\*?Notes?[\.:]\*?|Notes?[\.:])(.+)', note_line, re.I):
                    sections.append({
                        'header': '',
                        'level': 0,
                        'text': note_line,
                        'type': 'table_note'
                    })
                    i += 1
            continue

        # Standalone markdown table (no caption preceding it)
        if line.startswith('|') and '|' in line[1:]:
            table_lines = []
            while i < len(lines) and lines[i].strip().startswith('|'):
                row = lines[i].strip()
                # Stricter: every cell must contain at least one dash (true separator)
                if re.match(r'^\|(?:[\s\-:]*-[\s\-:]*\|)+\s*$', row):
                    i += 1
                    continue
                cells = [c.strip() for c in row.split('|')]
                if cells and cells[0] == '':
                    cells = cells[1:]
                if cells and cells[-1] == '':
                    cells = cells[:-1]
                table_lines.append('\t'.join(cells))
                i += 1
            if table_lines:
                sections.append({
                    'header': '',
                    'level': 0,
                    'text': '\n'.join(table_lines),
                    'type': 'table'
                })
            # Check for table note after standalone table too
            while i < len(lines) and not lines[i].strip():
                i += 1
            if i < len(lines):
                note_line = lines[i].strip()
                if re.match(r'^(\*?Notes?[\.:]\*?|Notes?[\.:])(.+)', note_line, re.I):
                    sections.append({
                        'header': '',
                        'level': 0,
                        'text': note_line,
                        'type': 'table_note'
                    })
                    i += 1
            continue

        # Figure: [INSERT FIGURE N HERE] or ![](path/figureN.png)
        # N can be a number (1, 2) or alphanumeric (S1, S2, A1)
        fig_match = re.match(r'^\[INSERT FIGURE ([A-Za-z]?\d+) HERE\]', line)
        md_img_match = re.match(r'^!\[.*\]\((.+)\)', line) if not fig_match else None
        if fig_match or md_img_match:
            if fig_match:
                fig_num = fig_match.group(1)
            else:
                # Extract figure number from path (e.g., figure_s1_..., figure3, Fig_S2)
                img_path = md_img_match.group(1)
                num_match = re.search(r'figure[_\-]?([A-Za-z]?\d+)', img_path, re.I)
                fig_num = num_match.group(1) if num_match else '0'
            i += 1
            # Skip blank lines between image and caption
            while i < len(lines) and not lines[i].strip():
                i += 1
            # Collect caption lines (starts with "**Figure N.**" or "Figure N.")
            caption_lines = []
            while i < len(lines):
                cl = lines[i].strip()
                if not cl:
                    break
                if cl.startswith('#') or cl.startswith('[INSERT') or cl.startswith('!['):
                    break
                if re.match(r'^\*\*Table [A-Za-z]?\d+\.\*\*', cl):
                    break
                caption_lines.append(cl)
                i += 1
            caption = ' '.join(caption_lines)
            caption = re.sub(r'\*\*(Figure [A-Za-z]?\d+\.)\*\*', r'\1', caption)
            sections.append({
                'header': '',
                'level': 0,
                'text': f'FIGURE:{fig_num}\n{caption}',
                'type': 'figure'
            })
            continue

        # Plain text paragraph (orphan text not under a heading)
        body_lines = [line]
        i += 1
        while i < len(lines):
            cur = lines[i].strip()
            if not cur:
                i += 1
                # Check if next non-empty line is a heading or special
                continue
            if re.match(r'^#{2,4}\s+', cur):
                break
            if re.match(r'^\*\*Table [A-Za-z]?\d+', cur):
                break
            if re.match(r'^\[INSERT FIGURE \d+ HERE\]', cur):
                break
            if re.match(r'^!\[', cur):
                break
            if re.match(r'^\*?Notes?[\.:]\*?', cur, re.I):
                break
            if cur.startswith('|') and '|' in cur[1:]:
                break
            body_lines.append(cur)
            i += 1
        text = '\n'.join(body_lines).strip()
        if text:
            sections.append({
                'header': '',
                'level': 0,
                'text': text,
                'type': 'text'
            })
        continue

    return sections


def main():
    parser = argparse.ArgumentParser(
        description='Parse manuscript markdown to JSON for docx-generator')
    parser.add_argument('manuscript', help='Path to manuscript .md file')
    parser.add_argument('--output', '-o', help='Output JSON path (default: same dir, _input.json)')
    parser.add_argument('--journal', '-j', default='journal-of-pain',
                        help='Journal profile name (default: journal-of-pain)')
    parser.add_argument('--authors', '-a',
                        default='valdes-hernandez,montesino-goicolea,fillingim,cruz-almeida',
                        help='Comma-separated author keys')
    parser.add_argument('--figures-dir', '-f', help='Directory containing figure images')
    parser.add_argument('--page-break-before', '-p',
                        default='Abstract,Introduction',
                        help='Comma-separated heading names to insert page breaks before')
    args = parser.parse_args()

    # Read manuscript
    with open(args.manuscript) as f:
        content = f.read()
    lines = content.split('\n')

    # Parse
    title, corresponding, header_end = parse_front_matter(lines)
    sections = parse_body(lines[header_end:])

    # Build output
    manuscript_dir = os.path.dirname(os.path.abspath(args.manuscript))
    manuscript_base = os.path.splitext(os.path.basename(args.manuscript))[0]

    output_path = args.output or os.path.join(
        manuscript_dir, f'{manuscript_base}_input.json')
    docx_path = os.path.join(manuscript_dir, f'{manuscript_base}.docx')
    figures_dir = args.figures_dir or os.path.join(
        os.path.dirname(manuscript_dir), 'figures')

    data = {
        'title': title,
        'authors': [a.strip() for a in args.authors.split(',')],
        'journal_profile': args.journal,
        'output_path': docx_path,
        'figures_dir': figures_dir,
        'page_break_before': [h.strip() for h in args.page_break_before.split(',')],
        'sections': sections,
    }
    if corresponding:
        data['corresponding_author'] = corresponding

    with open(output_path, 'w') as f:
        json.dump(data, f, indent=2)

    # Report
    type_counts = {}
    for s in sections:
        t = s.get('type', 'text')
        type_counts[t] = type_counts.get(t, 0) + 1
    print(f'Parsed {args.manuscript} → {output_path}')
    print(f'  Title: {title[:70]}...' if len(title) > 70 else f'  Title: {title}')
    print(f'  Sections: {len(sections)}')
    for t, c in sorted(type_counts.items()):
        print(f'    {t}: {c}')


if __name__ == '__main__':
    main()
