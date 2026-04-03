"""Convert LaTeX math to OMML (Office Math Markup Language) via MathML.

Uses latex2mathml for LaTeX->MathML, then a custom MathML->OMML converter.
This handles complex constructs (fractions, matrices, square roots, etc.)
that the simple tokenizer in docx-generator.py cannot.
"""
from lxml import etree
import latex2mathml.converter

OMML = 'http://schemas.openxmlformats.org/officeDocument/2006/math'
W = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'


def _tag(elem):
    """Get local tag name from a namespaced element."""
    return etree.QName(elem.tag).localname if '}' in elem.tag else elem.tag


def _omml_run(text, italic=True):
    """Create an OMML run with text."""
    r = etree.Element(f'{{{OMML}}}r')
    rPr = etree.SubElement(r, f'{{{OMML}}}rPr')
    sty = etree.SubElement(rPr, f'{{{OMML}}}sty')
    sty.set(f'{{{OMML}}}val', 'i' if italic else 'p')
    t = etree.SubElement(r, f'{{{OMML}}}t')
    t.text = text
    return r


def _append(parent, result):
    """Append a result (single element or list) to parent."""
    if result is None:
        return
    if isinstance(result, list):
        for r in result:
            parent.append(r)
    else:
        parent.append(result)


def _convert_node(node):
    """Recursively convert a MathML node to OMML element(s)."""
    tag = _tag(node)

    if tag == 'math':
        omath = etree.Element(f'{{{OMML}}}oMath')
        for child in node:
            _append(omath, _convert_node(child))
        return omath

    elif tag == 'mrow':
        results = []
        for child in node:
            r = _convert_node(child)
            if isinstance(r, list):
                results.extend(r)
            elif r is not None:
                results.append(r)
        return results

    elif tag == 'mi':
        return _omml_run(node.text or '', italic=True)

    elif tag == 'mn':
        return _omml_run(node.text or '', italic=False)

    elif tag == 'mo':
        r = etree.Element(f'{{{OMML}}}r')
        rPr = etree.SubElement(r, f'{{{OMML}}}rPr')
        sty = etree.SubElement(rPr, f'{{{OMML}}}sty')
        sty.set(f'{{{OMML}}}val', 'p')
        t = etree.SubElement(r, f'{{{OMML}}}t')
        t.text = node.text or ''
        return r

    elif tag == 'mtext':
        return _omml_run(node.text or '', italic=False)

    elif tag == 'mfrac':
        f_elem = etree.Element(f'{{{OMML}}}f')
        etree.SubElement(f_elem, f'{{{OMML}}}fPr')
        num = etree.SubElement(f_elem, f'{{{OMML}}}num')
        den = etree.SubElement(f_elem, f'{{{OMML}}}den')
        children = list(node)
        if len(children) >= 2:
            _append(num, _convert_node(children[0]))
            _append(den, _convert_node(children[1]))
        return f_elem

    elif tag == 'msub':
        sSub = etree.Element(f'{{{OMML}}}sSub')
        etree.SubElement(sSub, f'{{{OMML}}}sSubPr')
        e = etree.SubElement(sSub, f'{{{OMML}}}e')
        sub = etree.SubElement(sSub, f'{{{OMML}}}sub')
        children = list(node)
        if len(children) >= 2:
            _append(e, _convert_node(children[0]))
            _append(sub, _convert_node(children[1]))
        return sSub

    elif tag == 'msup':
        sSup = etree.Element(f'{{{OMML}}}sSup')
        etree.SubElement(sSup, f'{{{OMML}}}sSupPr')
        e = etree.SubElement(sSup, f'{{{OMML}}}e')
        sup = etree.SubElement(sSup, f'{{{OMML}}}sup')
        children = list(node)
        if len(children) >= 2:
            _append(e, _convert_node(children[0]))
            _append(sup, _convert_node(children[1]))
        return sSup

    elif tag == 'msubsup':
        sSubSup = etree.Element(f'{{{OMML}}}sSubSup')
        etree.SubElement(sSubSup, f'{{{OMML}}}sSubSupPr')
        e = etree.SubElement(sSubSup, f'{{{OMML}}}e')
        sub = etree.SubElement(sSubSup, f'{{{OMML}}}sub')
        sup = etree.SubElement(sSubSup, f'{{{OMML}}}sup')
        children = list(node)
        if len(children) >= 3:
            _append(e, _convert_node(children[0]))
            _append(sub, _convert_node(children[1]))
            _append(sup, _convert_node(children[2]))
        return sSubSup

    elif tag == 'msqrt':
        rad = etree.Element(f'{{{OMML}}}rad')
        radPr = etree.SubElement(rad, f'{{{OMML}}}radPr')
        degHide = etree.SubElement(radPr, f'{{{OMML}}}degHide')
        degHide.set(f'{{{OMML}}}val', '1')
        etree.SubElement(rad, f'{{{OMML}}}deg')
        e = etree.SubElement(rad, f'{{{OMML}}}e')
        for child in node:
            _append(e, _convert_node(child))
        return rad

    elif tag == 'mover':
        acc = etree.Element(f'{{{OMML}}}acc')
        accPr = etree.SubElement(acc, f'{{{OMML}}}accPr')
        children = list(node)
        # The accent character is in the second child (mo)
        if len(children) >= 2:
            accent_text = children[1].text or ''
            chr_elem = etree.SubElement(accPr, f'{{{OMML}}}chr')
            chr_elem.set(f'{{{OMML}}}val', accent_text)
        e = etree.SubElement(acc, f'{{{OMML}}}e')
        if children:
            _append(e, _convert_node(children[0]))
        return acc

    elif tag == 'munder':
        # Under element — treat like groupChr or limLow
        limLow = etree.Element(f'{{{OMML}}}limLow')
        etree.SubElement(limLow, f'{{{OMML}}}limLowPr')
        e = etree.SubElement(limLow, f'{{{OMML}}}e')
        lim = etree.SubElement(limLow, f'{{{OMML}}}lim')
        children = list(node)
        if len(children) >= 2:
            _append(e, _convert_node(children[0]))
            _append(lim, _convert_node(children[1]))
        return limLow

    elif tag == 'mtable':
        m = etree.Element(f'{{{OMML}}}m')
        mPr = etree.SubElement(m, f'{{{OMML}}}mPr')
        for row in node:
            if _tag(row) == 'mtr':
                mr = etree.SubElement(m, f'{{{OMML}}}mr')
                for cell in row:
                    if _tag(cell) == 'mtd':
                        e = etree.SubElement(mr, f'{{{OMML}}}e')
                        for child in cell:
                            _append(e, _convert_node(child))
        return m

    elif tag == 'mfenced':
        # Fenced expression (parentheses, brackets, etc.)
        d = etree.Element(f'{{{OMML}}}d')
        dPr = etree.SubElement(d, f'{{{OMML}}}dPr')
        open_char = node.get('open', '(')
        close_char = node.get('close', ')')
        if open_char != '(':
            begChr = etree.SubElement(dPr, f'{{{OMML}}}begChr')
            begChr.set(f'{{{OMML}}}val', open_char)
        if close_char != ')':
            endChr = etree.SubElement(dPr, f'{{{OMML}}}endChr')
            endChr.set(f'{{{OMML}}}val', close_char)
        e = etree.SubElement(d, f'{{{OMML}}}e')
        for child in node:
            _append(e, _convert_node(child))
        return d

    elif tag == 'mspace':
        # Spacing — just return a thin space run
        r = etree.Element(f'{{{OMML}}}r')
        t = etree.SubElement(r, f'{{{OMML}}}t')
        t.text = '\u2009'  # thin space
        return r

    elif tag == 'mstyle':
        # Style wrapper — process children
        results = []
        for child in node:
            r = _convert_node(child)
            if isinstance(r, list):
                results.extend(r)
            elif r is not None:
                results.append(r)
        return results

    elif tag == 'mpadded':
        # Padded — process children
        results = []
        for child in node:
            r = _convert_node(child)
            if isinstance(r, list):
                results.extend(r)
            elif r is not None:
                results.append(r)
        return results

    else:
        # Fallback: process children, emit text if present
        results = []
        if node.text and node.text.strip():
            results.append(_omml_run(node.text, italic=True))
        for child in node:
            r = _convert_node(child)
            if isinstance(r, list):
                results.extend(r)
            elif r is not None:
                results.append(r)
        return results if results else None


def latex_to_omml(latex_str):
    """Convert a LaTeX math string to an OMML oMath element.

    Args:
        latex_str: LaTeX math (without $$ delimiters)

    Returns:
        lxml Element: <m:oMath> element ready to insert into a docx paragraph
    """
    # Clean up: remove \tag{...} (equation numbers) — OMML doesn't support them inline
    import re
    tag_match = re.search(r'\\tag\{([^}]+)\}', latex_str)
    tag_text = tag_match.group(1) if tag_match else None
    latex_clean = re.sub(r'\s*\\tag\{[^}]+\}', '', latex_str)

    # Convert \; \, \! \quad spacing to standard LaTeX that latex2mathml handles
    latex_clean = latex_clean.replace(r'\;', r'\>')
    latex_clean = latex_clean.replace(r'\,', r'\>')
    latex_clean = latex_clean.replace(r'\!', '')

    # Convert LaTeX -> MathML
    mml_str = latex2mathml.converter.convert(latex_clean)
    mml_root = etree.fromstring(mml_str.encode())

    # Convert MathML -> OMML
    omml = _convert_node(mml_root)

    # If there was a \tag, append it as "(S1)" text
    if tag_text and omml is not None:
        # Add some space then the tag
        space_r = etree.SubElement(omml, f'{{{OMML}}}r')
        space_rPr = etree.SubElement(space_r, f'{{{OMML}}}rPr')
        space_sty = etree.SubElement(space_rPr, f'{{{OMML}}}sty')
        space_sty.set(f'{{{OMML}}}val', 'p')
        space_t = etree.SubElement(space_r, f'{{{OMML}}}t')
        space_t.set('{http://www.w3.org/XML/1998/namespace}space', 'preserve')
        space_t.text = f'   ({tag_text})'

    return omml
