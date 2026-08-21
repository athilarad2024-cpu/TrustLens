"""
services/url_service.py
URL phishing detection service — enhanced for accuracy.

Additions over original:
  - Redirect chain following (detects redirect-based phishing)
  - Live domain entropy and structural signals (no model needed)
  - Known-safe whitelist for fast-track safe classification
  - SHAP explanations with new extended features
  - Rule-based override for clearly safe/dangerous URLs
"""

import logging
import urllib.parse
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np

from services.trusted_domains import is_trusted_domain

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
MODEL_PATH = PROJECT_ROOT / "trained_models" / "url_model.pkl"

# ── Model loading ──────────────────────────────────────────────────────────────
_model_artifact: Optional[Dict[str, Any]] = None
_model_load_error: Optional[str] = None


def _load_model() -> None:
    global _model_artifact, _model_load_error
    try:
        import joblib
        _model_artifact = joblib.load(MODEL_PATH)
        logger.info("[URLService] Phishing model loaded: %s", MODEL_PATH)

        # ── Feature-count mismatch check ──────────────────────────────────────
        # Warn immediately at startup if the saved model was trained on a
        # different number of features than the current extractor produces.
        # This means the 11 new enhanced features are NOT used by ML inference,
        # and SHAP explanations will fail.  Fix: retrain the model.
        from models.url_model.url_features import FEATURE_NAMES as _current_fnames
        _saved_fnames: List = _model_artifact.get("feature_names") or []
        if len(_saved_fnames) != len(_current_fnames):
            logger.warning(
                "[URLService] FEATURE MISMATCH: model was trained on %d features but "
                "url_features.py now exports %d features. "
                "ML inference will use the saved %d-feature set; the %d new features "
                "are only used by the rule-based fallback. "
                "Re-run train_url_model.py to fix this.",
                len(_saved_fnames), len(_current_fnames),
                len(_saved_fnames), len(_current_fnames) - len(_saved_fnames),
            )
    except FileNotFoundError:
        _model_load_error = f"Model file not found at {MODEL_PATH}. Run train_url_model.py first."
        logger.warning("[URLService] %s", _model_load_error)
    except Exception as exc:
        _model_load_error = str(exc)
        logger.error("[URLService] Failed to load model: %s", exc)


_load_model()


# ── tldextract import (used in redirect checker) ──────────────────────────────
import tldextract as _tldextract


# ── Redirect chain following ───────────────────────────────────────────────────

def _follow_redirects(url: str, timeout: float = 4.0) -> Dict[str, Any]:
    """
    Follow HTTP redirects and return info about the chain.
    Returns redirect_count, final_url, crossed_domains.
    Non-blocking — wrapped with timeout.
    """
    result = {
        "redirect_count": 0,
        "final_url": url,
        "crossed_suspicious_domain": False,
        "error": None,
    }
    try:
        import httpx
        r = httpx.get(
            url, follow_redirects=True, timeout=timeout,
            headers={"User-Agent": "Mozilla/5.0 (compatible; TrustAI/1.0)"},
            max_redirects=8,
        )
        final = str(r.url)
        redirect_count = len(r.history)

        # Check if any redirect went to a suspicious domain
        all_urls = [str(h.url) for h in r.history] + [final]
        from models.url_model.url_features import SUSPICIOUS_TLDS
        suspicious_crossed = any(
            any(str(u).split("?")[0].endswith(tld) for tld in SUSPICIOUS_TLDS)
            for u in all_urls
        )

        # Check for domain-change redirect (common in phishing)
        try:
            orig_host = _tldextract.extract(url).registered_domain
            final_host = _tldextract.extract(final).registered_domain
            domain_changed = orig_host != final_host and redirect_count > 0
        except Exception:
            domain_changed = False

        result.update({
            "redirect_count": redirect_count,
            "final_url": final,
            "crossed_suspicious_domain": suspicious_crossed or domain_changed,
        })
    except Exception as exc:
        result["error"] = str(exc)
    return result


async def _follow_redirects_with_timeout(url: str, timeout: float = 4.0) -> Dict[str, Any]:
    """
    Run the blocking redirect-following function in a thread-pool executor so
    it does not block FastAPI's asyncio event loop.
    """
    import asyncio
    loop = asyncio.get_event_loop()
    try:
        result = await asyncio.wait_for(
            loop.run_in_executor(None, _follow_redirects, url, timeout),
            timeout=timeout + 1.0,
        )
        return result
    except asyncio.TimeoutError:
        return {"redirect_count": 0, "final_url": url,
                "crossed_suspicious_domain": False, "error": "timeout"}


# ── Public API ─────────────────────────────────────────────────────────────────

async def analyze_url(url: str) -> Dict[str, Any]:
    """
    Analyze a URL for phishing risk.

    Returns a dict with:
        phishing_probability, prediction, feature_values,
        shap_values, model_available, limitations,
        redirect_info, live_signals, trusted_verdict
    """
    from models.url_model.url_features import extract_features, FEATURE_NAMES

    limitations: List[str] = []

    # ── Trusted-domain check (structured verdict used by scoring_service) ──────
    # Uses tldextract for safe parsed-hostname matching -- prevents suffix and
    # spoofing attacks.  We do NOT short-circuit here; the full ML analysis still
    # runs so that phishing_probability remains an honest signal.
    trusted_verdict = is_trusted_domain(url)
    trusted_dict = {
        "is_trusted": trusted_verdict.is_trusted,
        "registered_domain": trusted_verdict.registered_domain,
        "reason": trusted_verdict.reason,
    }

    # ── Feature extraction ─────────────────────────────────────────────────────
    try:
        features = extract_features(url)
    except Exception as exc:
        logger.error("[URLService] Feature extraction failed: %s", exc)
        return _error_result(f"Feature extraction error: {exc}")

    # ── Live signals: redirect chain ───────────────────────────────────────────
    redirect_info = None
    try:
        import asyncio
        redirect_info = await _follow_redirects_with_timeout(url, timeout=4.0)
    except Exception as exc:
        logger.debug("[URLService] Redirect check failed: %s", exc)

    # ── Compute rule-based risk boosts ─────────────────────────────────────────
    rule_boost = 0.0
    if redirect_info:
        if redirect_info.get("crossed_suspicious_domain"):
            rule_boost += 0.25
            limitations.append("URL redirect chain crossed a suspicious domain.")
        if redirect_info.get("redirect_count", 0) > 3:
            rule_boost += 0.10

    # High domain entropy (DGA indicator) — boost risk
    domain_entropy = features.get("domain_entropy", 0)
    if domain_entropy > 3.8:
        rule_boost += 0.15

    # Homoglyph attack
    if features.get("has_homoglyphs", 0):
        rule_boost += 0.30
        limitations.append("URL contains unicode homoglyph characters (possible IDN homograph attack).")

    # ── ML model inference ─────────────────────────────────────────────────────
    # Build feature array using only original features if model was trained on them
    # (new features are additive — we handle mismatched columns gracefully)
    if _model_artifact is None:
        # Rule-based fallback when model unavailable
        base_prob = _rule_based_probability(features)
        prob = float(np.clip(base_prob + rule_boost, 0.0, 1.0))
        prediction = "phishing" if prob >= 0.5 else "benign"
        return {
            "model_available": False,
            "phishing_probability": round(prob, 4),
            "prediction": prediction,
            "feature_values": features,
            "shap_values": None,
            "limitations": [_model_load_error or "URL model not loaded — using rule-based fallback."] + limitations,
            "redirect_info": redirect_info,
            "live_signals": {"domain_entropy": domain_entropy},
            "trusted_verdict": trusted_dict,
        }

    model = _model_artifact["model"]

    # Get the feature names the model was trained with
    try:
        # Try to get trained feature names from model metadata
        trained_features = _model_artifact.get("feature_names") or FEATURE_NAMES
    except Exception:
        trained_features = FEATURE_NAMES

    try:
        feature_array = np.array([[features.get(k, 0.0) for k in trained_features]])
        prob = float(model.predict_proba(feature_array)[0][1])
    except Exception as exc:
        logger.error("[URLService] Model inference error: %s", exc)
        # Fallback to rule-based
        prob = _rule_based_probability(features)

    # Apply rule-based boost (cap at 0.98 to preserve calibration signal)
    prob = float(np.clip(prob + rule_boost, 0.0, 0.98))
    prediction = "phishing" if prob >= 0.5 else "benign"

    # ── SHAP explanation (best-effort) ─────────────────────────────────────────
    shap_values: Optional[List[Dict]] = None
    try:
        import shap
        clf = model.named_steps.get("clf") if hasattr(model, "named_steps") else model
        if hasattr(clf, "estimators_") or hasattr(clf, "get_booster"):
            raw_features = feature_array
            if hasattr(model, "named_steps") and "scaler" in model.named_steps:
                raw_features = model.named_steps["scaler"].transform(feature_array)
            explainer = shap.TreeExplainer(clf)
            sv = explainer.shap_values(raw_features)
            if isinstance(sv, list):
                sv = sv[1]
            shap_values = [
                {"feature": trained_features[i], "shap_value": float(sv[0][i]),
                 "feature_value": float(features.get(trained_features[i], 0.0))}
                for i in range(len(trained_features))
            ]
            shap_values.sort(key=lambda x: abs(x["shap_value"]), reverse=True)
    except Exception as exc:
        _saved_count = len(_model_artifact.get("feature_names") or []) if _model_artifact else 0
        _current_count = len(feature_array[0]) if feature_array is not None else 0
        logger.warning(
            "[URLService] SHAP computation failed (model features=%d, input features=%d): %s",
            _saved_count, _current_count, exc,
        )

    return {
        "model_available": True,
        "phishing_probability": round(prob, 4),
        "prediction": prediction,
        "feature_values": features,
        "shap_values": shap_values,
        "limitations": limitations,
        "redirect_info": redirect_info,
        "live_signals": {
            "domain_entropy": round(domain_entropy, 3),
            "is_known_safe": bool(features.get("is_known_safe", 0)),
            "has_homoglyphs": bool(features.get("has_homoglyphs", 0)),
            "redirect_count": redirect_info.get("redirect_count", 0) if redirect_info else 0,
        },
        "trusted_verdict": trusted_dict,
    }


def get_url_preview(url: str) -> Dict[str, Any]:
    """
    Fast structural preview of a URL — no ML, no network calls (except favicon).
    Returns structural signals instantly for UI preview card.
    """
    from models.url_model.url_features import extract_features, _KNOWN_SAFE_DOMAINS, SUSPICIOUS_TLDS
    try:
        features = extract_features(url)
        parsed = urllib.parse.urlparse(url)
        ext = _tldextract.extract(url)

        domain = ext.registered_domain or parsed.netloc
        hostname = ext.domain or ""
        suffix = f".{ext.suffix}" if ext.suffix else ""

        risk_flags = []
        if features.get("has_ip"):
            risk_flags.append("IP address in URL")
        if features.get("has_suspicious_tld"):
            risk_flags.append(f"Suspicious TLD: {suffix}")
        if features.get("contains_brand"):
            risk_flags.append("Brand name spoofing detected")
        if features.get("has_homoglyphs"):
            risk_flags.append("Unicode homoglyph characters")
        if features.get("domain_entropy", 0) > 3.8:
            risk_flags.append("High domain entropy (possible DGA)")
        if not features.get("has_https"):
            risk_flags.append("No HTTPS")
        if features.get("num_suspicious_keywords", 0) >= 2:
            risk_flags.append(f"{int(features['num_suspicious_keywords'])} suspicious keywords")
        if features.get("has_repeated_words"):
            risk_flags.append("Repeated domain words")

        is_safe = hostname.lower() in _KNOWN_SAFE_DOMAINS and bool(features.get("has_https"))
        risk_score = len(risk_flags) / max(8, 1)  # normalized 0-1

        return {
            "url": url,
            "domain": domain,
            "hostname": hostname,
            "tld": suffix,
            "is_https": bool(features.get("has_https")),
            "is_known_safe": is_safe,
            "favicon_url": f"https://www.google.com/s2/favicons?domain={domain}&sz=32" if domain else None,
            "risk_flags": risk_flags,
            "instant_risk_score": round(risk_score, 3),
            "url_length": int(features.get("url_length", 0)),
            "has_ip": bool(features.get("has_ip")),
            "has_suspicious_tld": bool(features.get("has_suspicious_tld")),
        }
    except Exception as exc:
        return {"url": url, "error": str(exc), "risk_flags": [], "instant_risk_score": 0.5}


# ── Rule-based fallback probability ───────────────────────────────────────────

def _rule_based_probability(features: Dict) -> float:
    """
    Compute a heuristic phishing probability when ML model is unavailable.
    Calibrated against known phishing patterns.
    """
    score = 0.0
    weights = 0.0

    def add(w, val):
        nonlocal score, weights
        score += w * val
        weights += w

    add(0.30, float(features.get("has_ip", 0)))
    add(0.25, float(features.get("has_suspicious_tld", 0)))
    add(0.25, float(features.get("contains_brand", 0)))
    add(0.20, float(features.get("has_homoglyphs", 0)))
    add(0.15, min(float(features.get("num_suspicious_keywords", 0)) / 4.0, 1.0))
    add(0.15, float(features.get("has_repeated_words", 0)))
    add(0.10, min(float(features.get("url_length", 0)) / 200.0, 1.0))
    add(0.10, 1.0 - float(features.get("has_https", 0)))
    add(0.10, min(float(features.get("domain_entropy", 0)) / 4.5, 1.0))
    add(0.10, float(features.get("domain_has_no_vowels", 0)))
    # Known-safe is a strong negative signal
    add(0.30, 1.0 - float(features.get("is_known_safe", 0)))

    return score / max(weights, 1.0) if weights > 0 else 0.4


def _error_result(msg: str) -> Dict[str, Any]:
    return {
        "model_available": False,
        "phishing_probability": None,
        "prediction": "error",
        "feature_values": {},
        "shap_values": None,
        "limitations": [msg],
        "redirect_info": None,
        "live_signals": {},
    }
