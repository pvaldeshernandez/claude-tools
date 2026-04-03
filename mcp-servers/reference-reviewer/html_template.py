"""CSS and JS template constants for the reference viewer HTML."""

CSS_TEMPLATE = """  * { box-sizing: border-box; margin: 0; padding: 0; }
  body {
    font-family: 'Segoe UI', system-ui, -apple-system, sans-serif;
    background: #f5f5f5;
    color: #333;
    line-height: 1.6;
    padding: 20px;
  }
  .header {
    background: linear-gradient(135deg, #1a365d 0%, #2a4a7f 100%);
    color: white;
    padding: 30px;
    border-radius: 12px;
    margin-bottom: 24px;
    box-shadow: 0 4px 6px rgba(0,0,0,0.1);
  }
  .header h1 { font-size: 1.5em; margin-bottom: 8px; }
  .header p { opacity: 0.85; font-size: 0.95em; }
  .stats {
    display: flex;
    gap: 16px;
    margin-top: 16px;
    flex-wrap: wrap;
  }
  .stat-box {
    background: rgba(255,255,255,0.15);
    padding: 8px 16px;
    border-radius: 8px;
    font-size: 0.9em;
  }
  .stat-box strong { font-size: 1.3em; }
  .controls {
    display: flex;
    gap: 12px;
    margin-bottom: 20px;
    flex-wrap: wrap;
    align-items: center;
  }
  .search-box {
    flex: 1;
    min-width: 250px;
    padding: 10px 16px;
    border: 2px solid #ddd;
    border-radius: 8px;
    font-size: 1em;
    transition: border-color 0.2s;
  }
  .search-box:focus { border-color: #2a4a7f; outline: none; }
  .filter-btn {
    padding: 8px 16px;
    border: 2px solid #ddd;
    background: white;
    border-radius: 8px;
    cursor: pointer;
    font-size: 0.9em;
    transition: all 0.2s;
  }
  .filter-btn:hover { border-color: #2a4a7f; background: #f0f4ff; }
  .filter-btn.active { border-color: #2a4a7f; background: #2a4a7f; color: white; }
  .ref-card {
    background: white;
    border-radius: 10px;
    margin-bottom: 12px;
    box-shadow: 0 1px 3px rgba(0,0,0,0.08);
    overflow: hidden;
    transition: box-shadow 0.2s;
  }
  .ref-card:hover { box-shadow: 0 2px 8px rgba(0,0,0,0.12); }
  .ref-card.uncited { border-left: 4px solid #e53e3e; }
  .ref-card.warning { border-left: 4px solid #dd6b20; }
  .ref-header {
    padding: 16px 20px;
    cursor: pointer;
    display: flex;
    align-items: flex-start;
    gap: 12px;
    user-select: none;
  }
  .ref-header:hover { background: #f8f9fa; }
  .ref-num {
    background: #2a4a7f;
    color: white;
    min-width: 36px;
    height: 36px;
    border-radius: 8px;
    display: flex;
    align-items: center;
    justify-content: center;
    font-weight: bold;
    font-size: 0.9em;
    flex-shrink: 0;
  }
  .ref-num.uncited { background: #e53e3e; }
  .ref-info { flex: 1; }
  .ref-title {
    font-weight: 600;
    color: #1a365d;
    margin-bottom: 4px;
  }
  .ref-meta {
    font-size: 0.85em;
    color: #666;
  }
  .ref-badges {
    display: flex;
    gap: 6px;
    flex-wrap: wrap;
    margin-top: 4px;
  }
  .badge {
    font-size: 0.75em;
    padding: 2px 8px;
    border-radius: 12px;
    font-weight: 500;
  }
  .badge-section { background: #e2e8f0; color: #4a5568; }
  .badge-count { background: #bee3f8; color: #2a4a7f; }
  .badge-uncited { background: #fed7d7; color: #c53030; }
  .chevron {
    font-size: 1.2em;
    color: #999;
    transition: transform 0.3s;
    flex-shrink: 0;
    margin-top: 8px;
  }
  .ref-card.open .chevron { transform: rotate(180deg); }
  .ref-body {
    display: none;
    border-top: 1px solid #eee;
  }
  .ref-card.open .ref-body { display: block; }
  .section-panel {
    padding: 16px 20px;
    border-bottom: 1px solid #f0f0f0;
  }
  .section-panel:last-child { border-bottom: none; }
  .section-label {
    font-size: 0.8em;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    color: #888;
    font-weight: 600;
    margin-bottom: 8px;
  }
  .paper-info-panel {
    border-top: 1px solid #eee;
  }
  .paper-info-header {
    display: flex;
    align-items: center;
    gap: 8px;
    cursor: pointer;
    color: #2a4a7f;
    font-weight: 600;
    font-size: 0.95em;
    padding: 14px 20px;
    background: #f0f4ff;
    user-select: none;
    border-bottom: 1px solid #e2e8f0;
  }
  .paper-info-header:hover { background: #e2ecff; }
  .paper-info-header .arrow {
    transition: transform 0.3s;
    font-size: 0.8em;
  }
  .paper-info-header.open .arrow { transform: rotate(90deg); }
  .paper-info-body {
    display: none;
  }
  .paper-info-body.show { display: block; }
  .sub-section {
    padding: 14px 20px;
    border-bottom: 1px solid #f0f0f0;
  }
  .sub-section:last-child { border-bottom: none; }
  .sub-section-label {
    font-size: 0.8em;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    color: #2a4a7f;
    font-weight: 700;
    margin-bottom: 8px;
  }
  .sub-section-content {
    font-size: 0.9em;
    line-height: 1.7;
    color: #444;
    text-align: justify;
  }
  .sub-section-content.unavailable {
    color: #999;
    font-style: italic;
    text-align: left;
  }
  .citation-item {
    margin-bottom: 10px;
    padding: 10px 14px;
    background: #f8f9fa;
    border-radius: 6px;
    border-left: 3px solid #cbd5e0;
    font-size: 0.9em;
  }
  .citation-item:last-child { margin-bottom: 0; }
  .citation-section {
    font-size: 0.75em;
    color: #888;
    margin-bottom: 4px;
    text-transform: uppercase;
    letter-spacing: 0.3px;
  }
  .citation-text { color: #333; }
  .citation-text mark {
    background: #fefcbf;
    padding: 0 2px;
    border-radius: 2px;
  }
  .line-num {
    font-size: 0.75em;
    color: #aaa;
    margin-left: 6px;
  }
  .expand-all-bar {
    display: flex;
    gap: 8px;
    margin-bottom: 16px;
    justify-content: flex-end;
  }
  .expand-btn {
    padding: 6px 14px;
    border: 1px solid #ccc;
    background: white;
    border-radius: 6px;
    cursor: pointer;
    font-size: 0.85em;
  }
  .expand-btn:hover { background: #f0f4ff; border-color: #2a4a7f; }
  .hidden { display: none !important; }
  /* Review UI */
  .review-panel {
    padding: 14px 20px;
    background: #fffbf0;
    border-top: 2px solid #f0e6cc;
  }
  .review-row {
    display: flex;
    align-items: center;
    gap: 12px;
    margin-bottom: 8px;
  }
  .review-checkbox-label {
    display: flex;
    align-items: center;
    gap: 6px;
    cursor: pointer;
    font-size: 0.9em;
    font-weight: 600;
    user-select: none;
  }
  .review-checkbox-label input[type="checkbox"] {
    width: 18px;
    height: 18px;
    accent-color: #38a169;
    cursor: pointer;
  }
  .review-status {
    font-size: 0.8em;
    padding: 2px 10px;
    border-radius: 10px;
    font-weight: 600;
  }
  .review-status.satisfied { background: #c6f6d5; color: #276749; }
  .review-status.needs-review { background: #fed7d7; color: #c53030; }
  .review-comment-box {
    width: 100%;
    min-height: 50px;
    padding: 8px 12px;
    border: 1px solid #ddd;
    border-radius: 6px;
    font-size: 0.85em;
    font-family: inherit;
    resize: vertical;
    line-height: 1.5;
  }
  .review-comment-box:focus { border-color: #dd6b20; outline: none; }
  .review-comment-box::placeholder { color: #bbb; }
  .ref-card.review-satisfied { border-left: 4px solid #38a169; }
  .ref-card.review-flagged { border-left: 4px solid #dd6b20; }
  /* Compile bar */
  .compile-bar {
    background: white;
    border-radius: 10px;
    padding: 16px 20px;
    margin-bottom: 16px;
    box-shadow: 0 1px 3px rgba(0,0,0,0.08);
    display: flex;
    gap: 12px;
    align-items: center;
    flex-wrap: wrap;
  }
  .compile-btn {
    padding: 10px 20px;
    border: none;
    border-radius: 8px;
    cursor: pointer;
    font-size: 0.9em;
    font-weight: 600;
    transition: all 0.2s;
  }
  .compile-btn.primary { background: #dd6b20; color: white; }
  .compile-btn.primary:hover { background: #c05621; }
  .compile-btn.secondary { background: #e2e8f0; color: #4a5568; }
  .compile-btn.secondary:hover { background: #cbd5e0; }
  .compile-btn.danger { background: #fed7d7; color: #c53030; }
  .compile-btn.danger:hover { background: #feb2b2; }
  .review-progress {
    flex: 1;
    min-width: 200px;
    display: flex;
    align-items: center;
    gap: 10px;
  }
  .progress-bar-outer {
    flex: 1;
    height: 8px;
    background: #e2e8f0;
    border-radius: 4px;
    overflow: hidden;
  }
  .progress-bar-inner {
    height: 100%;
    background: linear-gradient(90deg, #38a169, #48bb78);
    border-radius: 4px;
    transition: width 0.3s;
  }
  .progress-text { font-size: 0.85em; color: #666; white-space: nowrap; }
  /* Concerns modal */
  .modal-overlay {
    display: none;
    position: fixed;
    top: 0; left: 0; right: 0; bottom: 0;
    background: rgba(0,0,0,0.5);
    z-index: 1000;
    justify-content: center;
    align-items: center;
  }
  .modal-overlay.show { display: flex; }
  .modal-content {
    background: white;
    border-radius: 12px;
    max-width: 800px;
    width: 90%;
    max-height: 80vh;
    overflow-y: auto;
    box-shadow: 0 20px 60px rgba(0,0,0,0.3);
  }
  .modal-header {
    padding: 20px 24px;
    background: #dd6b20;
    color: white;
    border-radius: 12px 12px 0 0;
    display: flex;
    justify-content: space-between;
    align-items: center;
  }
  .modal-header h2 { font-size: 1.2em; }
  .modal-close {
    background: none;
    border: none;
    color: white;
    font-size: 1.5em;
    cursor: pointer;
    padding: 0 4px;
  }
  .modal-body { padding: 20px 24px; }
  .concern-item {
    padding: 12px 0;
    border-bottom: 1px solid #eee;
  }
  .concern-item:last-child { border-bottom: none; }
  .concern-ref-title { font-weight: 600; color: #1a365d; margin-bottom: 4px; }
  .concern-comment { font-size: 0.9em; color: #555; line-height: 1.5; }
  .modal-footer {
    padding: 16px 24px;
    border-top: 1px solid #eee;
    display: flex;
    gap: 10px;
    justify-content: flex-end;
  }
  .no-concerns { color: #888; font-style: italic; padding: 20px 0; text-align: center; }
  .doi-link {
    color: #2a4a7f;
    text-decoration: none;
    font-size: 0.8em;
  }
  .doi-link:hover { text-decoration: underline; }
  .full-ref {
    font-size: 0.85em;
    color: #555;
    padding: 12px 20px;
    background: #fafbfc;
    border-bottom: 1px solid #eee;
    line-height: 1.5;
  }
  /* AI Verification UI */
  .ai-review-row {
    display: flex;
    align-items: flex-start;
    gap: 10px;
    margin-top: 10px;
    padding: 10px 0 0 0;
    border-top: 1px dashed #e2e8f0;
  }
  .ai-badge {
    font-size: 0.75em;
    padding: 2px 10px;
    border-radius: 10px;
    font-weight: 600;
    white-space: nowrap;
    flex-shrink: 0;
  }
  .ai-badge.pass { background: #bee3f8; color: #2a4a7f; }
  .ai-badge.warning { background: #fefcbf; color: #975a16; }
  .ai-badge.flag { background: #fed7d7; color: #c53030; }
  .ai-badge.pending { background: #e2e8f0; color: #718096; }
  .ai-reason {
    font-size: 0.85em;
    color: #555;
    line-height: 1.5;
    flex: 1;
  }
  .ai-timestamp {
    font-size: 0.75em;
    color: #aaa;
    white-space: nowrap;
  }
  .ref-card.ai-verified { border-right: 4px solid #3182ce; }
  .ref-card.ai-flagged { border-right: 4px solid #e53e3e; }
  .ref-card.ai-warning { border-right: 4px solid #dd6b20; }
  .badge-ai-verified { background: #bee3f8; color: #2a4a7f; }
  .badge-ai-warning { background: #fefcbf; color: #975a16; }
  .badge-ai-flag { background: #fed7d7; color: #c53030; }"""


JS_TEMPLATE = r"""// ===== RENDERING =====
const container = document.getElementById('ref-container');

function highlightCitation(text, refNum) {
  // Highlight the [N] or [N,M,...] bracket containing this ref number
  return text.replace(/\[([0-9,\s]+)\]/g, (match, nums) => {
    const refNums = nums.split(',').map(n => parseInt(n.trim()));
    if (refNums.includes(refNum)) {
      return `<mark>${match}</mark>`;
    }
    return match;
  });
}

function getSections(refNum) {
  const cits = CITATIONS[refNum] || [];
  const sections = [...new Set(cits.map(c => c.section))];
  return sections;
}

function getAIVerification(refNum) {
  const reviews = getAllReviews();
  const review = reviews[refNum] || {};
  return {
    verified: review.claude_verified || false,
    verdict: review.claude_verdict || null,
    reason: review.claude_reason || '',
    timestamp: review.claude_timestamp || null,
  };
}

function renderCards() {
  container.innerHTML = '';
  const refNums = Object.keys(REFERENCES).map(Number).sort((a,b) => a-b);

  for (const num of refNums) {
    const ref = REFERENCES[num];
    const cits = CITATIONS[num] || [];
    const sections = getSections(num);
    const isUncited = cits.length === 0;
    const abstract = ABSTRACTS[num] || "Could not fetch the abstract.";
    const aiVerif = getAIVerification(num);

    const card = document.createElement('div');
    card.className = `ref-card${isUncited ? ' uncited' : ''}`;
    card.dataset.refnum = num;
    card.dataset.sections = sections.join(',').toLowerCase();
    const pSnippet = PAPER_SNIPPETS[num] || '';
    card.dataset.searchtext = `${ref.ref} ${ref.title} ${abstract} ${pSnippet} ${cits.map(c=>c.snippet).join(' ')}`.toLowerCase();

    // Apply AI verification styling to card
    if (aiVerif.verified) {
      if (aiVerif.verdict === 'pass') card.classList.add('ai-verified');
      else if (aiVerif.verdict === 'flag') card.classList.add('ai-flagged');
      else if (aiVerif.verdict === 'warning') card.classList.add('ai-warning');
    }

    // Header
    const header = document.createElement('div');
    header.className = 'ref-header';
    header.onclick = () => card.classList.toggle('open');

    const badges = sections.map(s => `<span class="badge badge-section">${s}</span>`).join('');
    const countBadge = `<span class="badge badge-count">${cits.length} citation${cits.length !== 1 ? 's' : ''}</span>`;
    const uncitedBadge = isUncited ? '<span class="badge badge-uncited">UNCITED</span>' : '';

    // AI badge in header
    let aiBadgeHtml = '';
    if (aiVerif.verified) {
      const verdictLabels = { pass: 'AI Verified', warning: 'AI Warning', flag: 'AI Flagged' };
      const badgeClass = { pass: 'badge-ai-verified', warning: 'badge-ai-warning', flag: 'badge-ai-flag' };
      aiBadgeHtml = `<span class="badge ${badgeClass[aiVerif.verdict] || ''}">${verdictLabels[aiVerif.verdict] || 'AI Checked'}</span>`;
    }

    header.innerHTML = `
      <div class="ref-num${isUncited ? ' uncited' : ''}">${num}</div>
      <div class="ref-info">
        <div class="ref-title">${ref.title}</div>
        <div class="ref-meta">${ref.authors} (${ref.year}) &mdash; ${ref.journal}</div>
        <div class="ref-badges">${countBadge} ${uncitedBadge} ${aiBadgeHtml} ${badges}</div>
      </div>
      <span class="chevron">&#9660;</span>
    `;
    card.appendChild(header);

    // Body
    const body = document.createElement('div');
    body.className = 'ref-body';

    // Full reference
    body.innerHTML += `<div class="full-ref">${ref.ref} <a class="doi-link" href="https://doi.org/${ref.doi}" target="_blank">doi:${ref.doi}</a></div>`;

    // === SECTION 1: Where cited in manuscript (FIRST) ===
    if (cits.length > 0) {
      const citPanel = document.createElement('div');
      citPanel.className = 'section-panel';
      citPanel.innerHTML = `<div class="section-label">Where cited in manuscript (${cits.length})</div>`;

      for (const cit of cits) {
        const citItem = document.createElement('div');
        citItem.className = 'citation-item';
        citItem.innerHTML = `
          <div class="citation-section">${cit.section} <span class="line-num">line ${cit.line}</span></div>
          <div class="citation-text">${highlightCitation(cit.snippet, num)}</div>
        `;
        citPanel.appendChild(citItem);
      }
      body.appendChild(citPanel);
    } else {
      const citPanel = document.createElement('div');
      citPanel.className = 'section-panel';
      citPanel.innerHTML = `<div class="section-label" style="color:#e53e3e;">This reference is not cited anywhere in the manuscript text</div>`;
      body.appendChild(citPanel);
    }

    // === SECTION 2: Paper info (collapsible: Abstract + Paper Snippets) ===
    const paperSnippet = PAPER_SNIPPETS[num] || null;
    const paperInfoPanel = document.createElement('div');
    paperInfoPanel.className = 'paper-info-panel';
    paperInfoPanel.innerHTML = `
      <div class="paper-info-header" onclick="this.classList.toggle('open'); this.nextElementSibling.classList.toggle('show');">
        <span class="arrow">&#9654;</span> Reference Info (Abstract &amp; Supporting Evidence)
      </div>
      <div class="paper-info-body">
        <div class="sub-section">
          <div class="sub-section-label">Abstract</div>
          <div class="sub-section-content">${abstract}</div>
        </div>
        <div class="sub-section">
          <div class="sub-section-label">Relevant passages from the full document</div>
          <div class="sub-section-content${paperSnippet ? '' : ' unavailable'}">${paperSnippet || 'Full document not available.'}</div>
        </div>
      </div>
    `;
    body.appendChild(paperInfoPanel);

    // === SECTION 3: Review panel ===
    const reviewPanel = document.createElement('div');
    reviewPanel.className = 'review-panel';
    const savedReview = getReview(num);
    let aiReviewHtml = '';
    if (aiVerif.verified) {
      const verdictLabels = { pass: 'PASS', warning: 'WARNING', flag: 'FLAG' };
      const verdictClass = aiVerif.verdict || 'pending';
      const ts = aiVerif.timestamp ? new Date(aiVerif.timestamp).toLocaleDateString() : '';
      aiReviewHtml = `
        <div class="ai-review-row">
          <span class="ai-badge ${verdictClass}">${verdictLabels[aiVerif.verdict] || 'CHECKED'}</span>
          <span class="ai-reason">${aiVerif.reason}</span>
          <span class="ai-timestamp">${ts}</span>
        </div>
      `;
    } else {
      aiReviewHtml = `
        <div class="ai-review-row">
          <span class="ai-badge pending">NOT VERIFIED</span>
          <span class="ai-reason" style="color:#aaa;">AI verification has not been run for this reference.</span>
        </div>
      `;
    }
    reviewPanel.innerHTML = `
      <div class="review-row">
        <label class="review-checkbox-label">
          <input type="checkbox" id="review-check-${num}" ${savedReview.satisfied ? 'checked' : ''}
            onchange="toggleSatisfied(${num}, this.checked)">
          Satisfied with this reference
        </label>
        <span class="review-status ${savedReview.satisfied ? 'satisfied' : (savedReview.comment ? 'needs-review' : '')}" id="review-badge-${num}">
          ${savedReview.satisfied ? 'Verified' : (savedReview.comment ? 'Flagged' : '')}
        </span>
      </div>
      <textarea class="review-comment-box" id="review-comment-${num}"
        placeholder="Note any concerns about this reference (e.g., abstract mismatch, claim not supported, wrong citation context...)"
        oninput="saveComment(${num}, this.value)">${savedReview.comment || ''}</textarea>
      ${aiReviewHtml}
    `;
    body.appendChild(reviewPanel);

    // Apply review styling to card
    if (savedReview.satisfied) {
      card.classList.add('review-satisfied');
    } else if (savedReview.comment) {
      card.classList.add('review-flagged');
    }

    card.appendChild(body);
    container.appendChild(card);
  }
  updateProgress();
}

// ===== SEARCH & FILTER =====
const searchBox = document.getElementById('searchBox');
searchBox.addEventListener('input', applyFilters);

document.querySelectorAll('.filter-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    applyFilters();
  });
});

function applyFilters() {
  const query = searchBox.value.toLowerCase();
  const filter = document.querySelector('.filter-btn.active').dataset.filter;

  document.querySelectorAll('.ref-card').forEach(card => {
    let show = true;

    // Text search
    if (query && !card.dataset.searchtext.includes(query)) {
      show = false;
    }

    // Section filter
    if (filter === 'uncited') {
      show = show && card.classList.contains('uncited');
    } else if (filter === 'intro') {
      show = show && card.dataset.sections.includes('introduction');
    } else if (filter === 'methods') {
      show = show && (card.dataset.sections.includes('analysis') || card.dataset.sections.includes('participants') || card.dataset.sections.includes('freesurfer') || card.dataset.sections.includes('biopsychosocial') || card.dataset.sections.includes('moderation') || card.dataset.sections.includes('vertex'));
    } else if (filter === 'discussion') {
      show = show && card.dataset.sections.includes('discussion');
    }

    card.classList.toggle('hidden', !show);
  });
}

function expandAll() {
  document.querySelectorAll('.ref-card:not(.hidden)').forEach(c => c.classList.add('open'));
}
function collapseAll() {
  document.querySelectorAll('.ref-card').forEach(c => c.classList.remove('open'));
}
function expandAllPaperInfo() {
  document.querySelectorAll('.ref-card:not(.hidden) .paper-info-header').forEach(t => {
    t.classList.add('open');
    t.nextElementSibling.classList.add('show');
  });
}
function collapseAllPaperInfo() {
  document.querySelectorAll('.paper-info-header').forEach(t => {
    t.classList.remove('open');
    t.nextElementSibling.classList.remove('show');
  });
}

// ===== REVIEW PERSISTENCE (localStorage) =====
const STORAGE_KEY = 'manuscript_ref_reviews_v2';

function getAllReviews() {
  try {
    return JSON.parse(localStorage.getItem(STORAGE_KEY)) || {};
  } catch { return {}; }
}

function getReview(refNum) {
  const reviews = getAllReviews();
  return reviews[refNum] || { satisfied: false, comment: '' };
}

function saveReview(refNum, data) {
  const reviews = getAllReviews();
  reviews[refNum] = data;
  localStorage.setItem(STORAGE_KEY, JSON.stringify(reviews));
}

function toggleSatisfied(refNum, checked) {
  const review = getReview(refNum);
  review.satisfied = checked;
  saveReview(refNum, review);

  // Update badge
  const badge = document.getElementById(`review-badge-${refNum}`);
  badge.className = `review-status ${checked ? 'satisfied' : (review.comment ? 'needs-review' : '')}`;
  badge.textContent = checked ? 'Verified' : (review.comment ? 'Flagged' : '');

  // Update card border
  const card = document.querySelector(`.ref-card[data-refnum="${refNum}"]`);
  card.classList.remove('review-satisfied', 'review-flagged');
  if (checked) {
    card.classList.add('review-satisfied');
  } else if (review.comment) {
    card.classList.add('review-flagged');
  }

  updateProgress();
}

function saveComment(refNum, text) {
  const review = getReview(refNum);
  review.comment = text;
  saveReview(refNum, review);

  // Update badge if not satisfied
  if (!review.satisfied) {
    const badge = document.getElementById(`review-badge-${refNum}`);
    badge.className = `review-status ${text ? 'needs-review' : ''}`;
    badge.textContent = text ? 'Flagged' : '';

    const card = document.querySelector(`.ref-card[data-refnum="${refNum}"]`);
    card.classList.remove('review-flagged');
    if (text) card.classList.add('review-flagged');
  }
}

function updateProgress() {
  const reviews = getAllReviews();
  const total = Object.keys(REFERENCES).length;
  const reviewed = Object.values(reviews).filter(r => r.satisfied).length;
  const aiVerified = Object.values(reviews).filter(r => r.claude_verified).length;
  const pct = Math.round((reviewed / total) * 100);

  let progressLabel = `${reviewed} / ${total} reviewed`;
  if (aiVerified > 0) {
    progressLabel += ` | ${aiVerified} AI verified`;
  }
  document.getElementById('progressText').textContent = progressLabel;
  document.getElementById('progressBar').style.width = `${pct}%`;
}

// ===== FILTER BY REVIEW STATUS =====
function filterByReviewStatus(status) {
  // Reset section filter buttons
  document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
  document.querySelector('.filter-btn[data-filter="all"]').classList.add('active');
  searchBox.value = '';

  const reviews = getAllReviews();

  document.querySelectorAll('.ref-card').forEach(card => {
    const num = parseInt(card.dataset.refnum);
    const review = reviews[num] || { satisfied: false, comment: '' };

    if (status === 'all') {
      card.classList.remove('hidden');
    } else if (status === 'flagged') {
      card.classList.toggle('hidden', !(!review.satisfied && review.comment));
    } else if (status === 'unreviewed') {
      card.classList.toggle('hidden', review.satisfied);
    } else if (status === 'ai-flagged') {
      const isFlagged = review.claude_verified && (review.claude_verdict === 'flag' || review.claude_verdict === 'warning');
      card.classList.toggle('hidden', !isFlagged);
    } else if (status === 'ai-unverified') {
      card.classList.toggle('hidden', !!review.claude_verified);
    }
  });
}

// ===== COMPILE CONCERNS =====
function compileConcerns() {
  const reviews = getAllReviews();
  const body = document.getElementById('concernsBody');
  body.innerHTML = '';

  const flagged = Object.entries(reviews)
    .filter(([num, r]) => !r.satisfied && r.comment)
    .sort(([a], [b]) => parseInt(a) - parseInt(b));

  const unsatisfiedNoComment = Object.keys(REFERENCES)
    .map(Number)
    .filter(num => {
      const r = reviews[num];
      return !r || !r.satisfied;
    })
    .filter(num => {
      const r = reviews[num];
      return !r || !r.comment;
    });

  if (flagged.length === 0 && unsatisfiedNoComment.length === 0) {
    body.innerHTML = '<div class="no-concerns">All references have been reviewed and marked as satisfied.</div>';
  } else {
    if (flagged.length > 0) {
      const h3 = document.createElement('h3');
      h3.style.cssText = 'margin-bottom:12px; color:#c53030;';
      h3.textContent = `Flagged references with comments (${flagged.length})`;
      body.appendChild(h3);

      for (const [num, review] of flagged) {
        const ref = REFERENCES[num];
        const item = document.createElement('div');
        item.className = 'concern-item';
        item.innerHTML = `
          <div class="concern-ref-title">[${num}] ${ref.title} (${ref.authors}, ${ref.year})</div>
          <div class="concern-comment">${review.comment.replace(/\n/g, '<br>')}</div>
        `;
        body.appendChild(item);
      }
    }

    if (unsatisfiedNoComment.length > 0) {
      const h3 = document.createElement('h3');
      h3.style.cssText = 'margin: 16px 0 8px 0; color:#666;';
      h3.textContent = `Unreviewed references (${unsatisfiedNoComment.length})`;
      body.appendChild(h3);
      const list = document.createElement('div');
      list.style.cssText = 'font-size:0.9em; color:#888; line-height:1.8;';
      list.textContent = unsatisfiedNoComment.map(n => `[${n}]`).join(', ');
      body.appendChild(list);
    }
  }

  document.getElementById('concernsModal').classList.add('show');
}

function closeModal() {
  document.getElementById('concernsModal').classList.remove('show');
}

function buildConcernsText() {
  const reviews = getAllReviews();
  const total = Object.keys(REFERENCES).length;
  const satisfied = Object.values(reviews).filter(r => r.satisfied).length;

  let text = `REFERENCE REVIEW CONCERNS\n`;
  text += `========================\n`;
  text += `Date: ${new Date().toLocaleString()}\n`;
  text += `Progress: ${satisfied}/${total} references verified\n\n`;

  const flagged = Object.entries(reviews)
    .filter(([num, r]) => !r.satisfied && r.comment)
    .sort(([a], [b]) => parseInt(a) - parseInt(b));

  if (flagged.length > 0) {
    text += `FLAGGED REFERENCES (${flagged.length}):\n`;
    text += `${'─'.repeat(40)}\n`;
    for (const [num, review] of flagged) {
      const ref = REFERENCES[num];
      text += `\n[${num}] ${ref.authors} (${ref.year}). ${ref.title}.\n`;
      text += `    Journal: ${ref.journal}\n`;
      text += `    Concern: ${review.comment}\n`;
    }
  }

  const unreviewed = Object.keys(REFERENCES)
    .map(Number)
    .filter(num => {
      const r = reviews[num];
      return !r || !r.satisfied;
    })
    .filter(num => {
      const r = reviews[num];
      return !r || !r.comment;
    });

  if (unreviewed.length > 0) {
    text += `\nUNREVIEWED REFERENCES (${unreviewed.length}):\n`;
    text += unreviewed.map(n => `[${n}]`).join(', ') + '\n';
  }

  return text;
}

function copyConcernsToClipboard() {
  navigator.clipboard.writeText(buildConcernsText()).then(() => {
    alert('Concerns copied to clipboard.');
  });
}

function downloadConcerns() {
  const text = buildConcernsText();
  const blob = new Blob([text], { type: 'text/plain' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `reference_concerns_${new Date().toISOString().slice(0,10)}.txt`;
  a.click();
  URL.revokeObjectURL(url);
}

function clearAllReviews() {
  if (confirm('This will reset ALL review checkboxes and comments. Are you sure?')) {
    localStorage.removeItem(STORAGE_KEY);
    renderCards();
  }
}

// ===== SAVE / LOAD STATE TO FILE =====
const STATE_FILENAME = 'ref_review_state.json';

function saveStateToFile() {
  const reviews = getAllReviews();
  const data = {
    version: 2,
    savedAt: new Date().toISOString(),
    reviews: reviews
  };
  const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = STATE_FILENAME;
  a.click();
  URL.revokeObjectURL(url);
  alert('Save the file to the same folder as this HTML.\nUse "Load State" to restore it in any viewer.');
}

function loadStateFromFile(input) {
  const file = input.files[0];
  if (!file) return;
  const reader = new FileReader();
  reader.onload = function(e) {
    try {
      const data = JSON.parse(e.target.result);
      const reviews = data.reviews || data;
      localStorage.setItem(STORAGE_KEY, JSON.stringify(reviews));
      renderCards();
      alert(`Loaded review state (saved ${data.savedAt || 'unknown date'}).`);
    } catch (err) {
      alert('Error reading file: ' + err.message);
    }
  };
  reader.readAsText(file);
  input.value = '';
}

// Auto-load from co-located JSON on startup
function autoLoadState() {
  fetch(STATE_FILENAME)
    .then(r => { if (r.ok) return r.json(); throw new Error('not found'); })
    .then(data => {
      const existing = getAllReviews();
      if (Object.keys(existing).length === 0 && data.reviews) {
        // No localStorage data — load everything from file
        localStorage.setItem(STORAGE_KEY, JSON.stringify(data.reviews));
        renderCards();
        console.log('Auto-loaded review state from ' + STATE_FILENAME);
      } else if (data.reviews) {
        // Merge AI verification fields from file into existing localStorage
        // (preserves user's satisfied/comment from localStorage)
        let merged = false;
        for (const [refNum, fileReview] of Object.entries(data.reviews)) {
          if (fileReview.claude_verified) {
            if (!existing[refNum]) {
              existing[refNum] = { satisfied: false, comment: '' };
            }
            // Only merge AI fields if file has newer or missing local AI data
            if (!existing[refNum].claude_verified) {
              existing[refNum].claude_verified = fileReview.claude_verified;
              existing[refNum].claude_verdict = fileReview.claude_verdict;
              existing[refNum].claude_reason = fileReview.claude_reason;
              existing[refNum].claude_timestamp = fileReview.claude_timestamp;
              if (fileReview.claude_details) {
                existing[refNum].claude_details = fileReview.claude_details;
              }
              merged = true;
            }
          }
        }
        if (merged) {
          localStorage.setItem(STORAGE_KEY, JSON.stringify(existing));
          renderCards();
          console.log('Merged AI verification data from ' + STATE_FILENAME);
        }
      }
    })
    .catch(() => {});  // no file yet, that's fine
}

// Initial render
renderCards();
autoLoadState();"""
