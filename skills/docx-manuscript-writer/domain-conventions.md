# Domain Conventions

## Reporting Rules

- Name indirect effects descriptively: "indirect-through-pain" not "ind1"
- Report every significant result with: interpretation in real units + variance proportion (V%)
- Use ranges to summarize multiple similar effects (e.g., "4.3–7.5 cm/s")
- Specify the multiple comparison correction method and significance threshold
- Discard effects below the V% threshold before reporting (e.g., V% < 10%)
- When reporting model counts: "11/24 models after Bonferroni correction"

## Statistical Notation

- Two-part mediation marginal effect: a1* = γ1×E[M1|M1>0] + P(M1>0)×a1
- BCa bootstrap confidence intervals (specify number of resamples)
- For zero-inflated mediators, explain the two-part decomposition (logistic + linear)
- Standardized notation: use Unicode symbols (×, →, –, ≥, ≤) not ASCII approximations

## Covariate Rules

- eTIV only as covariate when brain variables are present in the equation
- Age and sex as default covariates (column names: demo_age, demo_gender)
- Document which covariates are used in Methods, not just Results

## Figure and Table Placement

- Figures and tables must appear immediately after the paragraph where the corresponding results are first mentioned.
- For example, Table 4 goes right after the introductory paragraph of the Vertex-wise Results section, and each Figure goes after the paragraph that references it.
- Apply this rule consistently across all sections: Results, Discussion, or any section containing figures/tables.

## Abstract-Specific

- Each section should target the word limit from the journal profile (divide evenly if not specified per-section)
- Background: justify the research question, cite gaps
- Methods: sample, measures, statistical approach, corrections
- Results: only report effects that survived correction + V% threshold
- Discussion: interpret, acknowledge cross-sectional limitation, suggest future directions
