"""Unpaywall API client — find legal open access versions of articles by DOI."""

import os
from pathlib import Path
from typing import Any

import httpx

BASE_URL = "https://api.unpaywall.org/v2"
TIMEOUT = 30.0

_EMAIL_FILE = Path.home() / ".unpaywall" / "email.txt"


def _get_email() -> str:
    email = os.environ.get("UNPAYWALL_EMAIL", "").strip()
    if email:
        return email
    if _EMAIL_FILE.exists():
        email = _EMAIL_FILE.read_text(encoding="utf-8").strip()
        if email:
            return email
    raise RuntimeError(
        "No email configured for Unpaywall. Set UNPAYWALL_EMAIL env var "
        f"or put your email in {_EMAIL_FILE}. "
        "Unpaywall requires an email address (no key needed)."
    )


def _parse_oa_location(loc: dict[str, Any]) -> dict[str, Any]:
    return {
        "url": loc.get("url", ""),
        "url_for_pdf": loc.get("url_for_pdf", ""),
        "url_for_landing_page": loc.get("url_for_landing_page", ""),
        "host_type": loc.get("host_type", ""),  # publisher, repository
        "version": loc.get("version", ""),  # publishedVersion, acceptedVersion, submittedVersion
        "license": loc.get("license", ""),
    }


def unpaywall_lookup(doi: str) -> dict[str, Any]:
    """Look up a DOI to find open access full text URLs.

    Returns the best OA location plus all available locations.
    """
    email = _get_email()
    url = f"{BASE_URL}/{doi}"
    resp = httpx.get(url, params={"email": email}, timeout=TIMEOUT)
    resp.raise_for_status()
    data = resp.json()

    best_oa = data.get("best_oa_location")
    oa_locations = data.get("oa_locations", [])

    result: dict[str, Any] = {
        "doi": data.get("doi", ""),
        "title": data.get("title", ""),
        "is_oa": data.get("is_oa", False),
        "oa_status": data.get("oa_status", ""),  # gold, green, hybrid, bronze, closed
        "journal": data.get("journal_name", ""),
        "publisher": data.get("publisher", ""),
        "pub_date": data.get("published_date", ""),
        "year": data.get("year", ""),
        "authors": [
            a.get("name", "") for a in data.get("z_authors", []) or [] if a.get("name")
        ],
    }

    if best_oa:
        result["best_oa_url"] = best_oa.get("url", "")
        result["best_pdf_url"] = best_oa.get("url_for_pdf", "")
        result["best_oa_version"] = best_oa.get("version", "")
        result["best_oa_host"] = best_oa.get("host_type", "")
        result["best_oa_license"] = best_oa.get("license", "")

    result["all_oa_locations"] = [_parse_oa_location(loc) for loc in oa_locations]
    result["oa_location_count"] = len(oa_locations)

    return result


def unpaywall_batch(dois: list[str]) -> dict[str, Any]:
    """Look up multiple DOIs for OA status. Processes sequentially (API is per-DOI)."""
    email = _get_email()
    results: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []

    for doi in dois[:25]:  # cap to avoid rate issues
        try:
            url = f"{BASE_URL}/{doi}"
            resp = httpx.get(url, params={"email": email}, timeout=TIMEOUT)
            if resp.status_code == 404:
                errors.append({"doi": doi, "error": "DOI not found"})
                continue
            resp.raise_for_status()
            data = resp.json()
            best_oa = data.get("best_oa_location")
            results.append({
                "doi": data.get("doi", ""),
                "title": data.get("title", ""),
                "is_oa": data.get("is_oa", False),
                "oa_status": data.get("oa_status", ""),
                "best_pdf_url": best_oa.get("url_for_pdf", "") if best_oa else "",
                "best_oa_url": best_oa.get("url", "") if best_oa else "",
            })
        except Exception as e:
            errors.append({"doi": doi, "error": str(e)})

    return {
        "results": results,
        "errors": errors,
        "total_checked": len(results) + len(errors),
        "oa_found": sum(1 for r in results if r["is_oa"]),
    }


def unpaywall_api_status() -> dict[str, Any]:
    """Check Unpaywall configuration and connectivity."""
    try:
        email = _get_email()
        # Test with a known DOI
        result = unpaywall_lookup("10.1038/nature12373")
        return {
            "configured": True,
            "email": email,
            "connected": True,
            "test_title": result.get("title", ""),
            "test_is_oa": result.get("is_oa", False),
        }
    except RuntimeError as e:
        return {"configured": False, "error": str(e)}
    except Exception as e:
        return {"configured": True, "connected": False, "error": str(e)}
