#!/bin/bash
# hpg_session_watchdog.sh — Background daemon that monitors HiPerGator
# ondemand session lifetime and sends email warnings before expiration.
#
# Usage:
#   nohup bash ~/.claude/skills/session-monitor/hpg_session_watchdog.sh &
#
# It auto-detects the current ondemand SLURM job, computes remaining time,
# and sends email warnings on this schedule:
#   - 12 hours remaining
#   - Every 2 hours after that until 2 hours left
#   - Every 30 minutes after that
#
# The script also saves a state snapshot to the project memory directory
# at each warning so Claude can resume in a new session.
#
# To stop: kill the process, or it exits automatically when the job ends.

set -u

EMAIL="pvaldeshernandez@ufl.edu"
MEMORY_DIR="$HOME/.claude/projects/-orange-cruzalmeida-pvaldeshernandez-BAHC-adni-T1-dMRI/memory"
STATE_FILE="${MEMORY_DIR}/session-watchdog-state.md"
LOG_FILE="${MEMORY_DIR}/watchdog.log"

# ── Detect all ondemand jobs ──────────────────────────────────────────
log() { echo "$(date '+%Y-%m-%d %H:%M:%S') $*" >> "${LOG_FILE}"; }

# Get all ondemand jobs for this user
get_ondemand_jobs() {
  squeue -u "$(whoami)" -o "%i|%j|%M|%l" -h 2>/dev/null | grep "ondemand" || true
}

# ── Session labeling ─────────────────────────────────────────────────
# Labels are stored in ~/.claude/session-labels/<job_id>.label
# Written by Claude Code (session-monitor skill) or manually.
# Format: one line of text describing what's happening in that session.
# Fallback: derive a generic label from the SLURM job name.
SESSION_LABEL_DIR="$HOME/.claude/session-labels"
mkdir -p "${SESSION_LABEL_DIR}" 2>/dev/null || true

get_session_label() {
  local jobid="$1"
  local jobname="$2"

  # Check for a user/Claude-written label file first
  local label_file="${SESSION_LABEL_DIR}/${jobid}.label"
  if [[ -f "$label_file" ]]; then
    cat "$label_file"
    return
  fi

  # Fallback: derive from SLURM job name
  local type=$(echo "$jobname" | awk -F'/' '{print $NF}')
  case "$type" in
    console)  echo "Console" ;;
    vscode)   echo "VSCode" ;;
    matlab)   echo "MATLAB" ;;
    jupyter)  echo "Jupyter" ;;
    rstudio)  echo "RStudio" ;;
    *)        echo "$type" ;;
  esac
}

log "Watchdog started on $(hostname) — monitoring ALL ondemand sessions"

# ── Time parsing ─────────────────────────────────────────────────────
parse_slurm_time() {
  local t="$1" days=0 hours=0 mins=0 secs=0
  if [[ "$t" == *-* ]]; then
    days="${t%%-*}"; t="${t#*-}"
  fi
  IFS=: read -r a b c <<< "$t"
  if [[ -n "${c:-}" ]]; then
    hours=$a; mins=$b; secs=$c
  elif [[ -n "${b:-}" ]]; then
    mins=$a; secs=$b
  else
    secs=$a
  fi
  echo $(( days*86400 + hours*3600 + mins*60 + secs ))
}

# (remaining time computed inline per-job in main loop)

fmt_remaining() {
  local s=$1
  local d=$((s / 86400))
  local h=$(( (s % 86400) / 3600 ))
  local m=$(( (s % 3600) / 60 ))
  if [[ $d -gt 0 ]]; then
    echo "${d}d ${h}h ${m}m"
  elif [[ $h -gt 0 ]]; then
    echo "${h}h ${m}m"
  else
    echo "${m}m"
  fi
}

# (project context extracted inline where needed)

# ── Email ────────────────────────────────────────────────────────────
send_email() {
  local subject="$1" body="$2"
  # Write body to temp file to avoid quoting issues
  local tmpfile=$(mktemp)
  cat > "${tmpfile}" << 'EMAILEOF'
${body}
EMAILEOF
  # Re-expand — use printf to handle the body
  printf '%s' "${body}" > "${tmpfile}"
  python3 - "${subject}" "${EMAIL}" "${tmpfile}" << 'PYEOF'
import smtplib, sys
from email.mime.text import MIMEText
subject = sys.argv[1]
email = sys.argv[2]
with open(sys.argv[3]) as f:
    body = f.read()
msg = MIMEText(body)
msg['Subject'] = subject
msg['From'] = email
msg['To'] = email
s = smtplib.SMTP('smtp.ufl.edu', 25)
s.send_message(msg)
s.quit()
PYEOF
  rm -f "${tmpfile}"
  log "Email sent: ${subject}"
}

# ── State snapshot ───────────────────────────────────────────────────
save_state() {
  local remaining="$1"
  local expire_epoch=$(( $(date +%s) + remaining ))
  local expire_date=$(date -d "@${expire_epoch}" "+%a %b %d %I:%M %p %Z")

  # Capture all ondemand sessions with remaining time
  local sessions=$(squeue -u "$(whoami)" -o "%.18i %.50j %.8T %.12M %.14l" -h 2>/dev/null | grep "ondemand" || echo "(none)")
  # Capture running batch jobs
  local jobs=$(squeue -u "$(whoami)" -o "%.18i %.20j %.8T %.10M" -h 2>/dev/null | grep -v "ondemand" || echo "(none)")

  cat > "${STATE_FILE}" << SNAPSHOT
# Session Watchdog State
Last updated: $(date '+%Y-%m-%d %H:%M:%S %Z')
Soonest expiry: $(fmt_remaining ${remaining}) (~${expire_date})

## OnDemand Sessions
\`\`\`
${sessions}
\`\`\`

## Running SLURM Jobs
\`\`\`
${jobs}
\`\`\`
SNAPSHOT

  log "State saved (soonest expiry: ${remaining}s)"
}

# ── Track which jobs have been warned at which thresholds ────────────
# File-based tracking so state persists across loop iterations
WARNED_FILE="${MEMORY_DIR}/watchdog-warned.txt"
touch "${WARNED_FILE}" 2>/dev/null || true

was_warned() {
  # Usage: was_warned <job_id> <threshold_label>
  grep -q "^${1}:${2}$" "${WARNED_FILE}" 2>/dev/null
}

mark_warned() {
  echo "${1}:${2}" >> "${WARNED_FILE}"
}

# ── Main loop ────────────────────────────────────────────────────────
while true; do
  jobs_output=$(get_ondemand_jobs)

  # If no ondemand jobs at all, exit
  if [[ -z "$jobs_output" ]]; then
    log "No ondemand jobs found. Exiting."
    break
  fi

  # Find the soonest-expiring job to determine sleep interval
  min_remaining=999999
  any_warned=false

  while IFS='|' read -r jid jname jelapsed jlimit; do
    [[ -z "$jid" ]] && continue
    # Trim whitespace
    jid=$(echo "$jid" | xargs)
    jname=$(echo "$jname" | xargs)
    jelapsed=$(echo "$jelapsed" | xargs)
    jlimit=$(echo "$jlimit" | xargs)

    local_e=$(parse_slurm_time "$jelapsed")
    local_l=$(parse_slurm_time "$jlimit")
    remaining=$(( local_l - local_e ))

    [[ $remaining -lt 0 ]] && continue

    session_label=$(get_session_label "$jid" "$jname")
    expire_epoch=$(( $(date +%s) + remaining ))
    expire_date=$(date -d "@${expire_epoch}" "+%a %b %d %I:%M %p")

    log "Check: ${jid} (${session_label}) — $(fmt_remaining ${remaining}) remaining"

    # Determine if this job needs a warning
    if [[ $remaining -le 1800 ]]; then
      # <= 30 min: CRITICAL — always warn
      send_email "[CRITICAL] HPG ${session_label}: $(fmt_remaining ${remaining}) left" \
"Your HiPerGator ${session_label} session (job ${jid}) expires at ~${expire_date}.

Open a new ondemand session now to avoid losing your work environment. SLURM batch jobs will keep running.
"
      save_state "$remaining"
      any_warned=true

    elif [[ $remaining -le 7200 ]] && ! was_warned "$jid" "2h_$(( remaining / 1800 ))"; then
      # <= 2h: URGENT, every 30 min
      send_email "[URGENT] HPG ${session_label}: $(fmt_remaining ${remaining}) left" \
"Your HiPerGator ${session_label} session (job ${jid}) expires at ~${expire_date}.

Consider opening a new ondemand session soon.
"
      mark_warned "$jid" "2h_$(( remaining / 1800 ))"
      save_state "$remaining"
      any_warned=true

    elif [[ $remaining -le 43200 ]] && ! was_warned "$jid" "12h"; then
      # <= 12h: first warning
      send_email "[WARNING] HPG ${session_label}: $(fmt_remaining ${remaining}) left" \
"Your HiPerGator ${session_label} session (job ${jid}) expires at ~${expire_date}.
"
      mark_warned "$jid" "12h"
      save_state "$remaining"
      any_warned=true
    fi

    # Track soonest-expiring for sleep interval
    [[ $remaining -lt $min_remaining ]] && min_remaining=$remaining
  done <<< "$jobs_output"

  # Determine sleep interval based on soonest-expiring session
  if [[ $min_remaining -le 1800 ]]; then
    sleep_for=600        # 10 min
  elif [[ $min_remaining -le 7200 ]]; then
    sleep_for=1800       # 30 min
  elif [[ $min_remaining -le 43200 ]]; then
    sleep_for=7200       # 2h
  else
    sleep_for=21600      # 6h
  fi

  # Don't sleep longer than soonest expiry
  if [[ $sleep_for -gt $min_remaining ]]; then
    sleep_for=$((min_remaining > 60 ? min_remaining - 60 : 30))
  fi

  sleep "$sleep_for"
done

log "Watchdog exiting."
