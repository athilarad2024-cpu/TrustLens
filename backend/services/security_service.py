"""
services/security_service.py
External URL security intelligence — Section 21 of the master document.

Providers implemented:
  - Google Safe Browsing v4
  - VirusTotal API v3

Each provider is completely isolated. Failures (timeout, quota, error, no key)
are caught per-provider and returned as a structured status dict.

This module never raises exceptions to callers — it always returns a result dict.
"""

import logging
import os
from typing import Any, Dict, Optional

import httpx
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

GOOGLE_KEY: Optional[str] = os.getenv("GOOGLE_SAFE_BROWSING_API_KEY") or None
VIRUSTOTAL_KEY: Optional[str] = os.getenv("VIRUSTOTAL_API_KEY") or None

REQUEST_TIMEOUT = 10  # seconds per outbound request


# ── Public API ────────────────────────────────────────────────────────────────

def check_url(url: str) -> Dict[str, Any]:
    """
    Query all configured external providers and return a combined result dict.

    Result structure:
        {
          "google_safe_browsing": { status, threat_types, message },
          "virustotal":           { status, malicious, suspicious, harmless,
                                    undetected, total, message },
          "any_threat_found": bool,
          "overall_message": str
        }
    """
    gsb = _check_google_safe_browsing(url)
    vt = _check_virustotal(url)

    any_threat = (
        (gsb["status"] == "threat_found") or
        (vt["status"] == "ok" and (vt.get("malicious", 0) or 0) > 0)
    )

    return {
        "google_safe_browsing": gsb,
        "virustotal": vt,
        "any_threat_found": any_threat,
        "overall_message": _overall_message(gsb, vt, any_threat),
    }


# ── Google Safe Browsing v4 ───────────────────────────────────────────────────

def _check_google_safe_browsing(url: str) -> Dict[str, Any]:
    if not GOOGLE_KEY:
        return {
            "status": "not_configured",
            "threat_types": [],
            "message": "Google Safe Browsing API key not configured.",
        }

    endpoint = f"https://safebrowsing.googleapis.com/v4/threatMatches:find?key={GOOGLE_KEY}"
    payload = {
        "client": {"clientId": "trustai", "clientVersion": "1.0"},
        "threatInfo": {
            "threatTypes": [
                "MALWARE", "SOCIAL_ENGINEERING",
                "UNWANTED_SOFTWARE", "POTENTIALLY_HARMFUL_APPLICATION",
            ],
            "platformTypes": ["ANY_PLATFORM"],
            "threatEntryTypes": ["URL"],
            "threatEntries": [{"url": url}],
        },
    }

    try:
        response = httpx.post(endpoint, json=payload, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        data = response.json()
        matches = data.get("matches", [])
        if matches:
            threat_types = list({m.get("threatType", "UNKNOWN") for m in matches})
            return {
                "status": "threat_found",
                "threat_types": threat_types,
                "message": f"Google Safe Browsing flagged this URL: {', '.join(threat_types)}",
            }
        return {
            "status": "ok",
            "threat_types": [],
            "message": "No threats found by Google Safe Browsing.",
        }
    except httpx.TimeoutException:
        logger.warning("[SecurityService] Google Safe Browsing timeout for %s", url)
        return {
            "status": "timeout",
            "threat_types": [],
            "message": "Google Safe Browsing check timed out; result unavailable.",
        }
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == 429:
            return {
                "status": "quota_exceeded",
                "threat_types": [],
                "message": "Google Safe Browsing quota exceeded; result unavailable.",
            }
        logger.error("[SecurityService] Google Safe Browsing HTTP error: %s", exc)
        return {
            "status": "error",
            "threat_types": [],
            "message": "Google Safe Browsing returned an error; result unavailable.",
        }
    except Exception as exc:
        logger.error("[SecurityService] Google Safe Browsing unexpected error: %s", exc)
        return {
            "status": "error",
            "threat_types": [],
            "message": "Google Safe Browsing check failed; result unavailable.",
        }


# ── VirusTotal API v3 ─────────────────────────────────────────────────────────

def _check_virustotal(url: str) -> Dict[str, Any]:
    if not VIRUSTOTAL_KEY:
        return {
            "status": "not_configured",
            "malicious": 0,
            "suspicious": 0,
            "harmless": 0,
            "undetected": 0,
            "total": 0,
            "message": "VirusTotal API key not configured.",
        }

    headers = {"x-apikey": VIRUSTOTAL_KEY}

    try:
        # Step 1: Submit URL for scanning
        scan_resp = httpx.post(
            "https://www.virustotal.com/api/v3/urls",
            headers=headers,
            data={"url": url},
            timeout=REQUEST_TIMEOUT,
        )
        scan_resp.raise_for_status()
        scan_data = scan_resp.json()

        # Step 2: Retrieve analysis results via the analysis ID
        analysis_id: Optional[str] = None
        try:
            analysis_id = scan_data["data"]["id"]
        except (KeyError, TypeError):
            pass

        if not analysis_id:
            return _vt_error("VirusTotal did not return an analysis ID.")

        analysis_resp = httpx.get(
            f"https://www.virustotal.com/api/v3/analyses/{analysis_id}",
            headers=headers,
            timeout=REQUEST_TIMEOUT,
        )
        analysis_resp.raise_for_status()
        analysis_data = analysis_resp.json()

        stats = (
            analysis_data.get("data", {})
            .get("attributes", {})
            .get("stats", {})
        )
        malicious = int(stats.get("malicious", 0))
        suspicious = int(stats.get("suspicious", 0))
        harmless = int(stats.get("harmless", 0))
        undetected = int(stats.get("undetected", 0))
        total = malicious + suspicious + harmless + undetected

        if malicious > 0:
            msg = f"VirusTotal: {malicious}/{total} engines flagged this URL as malicious."
        elif suspicious > 0:
            msg = f"VirusTotal: {suspicious}/{total} engines flagged this URL as suspicious."
        else:
            msg = f"VirusTotal: No threats found ({harmless} engines returned clean)."

        return {
            "status": "ok",
            "malicious": malicious,
            "suspicious": suspicious,
            "harmless": harmless,
            "undetected": undetected,
            "total": total,
            "message": msg,
        }

    except httpx.TimeoutException:
        logger.warning("[SecurityService] VirusTotal timeout for %s", url)
        return _vt_unavailable("VirusTotal check timed out; result unavailable.")
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == 429:
            return _vt_unavailable("VirusTotal rate limit reached; result unavailable.")
        logger.error("[SecurityService] VirusTotal HTTP error: %s", exc)
        return _vt_unavailable("VirusTotal returned an error; result unavailable.")
    except Exception as exc:
        logger.error("[SecurityService] VirusTotal unexpected error: %s", exc)
        return _vt_unavailable("VirusTotal check failed; result unavailable.")


# ── Helpers ───────────────────────────────────────────────────────────────────

def _vt_error(msg: str) -> Dict[str, Any]:
    return {"status": "error", "malicious": 0, "suspicious": 0,
            "harmless": 0, "undetected": 0, "total": 0, "message": msg}


def _vt_unavailable(msg: str) -> Dict[str, Any]:
    return {"status": "unavailable", "malicious": 0, "suspicious": 0,
            "harmless": 0, "undetected": 0, "total": 0, "message": msg}


def _overall_message(gsb: Dict, vt: Dict, any_threat: bool) -> str:
    if any_threat:
        return "One or more external security sources flagged this URL as potentially malicious."
    providers_ok = [
        p for p, r in [("Google Safe Browsing", gsb), ("VirusTotal", vt)]
        if r["status"] == "ok"
    ]
    providers_unavail = [
        p for p, r in [("Google Safe Browsing", gsb), ("VirusTotal", vt)]
        if r["status"] not in ("ok", "threat_found")
    ]
    parts = []
    if providers_ok:
        parts.append(f"No threats found by: {', '.join(providers_ok)}.")
    if providers_unavail:
        parts.append(f"Results unavailable from: {', '.join(providers_unavail)}.")
    return " ".join(parts) if parts else "External security checks completed."
