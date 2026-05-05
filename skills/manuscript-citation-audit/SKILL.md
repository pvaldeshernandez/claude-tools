---
name: manuscript-citation-audit
description: Rigorously audit a manuscript section (Abstract, Introduction, Discussion, etc.) for citation accuracy and argument integrity. Use when an author wants to verify that every factual claim in a manuscript section is supported by the cited reference AND by the surrounding argument, with PDFs read fresh (no cached knowledge), and with explicit checks for negative/comparative claims that have no citation. Catches misattributions, misleading paraphrases, false statements, and knock-on contradictions that sentence-by-sentence audits miss.
allowed-tools: Read Write Edit Bash Glob Grep Agent
license: MIT license
metadata:
    skill-author: Pedro Valdes-Hernandez
---

# Manuscript Citation Audit

## Overview

Manuscripts routinely contain citation errors that sentence-by-sentence auditing misses. The three most common failure modes are:

1. **Misattributed citations** — a paper is cited for something it did not study or demonstrate.
2. **Misleading paraphrases** — the citation exists but the paraphrase overstates, understates, or flips the direction of the finding.
3. **Knock-on inconsistencies** — when one citation error is fixed, the corrected categorization silently invalidates a comparative or negative claim elsewhere in the paragraph (e.g., "no study has done X" becomes false if the corrected category now includes a study that does X).

Standard LLM audits catch (1) and (2) well. They miss (3) because they treat each sentence in isolation and do not verify the logical integrity of the surrounding argument.

This skill runs a **two-pass audit** that catches all three:

- **Pass 1** — sentence-level citation verification against PDFs.
- **Pass 1.5** (optional) — SemanticCite second opinion on each Pass-1 claim.
- **Pass 2** — argument-level integrity review that propagates Pass-1 corrections through the paragraph.

## When to Use This Skill

Use this skill when you want to verify the accuracy of a manuscript section (or any text with citations) against the cited literature. Especially valuable for:

- Discussion sections that compare the current study to prior work.
- Introductions that characterize "the existing literature" or make "no prior study" / "most studies" claims.
- Meta-analyses, reviews, or any text that groups studies by methodology, sample, or finding type.
- Rewritten or heavily edited sections where the original citations may no longer fit.

Do NOT use this skill when:
- You only want to verify that cited references exist (use citation-management).
- You are doing a general peer review (use peer-review).
- You just want to find missing references or suggest new ones.

## Inputs Required

- **Manuscript section** — Markdown, DOCX, or plain text. If DOCX, convert with markitdown.
- **Cited references** — numbered or author-year, with mapping to PDF files.
- **PDF folder** — path containing every cited paper as a PDF. Flag any missing PDFs upfront.
- **Scope instructions** (optional) — e.g., "only the Discussion", or "skip the Methods".

## Defaults and Invocation

These defaults apply when the user invokes this skill without overrides. They reflect Pedro's standing preferences and are documented here so a fresh-context session does not have to re-derive them.

### Backend default = Claude only

**Run Pass 1 (Claude reads each cited PDF directly) and Pass 4 (study-design terminology check) by default. Do NOT run Pass 1.5 (SemanticCite) unless the user explicitly opts in AND has explicitly acknowledged the cost on this turn.**

Opt-in triggers — these phrases tell you the user is *asking for* SemanticCite:

- "with SemanticCite" / "use SemanticCite"
- "second opinion" / "cross-check"
- "two backends" / "both backends" / "two parallel agents"
- `--with-semanticcite` flag
- Anything that explicitly names SemanticCite or asks for an independent second labeling

**Mandatory cost confirmation gate.** Even when the user asks for SemanticCite, do NOT dispatch the SemanticCite agent until you have asked a hard, single-turn confirmation question that explicitly reminds them they will be charged for UF Navigator use, e.g.:

> *"SemanticCite uses GPT-4.1-mini via UF Navigator (~2–3 min per claim-PDF pair, ~N claims here). This will charge against Pedro's UF Navigator account. Confirm you want to proceed?"*

If the user does not respond with an explicit "yes/proceed/confirmed" on the same turn, do not run it. A general "let's audit this" request does NOT count as cost acknowledgment, even if "with SemanticCite" was said earlier in the conversation. Re-confirm each time. This rule is non-negotiable: SemanticCite's UF Navigator usage is billed and Pedro wants every invocation to be a deliberate, cost-aware decision.

Why: SemanticCite is slow (~2–3 min per claim-PDF pair), relies on an external Conda environment, and — most importantly — incurs metered cost via UF Navigator (LLM API calls per claim-PDF pair). The Claude-only audit is fast, free at the per-invocation level, and sufficient for first-pass and routine checks.

When SemanticCite is approved (after the cost gate), deploy two parallel agents (one Claude, one SemanticCite) — not a single agent that runs both — and merge results in the assistant context using the stricter-wins table in Pass 1.5. This is the deployment Pedro prefers when both backends are wanted.

### Scope default = literal section name

**Audit the literal section the user names, in full.** No auto-narrowing.

- "audit the Discussion" → entire Discussion section (every subsection).
- "audit the Methods" → entire Methods section.
- "audit the Lateralization subsection" → only that subsection.
- "audit what we just wrote" / "audit the new section" → only the recently added content.

Do not assume the user means "just the new paragraph I added" when they say "Discussion." If the section is large and the user may have meant a subset, ASK before dispatching — do not silently scope down.

### Pass 2, Pass 3, and Pass 4 — all run by default

**Pass 2 (argument-integrity / absence-claim search), Pass 3 (multi-agent reconciliation), and Pass 4 (study-design terminology) all run by default.** They are part of the standard audit. Only Pass 1.5 (SemanticCite) is opt-in.

**Pass 3 default behavior** (unless the user opts out): dispatch **two parallel Claude agents** (general-purpose subagents), each running Pass 1 + Pass 2 + Pass 4 independently on the same scope. When both complete, the assistant reconciles disagreements by re-reading the contested PDFs directly, then merges the two reports into a single paper-grouped report (see "Output format" below).

**Opt-out triggers — skip Pass 3 (single agent only):**

- "single agent" / "one agent" / "no reconciliation" / "skip Pass 3"
- "fast audit" / "first-pass check" / "quick check"
- "just one pass" / "no need to cross-check"

When Pass 3 is skipped, dispatch a single Claude agent (or do the audit inline if scope is very small), and the output is the same paper-grouped format with one verdict per claim instead of merged-from-two.

**Why default-on:** Pass-3 reconciliation has repeatedly caught issues that single-agent audits missed (the Discussion audit on this project found that 4 of 5 flagged issues were caught by only one of two agents). The marginal runtime cost (~30–60 min wall-clock for two parallel agents on a typical Discussion section) is worth it for the reliability gain.

## Method

### Pass 1 — Sentence-level citation verification

**Granularity rule (default, unless user overrides):** walk the section
**sequentially, statement by statement, in document order**. A
"statement" is a claim-bearing unit that references the literature —
typically one sentence, but split a sentence into multiple statements
if it makes several independently-citable claims (e.g., "Makary 2020
showed reduced NAcc volume (26), increased NAcc–ACC connectivity (26),
and loss of low-frequency fluctuations (26)" = three statements).
**Skip any sentence that does not cite or depend on the literature**
(pure methods descriptions, internal results, equation statements,
transitions). This matches the fine-grained approach used for the
Introduction and Discussion audits.

For each statement:

1. Identify every claim that depends on a citation. A claim depends on a citation if (a) a citation appears in or near the sentence, OR (b) the sentence continues an argument anchored to a citation earlier in the paragraph.
2. For each such claim, open the cited PDF (convert with markitdown if needed) and read the **Abstract, Methods, and Results at minimum**. Do NOT rely on cached knowledge of the paper.
3. Classify the claim as:
   - **ACCURATE** — PDF supports the claim as stated.
   - **MISATTRIBUTED** — Paper did not study or demonstrate what it is cited for.
   - **FALSE** — PDF contradicts the claim.
   - **INCOMPLETE / MISLEADING** — PDF partially supports but the paraphrase omits or distorts important context.
   - **UNVERIFIABLE** — PDF not available (flag explicitly).
4. For each non-ACCURATE claim, quote the contradicting or missing PDF text.

### Pass 1.5 — SemanticCite second opinion (optional)

**Trigger:** only when the user asks for a second opinion or uses a flag
like `--with-semanticcite`. Off by default.

**⚠️ COST GATE (mandatory).** SemanticCite calls `gpt-4.1-mini` via UF
Navigator, which charges Pedro's UF Navigator account per call. Before
running Pass 1.5 you MUST ask a same-turn confirmation question that
explicitly reminds the user of this cost (see "Defaults and Invocation"
above for the wording). A previously-said "with SemanticCite" does not
constitute cost acknowledgment for a new invocation — confirm on the
turn that triggers the run. Skip Pass 1.5 if the user does not
explicitly confirm.

SemanticCite is an external tool (https://github.com/sebhaan/semanticcite)
that runs its own retrieval-and-reranking pipeline over the PDF and
returns an independent label on the same claim. It is a cross-check,
not a replacement for Pass 1. Running both and comparing catches cases
where either approach alone would miss an issue.

**How to invoke** (per Pass-1 claim + cited PDF):

```bash
module load conda
conda activate cite
export LD_LIBRARY_PATH="$CONDA_PREFIX/lib:$LD_LIBRARY_PATH"
python ~/.claude/skills/manuscript-citation-audit/scripts/semanticcite_backend.py \
    --claim "<one-sentence claim from Pass 1>" \
    --pdf   /path/to/cited_paper.pdf \
    --out   /tmp/semanticcite_<ref_key>.json
```

The backend defaults to UF Navigator (`~/.navigator_key`, model
`gpt-4.1-mini`). Override by setting `OPENAI_API_KEY` /
`OPENAI_API_BASE` before calling, or pass `--model <model-name>`.

First run on a fresh machine downloads ~550 MB (MPNet embeddings +
FlashRank reranker); subsequent runs use the cache. Expect ~2–3 min per
citation on `gpt-4.1-mini`.

**Returned JSON schema:**

```json
{
  "backend": "semanticcite",
  "classification": "SUPPORTED | PARTIALLY_SUPPORTED | UNSUPPORTED | UNCERTAIN",
  "confidence": 0.90,
  "reasoning": "...",
  "claim": "LLM-extracted core claim",
  "evidence": [{"text": "...", "score": 0.999, "chunk_id": 114}, ...],
  "runtime_sec": 194.7,
  "model": "gpt-4.1-mini"
}
```

**Merge with Pass 1 (stricter-wins):**

| Pass 1 | SemanticCite | Merged verdict |
|---|---|---|
| ACCURATE | SUPPORTED | **ACCURATE** |
| ACCURATE | PARTIALLY_SUPPORTED | **INCOMPLETE — check** (SemanticCite flagged gaps) |
| ACCURATE | UNSUPPORTED | **CONFLICT — human review** |
| ACCURATE | UNCERTAIN | ACCURATE (keep Pass 1) |
| INCOMPLETE / MISLEADING | SUPPORTED | INCOMPLETE (Pass 1 wins, it caught context Pass 1.5 missed) |
| INCOMPLETE / MISLEADING | PARTIALLY_SUPPORTED | **INCOMPLETE** (agree) |
| INCOMPLETE / MISLEADING | UNSUPPORTED | **FALSE or INCOMPLETE — human review** |
| MISATTRIBUTED | any | **MISATTRIBUTED** (Pass 1 dominates: SemanticCite cannot detect this) |
| FALSE | UNSUPPORTED | **FALSE** (agree) |
| FALSE | SUPPORTED | **CONFLICT — human review** |
| UNVERIFIABLE | any | UNVERIFIABLE |

General rule: when they disagree, pick the label closer to "flag for
human review," and always show both verdicts in the output so the
author sees why. Never silently drop a disagreement.

**When to use Pass 1.5:**

- High-stakes submissions (journal revision, grant).
- Paragraphs the author thinks are borderline.
- Spot-check sampling — run on a random 10–20% of references to audit
  Pass 1's own reliability.

**When NOT to use Pass 1.5:**

- First-draft self-checks where speed matters.
- Citations that are clearly single-factoid ("N = 188 participants (ref)")
  — both backends will agree, and the cost isn't worth it.

### Pass 2 — Argument-level integrity review

After Pass 1 completes, re-read the section as a whole. For each paragraph:

1. Identify **comparative claims** (e.g., "more than prior studies", "consistent with", "contrary to") and **absence claims** (e.g., "no prior study has done X", "most studies have not examined Y", "the literature is silent on Z"). These claims often have no citation.
2. For each comparative/absence claim, ask:
   - Does it survive the Pass-1 corrections? (e.g., if Mo was miscategorized from "cortical-only" to "whole-brain", does "no whole-brain study exists" still hold?)
   - Does any cited paper — including those correctly cited in Pass 1 — actually contradict the comparative/absence claim?
3. Verify absence claims by **actively searching for counterexamples** across all PDFs in scope, not just the cited ones. Use grep on method keywords, region names, or finding types.
4. Flag paragraphs where Pass-1 corrections propagate to weaken or invalidate other claims. This is the most important step and is what standard audits miss.

### Pass 3 — Multi-agent reconciliation (default; opt-out only)

**Default behavior** (unless the user opts out, see "Defaults and Invocation" above):

1. Dispatch **two parallel Claude general-purpose subagents**. Each runs Pass 1 + Pass 2 + Pass 4 independently on the same scope. Each writes its own report to `citation_audit_<section>_pass3_agentA.md` / `..._agentB.md`.
2. The dispatch prompt for each agent must include the line: *"keep tool result payloads small; read PDFs incrementally with offset/limit on Read, or pipe markitdown through head/grep — a previous run failed with 'Request too large (max 32MB)' from loading full long PDFs into single tool results."* This guards against the size-limit failure mode that has occurred in practice.
3. When both complete, the assistant reconciles disagreements by **re-reading the contested PDFs directly** (not by re-prompting an agent). For each claim where the two agents disagree, the assistant fetches the PDF passage, decides which agent was right, and records the merged verdict.
4. The merged report is written in the paper-grouped format described in "Output Format" below. Per-agent reports stay on disk as provenance.

**Why default-on:** in practice (Discussion audit on this project), 4 of 5 flagged issues were caught by only one of the two agents — running a single audit would have missed most of them. The runtime cost (~30–60 min wall-clock for two parallel agents on a Discussion-sized section) is worth it.

**Failure handling:** if one agent fails (e.g., 32 MB tool-result limit), do NOT silently fall back to the other agent's verdict. Treat the surviving agent's report plus the assistant's PDF-level reconciliation as the audit, but mark the failure in the merged report's "Multi-agent merge metadata" footer so the user knows reconciliation was 1-of-2 not 2-of-2.

**Opt-out path** (single agent): the user must use one of the opt-out triggers documented in "Defaults and Invocation". When opting out, skip the parallel-dispatch step and run a single Claude audit inline (or in one subagent if scope is large). The output format is otherwise identical.

### Pass 4 — Study-design terminology check

Language must match the design of each cited study. The most common violations:

- **"Reduction", "reduced", "decrease", "decreased", "increase", "increased", "loss", "atrophy"** — these terms imply longitudinal change (something got smaller or larger over time). They are correct only if the cited study has a longitudinal arm (baseline vs follow-up scans, or pre-vs-post treatment). For cross-sectional between-group comparisons the correct terms are **"smaller", "lower", "greater", "higher", "thinner", "thicker", "shallower"** (steady-state descriptors).
- **"Reversed", "recovered", "normalized"** — strictly longitudinal. Cross-sectional studies cannot support these.
- **"Progression", "progressed"** — implies a time course. Cross-sectional correlations with disease duration are *consistent with* progression but do not demonstrate it.
- **"Predicted"** — implies prospective data. A cross-sectional correlation does not predict anything.

For each cited study flagged in Pass 1, verify its design (cross-sectional vs longitudinal vs mixed) by reading the Methods section. Then scan the manuscript's paraphrase of that study for design-mismatched verbs. Flag each mismatch and propose the correct steady-state alternative.

Exception: if the cited paper's own abstract uses a longitudinal-implying word loosely to describe a cross-sectional finding, the manuscript may legitimately mirror the paper's wording — but flag it as inherited imprecision so the author can decide.

## Output Format

The audit produces a single paper-grouped Markdown report. The layout is fixed and must be followed exactly so a fresh-context Claude in a future session can produce the same artifact without explanation.

**File path convention:** `<manuscript_dir>/citation_audit_<section>_by_paper.md` (e.g., `citation_audit_discussion_by_paper.md`, `citation_audit_introduction_by_paper.md`).

**Structure of the report, top to bottom:**

### 1. Header

- Manuscript path, section audited, backend (Claude only or Claude + SemanticCite), Pass 3 status (single-agent or multi-agent reconciled), PDF folder path, count of cited PDFs found vs missing.

### 2. Executive summary

- One-sentence finding count: e.g., *"Audited N claims across M papers; X papers flagged with at least one issue, Y papers ACCURATE on every claim."*
- A small "verdict-by-paper" table: paper | times cited | final verdict (or, in multi-agent mode, agreement/disagreement state).
- One-line Pass-2 status (absence/novelty claims hold? or which broke).
- One-line Pass-4 status (clean? or which terms flagged).

### 3. Recommended fix priority

- Numbered list of the issues that need an action, ordered by severity (FALSE > MISATTRIBUTED > INCOMPLETE/MISLEADING > BORDERLINE).
- Each entry: paper name + one-sentence summary of the issue + one-sentence fix direction.

### 4. Per-paper sections, with issue-papers listed FIRST

The body of the report is one section per cited paper. **Papers are ordered with issue-papers listed first**, followed by **a clear horizontal-rule separator (`---`) and a marker heading**, and then **all-ACCURATE papers**.

**Definition of an "issue-paper":** any paper with at least one claim whose verdict is **MISATTRIBUTED**, **FALSE**, **INCOMPLETE/MISLEADING**, or **UNVERIFIABLE** (e.g., PDF missing). UNVERIFIABLE counts as an issue, NOT as an accurate claim — the audit cannot vouch for the citation, so it belongs in the issues block where the user can decide what to do (locate the PDF, drop the citation, or replace with an accessible source). A paper with all claims either ACCURATE or BORDERLINE-acceptable is an all-ACCURATE paper. BORDERLINE on its own (e.g., a Pass-4 inherited-imprecision flag the skill explicitly accepts) does not promote a paper into the issues block; only verdicts requiring author action do.

Within each per-paper section, claims that triggered an issue are listed first (under an `## Issues` sub-heading), then a separator, then the paper's accurate claims (under `## ACCURATE claims`).

Example layout:

```markdown
# Wang et al., 2017 ★ ISSUES

**PDF:** `Wang-...pdf`
**Cohort/method:** [one-line summary]
**Final verdict:** INCOMPLETE/MISLEADING

## Issues

### Claim — [subsection in manuscript]
> "Verbatim sentence."
**Verdict:** INCOMPLETE/MISLEADING
**Why:** [1–3 sentences with PDF evidence quoted]
**Fix:** [a concrete proposed edit, not a vague direction. Show the old text and the new text in find/replace style, OR write the new sentence in full so the user can paste it. Examples below.]

## ACCURATE claims

### Claim — [subsection]
> "Verbatim sentence."
**Verdict:** ACCURATE
**Why:** [1–2 sentences with PDF evidence quoted]
```

After all issue-papers, insert a clear separator before the all-ACCURATE block:

```markdown
---

# Papers with all-ACCURATE claims

# DeSouza et al., 2013

**PDF:** `DeSouza-...pdf`
**Cohort/method:** [one-line]
**Final verdict:** ACCURATE

### Claim — [subsection]
> "Verbatim sentence."
**Verdict:** ACCURATE
**Why:** ...
```

(All-ACCURATE papers do not need an `## Issues` sub-heading; just list the claims directly under the paper header.)

#### What counts as a concrete `Fix:`

Every flagged claim must propose a *specific edit*, not a generic recommendation. Three formats are acceptable:

1. **Find/replace** — when the fix is a localized substring change, show the exact strings:

   ```
   **Fix:** In paragraph N, replace
   > "right-hemisphere predominance of structural change has been reported"
   with
   > "the largest cluster of reduced gray-matter volume was right-hemisphere"
   ```

2. **Full sentence rewrite** — when the fix needs sentence-level restructuring, write the new sentence in full so the user can paste it directly:

   ```
   **Fix:** Replace the Pashkov sentence at the end of paragraph 3 with:
   > "Pashkov et al. (2025) reported a count divergence between left- and right-pain subgroups in significant thalamic nuclei from controls, but their direct between-pain-side test was null (Pashkov et al., 2025)."
   ```

3. **Action + concrete content** — when the fix is structural (drop a citation, move a clause, split a sentence):

   ```
   **Fix:** Remove "Hashmi et al., 2013" from the citation list at the end of the corticostriatal sentence. The remaining citation (Baliki et al., 2012) supports the NAc-centered claim directly. If the broader chronification-shift framing is still wanted, cite Hashmi separately in a new sentence: "A complementary longitudinal study found that chronification shifts brain activity from nociceptive to emotional circuits (Hashmi et al., 2013)."
   ```

Generic phrasings like "consider rewording," "tighten the wording," or "soften this claim" are NOT acceptable as `Fix:` entries — they push the writing work back onto the author and defeat the point of the audit. If the audit cannot propose a concrete fix (e.g., the right rephrasing depends on a literature search the author still needs to do), say so explicitly: `**Fix:** Cannot be proposed without [specific information]; flag for author judgment.`

### 5. Pass-2 absence/novelty claims

Final section. Lists every claim that has no citation but makes an absence or comparative argument ("no prior study...", "first to...", "consistent with...", "unlike..."). Each entry: verbatim claim + verdict (HOLDS / BROKE) + justification (which PDFs were searched, what the closest neighbor was, whether any counterexample was found).

### 6. Pass-4 design-terminology check

Final section. Lists every flagged longitudinal-implying verb applied to a cross-sectional study, with the cited paper's design and a recommended steady-state replacement. Omit if clean (mention "Pass 4 clean" in the executive summary instead).

### 7. Multi-agent merge metadata (Pass 3 default)

Brief footer noting which agents ran and where their per-agent reports live (e.g., `citation_audit_<section>_pass3_agentA.md`, `..._agentB.md`). If they disagreed, list the contested claims and which agent the reconciler sided with after re-reading the PDF.

**Forbidden in the report:**

- Do NOT produce rewritten manuscript text. The audit is a flagging document.
- Do NOT cluster issue-papers and accurate-papers in document order; the issues-first ordering is mandatory.
- Do NOT collapse the per-paper sections into a single subsection-grouped chronological list. The grouping is by cited paper, not by manuscript subsection. Each claim names its manuscript subsection inside the claim block, not as the top-level grouping.
- Do NOT include the SemanticCite cost-confirmation conversation inside the report; the report only shows verdicts.

## Key Principles

- **No cached knowledge.** Read the PDF fresh for every verification. Your prior beliefs about a paper are unreliable.
- **Quote the PDF.** Every verdict must be backed by a literal quote from the paper.
- **Absence claims need active counterexample search.** A claim like "no prior study has done X" cannot be verified by reading one paper; it requires searching all candidate papers for counterexamples.
- **Propagate Pass-1 corrections.** A single fix to a citation category can invalidate an adjacent absence claim. Never finalize an audit without checking propagation.
- **Strict over lenient.** When in doubt between ACCURATE and INCOMPLETE, choose INCOMPLETE. It is easier for an author to dismiss a conservative flag than to recover from a published error.
- **Numbering mismatches are common.** If the audit prompt gives you reference numbers, always re-verify numbering against the manuscript's own reference list before using them.

## Red Flags That Indicate This Skill Is Needed

If a paragraph contains any of these patterns, trigger this skill:

- "No prior study has..." / "Most studies have not..." / "The literature is silent on..."
- "Prior studies fall into three categories..." (any explicit grouping of studies by methodology or finding)
- "Consistent with..." / "In contrast to..." / "Unlike..."
- "This is the first..." — always verify against the full literature.
- Heavy meta-analytic framing (e.g., "X% of studies report...").
- Citation pooling of 3+ papers for a single claim (e.g., "[5,7,12,18,22]").
- Longitudinal-implying verbs ("reduction", "decreased", "progression", "predicted", "reversed") applied to cross-sectional findings.

## See Also

- **peer-review** — broader manuscript review, not citation-focused.
- **citation-management** — finding and managing references, not verifying them.
- **scholar-evaluation** — structured scoring frameworks for research quality.
- **scientific-critical-thinking** — claim-level evidence evaluation, not citation-specific.
