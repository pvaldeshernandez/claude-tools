"""Generate a self-contained HTML reference viewer.

Replicates the existing viewer CSS, JS, and card layout verbatim,
with enhancements for PDF snippets, abstracts, and grouped citation instances.
"""

import json
import re
from pathlib import Path


def _sanitize_storage_key(subtitle: str) -> str:
    """Create a localStorage key from the subtitle."""
    return 'manuscript_ref_reviews_' + re.sub(r'[^a-z0-9]+', '_', subtitle.lower()).strip('_')


def _convert_citations(citations: dict) -> dict:
    """Convert internal citation format to JS-ready format.

    Input per ref_num:
      [ { "instances": [{"section","line"}, ...],
          "manuscript_context": str,
          "pdf_snippets": [str, ...] }, ... ]

    Output per ref_num (JS format):
      [ { "section": str, "line": int, "snippet": str,
          "also_at": [{"section","line"}, ...],   # optional
          "pdf_snippets": [str, ...]               # optional
        }, ... ]
    """
    js_citations = {}
    for ref_num, citation_groups in citations.items():
        js_list = []
        for group in citation_groups:
            instances = group.get('instances', [])
            if not instances:
                continue
            entry = {
                'section': instances[0]['section'],
                'line': instances[0]['line'],
                'snippet': group.get('manuscript_context', ''),
            }
            if len(instances) > 1:
                entry['also_at'] = instances[1:]
            pdf_snips = group.get('pdf_snippets', [])
            if pdf_snips:
                entry['pdf_snippets'] = pdf_snips
            js_list.append(entry)
        if js_list:
            js_citations[str(ref_num)] = js_list
    return js_citations


def _count_citation_instances(js_citations: dict) -> int:
    """Count total citation instances including also_at entries."""
    total = 0
    for ref_num, groups in js_citations.items():
        for g in groups:
            total += 1
            total += len(g.get('also_at', []))
    return total


def _build_filter_buttons(hierarchy: dict) -> str:
    """Build the section filter buttons from the hierarchy keys.

    Only includes major sections: Abstract, Introduction, Methods, Results, Discussion.
    """
    major = ['Abstract', 'Introduction', 'Methods', 'Results', 'Discussion']
    buttons = ['  <button class="filter-btn active" data-filter="all">All</button>',
               '  <button class="filter-btn" data-filter="uncited">Uncited</button>']
    for sec in major:
        if sec in hierarchy:
            buttons.append(f'  <button class="filter-btn" data-filter="{sec.lower()}">{sec}</button>')
    return '\n'.join(buttons)


def generate(title: str, subtitle: str, sections: list, hierarchy: dict,
             references: dict, citations: dict, abstracts: dict,
             total_refs: int, output_path: Path, state: dict = None) -> None:
    """Generate the self-contained reference_viewer.html.

    Args:
        title: Page title (e.g., "Manuscript Reference Viewer")
        subtitle: Manuscript title (shown in header)
        sections: list of {"line": int, "level": int, "heading": str}
        hierarchy: dict {l2_heading: [child_headings]}
        references: dict {ref_num(int): {"ref","doi","title","authors","year","journal"}}
        citations: dict {ref_num(int): [{"instances":[{"section","line"},...],
                   "manuscript_context":str, "pdf_snippets":[str,...]}, ...]}
        abstracts: dict {ref_num(int): abstract_text_str}
        total_refs: int
        output_path: Path -- where to write the HTML
    """
    # Convert citations to JS format
    js_citations = _convert_citations(citations)

    # Compute stats
    citation_instance_count = _count_citation_instances(js_citations)
    cited_count = len(js_citations)
    uncited_count = total_refs - cited_count

    # Convert references keys to strings for JSON
    js_references = {}
    for k, v in references.items():
        js_references[str(k)] = v

    # Convert abstracts keys to strings
    js_abstracts = {}
    for k, v in abstracts.items():
        js_abstracts[str(k)] = v

    # Build hierarchy with string keys
    js_hierarchy = {}
    for k, v in hierarchy.items():
        js_hierarchy[str(k)] = v

    storage_key = _sanitize_storage_key(subtitle)

    # Build AI verdicts from state
    ai_verdicts = {}
    if state:
        for ref_key, review in state.get('reviews', {}).items():
            if review.get('claude_verdict'):
                ai_verdicts[str(ref_key)] = {
                    'verdict': review.get('claude_verdict', ''),
                    'reason': review.get('claude_reason', ''),
                }

    filter_buttons = _build_filter_buttons(hierarchy)

    # Build the HTML
    html = f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{_escape_html(title)}</title>
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/katex@0.16.21/dist/katex.min.css">
<script src="https://cdn.jsdelivr.net/npm/katex@0.16.21/dist/katex.min.js"></script>
<style>
* {{ box-sizing: border-box; margin: 0; padding: 0; }}
body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #f5f7fa; color: #2d3748; line-height: 1.6; }}
.header {{ background: linear-gradient(135deg, #1a365d 0%, #2a4a7f 100%); color: white; padding: 24px 32px; }}
.header h1 {{ font-size: 1.6rem; margin-bottom: 4px; }}
.header .subtitle {{ font-size: 0.9rem; opacity: 0.85; margin-bottom: 16px; font-style: italic; }}
.stats {{ display: flex; gap: 16px; flex-wrap: wrap; }}
.stats .stat-box {{ background: rgba(255,255,255,0.15); border-radius: 8px; padding: 8px 16px; text-align: center; min-width: 100px; }}
.stats .stat-box .stat-num {{ font-size: 1.5rem; font-weight: 700; }}
.stats .stat-box .stat-label {{ font-size: 0.75rem; text-transform: uppercase; opacity: 0.8; }}
.controls {{ background: white; border-bottom: 1px solid #e2e8f0; padding: 12px 32px; display: flex; gap: 12px; align-items: center; flex-wrap: wrap; position: sticky; top: 0; z-index: 100; }}
.search-box {{ flex: 1; min-width: 200px; padding: 8px 14px; border: 1px solid #cbd5e0; border-radius: 6px; font-size: 0.9rem; outline: none; }}
.search-box:focus {{ border-color: #4299e1; box-shadow: 0 0 0 3px rgba(66,153,225,0.15); }}
.filter-btn {{ padding: 6px 14px; border: 1px solid #cbd5e0; border-radius: 6px; background: white; cursor: pointer; font-size: 0.82rem; transition: all 0.15s; }}
.filter-btn:hover {{ background: #edf2f7; }}
.filter-btn.active {{ background: #2a4a7f; color: white; border-color: #2a4a7f; }}
.expand-bar {{ background: #edf2f7; padding: 8px 32px; display: flex; gap: 8px; flex-wrap: wrap; border-bottom: 1px solid #e2e8f0; }}
.expand-bar button {{ padding: 4px 12px; border: 1px solid #cbd5e0; border-radius: 4px; background: white; cursor: pointer; font-size: 0.78rem; }}
.expand-bar button:hover {{ background: #e2e8f0; }}
.container {{ max-width: 1100px; margin: 24px auto; padding: 0 16px; }}
.ref-card {{ background: white; border-radius: 8px; margin-bottom: 12px; box-shadow: 0 1px 3px rgba(0,0,0,0.08); border-left: 4px solid #4299e1; overflow: hidden; transition: border-color 0.2s; }}
.ref-card.uncited {{ border-left-color: #e53e3e; }}
.ref-card.review-satisfied {{ border-left-color: #38a169; }}
.ref-card.review-flagged {{ border-left-color: #dd6b20; }}
.ref-card.ai-pass {{ border-left-color: #38a169; }}
.ref-header {{ padding: 14px 18px; cursor: pointer; display: flex; align-items: flex-start; gap: 12px; user-select: none; }}
.ref-header:hover {{ background: #f7fafc; }}
.ref-num {{ background: #2a4a7f; color: white; font-weight: 700; font-size: 0.85rem; min-width: 36px; height: 36px; border-radius: 50%; display: flex; align-items: center; justify-content: center; flex-shrink: 0; }}
.ref-card.uncited .ref-num {{ background: #e53e3e; }}
.ref-info {{ flex: 1; }}
.ref-info .ref-title {{ font-weight: 600; font-size: 0.95rem; margin-bottom: 2px; }}
.ref-info .ref-meta {{ font-size: 0.82rem; color: #718096; }}
.ref-badges {{ display: flex; gap: 6px; flex-wrap: wrap; align-items: center; flex-shrink: 0; }}
.badge {{ font-size: 0.7rem; padding: 2px 8px; border-radius: 10px; font-weight: 600; }}
.badge-count {{ background: #ebf4ff; color: #2b6cb0; }}
.badge-section {{ background: #f0fff4; color: #276749; }}
.badge-uncited {{ background: #fed7d7; color: #c53030; }}
.badge-ai-pass {{ background: #c6f6d5; color: #276749; }}
.badge-ai-warning {{ background: #fefcbf; color: #975a16; }}
.badge-ai-flag {{ background: #fed7d7; color: #c53030; }}
.ref-card.ai-flagged {{ border-left-color: #c53030; }}
.ref-card.ai-warning {{ border-left-color: #dd6b20; }}
.chevron {{ font-size: 1.2rem; color: #a0aec0; transition: transform 0.2s; flex-shrink: 0; margin-top: 6px; }}
.ref-card.open .chevron {{ transform: rotate(90deg); }}
.ref-body {{ display: none; padding: 0 18px 18px 66px; }}
.ref-card.open .ref-body {{ display: block; }}
.ref-full {{ font-size: 0.88rem; color: #4a5568; margin-bottom: 14px; padding: 10px 14px; background: #f7fafc; border-radius: 6px; border-left: 3px solid #cbd5e0; }}
.ref-full a {{ color: #2b6cb0; text-decoration: none; }}
.ref-full a:hover {{ text-decoration: underline; }}
.section-panel {{ margin-bottom: 14px; }}
.section-panel h4 {{ font-size: 0.82rem; text-transform: uppercase; color: #718096; margin-bottom: 8px; letter-spacing: 0.5px; }}
.citation-item {{ padding: 8px 12px; background: #fffbeb; border-radius: 6px; margin-bottom: 6px; font-size: 0.85rem; border-left: 3px solid #ecc94b; }}
.citation-item .cit-section {{ font-weight: 600; color: #975a16; font-size: 0.78rem; }}
.citation-item .cit-line {{ color: #a0aec0; font-size: 0.75rem; }}
.citation-item .cit-text {{ margin-top: 4px; color: #4a5568; }}
.citation-item mark {{ background: #fefcbf; padding: 1px 3px; border-radius: 2px; font-weight: 600; }}
.pdf-snippet-panel {{ margin-top: 8px; padding: 8px 12px; background: #f0f7ff; border-radius: 6px; border-left: 3px solid #4299e1; }}
.pdf-snippet-label {{ font-size: 0.75rem; font-weight: 600; color: #2b6cb0; margin-bottom: 4px; text-transform: uppercase; letter-spacing: 0.3px; }}
.pdf-snippet {{ font-size: 0.82rem; color: #4a5568; margin-bottom: 6px; line-height: 1.5; }}
.pdf-snippet:last-child {{ margin-bottom: 0; }}
.also-at {{ font-size: 0.75rem; color: #a0aec0; margin-top: 4px; font-style: italic; }}
.paper-info-panel {{ margin-bottom: 14px; border: 1px solid #e2e8f0; border-radius: 6px; overflow: hidden; }}
.paper-info-header {{ padding: 8px 12px; background: #edf2f7; cursor: pointer; font-size: 0.82rem; font-weight: 600; color: #4a5568; display: flex; justify-content: space-between; align-items: center; }}
.paper-info-header:hover {{ background: #e2e8f0; }}
.paper-info-chevron {{ transition: transform 0.2s; }}
.paper-info-panel.open .paper-info-chevron {{ transform: rotate(90deg); }}
.paper-info-body {{ display: none; padding: 12px; font-size: 0.85rem; color: #4a5568; }}
.paper-info-panel.open .paper-info-body {{ display: block; }}
.paper-info-body .info-label {{ font-weight: 600; color: #2d3748; margin-top: 8px; }}
.paper-info-body .info-label:first-child {{ margin-top: 0; }}
.paper-info-body .info-content {{ margin-top: 2px; color: #4a5568; }}
.paper-info-body .info-none {{ color: #a0aec0; font-style: italic; }}
.review-panel {{ margin-top: 14px; padding: 12px 14px; background: #fafafa; border-radius: 6px; border: 1px solid #e2e8f0; }}
.review-row {{ display: flex; align-items: center; gap: 12px; margin-bottom: 6px; }}
.review-row:last-of-type {{ margin-bottom: 0; }}
.review-checkbox-label {{ display: flex; align-items: center; gap: 6px; font-size: 0.85rem; cursor: pointer; font-weight: 500; }}
.review-checkbox-label input[type="checkbox"] {{ width: 16px; height: 16px; cursor: pointer; }}
.review-status {{ font-size: 0.72rem; padding: 2px 8px; border-radius: 10px; font-weight: 600; }}
.review-status.satisfied {{ background: #c6f6d5; color: #276749; }}
.review-status.not-reviewed {{ background: #fed7d7; color: #c53030; }}
.review-comment {{ width: 100%; margin-top: 8px; padding: 8px 10px; border: 1px solid #e2e8f0; border-radius: 4px; font-size: 0.82rem; font-family: inherit; resize: vertical; min-height: 36px; }}
.review-comment:focus {{ border-color: #4299e1; outline: none; }}
.compile-bar {{ background: white; border-top: 1px solid #e2e8f0; padding: 10px 32px; display: flex; gap: 10px; align-items: center; flex-wrap: wrap; position: sticky; bottom: 0; z-index: 100; }}
.compile-bar .progress-section {{ flex: 1; min-width: 200px; }}
.progress-bar-bg {{ background: #e2e8f0; border-radius: 6px; height: 8px; overflow: hidden; }}
.progress-bar-fill {{ background: linear-gradient(90deg, #38a169, #48bb78); height: 100%; border-radius: 6px; transition: width 0.3s; }}
.progress-text {{ font-size: 0.75rem; color: #718096; margin-top: 2px; }}
.compile-bar button {{ padding: 6px 14px; border: 1px solid #cbd5e0; border-radius: 6px; background: white; cursor: pointer; font-size: 0.8rem; }}
.compile-bar button:hover {{ background: #edf2f7; }}
.compile-bar .btn-primary {{ background: #dd6b20; color: white; border-color: #dd6b20; }}
.compile-bar .btn-primary:hover {{ background: #c05621; }}
.compile-bar .btn-danger {{ background: #e53e3e; color: white; border-color: #e53e3e; font-size: 0.75rem; }}
.compile-bar .btn-danger:hover {{ background: #c53030; }}
.modal-overlay {{ display: none; position: fixed; top: 0; left: 0; right: 0; bottom: 0; background: rgba(0,0,0,0.5); z-index: 1000; justify-content: center; align-items: center; }}
.modal-overlay.open {{ display: flex; }}
.modal {{ background: white; border-radius: 12px; width: 90%; max-width: 700px; max-height: 80vh; overflow: hidden; display: flex; flex-direction: column; }}
.modal-header {{ padding: 16px 20px; border-bottom: 1px solid #e2e8f0; display: flex; justify-content: space-between; align-items: center; }}
.modal-header h2 {{ font-size: 1.1rem; }}
.modal-close {{ background: none; border: none; font-size: 1.5rem; cursor: pointer; color: #a0aec0; }}
.modal-body {{ padding: 20px; overflow-y: auto; flex: 1; }}
.modal-body pre {{ white-space: pre-wrap; font-size: 0.82rem; background: #f7fafc; padding: 14px; border-radius: 6px; border: 1px solid #e2e8f0; max-height: 400px; overflow-y: auto; }}
.modal-footer {{ padding: 12px 20px; border-top: 1px solid #e2e8f0; display: flex; gap: 8px; justify-content: flex-end; }}
.modal-footer button {{ padding: 6px 14px; border: 1px solid #cbd5e0; border-radius: 6px; background: white; cursor: pointer; font-size: 0.82rem; }}
.modal-footer button:hover {{ background: #edf2f7; }}
.modal-footer .btn-primary {{ background: #2a4a7f; color: white; border-color: #2a4a7f; }}
.hidden-input {{ display: none; }}
</style>
</head>
<body>

<div class="header">
  <h1>{_escape_html(title)}</h1>
  <div class="subtitle">{_escape_html(subtitle)}</div>
  <div class="stats">
    <div class="stat-box"><div class="stat-num">{total_refs}</div><div class="stat-label">Total Refs</div></div>
    <div class="stat-box"><div class="stat-num">{citation_instance_count}</div><div class="stat-label">Citation Instances</div></div>
    <div class="stat-box"><div class="stat-num">{cited_count}</div><div class="stat-label">Cited</div></div>
    <div class="stat-box"><div class="stat-num">{uncited_count}</div><div class="stat-label">Uncited</div></div>
  </div>
</div>

<div class="controls">
  <input type="text" class="search-box" id="searchBox" placeholder="Search references, sections, text...">
{filter_buttons}
</div>

<div class="expand-bar">
  <button onclick="expandAll()">Expand All</button>
  <button onclick="collapseAll()">Collapse All</button>
  <button onclick="expandAllPaperInfo()">Show All Paper Info</button>
  <button onclick="collapseAllPaperInfo()">Hide All Paper Info</button>
</div>

<div class="container" id="ref-container"></div>

<div class="compile-bar">
  <div class="progress-section">
    <div class="progress-bar-bg"><div class="progress-bar-fill" id="progressFill" style="width:0%"></div></div>
    <div class="progress-text" id="progressText">0 / {total_refs} reviewed</div>
  </div>
  <button onclick="filterByReviewStatus('flagged')">Show Flagged</button>
  <button onclick="filterByReviewStatus('unreviewed')">Show Unreviewed</button>
  <button onclick="filterByReviewStatus('ai-flagged')">Show AI Flagged</button>
  <button onclick="filterByReviewStatus('all')">Show All</button>
  <button class="btn-primary" onclick="compileConcerns()">Compile Concerns</button>
  <button onclick="saveStateToFile()">Save State</button>
  <button onclick="document.getElementById('loadFileInput').click()">Load State</button>
  <input type="file" id="loadFileInput" class="hidden-input" accept=".json" onchange="loadStateFromFile(this)">
  <button class="btn-danger" onclick="clearAllReviews()">Reset All Reviews</button>
</div>

<div class="modal-overlay" id="modalOverlay">
  <div class="modal">
    <div class="modal-header">
      <h2>Compiled Concerns</h2>
      <button class="modal-close" onclick="closeModal()">&times;</button>
    </div>
    <div class="modal-body" id="modalBody">
      <pre id="concernsText"></pre>
    </div>
    <div class="modal-footer">
      <button onclick="copyConcernsToClipboard()">Copy to Clipboard</button>
      <button class="btn-primary" onclick="downloadConcerns()">Download</button>
    </div>
  </div>
</div>

<script>
const SECTIONS = {json.dumps(sections, indent=2)};

const REFERENCES = {json.dumps(js_references, indent=2)};

const CITATIONS = {json.dumps(js_citations, indent=2)};

const SECTION_HIERARCHY = {json.dumps(js_hierarchy, indent=2)};

const TOTAL_REFS = {total_refs};

const ABSTRACTS = {json.dumps(js_abstracts, indent=2)};

const AI_VERDICTS = {json.dumps(ai_verdicts, indent=2)};

// ---- STORAGE ----
const STORAGE_KEY = {json.dumps(storage_key)};
const STATE_FILENAME = 'ref_review_state.json';

function getAllReviews() {{
  try {{ return JSON.parse(localStorage.getItem(STORAGE_KEY) || '{{}}'); }} catch(e) {{ return {{}}; }}
}}
function getReview(refNum) {{
  var all = getAllReviews();
  return all[refNum] || {{ satisfied: false, comment: '' }};
}}
function saveReview(refNum, data) {{
  var all = getAllReviews();
  all[refNum] = data;
  localStorage.setItem(STORAGE_KEY, JSON.stringify(all));
  updateProgress();
  updateCardReviewState(refNum);
}}
function toggleSatisfied(refNum, checked) {{
  var r = getReview(refNum);
  r.satisfied = checked;
  saveReview(refNum, r);
  var badge = document.getElementById('review-badge-' + refNum);
  if (badge) {{
    badge.textContent = checked ? 'Reviewed' : 'Not reviewed';
    badge.className = 'review-status ' + (checked ? 'satisfied' : 'not-reviewed');
  }}
}}
function saveComment(refNum, text) {{
  var r = getReview(refNum);
  r.comment = text;
  saveReview(refNum, r);
}}
function updateCardReviewState(refNum) {{
  var card = document.querySelector('[data-refnum="' + refNum + '"]');
  if (!card) return;
  var r = getReview(refNum);
  card.classList.remove('review-satisfied', 'review-flagged', 'ai-pass');
  if (r.satisfied) card.classList.add('review-satisfied');
  else if (r.comment && r.comment.trim()) card.classList.add('review-flagged');
}}
function updateProgress() {{
  var total = TOTAL_REFS;
  var reviewed = 0;
  var all = getAllReviews();
  for (var i = 1; i <= total; i++) {{
    var r = all[i];
    if (r && r.satisfied) reviewed++;
  }}
  var pct = Math.round((reviewed / total) * 100);
  document.getElementById('progressFill').style.width = pct + '%';
  document.getElementById('progressText').textContent = reviewed + ' / ' + total + ' reviewed';
}}

// ---- HIGHLIGHT ----
function highlightCitation(text, refNum) {{
  text = text.replace(/\\[([0-9,\\s]+)\\]/g, function(match, nums) {{
    var refNums = nums.split(',').map(function(n) {{ return parseInt(n.trim()); }});
    if (refNums.includes(refNum)) return '<mark>' + match + '</mark>';
    return match;
  }});
  text = text.replace(/\\[(\\d+)[\\u2013\\-](\\d+)\\]/g, function(match, start, end) {{
    var s = parseInt(start), e = parseInt(end);
    if (refNum >= s && refNum <= e) return '<mark>' + match + '</mark>';
    return match;
  }});
  return text;
}}

function getSections(refNum) {{
  var cits = CITATIONS[refNum] || [];
  var secs = [];
  cits.forEach(function(c) {{ if (secs.indexOf(c.section) === -1) secs.push(c.section); }});
  return secs;
}}

function formatRef(refText) {{
  return refText.replace(/\\*([^*]+)\\*/g, '<em>$1</em>');
}}

function formatSnippet(text) {{
  // Escape HTML angle brackets for safety
  text = text.replace(/</g, '&lt;').replace(/>/g, '&gt;');
  // Render inline LaTeX $...$ via KaTeX (balance already fixed in Python)
  if (typeof katex !== 'undefined') {{
    // Merge adjacent $expr$TEXT$expr$ into single expression
    text = text.replace(/\$([^$]+)\$([A-Za-z_/]{{1,20}})\$([^$]+)\$/g, function(m, a, mid, b) {{
      return '$' + a + '\\text{{' + mid + '}}' + b + '$';
    }});
    // Render display math $$...$$
    text = text.replace(/\$\$([^$]+)\$\$/g, function(m, expr) {{
      try {{ return katex.renderToString(expr, {{displayMode: true, throwOnError: false}}); }}
      catch(e) {{ return m; }}
    }});
    // Render inline math $...$
    text = text.replace(/\$([^$]+)\$/g, function(m, expr) {{
      try {{ return katex.renderToString(expr, {{displayMode: false, throwOnError: false}}); }}
      catch(e) {{ return m; }}
    }});
  }}
  // Convert markdown bold **text** and italic *text*
  text = text.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
  text = text.replace(/\*([^*]+)\*/g, '<em>$1</em>');
  return text;
}}

// ---- ESCAPE HTML ----
function escapeHtml(text) {{
  var div = document.createElement('div');
  div.appendChild(document.createTextNode(text));
  return div.innerHTML;
}}

// ---- RENDER ----
function renderCards() {{
  var container = document.getElementById('ref-container');
  container.innerHTML = '';
  var refNums = Object.keys(REFERENCES).map(Number).sort(function(a,b){{return a-b;}});
  refNums.forEach(function(num) {{
    var ref = REFERENCES[num];
    if (!ref) return;
    var cits = CITATIONS[num] || [];
    var sections = getSections(num);
    var isUncited = cits.length === 0;
    var review = getReview(num);
    var card = document.createElement('div');
    card.className = 'ref-card' + (isUncited ? ' uncited' : '');
    if (review.satisfied) card.classList.add('review-satisfied');
    else if (review.comment && review.comment.trim()) card.classList.add('review-flagged');
    var aiV = AI_VERDICTS[String(num)];
    if (aiV && aiV.verdict === 'flag') card.classList.add('ai-flagged');
    else if (aiV && aiV.verdict === 'warning') card.classList.add('ai-warning');
    card.dataset.refnum = String(num);
    card.dataset.sections = sections.map(function(s) {{ return s.toLowerCase(); }}).join(',');
    var searchParts = [ref.ref, ref.title, ref.authors, ref.journal, String(ref.year)];
    cits.forEach(function(c) {{ searchParts.push(c.snippet); searchParts.push(c.section); }});
    if (ABSTRACTS[num]) searchParts.push(ABSTRACTS[num]);
    cits.forEach(function(c) {{
      if (c.pdf_snippets) c.pdf_snippets.forEach(function(s) {{ searchParts.push(s); }});
    }});
    card.dataset.searchtext = searchParts.join(' ').toLowerCase();

    // Header
    var header = document.createElement('div');
    header.className = 'ref-header';
    header.onclick = (function(c) {{ return function() {{ c.classList.toggle('open'); }}; }})(card);
    var numBadge = document.createElement('div');
    numBadge.className = 'ref-num';
    numBadge.textContent = String(num);
    var info = document.createElement('div');
    info.className = 'ref-info';
    var titleDiv = document.createElement('div');
    titleDiv.className = 'ref-title';
    titleDiv.textContent = ref.title || ref.journal;
    var metaDiv = document.createElement('div');
    metaDiv.className = 'ref-meta';
    metaDiv.textContent = ref.authors + ' (' + ref.year + ') ' + ref.journal;
    info.appendChild(titleDiv);
    info.appendChild(metaDiv);
    var badges = document.createElement('div');
    badges.className = 'ref-badges';
    if (!isUncited) {{
      var countBadge = document.createElement('span');
      countBadge.className = 'badge badge-count';
      var totalInstances = 0;
      cits.forEach(function(c) {{ totalInstances += 1 + (c.also_at ? c.also_at.length : 0); }});
      countBadge.textContent = totalInstances + ' citation' + (totalInstances !== 1 ? 's' : '');
      badges.appendChild(countBadge);
      sections.forEach(function(s) {{
        var sb = document.createElement('span');
        sb.className = 'badge badge-section';
        sb.textContent = s;
        badges.appendChild(sb);
      }});
    }} else {{
      var ub = document.createElement('span');
      ub.className = 'badge badge-uncited';
      ub.textContent = 'UNCITED';
      badges.appendChild(ub);
    }}
    // AI verification badge
    var aiV = AI_VERDICTS[String(num)];
    if (aiV) {{
      var aiBadge = document.createElement('span');
      aiBadge.className = 'badge badge-ai-' + aiV.verdict;
      aiBadge.textContent = aiV.verdict === 'pass' ? 'AI: Pass' :
                             aiV.verdict === 'warning' ? 'AI: Warning' : 'AI: Flag';
      aiBadge.title = aiV.reason || '';
      badges.appendChild(aiBadge);
    }}
    var chevron = document.createElement('span');
    chevron.className = 'chevron';
    chevron.innerHTML = '&#9654;';
    header.appendChild(numBadge);
    header.appendChild(info);
    header.appendChild(badges);
    header.appendChild(chevron);
    card.appendChild(header);

    // Body
    var body = document.createElement('div');
    body.className = 'ref-body';

    // Full reference
    var fullRef = document.createElement('div');
    fullRef.className = 'ref-full';
    fullRef.innerHTML = formatRef(ref.ref);
    if (ref.doi) {{
      fullRef.innerHTML += ' <a href="https://doi.org/' + ref.doi + '" target="_blank">DOI</a>';
    }}
    body.appendChild(fullRef);

    // Citations panel
    if (cits.length > 0) {{
      var citPanel = document.createElement('div');
      citPanel.className = 'section-panel';
      var citH4 = document.createElement('h4');
      citH4.textContent = 'Where cited in manuscript';
      citPanel.appendChild(citH4);
      cits.forEach(function(c) {{
        var item = document.createElement('div');
        item.className = 'citation-item';
        var secSpan = document.createElement('span');
        secSpan.className = 'cit-section';
        secSpan.textContent = c.section;
        var lineSpan = document.createElement('span');
        lineSpan.className = 'cit-line';
        lineSpan.textContent = ' (line ' + c.line + ')';
        var textDiv = document.createElement('div');
        textDiv.className = 'cit-text';
        textDiv.innerHTML = highlightCitation(formatSnippet(c.snippet), num);
        item.appendChild(secSpan);
        item.appendChild(lineSpan);
        item.appendChild(textDiv);

        // Also cited at
        if (c.also_at && c.also_at.length > 0) {{
          var alsoDiv = document.createElement('div');
          alsoDiv.className = 'also-at';
          var parts = c.also_at.map(function(a) {{ return a.section + ' (line ' + a.line + ')'; }});
          alsoDiv.textContent = 'Also cited at: ' + parts.join(', ');
          item.appendChild(alsoDiv);
        }}

        // PDF snippets
        if (c.pdf_snippets && c.pdf_snippets.length > 0) {{
          var pdfPanel = document.createElement('div');
          pdfPanel.className = 'pdf-snippet-panel';
          var pdfLabel = document.createElement('div');
          pdfLabel.className = 'pdf-snippet-label';
          pdfLabel.textContent = 'Supporting evidence from paper:';
          pdfPanel.appendChild(pdfLabel);
          c.pdf_snippets.forEach(function(snip) {{
            var pdfDiv = document.createElement('div');
            pdfDiv.className = 'pdf-snippet';
            pdfDiv.textContent = snip;
            pdfPanel.appendChild(pdfDiv);
          }});
          item.appendChild(pdfPanel);
        }}

        citPanel.appendChild(item);
      }});
      body.appendChild(citPanel);
    }}

    // Paper info panel
    var pip = document.createElement('div');
    pip.className = 'paper-info-panel';
    pip.dataset.refnum = String(num);
    var pipHeader = document.createElement('div');
    pipHeader.className = 'paper-info-header';
    pipHeader.innerHTML = 'Abstract <span class="paper-info-chevron">&#9654;</span>';
    pipHeader.onclick = (function(p) {{ return function(e) {{ e.stopPropagation(); p.classList.toggle('open'); }}; }})(pip);
    var pipBody = document.createElement('div');
    pipBody.className = 'paper-info-body';
    var absText = ABSTRACTS[num] || '';
    pipBody.innerHTML = '<div class="info-content">' +
      (absText ? escapeHtml(absText) : '<span class="info-none">Abstract not available</span>') + '</div>';
    pip.appendChild(pipHeader);
    pip.appendChild(pipBody);
    body.appendChild(pip);

    // Review panel
    var rp = document.createElement('div');
    rp.className = 'review-panel';
    var rpHTML = '<div class="review-row">' +
      '<label class="review-checkbox-label"><input type="checkbox" id="review-check-' + num + '"' +
      (review.satisfied ? ' checked' : '') +
      ' onchange="toggleSatisfied(' + num + ', this.checked)"> Satisfied with this reference</label>' +
      '<span class="review-status ' + (review.satisfied ? 'satisfied' : 'not-reviewed') + '" id="review-badge-' + num + '">' +
      (review.satisfied ? 'Reviewed' : 'Not reviewed') + '</span></div>' +
      '<textarea class="review-comment" id="review-comment-' + num + '" placeholder="Notes or concerns..." onchange="saveComment(' + num + ', this.value)">' +
      (review.comment || '').replace(/</g, '&lt;').replace(/>/g, '&gt;') + '</textarea>';
    var aiV = AI_VERDICTS[String(num)];
    if (aiV) {{
      rpHTML += '<div style="margin-top:6px;font-size:0.82rem;padding:6px 10px;background:' +
        (aiV.verdict === 'pass' ? '#f0fff4' : aiV.verdict === 'warning' ? '#fffbeb' : '#fff5f5') +
        ';border:1px solid ' +
        (aiV.verdict === 'pass' ? '#c6f6d5' : aiV.verdict === 'warning' ? '#fefcbf' : '#fed7d7') +
        ';border-radius:4px;"><strong>AI verdict: ' + aiV.verdict.toUpperCase() + '</strong> — ' + escapeHtml(aiV.reason) + '</div>';
    }}
    rp.innerHTML = rpHTML;
    body.appendChild(rp);

    card.appendChild(body);
    container.appendChild(card);
  }});
  updateProgress();
}}

// ---- FILTER ----
var currentFilter = 'all';
var currentSearch = '';

function sectionMatchesFilter(sectionsStr, filter) {{
  if (filter === 'all') return true;
  if (filter === 'uncited') return false;
  var sLow = sectionsStr;
  // Use the hierarchy to determine which sections belong to each level-2 heading
  var filterKey = null;
  // Find the level-2 heading that matches this filter
  for (var h2 in SECTION_HIERARCHY) {{
    if (h2.toLowerCase() === filter) {{
      filterKey = h2;
      break;
    }}
  }}
  if (!filterKey) return false;
  // Check if the card's sections include the L2 heading or any of its children
  if (sLow.indexOf(filterKey.toLowerCase()) !== -1) return true;
  var children = SECTION_HIERARCHY[filterKey] || [];
  for (var i = 0; i < children.length; i++) {{
    if (sLow.indexOf(children[i].toLowerCase()) !== -1) return true;
  }}
  return false;
}}

function applyFilters() {{
  var cards = document.querySelectorAll('.ref-card');
  var searchLow = currentSearch.toLowerCase();
  cards.forEach(function(card) {{
    var show = true;
    if (currentFilter === 'uncited') {{
      show = card.classList.contains('uncited');
    }} else if (currentFilter !== 'all') {{
      show = sectionMatchesFilter(card.dataset.sections || '', currentFilter);
    }}
    if (show && searchLow) {{
      show = (card.dataset.searchtext || '').indexOf(searchLow) !== -1;
    }}
    card.style.display = show ? '' : 'none';
  }});
}}

document.getElementById('searchBox').addEventListener('input', function() {{
  currentSearch = this.value;
  applyFilters();
}});

document.querySelectorAll('.filter-btn').forEach(function(btn) {{
  btn.addEventListener('click', function() {{
    document.querySelectorAll('.filter-btn').forEach(function(b) {{ b.classList.remove('active'); }});
    this.classList.add('active');
    currentFilter = this.dataset.filter;
    applyFilters();
  }});
}});

// ---- EXPAND/COLLAPSE ----
function expandAll() {{
  document.querySelectorAll('.ref-card').forEach(function(c) {{
    if (c.style.display !== 'none') c.classList.add('open');
  }});
}}
function collapseAll() {{
  document.querySelectorAll('.ref-card').forEach(function(c) {{ c.classList.remove('open'); }});
}}
function expandAllPaperInfo() {{
  document.querySelectorAll('.paper-info-panel').forEach(function(p) {{ p.classList.add('open'); }});
}}
function collapseAllPaperInfo() {{
  document.querySelectorAll('.paper-info-panel').forEach(function(p) {{ p.classList.remove('open'); }});
}}

// ---- REVIEW FILTER ----
function filterByReviewStatus(status) {{
  document.querySelectorAll('.filter-btn').forEach(function(b) {{ b.classList.remove('active'); }});
  document.querySelector('[data-filter="all"]').classList.add('active');
  currentFilter = 'all';
  currentSearch = '';
  document.getElementById('searchBox').value = '';
  var cards = document.querySelectorAll('.ref-card');
  cards.forEach(function(card) {{
    var refNum = parseInt(card.dataset.refnum);
    var r = getReview(refNum);
    if (status === 'all') {{
      card.style.display = '';
    }} else if (status === 'flagged') {{
      card.style.display = (r.comment && r.comment.trim() && !r.satisfied) ? '' : 'none';
    }} else if (status === 'unreviewed') {{
      card.style.display = (!r.satisfied) ? '' : 'none';
    }} else if (status === 'ai-flagged') {{
      var aiV = AI_VERDICTS[String(refNum)];
      card.style.display = (aiV && (aiV.verdict === 'flag' || aiV.verdict === 'warning')) ? '' : 'none';
    }} else if (status === 'ai-unverified') {{
      card.style.display = (!AI_VERDICTS[String(refNum)]) ? '' : 'none';
    }}
  }});
}}

// ---- COMPILE CONCERNS ----
function compileConcerns() {{
  var text = buildConcernsText();
  document.getElementById('concernsText').textContent = text;
  document.getElementById('modalOverlay').classList.add('open');
}}
function closeModal() {{
  document.getElementById('modalOverlay').classList.remove('open');
}}
function buildConcernsText() {{
  var lines = ['MANUSCRIPT REFERENCE CONCERNS', '============================', ''];
  var flagged = [], unreviewed = [];
  var refNums = Object.keys(REFERENCES).map(Number).sort(function(a,b){{return a-b;}});
  refNums.forEach(function(i) {{
    var r = getReview(i);
    var ref = REFERENCES[i];
    if (!ref) return;
    if (r.comment && r.comment.trim() && !r.satisfied) {{
      flagged.push({{ num: i, ref: ref, review: r }});
    }}
    if (!r.satisfied) {{
      unreviewed.push({{ num: i, ref: ref, review: r }});
    }}
  }});
  lines.push('FLAGGED (' + flagged.length + '):');
  lines.push('---');
  flagged.forEach(function(f) {{
    lines.push('[' + f.num + '] ' + f.ref.authors + ' (' + f.ref.year + ')');
    lines.push('    ' + (f.ref.title || f.ref.journal));
    lines.push('    Comment: ' + f.review.comment);
    lines.push('');
  }});
  lines.push('');
  lines.push('UNREVIEWED (' + unreviewed.length + '):');
  lines.push('---');
  unreviewed.forEach(function(u) {{
    lines.push('[' + u.num + '] ' + u.ref.authors + ' (' + u.ref.year + ') - ' + (u.ref.title || u.ref.journal));
  }});
  return lines.join('\\n');
}}
function copyConcernsToClipboard() {{
  var text = buildConcernsText();
  navigator.clipboard.writeText(text).then(function() {{ alert('Copied to clipboard!'); }});
}}
function downloadConcerns() {{
  var text = buildConcernsText();
  var blob = new Blob([text], {{ type: 'text/plain' }});
  var a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = 'reference_concerns.txt';
  a.click();
  URL.revokeObjectURL(a.href);
}}
function clearAllReviews() {{
  if (!confirm('Reset all review states? This cannot be undone.')) return;
  localStorage.removeItem(STORAGE_KEY);
  renderCards();
}}

// ---- SAVE/LOAD STATE ----
function saveStateToFile() {{
  var data = getAllReviews();
  // Merge AI verdicts into state
  for (var refNum in AI_VERDICTS) {{
    if (!data[refNum]) data[refNum] = {{ satisfied: false, comment: '' }};
    data[refNum].claude_verdict = AI_VERDICTS[refNum].verdict;
    data[refNum].claude_reason = AI_VERDICTS[refNum].reason;
  }}
  var wrapper = {{ version: 3, savedAt: new Date().toISOString(), reviews: data }};
  var blob = new Blob([JSON.stringify(wrapper, null, 2)], {{ type: 'application/json' }});
  var a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = STATE_FILENAME;
  a.click();
  URL.revokeObjectURL(a.href);
}}
function loadStateFromFile(input) {{
  var file = input.files[0];
  if (!file) return;
  var reader = new FileReader();
  reader.onload = function(e) {{
    try {{
      var raw = JSON.parse(e.target.result);
      var data = raw.reviews || raw;  // Handle both v3 wrapper and bare dict
      localStorage.setItem(STORAGE_KEY, JSON.stringify(data));
      renderCards();
          alert('State loaded successfully!');
    }} catch(err) {{
      alert('Error loading state file: ' + err.message);
    }}
  }};
  reader.readAsText(file);
  input.value = '';
}}
function autoLoadState() {{
  updateProgress();
}}

// ---- INIT ----
renderCards();
autoLoadState();
</script>
</body>
</html>'''

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html, encoding='utf-8')


def _escape_html(text: str) -> str:
    """Escape HTML special characters."""
    return (text
            .replace('&', '&amp;')
            .replace('<', '&lt;')
            .replace('>', '&gt;')
            .replace('"', '&quot;')
            .replace("'", '&#39;'))
