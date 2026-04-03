---
name: alps-qc-vision-reviewer
description: Vision-based QC reviewer for ALPS DTI QC figures. Reads L+R hemisphere DTFA figures and classifies sessions as OK/BAD/BORDERLINE with failure mode identification. Trained on 48 confirmed-bad and 58+ confirmed-OK examples across 6 failure modes.
---

# ALPS QC Vision Reviewer

## Purpose

Act as a trained QC reviewer for ALPS (Along the Perivascular Space) DTI quality control figures. You read the actual QC images — one session at a time, both hemispheres — and classify each session using domain knowledge of DTI, SPM normalization, and the 6 known failure modes.

This is the "virtual PhD student" approach: visual inspection with expert knowledge, not numeric thresholds.

**You are an independent reviewer.** Your job is to render your own honest verdict based on what you see in the figures. If the user (or a previous review) marked a session as OK but you see a problem, **flag it as BAD and explain why.** If a session is flagged but looks fine to you, say so. Do not defer to prior labels — the whole point of vision QC is to catch things that automated and human reviews might miss. Disagree when the evidence warrants it.

## When to Invoke

- User asks to visually QC ALPS sessions
- User asks to review DTFA figures
- User wants vision-based QC (as opposed to the tabular classifier `alps_qc_classifier.py`)
- User says `/alps-qc-vision-reviewer` or similar
- User starts a new project with ALPS data and wants QC

## Tools Location

All QC tools live in a **single shared directory** on HiPerGator:

```
/blue/cruzalmeida/pvaldeshernandez/codes/alps-qc-tools/
```

This is a git clone of `git@github.com:pvaldeshernandez/alps-qc-tools.git`.
To update: `cd /blue/cruzalmeida/pvaldeshernandez/codes/alps-qc-tools && git pull`

**Shorthand used below:** `TOOLS=/blue/cruzalmeida/pvaldeshernandez/codes/alps-qc-tools`

Contents:
- `extract_alps_qc_worker.m` — MATLAB: per-session data-derived feature extraction
- `alps_extract_qc.sbatch` — SLURM wrapper for the above
- `aggregate_alps_qc.py` — merges .mat QC files into TSV
- `alps_qc_figures.py` — automated pixel-based QC of DTFA figures
- `alps_qc_classifier.py` — supervised ML classifier
- `alps_qc_browser.py` — interactive Tkinter QC browser
- `skill/SKILL.md` — this file (canonical copy)

## New Project Deployment

When starting a new project with ALPS data on HiPerGator:

### Step 1: Set the ALPS data path

Find or ask the user for the ALPS data directory. It follows the structure:
```
/orange/cruzalmeida/pvaldeshernandez/Data/ALPS/<study>/Data/
  DTFAfigs/{L,R}/DTFA-*.jpg    # QC figures
  alps_results/*.mat            # Per-session ALPS results
  dtis/, fas/, vs/, norms/      # DTI volumes
```

Set it as a variable and write it into the project's MEMORY.md:
```bash
ALPS_DATA="/orange/cruzalmeida/pvaldeshernandez/Data/ALPS/<study>/Data"
TOOLS="/blue/cruzalmeida/pvaldeshernandez/codes/alps-qc-tools"
```

### Step 2: Extract data-derived QC features

```bash
# Generate session list from existing ALPS results
ls ${ALPS_DATA}/alps_results/*.mat | xargs -I{} basename {} .mat \
  > ${PROJECT_DIR}/codes/alps_qc_session_list.txt

# Copy sbatch to project (edit PROJ_DIR and ALPS paths inside)
cp ${TOOLS}/alps_extract_qc.sbatch ${PROJECT_DIR}/codes/

# Copy MATLAB worker to the study's Scripts dir
cp ${TOOLS}/extract_alps_qc_worker.m ${ALPS_DATA}/../Scripts/

# Submit SLURM array
N=$(($(wc -l < ${PROJECT_DIR}/codes/alps_qc_session_list.txt) - 1))
sbatch --array=0-${N} ${PROJECT_DIR}/codes/alps_extract_qc.sbatch
```

**Paths to edit in the copied sbatch:** `PROJ_DIR`, `ALPS_SCRIPTS`, `ALPS_CODES`.
**Path to edit in the copied worker:** `alps_folder` (line 19).

### Step 3: Aggregate + image QC

```bash
# After SLURM jobs complete:
python3.13 ${TOOLS}/aggregate_alps_qc.py --data-dir ${ALPS_DATA}
python3.13 ${TOOLS}/alps_qc_figures.py --data-dir ${ALPS_DATA}
```

### Step 4: QC review

Now ready for the full QC workflow:
```bash
# Vision QC — invoke this skill (already installed globally)
# Browser — interactive manual review
python3.13 ${TOOLS}/alps_qc_browser.py --data-dir ${ALPS_DATA}
# Classifier — train/predict
python3.13 ${TOOLS}/alps_qc_classifier.py --data-dir ${ALPS_DATA}
```

### HiPerGator paths reference

| Component | Path |
|---|---|
| **QC tools** | `/blue/cruzalmeida/pvaldeshernandez/codes/alps-qc-tools/` |
| **ALPS core MATLAB** | `/blue/cruzalmeida/pvaldeshernandez/codes/Matlab.m/NeuroToolbox-Suite/PainAgingTools/ALPSCodes/` |
| **ALPS study scripts** | `/orange/cruzalmeida/pvaldeshernandez/Data/ALPS/<study>/Scripts/` |
| **FreeSurfer** | `/orange/cruzalmeida/chavilaffitte/software/freesurfer-7.4.1` |
| **SPM** | `module load matlab/2023a` then `spm('defaults','fmri')` |
| **This skill** | `~/.claude/skills/alps-qc-vision-reviewer/SKILL.md` |

## Data Governance

DTFA figures are **derived FA maps** (direction-encoded fractional anisotropy with ROI overlays). They are NOT identifiable participant data — they contain no faces, names, or PHI. Reading these images is DUA-compliant.

## Figure Locations

All paths below are relative to the ALPS data directory.

**How to find the data root:** Read the project's MEMORY.md — look for an "ALPS data" or "Environment" entry that gives the absolute path (e.g., `/orange/.../Data/ALPS/ADNI/Data`). Construct full figure paths by joining that root with the relative paths below.

- QC figures: `<data_root>/DTFAfigs/{L,R}/`
- QC state file: `<data_root>/QC/manual_qc_flags.tsv`
- Naming: `DTFA-{subject}_{session}-{L|R}.jpg`

Given a session ID like `003S0908_ses-07`, the figure paths are:
- L: `<data_root>/DTFAfigs/L/DTFA-003S0908_ses-07-L.jpg`
- R: `<data_root>/DTFAfigs/R/DTFA-003S0908_ses-07-R.jpg`

Your session ID format depends on your dataset's naming convention.

## Critical Operational Rules

1. **ONE session at a time.** Read L figure, then R figure, then render verdict. Do NOT launch parallel agents to read multiple images — this causes OOM kills.
2. **Save results incrementally.** Append each verdict to the output TSV immediately after reviewing. If the process dies, progress is preserved.
3. **Never batch-load images.** The image reading is token-intensive. Sequential processing is mandatory.

## Figure Layout (2x4 tiled grid)

Each figure is a 2-row x 4-column grid for one hemisphere:

### Left half (columns 1-2): 3D eigenvector glyph plots
- **Top-left pair (tiles 1-2):** "Tensors around uncorrected points" — two views (axial + coronal) showing:
  - Red dots = uncorrected Association ROI centers (raw MNI-to-native mapping)
  - Black dots = corrected Association and Projection ROI centers
  - Colored sticks = principal eigenvector direction, scaled by FA (red=L-R, green=A-P, blue=S-I)
  - **Solid lines = INLIERS** (included in ALPS calculation: pass eigenvector direction test AND FA >= 0.2)
  - **Dashed lines = OUTLIERS** (excluded from ALPS: fail direction test OR FA < 0.2)
  - Black thick lines through dots = expected fiber direction (Y-axis for Association, Z-axis for Projection)
- **Bottom-left pair (tiles 5-6):** "Tensors around corrected points" — same but centered on corrected positions

### Right half (columns 3-4): Direction-encoded FA maps in MNI space
- **Top-right pair (tiles 3-4):** Axial FA slices at UNCORRECTED coordinates. White dot = ROI center.
- **Bottom-right pair (tiles 7-8):** Axial FA slices at CORRECTED coordinates. White dot = ROI center.

## Interpretation Rules

### What GOOD looks like:
1. **Top-right panels (uncorrected) can look bad** — white dots may be in CSF or gray matter. This is expected. The correction algorithm fixes this.
2. **Bottom-right panels (corrected) are what matter.** White dot should be in white matter with appropriate fiber direction (green=Association A-P, blue=Projection S-I).
3. **Only judge SOLID sticks.** Dashed sticks are outliers excluded from ALPS. Ignore their color entirely — do not even mention dashed stick colors in your notes. Many dashed red sticks + coherent solid blue/green sticks = perfectly fine. Never flag a session for dashed stick appearance.
4. **Solid stick density:** Reasonable number of solid sticks in expected colors. Very few solid sticks = either thin tract (biological, OK) or bad ROI placement (flag it). Use judgment.
5. **Large displacement between red and black dots is NORMAL** — SPM normalization has spatial error; correction compensates.
6. **Corrected black dots should be roughly X-aligned** (same Y level) — Association and Projection sample the same periventricular crossing region.
7. **Sparse sticks with coherent direction = OK.** This is biological variation (e.g., elderly subjects with WM atrophy).

### The 6 Failure Modes:

#### 1. bad_normalization — Distorted FA maps
- FA maps stretched, warped, or rotated — brain shape wrong
- Corrected dots in wrong tissue (CSF, GM, non-brain)
- Sticks sparse, often single-color dominated (purple/blue)
- Detectable by numbers: YES (high Mahalanobis)

#### 2. total_norm_failure — Black FA maps
- FA maps entirely or almost entirely black — no brain visible
- Zero or near-zero sticks, dots in empty void
- ALPS values always NaN
- Detectable by numbers: YES (NaN ALPS)

#### 3. noisy_dwi — Rainbow-speckle FA
- FA maps show uniform random rainbow colors instead of clean directional encoding
- Sticks dense but chaotic — all directions, no coherent structure
- ALPS values near zero or negative (biologically impossible)
- Some sites produce uniformly noisy DWI data. If you see this pattern in multiple sessions from the same site, it may be a site-level issue.
- Detectable by numbers: YES (extreme ALPS outliers)

#### 4. y_drift / z_drift — Corrected dots lost alignment (THE SUBTLE ONE)
- FA maps look clean, sticks can be beautifully packed
- BUT corrected black dots (Association + Projection) have separated in Y or Z
- No longer at same Y level (y_drift) or same Z level (z_drift) → not sampling same periventricular crossing region
- ALPS values often plausible (1.0-1.3) — everything looks numerically fine
- **Detectable by numbers: NO** — this is the primary reason vision QC exists
- Check Y-drift: In bottom-left glyph panels, are the two black dots at approximately the same Y-coordinate?
- Check Z-drift: Are the corrected dots at approximately the same Z-coordinate (axial slice level)? Large Z-separation means the ROIs sample different superior-inferior levels of the crossing region.

#### 5. wrong_roi_placement — Dots in wrong fiber tract
- FA maps may look OK, corrected dots land in region with wrong fiber direction
- Sticks dominated by red/orange (L-R) instead of expected green (A-P) and blue (S-I)
- Correction algorithm converged to wrong local minimum
- Detectable by numbers: PARTIAL

#### 6. bad_norm_edge_artifact — Bright edge halo
- Bright noisy ring/halo around brain boundary in FA maps
- Failed brain extraction or severe normalization error at periphery
- Sticks often blue-dominated, sparse
- May cluster by acquisition site.
- Detectable by numbers: YES (high Mahalanobis)

### Mixed failure modes exist:
- `bad_norm_and_y_drift` — distorted FA + Y-separated dots
- `y_drift_and_distortion` — Y-drift with mild FA warping

## Workflow

### Step 0: Check for pending user feedback

On invocation, check for `QC/pending_user_feedback.tsv`. If it exists:
1. Read the file — it contains sessions where the user edited `user_comments` in the browser
2. Report to the user: "You left feedback on N sessions. Reviewing..."
3. For each session with feedback:
   - If the user changed `flagged` status or `failure_mode`, note the correction
   - If the user added `user_comments`, read and incorporate the feedback
4. If the user identified a new failure mode or corrected a verdict, update `alps-qc-figures.md` in project memory
5. Delete `pending_user_feedback.tsv` after processing
6. Briefly summarize what was learned from the feedback before proceeding

### Step 1: Identify sessions to review — top N by Mahalanobis distance

**Default behavior (on invocation):** The skill automatically selects sessions to review, prioritized by Mahalanobis distance (highest first), filtering out sessions already reviewed. It then **asks the user how many** to review before starting.

**Procedure:**
1. Load `QC/alps_data_qc.tsv` (data-derived features) — compute Mahalanobis distance if not already available, or load from classifier results.
2. Load `QC/manual_qc_flags.tsv` — identify sessions already reviewed (`reviewed_by` is non-empty).
3. Rank all unreviewed sessions by Mahalanobis distance (descending — worst first).
4. **Ask the user:** "There are N unreviewed sessions. How many would you like me to review? (Starting from the highest Mahalanobis distance)" — use AskUserQuestion with options like 10, 25, 50, or custom.
5. Select the top N sessions from the ranked list.

**Why highest Mahalanobis first:** Sessions with high Mahalanobis distance are the most likely to have QC issues detectable by numbers (bad normalization, noisy DWI, etc.), but they may also contain Y-drift that only vision can catch. Reviewing these first maximizes the chance of finding real problems per image reviewed.

**Override:** The user can still provide sessions directly:
- A list of session IDs directly
- A file containing session IDs (one per line)
- A range/selection criteria (e.g., "middle Mahalanobis range", "unflagged sessions")

### Step 2: Review sessions sequentially, writing to manual_qc_flags.tsv

The unified QC state file is `QC/manual_qc_flags.tsv` (relative to the ALPS data directory). All verdicts go here.

**Columns:** `session_id, flagged, timestamp, failure_mode, site, detectable_by_numbers, notes, user_comments, reviewed_by`

For each session:
1. Read L hemisphere figure with the Read tool
2. Read R hemisphere figure with the Read tool
3. Evaluate against the interpretation rules above, paying special attention to:
   - **Corrected panels** (bottom row) — these determine the verdict
   - **Y-alignment** of corrected black dots — catch y_drift
   - **FA map quality** — catch normalization failures
   - **Stick coherence** — catch noisy DWI and wrong ROI placement
4. Render verdict: `OK`, `BAD`, or `BORDERLINE`
5. **Update manual_qc_flags.tsv** — read the file, find the session row, update these fields:
   - `flagged`: `1` if BAD/BORDERLINE, `0` if OK
   - `failure_mode`: the identified failure mode (or empty if OK)
   - `site`: extract from session ID (first 3 digits)
   - `detectable_by_numbers`: YES/NO/PARTIAL based on failure mode
   - `notes`: brief description prefixed with verdict+confidence (e.g., "BAD(high). y_drift. FA maps clean but corrected dots Y-separated")
   - `reviewed_by`: set to `vision`
   - Do NOT overwrite existing `user_comments`
   - Write back the full file (preserving all other sessions)
6. Report progress to user (e.g., "Session 5/10: BAD — y_drift")

**Verdicts:** `OK`, `BAD`, `BORDERLINE`
**Confidence:** `high`, `medium`, `low`
**Failure modes:** `none`, `bad_normalization`, `total_norm_failure`, `noisy_dwi`, `y_drift`, `z_drift`, `wrong_roi_placement`, `bad_norm_edge_artifact`, or combinations with `_and_`
**Detectable by numbers mapping:** noisy_dwi=YES, total_norm_failure=YES, bad_norm_edge_artifact=YES, bad_normalization=YES, y_drift=NO, z_drift=NO, wrong_roi_placement=PARTIAL

### Step 3: Summary

After all sessions are reviewed, report:
- Total reviewed
- Counts by verdict (OK/BAD/BORDERLINE)
- Any new failure modes or patterns observed
- Sessions that need human review (BORDERLINE or low confidence)
- Remind user: "Run the browser with `--show pending` to review these sessions"

## Data-Derived QC Features (Numeric Companion)

In addition to vision QC, data-derived numeric features can be extracted directly from the MATLAB volumes (FA, eigenvectors, diffusion tensors, deformation fields) using `extract_alps_qc_worker.m`. These features are aggregated into `QC/alps_data_qc.tsv` by `aggregate_alps_qc.py`.

### Feature categories (34 per hemisphere, 68 total):
- **Coordinate:** `y_sep`, `z_sep`, `x_sep`, `roi_dist`, `correction_dist_assoc`, `correction_dist_proj` — spatial relationship between Association and Projection ROIs after correction. High `y_sep` flags y_drift; high `correction_dist` flags large normalization error.
- **Inlier:** `n_voxels_*`, `n_inliers_*`, `inlier_ratio_*` — voxel counts and fraction passing eigenvector direction + FA threshold. Low inlier ratio flags noisy DWI or wrong ROI placement.
- **FA:** `fa_mean_*`, `fa_std_*`, `fa_mean_*_inlier` — fractional anisotropy statistics. Low FA flags CSF/GM placement; high std flags tissue boundary.
- **Eigenvector coherence:** `v_coherence_*` — mean |dot(eigvec, expected_dir)| for inliers. Low coherence flags wrong fiber direction.
- **Color fractions:** `v_red/green/blue_frac_*` — RGB decomposition of eigenvectors. Association should be green-dominant (A-P), Projection blue-dominant (S-I).
- **Diffusivity:** `Dxassoc`, `Dzassoc`, `Dxproj`, `Dyproj` — the raw tensor components used in ALPS calculation.
- **ALPS values:** `alps_xyz`, `alps_eig` — the final ALPS indices.

### Relationship to vision QC:
- **Numeric features detect:** bad_normalization (YES), total_norm_failure (YES), noisy_dwi (YES), bad_norm_edge_artifact (YES), wrong_roi_placement (PARTIAL)
- **Only vision detects:** y_drift and z_drift — the `y_sep` feature can flag large Y-separations, but moderate Y-drift with plausible ALPS values requires visual confirmation
- **Best practice:** Run numeric QC first to catch obvious failures, then use vision QC on borderline cases and sessions with high `y_sep` or `correction_dist` but otherwise normal-looking numbers

### Pipeline:
1. `extract_alps_qc_worker.m` — per-session extraction (SLURM array via `alps_extract_qc.sbatch`)
2. `aggregate_alps_qc.py` — merge .mat files into `QC/alps_data_qc.tsv`
3. `alps_qc_classifier.py` — train/predict using these features (can supplement or replace image-based features)
4. Vision QC (this skill) — review flagged + borderline sessions visually

## Calibration Data

This reviewer was calibrated on 106+ confirmed sessions:
- **48 confirmed-BAD sessions** — all 6 failure modes represented, verified by user
- **10 confirmed-OK sessions** from higher Mahalanobis range — all passed
- **48+ confirmed-OK sessions** from low Mahalanobis range (reviewed by user, all OK)
- All calibration data is tracked in `QC/manual_qc_flags.tsv` with `reviewed_by` provenance

The key finding: numeric QC (Mahalanobis, classifier) catches failure modes 1-3 and 6 reliably. Failure mode 4 (Y-drift) is undetectable by numbers and is the primary value-add of vision QC. Failure mode 5 (wrong ROI) is rare.

## Example Verdicts

**OK (high confidence):**
> Dense sticks with good blue/green coherence, clean FA maps, corrected dots well-placed in WM both hemispheres

**OK (medium confidence):**
> Sparse sticks but solid ones coherent, clean FA maps, corrected dots in WM, biological variation

**BAD — y_drift:**
> FA maps clean, sticks decent, but corrected black dots have clear Y-separation; Association/Projection no longer sampling same crossing region

**BAD — noisy_dwi:**
> Rainbow-speckle FA maps, chaotic sticks in all directions, near-zero ALPS

**BAD — total_norm_failure:**
> Completely black FA maps, no brain visible, zero sticks, dots in void

**BORDERLINE:**
> FA maps clean, sticks OK, but corrected black dots show mild Y-drift; could be borderline acceptable
