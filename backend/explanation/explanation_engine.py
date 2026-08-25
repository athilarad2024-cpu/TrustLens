"""
explanation/explanation_engine.py
Evidence Engine + Explanation Engine — Sections 18 and 19.

Converts raw model outputs, feature values, and external intelligence results
into human-readable evidence items and explanation text.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


# ── Evidence item structure ───────────────────────────────────────────────────

def _evidence(source: str, description: str, severity: str, value: Any = None) -> Dict:
    return {
        "source": source,
        "description": description,
        "severity": severity,          # "high" | "medium" | "low" | "info"
        "supporting_value": str(value) if value is not None else None,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


# ── URL Evidence & Explanation ────────────────────────────────────────────────

def generate_url_evidence(
    url: str,
    url_result: Dict[str, Any],
    security_result: Dict[str, Any],
    trust_score: int,
    verified_safe: bool = False,
    ext_status: str = "unavailable",
) -> Dict[str, Any]:
    """
    Build human-readable evidence items and explanation text.

    Parameters
    ----------
    url            : The URL that was analysed.
    url_result     : Output of url_service.analyze_url().
    security_result: Output of security_service.check_url().
    trust_score    : Final trust score from compute_url_trust_score().
    verified_safe  : True when the URL qualified for the verified-safe fast path.
    ext_status     : "clean" | "threat" | "unavailable" — typed external verdict.
    """
    evidence: List[Dict] = []
    explanation_parts: List[str] = []
    limitations: List[str] = list(url_result.get("limitations", []))

    prob = url_result.get("phishing_probability")

    # ── Trusted-domain evidence (highest priority) ────────────────────────────
    # Shown when tldextract-safe hostname parsing confirmed a trusted registered
    # domain.  We are explicit about WHAT verified it (local domain list, parsed
    # hostname) and what did NOT verify it (external APIs, unless they ran).
    trusted_verdict   = url_result.get("trusted_verdict", {})
    is_trusted        = bool(trusted_verdict.get("is_trusted", False))
    registered_domain = trusted_verdict.get("registered_domain", "")
    any_threat_found  = bool(security_result.get("any_threat_found", False))

    if verified_safe:
        # URL passed all verified-safe conditions
        evidence.insert(0, _evidence(
            "trusted_domain_verification",
            f"Registered domain '{registered_domain}' matched the verified trusted-domain list "
            "and no threat evidence was found. Hostname parsed with tldextract to prevent suffix "
            "spoofing, @ credential attacks, and substring matching mistakes.",
            "info",
            f"verified_safe=True,registered_domain={registered_domain}",
        ))
        explanation_parts.insert(0,
            f"The URL belongs to a verified trusted registered domain ('{registered_domain}'). "
            "The hostname was parsed with tldextract — this blocks spoofing patterns such as "
            "'google.com.evil.example' (suffix attack) and 'user@attacker.com' (@ credential trick). "
            "The phishing model found no significant phishing indicators."
        )

    elif is_trusted and any_threat_found:
        # Trusted domain but a live threat was found — report honestly
        evidence.insert(0, _evidence(
            "trusted_domain_verification",
            f"Domain '{registered_domain}' is on the trusted list but an external security "
            "source reported an active threat. Trusted status is overridden.",
            "high",
            f"trusted_domain={registered_domain},threat_override=True",
        ))
        explanation_parts.insert(0,
            f"Although '{registered_domain}' is a known trusted domain, an active threat "
            "was reported by an external security source. The URL is scored using the generic "
            "evidence-based path."
        )

    elif is_trusted:
        # Trusted domain but failed one of the other verified-safe conditions
        override_reason = url_result.get("override_reason", "")
        evidence.insert(0, _evidence(
            "trusted_domain_verification",
            f"Domain '{registered_domain}' is on the trusted list, but the verified-safe path "
            f"was not applied: {override_reason}",
            "medium",
            f"trusted_domain={registered_domain},verified_safe=False",
        ))

    # ── ML model evidence ─────────────────────────────────────────────────────
    if prob is not None:
        if prob >= 0.75:
            sev = "high"
            explanation_parts.append(
                f"The phishing detection model assigned a high risk probability ({prob:.0%}), "
                "indicating strong structural similarity to known phishing URLs."
            )
        elif prob >= 0.5:
            sev = "medium"
            explanation_parts.append(
                f"The phishing detection model assigned a moderate risk probability ({prob:.0%})."
            )
        else:
            sev = "low"
            explanation_parts.append(
                f"The phishing detection model assigned a low risk probability ({prob:.0%}), "
                "suggesting the URL structure is more typical of legitimate sites."
            )
        evidence.append(_evidence(
            "url_ml_model", f"Phishing probability: {prob:.2%}", sev, f"{prob:.4f}"
        ))
    else:
        limitations.append("URL phishing ML model was not available for this analysis.")
        evidence.append(_evidence("url_ml_model", "Phishing model unavailable.", "info"))

    # ── Feature-level evidence ────────────────────────────────────────────────
    features = url_result.get("feature_values", {})
    _add_url_feature_evidence(features, evidence, explanation_parts)

    # ── SHAP evidence ─────────────────────────────────────────────────────────
    shap_vals = url_result.get("shap_values") or []
    for sv in shap_vals[:5]:  # top 5 SHAP features
        impact = "increases" if sv["shap_value"] > 0 else "reduces"
        evidence.append(_evidence(
            "shap_explanation",
            f"Feature '{sv['feature']}' (value={sv['feature_value']:.2f}) {impact} phishing risk.",
            "info",
            f"SHAP={sv['shap_value']:.4f}",
        ))

    # ── External security intelligence ────────────────────────────────────────
    gsb = security_result.get("google_safe_browsing", {})
    vt  = security_result.get("virustotal", {})

    _add_gsb_evidence(gsb, evidence, explanation_parts, limitations)
    _add_vt_evidence(vt, evidence, explanation_parts, limitations)

    # ── Overall explanation ───────────────────────────────────────────────────
    prediction_label = _url_prediction_label(trust_score, prob, verified_safe=verified_safe)
    explanation = _build_explanation(prediction_label, explanation_parts, limitations, trust_score)

    return {"evidence": evidence, "explanation": explanation, "limitations": limitations}


def _add_url_feature_evidence(features: Dict, evidence: List, parts: List) -> None:
    if features.get("has_ip"):
        evidence.append(_evidence("url_features", "URL uses an IP address instead of a domain name.", "high", "has_ip=1"))
        parts.append("The URL contains a raw IP address instead of a domain name — a common phishing indicator.")

    if features.get("has_suspicious_tld"):
        evidence.append(_evidence("url_features", "URL uses a high-risk TLD associated with phishing.", "high", "suspicious_tld=1"))
        parts.append("The URL uses a top-level domain (TLD) that is statistically over-represented in phishing campaigns.")

    if features.get("contains_brand"):
        evidence.append(_evidence("url_features", "URL mentions a well-known brand name not matching the domain.", "high", "brand_spoofing=1"))
        parts.append("The URL contains a recognizable brand name in a path or subdomain while the registered domain is different — a common spoofing technique.")

    num_kw = int(features.get("num_suspicious_keywords", 0))
    if num_kw >= 2:
        evidence.append(_evidence("url_features", f"{num_kw} suspicious keywords found (e.g., login, verify, payment).", "medium", f"keywords={num_kw}"))
        parts.append(f"The URL contains {num_kw} suspicious keywords commonly used in phishing URLs.")

    url_len = int(features.get("url_length", 0))
    if url_len > 100:
        evidence.append(_evidence("url_features", f"URL is unusually long ({url_len} characters).", "medium", f"length={url_len}"))

    if not features.get("has_https"):
        evidence.append(_evidence("url_features", "URL uses HTTP (unencrypted).", "low", "https=0"))


def _add_gsb_evidence(gsb: Dict, evidence: List, parts: List, limitations: List) -> None:
    status = gsb.get("status")
    if status == "threat_found":
        threats = ", ".join(gsb.get("threat_types", []))
        evidence.append(_evidence("google_safe_browsing", f"Google Safe Browsing threat detected: {threats}", "high", threats))
        parts.append(f"Google Safe Browsing flagged this URL as: {threats}.")
    elif status == "ok":
        evidence.append(_evidence("google_safe_browsing", "Google Safe Browsing found no threats.", "info"))
    else:
        limitations.append(f"Google Safe Browsing: {gsb.get('message', 'result unavailable')}")
        evidence.append(_evidence("google_safe_browsing", gsb.get("message", "Unavailable."), "info"))


def _add_vt_evidence(vt: Dict, evidence: List, parts: List, limitations: List) -> None:
    status = vt.get("status")
    if status == "ok":
        malicious = vt.get("malicious", 0)
        suspicious = vt.get("suspicious", 0)
        total = vt.get("total", 0)
        if malicious > 0:
            evidence.append(_evidence("virustotal", f"{malicious}/{total} engines flagged as malicious.", "high", f"malicious={malicious}"))
            parts.append(f"VirusTotal: {malicious} out of {total} security engines flagged this URL as malicious.")
        elif suspicious > 0:
            evidence.append(_evidence("virustotal", f"{suspicious}/{total} engines flagged as suspicious.", "medium", f"suspicious={suspicious}"))
        else:
            evidence.append(_evidence("virustotal", f"No threats found by VirusTotal ({total} engines checked).", "info"))
    else:
        limitations.append(f"VirusTotal: {vt.get('message', 'result unavailable')}")
        evidence.append(_evidence("virustotal", vt.get("message", "Unavailable."), "info"))


def _url_prediction_label(score: int, prob: Optional[float], verified_safe: bool = False) -> str:
    if score == 100 and verified_safe:
        return "Safe — Verified Trusted Domain"
    if score >= 80:
        return "Low Risk — Likely Safe"
    if score <= 19:
        return "Very High Risk — Likely Phishing"
    if score <= 39:
        return "High Risk — Suspicious URL"
    if score <= 59:
        return "Medium Risk — Possibly Suspicious"
    return "Low-Moderate Risk — Likely Safe"


# ── Image Evidence & Explanation ──────────────────────────────────────────────

def generate_image_evidence(
    image_result: Dict[str, Any],
    trust_score: int,
) -> Dict[str, Any]:
    evidence: List[Dict] = []
    parts: List[str] = list(image_result.get("reasons", []))
    limitations: List[str] = list(image_result.get("limitations", []))

    prob = image_result.get("ai_probability")
    if prob is None:
        prob = image_result.get("ai_generated_probability")
    confidence = image_result.get("confidence")
    classification = image_result.get("classification", "uncertain")

    if prob is not None:
        sev = "high" if prob >= 0.70 else "medium" if prob >= 0.30 else "low"
        evidence.append(_evidence("image_ai_model", f"AI-generation probability: {prob:.2%}", sev, f"{prob:.4f}"))
        if confidence is not None:
            evidence.append(_evidence("model_confidence", f"Analysis confidence: {confidence:.2%}", "info", f"{confidence:.4f}"))

    # Gemini Multimodal Evidence
    if image_result.get("gemini_available"):
        evidence.append(_evidence("gemini_multimodal_vision", "Gemini 2.5 multimodal visual inspection completed.", "info", "gemini=active"))

    # Visual signals from Gemini
    for sig in image_result.get("visual_signals", []):
        feat = sig.get("feature", "Visual Feature")
        obs = sig.get("observation", "")
        assess = sig.get("assessment", "inconclusive")
        sev = "high" if assess == "synthetic" else "low" if assess == "natural" else "medium"
        evidence.append(_evidence(f"visual_{feat.lower().replace(' ', '_')}", f"{feat}: {obs}", sev, assess))

    # Technical / forensic signals
    signals = image_result.get("technical_signals", {})
    if signals:
        fmt = signals.get("format", "unknown")
        w, h = signals.get("width", 0), signals.get("height", 0)
        has_exif = bool(signals.get("has_exif", True))
        evidence.append(_evidence("technical_signals", f"Format: {fmt}, Size: {int(w)}x{int(h)}px", "info"))

        ela = signals.get("ela_score")
        if ela is not None:
            ela_sev = "high" if ela > 0.6 else "medium" if ela > 0.35 else "low"
            evidence.append(_evidence(
                "ela_analysis",
                f"Error Level Analysis (ELA) score: {ela:.2f} — "
                + ("elevated ELA indicates possible re-compression or AI generation patterns." if ela > 0.4
                   else "ELA score is within normal range for authentic images."),
                ela_sev, f"ela={ela:.4f}",
            ))

        freq = signals.get("freq_score")
        if freq is not None:
            freq_sev = "high" if freq > 0.6 else "medium" if freq > 0.35 else "low"
            evidence.append(_evidence(
                "frequency_analysis",
                f"DCT frequency analysis score: {freq:.2f} — "
                + ("abnormal frequency distribution detected." if freq > 0.4
                   else "frequency distribution is typical of real photographic content."),
                freq_sev, f"freq={freq:.4f}",
            ))

        noise = signals.get("noise_score")
        if noise is not None:
            noise_sev = "high" if noise > 0.6 else "medium" if noise > 0.35 else "low"
            evidence.append(_evidence(
                "noise_analysis",
                f"Noise pattern analysis score: {noise:.2f} — "
                + ("irregular noise pattern." if noise > 0.4
                   else "noise pattern is consistent with real camera sensor noise."),
                noise_sev, f"noise={noise:.4f}",
            ))

        if not has_exif:
            evidence.append(_evidence("technical_signals", "No EXIF metadata detected (normal on social media).", "low"))

    explanation = _build_explanation(
        _image_prediction_label(trust_score),
        parts,
        limitations,
        trust_score,
    )

    return {"evidence": evidence, "explanation": explanation, "limitations": limitations}


def _image_prediction_label(score: int) -> str:
    if score >= 70:
        return "Likely Authentic Image"
    if score <= 30:
        return "Likely AI-Generated Image"
    return "Uncertain / Mixed Signals"


# ── Video Evidence & Explanation ──────────────────────────────────────────────

def generate_video_evidence(
    video_result: Dict[str, Any],
    trust_score: int,
) -> Dict[str, Any]:
    evidence: List[Dict] = []
    parts: List[str] = list(video_result.get("reasons", []))
    limitations: List[str] = list(video_result.get("limitations", []))

    prob = video_result.get("ai_probability")
    if prob is None:
        prob = video_result.get("deepfake_probability")
    confidence = video_result.get("confidence")
    temporal_score = video_result.get("temporal_consistency_score", 0.7)
    frames_analyzed = video_result.get("frames_analyzed", 0)

    if prob is not None:
        sev = "high" if prob >= 0.70 else "medium" if prob >= 0.30 else "low"
        evidence.append(_evidence("video_ai_model", f"AI / Deepfake probability: {prob:.2%}", sev, f"{prob:.4f}"))
        if confidence is not None:
            evidence.append(_evidence("model_confidence", f"Analysis confidence: {confidence:.2%}", "info", f"{confidence:.4f}"))

    evidence.append(_evidence(
        "temporal_consistency",
        f"Temporal consistency across {frames_analyzed} frames: {temporal_score:.2%} — "
        + ("smooth inter-frame flow and identity stability." if temporal_score >= 0.7
           else "detected boundary warping or inter-frame flickering."),
        "low" if temporal_score >= 0.7 else "high" if temporal_score < 0.4 else "medium",
        f"{temporal_score:.4f}",
    ))

    # Gemini Multimodal Evidence
    if video_result.get("gemini_available"):
        evidence.append(_evidence("gemini_video_analysis", f"Gemini 2.5 analyzed {frames_analyzed} representative video keyframes.", "info", "gemini=active"))

    # Visual signals
    for sig in video_result.get("visual_signals", []):
        feat = sig.get("feature", "Visual Feature")
        obs = sig.get("observation", "")
        assess = sig.get("assessment", "inconclusive")
        sev = "high" if assess == "synthetic" else "low" if assess == "natural" else "medium"
        evidence.append(_evidence(f"visual_{feat.lower().replace(' ', '_')}", f"{feat}: {obs}", sev, assess))

    # Temporal signals
    for sig in video_result.get("temporal_signals", []):
        name = sig.get("signal", "Temporal Signal")
        obs = sig.get("observation", "")
        susp = sig.get("is_suspicious", False)
        evidence.append(_evidence(f"temporal_{name.lower().replace(' ', '_')}", f"{name}: {obs}", "high" if susp else "low", str(susp)))

    meta = video_result.get("technical_signals", {})
    if meta:
        evidence.append(_evidence("technical_signals",
            f"Video: {meta.get('width',0)}×{meta.get('height',0)}px, "
            f"{meta.get('fps',0):.1f}fps, {meta.get('duration_seconds',0):.1f}s, "
            f"{frames_analyzed} frames sampled throughout video",
            "info",
        ))

    explanation = _build_explanation(
        _video_prediction_label(trust_score),
        parts,
        limitations,
        trust_score,
    )

    return {"evidence": evidence, "explanation": explanation, "limitations": limitations}


def _video_prediction_label(score: int) -> str:
    if score >= 70:
        return "Likely Authentic Video"
    if score <= 30:
        return "Likely AI-Generated / Deepfake Video"
    return "Uncertain / Mixed Video Signals"


# ── Shared helper ─────────────────────────────────────────────────────────────

def _build_explanation(
    prediction_label: str,
    reason_parts: List[str],
    limitations: List[str],
    trust_score: int,
) -> Dict[str, Any]:
    # Deduplicate reason parts
    dedup_parts = list(dict.fromkeys(reason_parts))
    return {
        "prediction_label": prediction_label,
        "trust_score": trust_score,
        "reasons": dedup_parts if dedup_parts else ["Analysis completed based on available forensic and visual signals."],
        "limitations": [
            *list(dict.fromkeys(limitations)),
            "TrustAI provides a decision-support risk assessment, not an absolute truth oracle.",
            "Never claim media is 100% real or 100% AI-generated.",
        ],
    }
