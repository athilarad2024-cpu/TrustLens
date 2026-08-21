"""
services/scoring_service.py
Trust Score Engine — Section 17 of the master document.

Converts normalized evidence from all analysis modules into a 0–100
application-level Trust Score and a named Risk Level.

Score = 100 means lower assessed risk.
Score = 0   means higher assessed risk.

Architecture
------------
URL scoring uses a two-path design:

  VERIFIED-SAFE FAST PATH
  ─────────────────────────────────────────────────────────────────────────
  When a URL's registered domain is in the trusted-domain list (verified
  with tldextract to prevent suffix / @ / substring spoofing) AND no threat
  evidence exists AND no serious structural anomaly is present:

      trust_score = 100   (risk_level = "safe")

  Missing external API keys do NOT reduce the score.  They are recorded in
  limitations only — unavailability ≠ risk.

  GENERIC EVIDENCE-BASED PATH
  ─────────────────────────────────────────────────────────────────────────
  All URLs that do not qualify for the fast path are scored with a weighted
  combination of ML probability, external intelligence, URL structure, HTTPS
  status, and suspicious keywords.  External APIs that are not configured
  contribute zero weighted risk and add a limitations note.

These weights are engineering starting points. Tune with held-out validation
data and document the final values used in the project report.
"""

from typing import Any, Dict, Literal, Optional, Tuple

# ── Weight tables (Section 17.2) ──────────────────────────────────────────────

URL_WEIGHTS = {
    "phishing_ml":            0.40,
    "external_intelligence":  0.30,
    "url_structure":          0.15,
    "domain_https":           0.10,
    "safe_signals":           0.05,
}

IMAGE_WEIGHTS = {
    "synthetic_model":    0.65,
    "forensic_signals":   0.15,
    "model_reliability":  0.20,
}

VIDEO_WEIGHTS = {
    "deepfake_model":          0.50,
    "suspicious_frame_ratio":  0.20,
    "technical_signals":       0.15,
    "reliability":             0.15,
}

# ── Risk bands (Section 17.3) ─────────────────────────────────────────────────

RISK_BANDS = [
    (100, 100, "safe"),          # Verified trusted domain — no known threats
    (80,  99,  "low"),
    (60,  79,  "moderate-low"),
    (40,  59,  "medium"),
    (20,  39,  "high"),
    (0,   19,  "very-high"),
]


def score_to_risk(score: int) -> str:
    for low, high, label in RISK_BANDS:
        if low <= score <= high:
            return label
    return "very-high"


# ── External intelligence status ──────────────────────────────────────────────
# Typed representation that separates "no data" from "threat found".
# This prevents the confusion of returning 0.30 risk for unconfigured APIs.

ExternalStatus = Literal["clean", "threat", "unavailable"]


def _evaluate_external(
    gsb: Dict,
    vt: Dict,
    limitations: list,
) -> Tuple[ExternalStatus, float]:
    """
    Evaluate external security intelligence (GSB + VirusTotal).

    Returns
    -------
    status : ExternalStatus
        "clean"       — at least one API ran and found no threats.
        "threat"      — at least one API found a confirmed threat.
        "unavailable" — no API is configured / reachable; we have no data.

    ext_risk : float
        0.0  when clean or unavailable.
        0.0–1.0 proportional severity when threat found.

    Design principle
    ----------------
    "Unavailable" means we have no information from that source.
    It does NOT mean the URL is risky.  We record it in limitations and
    contribute ZERO to the weighted risk so that missing API keys do not
    artificially lower the trust score of verified trusted domains.
    """
    gsb_status = gsb.get("status")
    vt_status  = vt.get("status")

    has_gsb = gsb_status is not None and gsb_status != ""
    has_vt  = vt_status  is not None and vt_status  != ""

    # Collect per-source risks where data is available
    available_risks: list = []

    # Google Safe Browsing
    if gsb_status == "threat_found":
        available_risks.append(1.0)
    elif gsb_status == "ok":
        available_risks.append(0.0)
    else:
        limitations.append(
            f"Google Safe Browsing: {gsb.get('message', 'API not configured or unavailable')}. "
            "This check was skipped — no threat or clean verdict was obtained."
        )

    # VirusTotal
    if vt_status == "ok":
        malicious  = vt.get("malicious", 0)  or 0
        suspicious = vt.get("suspicious", 0) or 0
        total      = vt.get("total", 0)      or 1
        vt_risk    = min(1.0, (malicious + 0.5 * suspicious) / max(total, 1))
        available_risks.append(vt_risk)
    elif vt_status == "threat_found":
        available_risks.append(1.0)
    else:
        limitations.append(
            f"VirusTotal: {vt.get('message', 'API not configured or unavailable')}. "
            "This check was skipped — no threat or clean verdict was obtained."
        )

    if not available_risks:
        # Genuinely no external data — do NOT penalise
        return "unavailable", 0.0

    max_risk = max(available_risks)
    avg_risk = sum(available_risks) / len(available_risks)
    # Blend: weight max higher so a single high-risk source dominates
    combined = max_risk * 0.6 + avg_risk * 0.4

    if max_risk >= 0.5:
        return "threat", combined
    return "clean", combined


# ── Verified-safe predicate ───────────────────────────────────────────────────

# Maximum ML phishing probability a trusted domain may have and still be
# classified as verified-safe.  Values at or above this threshold indicate a
# genuine contradiction between the domain-list trust and the ML model output,
# and the URL falls through to the generic weighted scoring path.
_VERIFIED_SAFE_ML_THRESHOLD = 0.50


def _is_verified_safe(
    is_trusted: bool,
    any_threat_found: bool,
    ml_prob: Optional[float],
    features: Dict,
    redirect_info: Optional[Dict],
) -> Tuple[bool, str]:
    """
    Determine whether a URL qualifies for the verified-safe fast path.

    A URL is verified-safe when ALL of the following hold:
        1. registered domain is in the trusted-domain list (tldextract-verified)
        2. no external security source reported an active threat
        3. ML phishing probability is below the contradiction threshold (< 0.50)
        4. URL does not contain an IP address (structural spoofing)
        5. URL does not contain unicode homoglyph characters (IDN attack)
        6. Redirect chain did not cross a suspicious domain

    Returns
    -------
    (True, "")             when all conditions pass.
    (False, reason_str)    when any condition fails, with an explanation.
    """
    if not is_trusted:
        return False, "Domain is not on the trusted-domain list."

    if any_threat_found:
        return False, (
            "An active threat was reported by an external security source. "
            "Trusted-domain status is overridden."
        )

    if ml_prob is not None and ml_prob >= _VERIFIED_SAFE_ML_THRESHOLD:
        return False, (
            f"ML phishing model returned a high risk probability ({ml_prob:.0%}), "
            "contradicting the trusted-domain classification. "
            "Generic evidence-based scoring applied."
        )

    if features.get("has_ip", 0):
        return False, "URL uses an IP address — structural spoofing cannot be ruled out."

    if features.get("has_homoglyphs", 0):
        return False, "URL contains unicode homoglyph characters (possible IDN homograph attack)."

    if redirect_info and redirect_info.get("crossed_suspicious_domain"):
        return False, "Redirect chain crossed a suspicious or different domain."

    return True, ""


# ── URL Trust Score ───────────────────────────────────────────────────────────

def compute_url_trust_score(
    url_result: Dict[str, Any],
    security_result: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Compute trust score for a URL analysis.

    Evidence sources
    ----------------
    url_result      : output of url_service.analyze_url()
    security_result : output of security_service.check_url()

    Scoring paths
    -------------
    VERIFIED-SAFE FAST PATH
        trust_score = 100 when the registered domain is in the trusted-domain
        list AND no threat evidence exists AND no serious URL anomaly is
        present.  Missing external API keys do NOT contribute risk.

    GENERIC EVIDENCE-BASED PATH
        Weighted combination of ML, external intelligence, URL structure,
        HTTPS, and suspicious keywords.  External APIs that are not
        configured contribute 0.0 risk (recorded in limitations).
    """
    limitations: list = list(url_result.get("limitations", []))

    # ── Read trusted-domain verdict ──────────────────────────────────────────
    trusted_verdict   = url_result.get("trusted_verdict", {})
    is_trusted        = bool(trusted_verdict.get("is_trusted", False))
    any_threat_found  = bool(security_result.get("any_threat_found", False))

    # ── Core signals ──────────────────────────────────────────────────────────
    ml_prob      = url_result.get("phishing_probability")
    features     = url_result.get("feature_values", {})
    redirect_info = url_result.get("redirect_info")

    # ── External intelligence evaluation ─────────────────────────────────────
    gsb = security_result.get("google_safe_browsing", {})
    vt  = security_result.get("virustotal", {})
    ext_status, ext_risk = _evaluate_external(gsb, vt, limitations)

    # ── Verified-safe fast path ───────────────────────────────────────────────
    verified_safe, override_reason = _is_verified_safe(
        is_trusted=is_trusted,
        any_threat_found=any_threat_found,
        ml_prob=ml_prob,
        features=features,
        redirect_info=redirect_info,
    )

    if verified_safe:
        # Confidence: ML available + trusted domain both contribute positively.
        # We cannot claim full confidence without external APIs.
        n_available = sum([
            ml_prob is not None,
            ext_status == "clean",
        ])
        confidence = 0.60 + 0.15 * n_available  # 0.60 – 0.90
        confidence = min(confidence + 0.10, 1.0)  # trusted domain bonus

        return {
            "trust_score":            100,
            "risk_level":             "safe",
            "confidence":             round(min(confidence, 1.0), 3),
            "limitations":            limitations,
            "verified_safe":          True,
            "trusted_domain_applied": True,
            "override_reason":        "",
            "ext_status":             ext_status,
        }

    # ── Generic evidence-based path ───────────────────────────────────────────
    weighted_risk = 0.0

    # ── Phishing ML component (40%) ──────────────────────────────────────────
    if ml_prob is not None:
        weighted_risk += URL_WEIGHTS["phishing_ml"] * ml_prob
    else:
        # Model unavailable — moderate uncertainty penalty only on generic path
        limitations.append(
            "URL phishing ML model unavailable; score is based on structural signals only."
        )
        weighted_risk += URL_WEIGHTS["phishing_ml"] * 0.4

    # ── External intelligence component (30%) ────────────────────────────────
    # ext_risk is 0.0 when unavailable (not a risk signal)
    weighted_risk += URL_WEIGHTS["external_intelligence"] * ext_risk

    # ── URL structure component (15%) ────────────────────────────────────────
    struct_risk = _url_structure_risk(features, is_trusted=is_trusted)
    weighted_risk += URL_WEIGHTS["url_structure"] * struct_risk

    # ── Domain / HTTPS component (10%) ───────────────────────────────────────
    # 0.0 for HTTPS, 1.0 for plain HTTP.
    https_ok    = float(features.get("has_https", 0.0))
    domain_risk = 1.0 - https_ok
    weighted_risk += URL_WEIGHTS["domain_https"] * domain_risk

    # ── Safe signals (5%) ────────────────────────────────────────────────────
    # Only applied for non-trusted domains to prevent self-penalisation of
    # legitimate brand names that appear in their own trusted hostname.
    if not is_trusted:
        num_kw = float(features.get("num_suspicious_keywords", 0))
        safe_signal_risk = min(num_kw / 5.0, 1.0)
        weighted_risk += URL_WEIGHTS["safe_signals"] * safe_signal_risk

    # ── Rule-based boosts (redirect chain, high entropy, homoglyphs) ─────────
    if redirect_info:
        if redirect_info.get("crossed_suspicious_domain"):
            weighted_risk += 0.25
            limitations.append("URL redirect chain crossed a suspicious domain.")
        if redirect_info.get("redirect_count", 0) > 3:
            weighted_risk += 0.10

    domain_entropy = features.get("domain_entropy", 0)
    if domain_entropy > 3.8:
        weighted_risk += 0.15

    if features.get("has_homoglyphs", 0):
        weighted_risk += 0.30
        limitations.append(
            "URL contains unicode homoglyph characters (possible IDN homograph attack)."
        )

    # ── Convert to 0–100 trust score ─────────────────────────────────────────
    weighted_risk = max(0.0, min(1.0, weighted_risk))
    score         = int(round((1.0 - weighted_risk) * 100))
    risk_level    = score_to_risk(score)

    # ── Confidence ────────────────────────────────────────────────────────────
    n_available = sum([
        ml_prob is not None,
        ext_status == "clean",
        ext_status == "threat",
    ])
    confidence = 0.5 + 0.17 * n_available
    if is_trusted:
        confidence = min(confidence + 0.10, 1.0)

    return {
        "trust_score":            score,
        "risk_level":             risk_level,
        "confidence":             round(min(confidence, 1.0), 3),
        "limitations":            limitations,
        "verified_safe":          False,
        "trusted_domain_applied": False,
        "override_reason":        override_reason,
        "ext_status":             ext_status,
    }


# ── Image Trust Score ─────────────────────────────────────────────────────────

def compute_image_trust_score(image_result: Dict[str, Any]) -> Dict[str, Any]:
    """Compute trust score for an image analysis."""
    limitations = list(image_result.get("limitations", []))

    prob       = image_result.get("ai_generated_probability")
    confidence = image_result.get("confidence")

    if prob is None:
        limitations.append("Image model unavailable; trust score based on technical signals only.")
        model_risk = 0.4
        conf = 0.35
    else:
        model_risk = float(prob)
        conf = float(confidence or 0.6)

    # ── Forensic signals component (15%) ──────────────────────────────────────
    signals      = image_result.get("technical_signals", {})
    forensic_risk = _image_forensic_risk(signals, limitations)

    # ── Model reliability component (20%) ────────────────────────────────────
    reliability_risk = 1.0 - conf

    weighted_risk = (
        IMAGE_WEIGHTS["synthetic_model"]   * model_risk +
        IMAGE_WEIGHTS["forensic_signals"]  * forensic_risk +
        IMAGE_WEIGHTS["model_reliability"] * reliability_risk
    )

    score = int(round((1.0 - max(0.0, min(1.0, weighted_risk))) * 100))
    return {
        "trust_score": score,
        "risk_level":  score_to_risk(score),
        "confidence":  round(conf, 3),
        "limitations": limitations,
    }


# ── Video Trust Score ─────────────────────────────────────────────────────────

def compute_video_trust_score(video_result: Dict[str, Any]) -> Dict[str, Any]:
    """Compute trust score for a video analysis."""
    limitations = list(video_result.get("limitations", []))

    deepfake_prob = video_result.get("deepfake_probability")
    sfr           = video_result.get("suspicious_frame_ratio")
    confidence    = video_result.get("confidence")

    if deepfake_prob is None:
        limitations.append("Deepfake model unavailable; trust score based on available signals only.")
        model_risk = 0.4
        sfr_risk   = 0.4
        conf       = 0.3
    else:
        model_risk = float(deepfake_prob)
        sfr_risk   = float(sfr) if sfr is not None else 0.4
        conf       = float(confidence or 0.5)

    # ── Technical signals (15%) ───────────────────────────────────────────────
    tech_signals  = video_result.get("technical_signals", {})
    tech_risk     = _video_technical_risk(tech_signals)

    # ── Reliability (15%) ─────────────────────────────────────────────────────
    reliability_risk = 1.0 - conf

    weighted_risk = (
        VIDEO_WEIGHTS["deepfake_model"]         * model_risk +
        VIDEO_WEIGHTS["suspicious_frame_ratio"] * sfr_risk +
        VIDEO_WEIGHTS["technical_signals"]      * tech_risk +
        VIDEO_WEIGHTS["reliability"]            * reliability_risk
    )

    score = int(round((1.0 - max(0.0, min(1.0, weighted_risk))) * 100))
    return {
        "trust_score": score,
        "risk_level":  score_to_risk(score),
        "confidence":  round(conf, 3),
        "limitations": limitations,
    }


# ── Internal helpers ──────────────────────────────────────────────────────────

def _url_structure_risk(features: Dict, is_trusted: bool = False) -> float:
    """
    Compute structural risk from URL features.

    is_trusted
        When True the suspicious-keyword component is skipped.
        A legitimate trusted domain (e.g. google.com) may contain brand
        keywords in its own hostname and must not be penalised for them.
        All other structural signals (IP, suspicious TLD, brand spoofing,
        dots, hyphens) still apply — a trusted domain with a suspicious
        structure is a genuine anomaly worth flagging.
    """
    risk = 0.0

    # High URL length is suspicious
    url_len = features.get("url_length", 0)
    if url_len > 100:
        risk += 0.3
    elif url_len > 75:
        risk += 0.15

    # Many dots
    dots = features.get("num_dots", 0)
    if dots > 5:
        risk += 0.2
    elif dots > 3:
        risk += 0.1

    # Many hyphens (common in phishing)
    hyphens = features.get("num_hyphens", 0)
    if hyphens > 3:
        risk += 0.2

    # IP address in URL
    if features.get("has_ip", 0):
        risk += 0.3

    # Suspicious TLD
    if features.get("has_suspicious_tld", 0):
        risk += 0.25

    # Brand name spoofing — only meaningful for untrusted domains
    # (trusted domain's own brand name in hostname is not spoofing)
    if not is_trusted and features.get("contains_brand", 0):
        risk += 0.3

    return min(risk, 1.0)


def _image_forensic_risk(signals: Dict, limitations: list) -> float:
    risk = 0.0
    has_exif = signals.get("has_exif", True)
    if not has_exif:
        risk += 0.2
        limitations.append(
            "Image has no EXIF metadata. Note: missing metadata is not proof of manipulation — "
            "many legitimate images have metadata removed."
        )
    # Unusual aspect ratio (very wide or tall)
    w = signals.get("width", 0)
    h = signals.get("height", 0)
    if w > 0 and h > 0:
        ratio = max(w, h) / max(min(w, h), 1)
        if ratio > 4:
            risk += 0.1
    return min(risk, 1.0)


def _video_technical_risk(signals: Dict) -> float:
    # Low FPS could indicate manipulation (not conclusive)
    fps = signals.get("fps", 30)
    if fps and fps < 15:
        return 0.3
    return 0.0
