"""State file I/O for reference review state with schema migration.

Manages a JSON state file that stores both user reviews (satisfied/comment)
and AI verification results (claude_verified, claude_verdict, claude_reason).
"""

import json
import os
from datetime import datetime, timezone


CURRENT_VERSION = 3


def load_state(state_path: str) -> dict:
    """Read JSON state file, migrating from v2 to v3 if needed.

    Args:
        state_path: Absolute path to the state JSON file.

    Returns:
        dict with keys: version, savedAt, reviews.
        Each review entry has: satisfied, comment, claude_verified,
        claude_verdict, claude_reason, claude_timestamp.
    """
    if not os.path.isfile(state_path):
        return {
            "version": CURRENT_VERSION,
            "savedAt": _now_iso(),
            "reviews": {},
        }

    with open(state_path, "r") as f:
        data = json.load(f)

    version = data.get("version", 1)

    # Handle bare dict (v1: no version key, just {refnum: {satisfied, comment}})
    if "version" not in data:
        data = {"version": 1, "savedAt": _now_iso(), "reviews": data}
        version = 1

    # Migrate v1/v2 -> v3: add claude_* fields as None
    if version < CURRENT_VERSION:
        reviews = data.get("reviews", {})
        for ref_num, review in reviews.items():
            if "claude_verified" not in review:
                review["claude_verified"] = None
            if "claude_verdict" not in review:
                review["claude_verdict"] = None
            if "claude_reason" not in review:
                review["claude_reason"] = None
            if "claude_timestamp" not in review:
                review["claude_timestamp"] = None
        data["version"] = CURRENT_VERSION

    return data


def save_state(state_path: str, state: dict) -> None:
    """Write state to JSON file.

    Args:
        state_path: Absolute path to the state JSON file.
        state: Full state dict with version, savedAt, reviews.
    """
    state["version"] = CURRENT_VERSION
    state["savedAt"] = _now_iso()

    os.makedirs(os.path.dirname(os.path.abspath(state_path)), exist_ok=True)
    with open(state_path, "w") as f:
        json.dump(state, f, indent=2)


def save_verification_result(
    state_path: str,
    ref_num: int,
    verdict: str,
    reason: str,
    details: dict = None,
) -> dict:
    """Update one reference's AI verification in the state file.

    Args:
        state_path: Absolute path to the state JSON file.
        ref_num: Reference number.
        verdict: One of "pass", "flag", "warning".
        reason: Text explanation of the verdict.
        details: Optional extra details dict.

    Returns:
        The updated review entry for this reference.
    """
    if verdict not in ("pass", "flag", "warning"):
        raise ValueError(f"verdict must be 'pass', 'flag', or 'warning', got '{verdict}'")

    state = load_state(state_path)
    reviews = state.get("reviews", {})
    ref_key = str(ref_num)

    # Get or create entry
    if ref_key not in reviews:
        reviews[ref_key] = {
            "satisfied": False,
            "comment": "",
        }

    entry = reviews[ref_key]
    entry["claude_verified"] = True
    entry["claude_verdict"] = verdict
    entry["claude_reason"] = reason
    entry["claude_timestamp"] = _now_iso()
    if details:
        entry["claude_details"] = details

    reviews[ref_key] = entry
    state["reviews"] = reviews
    save_state(state_path, state)

    return entry


def _now_iso() -> str:
    """Return current UTC time in ISO format."""
    return datetime.now(timezone.utc).isoformat()
