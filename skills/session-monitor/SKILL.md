---
name: session-monitor
description: Use at the START of every session on HiPerGator (when SLURM_JOB_ID is set) to monitor ondemand session lifetime, warn the user before expiration, and auto-save project state to memory. Also invoke when the user asks about session time remaining.
---

# HiPerGator OnDemand Session Monitor

## Purpose
OnDemand sessions on HiPerGator have a fixed time limit (typically 12d 12h). When they expire, everything dies — running processes, unsaved context, background tasks. This skill ensures:
1. The user is warned IN THE CONVERSATION and by email before expiration
2. Project state is saved to memory so the next session can resume seamlessly

## On Session Start

Do THREE things:

### 1. Report remaining time
```bash
SLURM_ELAPSED=$(squeue -j ${SLURM_JOB_ID} -o "%M" -h 2>/dev/null)
SLURM_LIMIT=$(squeue -j ${SLURM_JOB_ID} -o "%l" -h 2>/dev/null)
echo "Job ${SLURM_JOB_ID}: elapsed=${SLURM_ELAPSED} limit=${SLURM_LIMIT}"
```
Report to the user in a brief one-liner like:
> OnDemand session 24817445: ~7d 17h remaining (expires ~Feb 24 4:47 AM)

### 2. Start the email watchdog daemon (if not already running)
```bash
if ! ps aux | grep "hpg_session_watchdog.sh" | grep -v grep > /dev/null 2>&1; then
  nohup bash ~/.claude/skills/session-monitor/hpg_session_watchdog.sh </dev/null > /dev/null 2>&1 &
  echo "Watchdog daemon started (PID $!)"
else
  echo "Watchdog daemon already running"
fi
```
The watchdog runs independently of Claude — it survives conversation restarts and sends email warnings to pvaldeshernandez@ufl.edu via smtp.ufl.edu. It monitors ALL ondemand sessions (not just this one) and labels each by type (Console, VSCode, MATLAB, etc.) or by project context if a label file exists.

### 3. Write a session label for the watchdog
Write a short label describing what's happening in this session so the watchdog emails are informative. The label should reflect the project/task context (e.g. "ADNI ALPS pipeline", "NEPAL fMRI analysis", "LOSO SSM modeling").

```bash
mkdir -p ~/.claude/session-labels
# Derive label from project MEMORY.md title, or the working directory basename
echo "<project_or_task_description>" > ~/.claude/session-labels/${SLURM_JOB_ID}.label
```

Choose the label based on:
1. The first `# heading` in the project's MEMORY.md (e.g. "ADNI T1_dMRI" → "ADNI ALPS pipeline")
2. If no MEMORY.md, use the working directory name
3. Keep it short (2-5 words) and descriptive of the work being done

### 4. Start in-conversation background warning timer
Set up a background `sleep` command that will fire back into the conversation at the appropriate interval based on remaining time:

| Time Remaining | Sleep interval |
|---|---|
| > 12 hours | 6 hours (21600s) |
| 4-12 hours | 2 hours (7200s) |
| 2-4 hours | 1 hour (3600s) |
| 30min-2 hours | 30 minutes (1800s) |
| < 30 minutes | 10 minutes (600s) |

Use Bash with `run_in_background`:
```bash
sleep <seconds> && echo "SESSION_MONITOR_WARNING: <remaining_time> left on ondemand session ${SLURM_JOB_ID}. Save state and warn user."
```

When a background timer fires:
1. **Tell the user directly** how much time remains — this is the primary warning
2. Run the **State Save** procedure
3. Set the next background timer based on the new remaining time

## State Save Procedure

When saving state (on warnings or when the user ends a session), update the project memory file at the project's memory directory.

Save:
1. **Running SLURM jobs** — `squeue -u pvaldeshernandez -o "%.18i %.20j %.8T %.10M" | grep -v ondemand`
2. **Recent job completions** — `sacct` for any tracked job IDs mentioned in MEMORY.md
3. **What was being worked on** — update the "What to do when resuming" section
4. **Any uncommitted script changes** — note modified files

The memory file MUST be self-contained enough that a fresh session can pick up where this one left off without asking the user what was happening.

## On Session Resume (New Session)

When starting a new session, if MEMORY.md has a "What to do when resuming" section:
1. Read it
2. Check the status of any SLURM jobs mentioned (they may have completed while the session was down)
3. Brief the user on what happened and what's next
4. Start the session monitor for the new session

## Time Parsing Helper

SLURM time formats: `MM:SS`, `HH:MM:SS`, `D-HH:MM:SS`. To compute remaining seconds:
```bash
parse_slurm_time() {
  local t="$1"
  local days=0 hours=0 mins=0 secs=0
  if [[ "$t" == *-* ]]; then
    days="${t%%-*}"; t="${t#*-}"
  fi
  IFS=: read -r a b c <<< "$t"
  if [[ -n "$c" ]]; then
    hours=$a; mins=$b; secs=$c
  else
    mins=$a; secs=$b
  fi
  echo $(( days*86400 + hours*3600 + mins*60 + secs ))
}

elapsed_s=$(parse_slurm_time "$SLURM_ELAPSED")
limit_s=$(parse_slurm_time "$SLURM_LIMIT")
remaining_s=$((limit_s - elapsed_s))
remaining_h=$((remaining_s / 3600))
echo "Remaining: ${remaining_h} hours"
```
