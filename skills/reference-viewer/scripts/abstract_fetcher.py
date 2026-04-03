#!/usr/bin/env python3
"""Fetch abstracts for manuscript references using a multi-source cascade.

Sources tried in order for each reference:
  1. CrossRef (works for any DOI; many publishers omit abstracts)
  2. PubMed E-utilities (works for all biomedical articles with PMIDs)
  3. Scopus (works with institutional API key, good for Elsevier/Springer)

Only needs `requests` (stdlib otherwise). All network calls have timeouts
and graceful fallbacks — a failure in one source just moves to the next.
"""

import re
import time
import xml.etree.ElementTree as ET

try:
    import requests
except ImportError:
    requests = None

# ---------------------------------------------------------------------------
# HTML / JATS tag stripping
# ---------------------------------------------------------------------------

def _strip_tags(text):
    """Remove HTML/JATS/XML tags, leading 'Abstract' label, and collapse whitespace."""
    text = re.sub(r'<[^>]+>', '', text)
    text = re.sub(r'\s+', ' ', text).strip()
    # Strip leading "Abstract" label left behind after removing <jats:title>
    text = re.sub(r'^Abstract\s*', '', text)
    return text


# ---------------------------------------------------------------------------
# Source 1: CrossRef
# ---------------------------------------------------------------------------

def _fetch_crossref(doi, email=None, timeout=15):
    """GET abstract from CrossRef. Returns abstract str or None."""
    if not doi or not requests:
        return None
    url = f'https://api.crossref.org/works/{doi}'
    headers = {'User-Agent': f'reference-viewer/2.0 (mailto:{email})' if email
               else 'reference-viewer/2.0'}
    try:
        r = requests.get(url, headers=headers, timeout=timeout)
        if r.status_code != 200:
            return None
        data = r.json().get('message', {})
        abstract = data.get('abstract', '')
        if abstract:
            return _strip_tags(abstract)
    except Exception:
        pass
    return None


# ---------------------------------------------------------------------------
# Source 2: PubMed E-utilities (esearch + efetch)
# ---------------------------------------------------------------------------

_ESEARCH = 'https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi'
_EFETCH = 'https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi'


def _doi_to_pmid(doi, timeout=15):
    """Look up a PMID from a DOI via PubMed esearch."""
    if not doi or not requests:
        return None
    params = {
        'db': 'pubmed',
        'term': f'{doi}[doi]',
        'retmode': 'json',
        'retmax': 1,
    }
    try:
        r = requests.get(_ESEARCH, params=params, timeout=timeout)
        if r.status_code != 200:
            return None
        data = r.json()
        ids = data.get('esearchresult', {}).get('idlist', [])
        return ids[0] if ids else None
    except Exception:
        return None


def _title_to_pmid(title, timeout=15):
    """Look up a PMID from a title via PubMed esearch."""
    if not title or not requests:
        return None
    # Use title field search for precision
    clean = re.sub(r'[^\w\s]', '', title)[:200]
    params = {
        'db': 'pubmed',
        'term': f'{clean}[ti]',
        'retmode': 'json',
        'retmax': 1,
    }
    try:
        r = requests.get(_ESEARCH, params=params, timeout=timeout)
        if r.status_code != 200:
            return None
        data = r.json()
        ids = data.get('esearchresult', {}).get('idlist', [])
        return ids[0] if ids else None
    except Exception:
        return None


def _fetch_pubmed_abstracts_batch(pmids, timeout=30):
    """Fetch abstracts for a list of PMIDs via efetch (XML).

    Returns dict {pmid_str: abstract_text}.
    """
    if not pmids or not requests:
        return {}
    params = {
        'db': 'pubmed',
        'id': ','.join(str(p) for p in pmids),
        'rettype': 'xml',
        'retmode': 'xml',
    }
    try:
        r = requests.get(_EFETCH, params=params, timeout=timeout)
        if r.status_code != 200:
            return {}
        root = ET.fromstring(r.content)
        results = {}
        for article in root.findall('.//PubmedArticle'):
            pmid_el = article.find('.//PMID')
            if pmid_el is None:
                continue
            pmid = pmid_el.text
            # Abstract may have multiple AbstractText elements (structured)
            abstract_parts = []
            for at in article.findall('.//AbstractText'):
                label = at.get('Label', '')
                text = ''.join(at.itertext()).strip()
                if label:
                    abstract_parts.append(f'{label}: {text}')
                else:
                    abstract_parts.append(text)
            if abstract_parts:
                results[pmid] = ' '.join(abstract_parts)
        return results
    except Exception:
        return {}


# ---------------------------------------------------------------------------
# Source 3: Scopus (via DOI)
# ---------------------------------------------------------------------------

def _fetch_scopus(doi, api_key=None, timeout=15):
    """GET abstract from Scopus. Needs an API key. Returns abstract str or None."""
    if not doi or not requests or not api_key:
        return None
    url = f'https://api.elsevier.com/content/abstract/doi/{doi}'
    headers = {
        'X-ELS-APIKey': api_key,
        'Accept': 'application/json',
    }
    try:
        r = requests.get(url, headers=headers, timeout=timeout)
        if r.status_code != 200:
            return None
        data = r.json()
        desc = (data.get('abstracts-retrieval-response', {})
                .get('coredata', {})
                .get('dc:description', ''))
        if desc:
            # Scopus prepends copyright notice — strip it
            desc = re.sub(r'^©.*?\.\s*', '', desc, count=1)
            return _strip_tags(desc).strip()
    except Exception:
        pass
    return None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def fetch_abstracts(references, email=None, scopus_api_key=None, verbose=True):
    """Fetch abstracts for all references using a multi-source cascade.

    For each reference:
      1. Try CrossRef (if DOI exists)
      2. Try PubMed (look up PMID via DOI or title, then batch fetch)
      3. Try Scopus (if DOI exists and API key provided)

    Args:
        references: dict {ref_num: {ref, doi, title, authors, year, journal}}
        email: Optional email for CrossRef polite pool.
        scopus_api_key: Optional Scopus API key for fallback.
        verbose: Print progress to stdout.

    Returns:
        (abstracts, failures)
        abstracts: dict {ref_num: abstract_text}
        failures: list of {ref_num, reason}
    """
    if not requests:
        if verbose:
            print('  WARNING: requests not installed, skipping abstract fetch')
        return {}, [{'ref_num': n, 'reason': 'requests not installed'}
                    for n in references]

    abstracts = {}
    needs_pubmed = {}  # ref_num -> doi or title (for PMID lookup)
    needs_scopus = []  # ref_nums that still need abstracts after PubMed

    # ----- Phase 1: CrossRef (fast, one request per DOI) -----
    refs_with_doi = {n: r for n, r in references.items() if r.get('doi')}
    if verbose:
        print(f'  Fetching abstracts: {len(references)} refs, {len(refs_with_doi)} with DOIs')
        print(f'  Phase 1: CrossRef...', end='', flush=True)

    crossref_hits = 0
    for i, (ref_num, ref) in enumerate(sorted(refs_with_doi.items())):
        abstract = _fetch_crossref(ref['doi'], email=email)
        if abstract and len(abstract) > 30:
            abstracts[ref_num] = abstract
            crossref_hits += 1
        else:
            needs_pubmed[ref_num] = ref
        # Rate limit: ~10 req/sec for polite pool, ~1 req/sec otherwise
        if i < len(refs_with_doi) - 1:
            time.sleep(0.15 if email else 1.0)

    # Also add refs without DOI to the PubMed queue
    for n, r in references.items():
        if n not in abstracts and n not in needs_pubmed:
            needs_pubmed[n] = r

    if verbose:
        print(f' {crossref_hits}/{len(refs_with_doi)} found')

    if not needs_pubmed:
        if verbose:
            print(f'  All abstracts found via CrossRef!')
        return abstracts, []

    # ----- Phase 2: PubMed (batch fetch via E-utilities) -----
    if verbose:
        print(f'  Phase 2: PubMed ({len(needs_pubmed)} remaining)...', end='', flush=True)

    # Step 2a: Resolve PMIDs (DOI lookup first, then title)
    ref_to_pmid = {}
    for ref_num, ref in sorted(needs_pubmed.items()):
        pmid = None
        if ref.get('doi'):
            pmid = _doi_to_pmid(ref['doi'])
            time.sleep(0.35)  # NCBI rate limit: 3 req/sec without API key
        if not pmid and ref.get('title'):
            pmid = _title_to_pmid(ref['title'])
            time.sleep(0.35)
        if pmid:
            ref_to_pmid[ref_num] = pmid

    # Step 2b: Batch fetch abstracts (up to 50 per request)
    pmid_to_ref = {pmid: ref_num for ref_num, pmid in ref_to_pmid.items()}
    all_pmids = list(ref_to_pmid.values())
    pubmed_hits = 0

    for batch_start in range(0, len(all_pmids), 50):
        batch = all_pmids[batch_start:batch_start + 50]
        batch_abstracts = _fetch_pubmed_abstracts_batch(batch)
        for pmid, abstract in batch_abstracts.items():
            if abstract and len(abstract) > 30:
                ref_num = pmid_to_ref.get(pmid)
                if ref_num and ref_num not in abstracts:
                    abstracts[ref_num] = abstract
                    pubmed_hits += 1
        if batch_start + 50 < len(all_pmids):
            time.sleep(0.5)

    if verbose:
        print(f' {pubmed_hits}/{len(needs_pubmed)} found')

    # Identify what still needs Scopus
    for ref_num in needs_pubmed:
        if ref_num not in abstracts and references[ref_num].get('doi'):
            needs_scopus.append(ref_num)

    # ----- Phase 3: Scopus (only if API key provided) -----
    if needs_scopus and scopus_api_key:
        if verbose:
            print(f'  Phase 3: Scopus ({len(needs_scopus)} remaining)...', end='', flush=True)
        scopus_hits = 0
        for ref_num in needs_scopus:
            abstract = _fetch_scopus(references[ref_num]['doi'],
                                     api_key=scopus_api_key)
            if abstract and len(abstract) > 30:
                abstracts[ref_num] = abstract
                scopus_hits += 1
            time.sleep(0.2)
        if verbose:
            print(f' {scopus_hits}/{len(needs_scopus)} found')

    # ----- Build failures list -----
    failures = []
    for ref_num in references:
        if ref_num not in abstracts:
            ref = references[ref_num]
            if not ref.get('doi'):
                reason = 'no DOI and not found in PubMed'
            else:
                reason = 'not found in CrossRef, PubMed, or Scopus'
            failures.append({'ref_num': ref_num, 'reason': reason})

    if verbose:
        print(f'  Final: {len(abstracts)}/{len(references)} abstracts fetched, '
              f'{len(failures)} missing')

    return abstracts, failures
