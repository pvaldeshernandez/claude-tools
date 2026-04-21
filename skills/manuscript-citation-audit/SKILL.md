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

### Pass 3 — Reconciliation (optional, recommended for high-stakes submissions)

Deploy 2–3 independent agents with the same Pass 1 + Pass 2 prompt and compare their reports. When they disagree, re-verify the contested claim against the PDF manually. Areas where agents disagree are usually where the claim is genuinely borderline and the text needs to be tightened.

### Pass 4 — Study-design terminology check

Language must match the design of each cited study. The most common violations:

- **"Reduction", "reduced", "decrease", "decreased", "increase", "increased", "loss", "atrophy"** — these terms imply longitudinal change (something got smaller or larger over time). They are correct only if the cited study has a longitudinal arm (baseline vs follow-up scans, or pre-vs-post treatment). For cross-sectional between-group comparisons the correct terms are **"smaller", "lower", "greater", "higher", "thinner", "thicker", "shallower"** (steady-state descriptors).
- **"Reversed", "recovered", "normalized"** — strictly longitudinal. Cross-sectional studies cannot support these.
- **"Progression", "progressed"** — implies a time course. Cross-sectional correlations with disease duration are *consistent with* progression but do not demonstrate it.
- **"Predicted"** — implies prospective data. A cross-sectional correlation does not predict anything.

For each cited study flagged in Pass 1, verify its design (cross-sectional vs longitudinal vs mixed) by reading the Methods section. Then scan the manuscript's paraphrase of that study for design-mismatched verbs. Flag each mismatch and propose the correct steady-state alternative.

Exception: if the cited paper's own abstract uses a longitudinal-implying word loosely to describe a cross-sectional finding, the manuscript may legitimately mirror the paper's wording — but flag it as inherited imprecision so the author can decide.

## Output Format

A single Markdown report containing:

1. **Summary** — count of ACCURATE / MISATTRIBUTED / FALSE / INCOMPLETE / UNVERIFIABLE claims.
2. **Confirmed errors to fix** — each with quoted sentence, PDF evidence, and proposed direction of fix (not the rewrite itself).
3. **Pass-2 knock-on issues** — paragraphs where a Pass-1 fix invalidates a comparative/absence claim.
4. **Reference-level verdict table** — one row per cited paper with verdict label. If Pass 1.5 ran, include a **SemanticCite** column with its independent label, a **Merged** column with the stricter-wins verdict, and an explicit **AGREE/DISAGREE** flag. Cite disagreements at the top of the report so the author never misses them.
5. **Unverifiable references** — PDFs missing; claims cannot be checked.

Do NOT produce rewritten text inside the audit. Keep the audit as a flagging document so the author can decide how to fix each issue.

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
