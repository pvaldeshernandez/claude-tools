---
name: analysis-reporter
description: Use when the user asks to write up, summarize, or report the analysis performed in the current session, or requests a chronological account of data processing, statistical methods, and results as a markdown document.
---

# Analysis Reporter

Write a comprehensive, chronological markdown report of all analysis work done in the current conversation. The report tells the full story — from data description through methods, formulas, results, and interpretation — in the order things were done.

## When to Use

- User says "write the report", "write up what we did", "summarize the analysis", "create a report"
- User wants a documented record of an analysis session
- User needs a reproducible narrative of their analytical workflow

## Report Structure

The report follows this fixed skeleton. Include each section **only if relevant content exists in the conversation**:

```markdown
# Analysis Report: [Descriptive Title Inferred from the Work]
> Generated: YYYY-MM-DD

## 1. Data Description
## 2. Methods
## 3. Results
## 4. Summary
```

### Section Details

**1. Data Description:**
- Dataset name, source, sample size (N)
- Variables used with types (continuous, categorical, ordinal)
- Inclusion/exclusion criteria if discussed
- Summary statistics as a **full markdown table** (mean, SD, range, N per group)
- Missing data: how much, which variables, how handled
- If descriptive stats were computed in the session, **reproduce the actual numbers in a table — never just say "were calculated"**

**2. Methods:**
- Each analysis step **in the order it was performed**
- For each step:
  - What was done and why (connecting to previous results when applicable)
  - Mathematical formulation in LaTeX: inline `$...$`, display `$$...$$`
  - Software in format: `package vX.Y.Z in Language vX.Y` (e.g., "lme4 v1.1-35 in R v4.3.2")
  - Key parameters or settings chosen

**3. Results:**
- Each analysis result **in chronological order**, containing:
  - **Full statistical table** as a markdown pipe table with caption (e.g., **Table N.** Description)
  - Tables must include ALL available statistics: coefficients, SE, CI, t/F/z values, p-values, effect sizes
  - Bold significant results in tables (p < threshold used in session)
  - **Figures embedded** as `![Figure N. Descriptive caption](path/to/figure.png)` — they must render inline
  - **Interpretation immediately after** each table/figure — what the result means for the research question
  - Any follow-up decisions triggered by this result (e.g., "Because the interaction was significant, post-hoc contrasts were computed")

**4. Summary:**
- Key findings as bullet points
- Limitations noted during the session
- Next steps if discussed

## Formatting Rules

### LaTeX Math
- Inline: `$\beta_1 = 0.45$`
- Display blocks for model specifications:
```
$$
Y_{ij} = \beta_0 + \beta_1 X_{1ij} + \beta_2 X_{2ij} + \gamma_{0j} + \varepsilon_{ij}
$$
```
- Every formula gets a brief label before it (e.g., "The linear mixed model was specified as:")
- Use proper Greek letters ($\beta$, $\gamma$, $\varepsilon$), subscripts, and notation

### Tables
- Standard markdown pipe tables with header row
- Right-align numeric columns
- **Bold** significant p-values
- Caption above each table: **Table N.** Description
- Never leave a table empty or say "statistics were calculated" — fill in the actual numbers from the session

### Figures
- Embed as `![Figure N. Caption describing what it shows](path/to/figure.png)`
- The path must come from the session (whatever file was saved)
- If a figure path is unclear, **ask the user** before writing the report
- Every figure gets a descriptive caption explaining what it shows (axes, groups, trends)

### Interpretation
- Appears **immediately after** each result (table or figure), not in a separate section at the end
- Written in plain language connecting the statistical finding to the research question
- Example: "The significant interaction ($p = 0.003$) indicates that the effect of sleep efficiency on pain threshold differs between FM and HC groups."

### Software
- Format: `package vX.Y.Z in Language vX.Y`
- Report tools where they are used in the Methods section, not in a separate section
- If a version is unknown from the session, write "version not recorded" — never guess

## Workflow

1. **Scan conversation** — Review the full session to identify:
   - Datasets loaded, variables discussed
   - Analyses performed (in chronological order)
   - Code executed and outputs produced
   - Figures saved (collect file paths)
   - Tools, packages, versions mentioned
   - Actual numeric results (statistics, p-values, coefficients)

2. **Ask clarifying questions** (only if needed):
   - "Where should I save the report?" (default: project root as `analysis_report.md`)
   - "What title do you want?" (or infer from the analysis topic)
   - Confirm any ambiguous figure paths

3. **Write the full report** following the structure and rules above

4. **Present a summary to the user:**
   - Sections included
   - Number of tables, figures, formulas
   - Output file path
   - "Want me to adjust anything?"

5. **Save the `.md` file**

6. **Revisions** — If the user requests changes, edit the same file. No file proliferation.

## Common Mistakes

| Mistake | Correct Approach |
|---------|-----------------|
| Writing "descriptive statistics were computed" without numbers | Always reproduce actual values in a table |
| Listing figures as text references | Embed with `![caption](path)` so they render |
| Writing the model in code syntax (`y ~ x * z`) | Write as LaTeX: $Y = \beta_0 + \beta_1 X_1 + ...$ |
| Putting all interpretation at the end | Interleave interpretation after each result |
| Reporting results as inline text | Use full markdown tables with all statistics |
| Omitting software versions | Always include in format `package vX.Y.Z in Language vX.Y` |
| Inventing or rounding statistics | Report exactly what appeared in the session output |
