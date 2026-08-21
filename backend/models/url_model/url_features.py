"""
models/url_model/url_features.py
URL feature extraction — enhanced for accuracy.

Features include structural signals, entropy measures, homoglyph detection,
known-safe domain whitelist, and redirect/domain signals.
All features are numeric (float) for sklearn pipeline compatibility.
"""

import ipaddress
import math
import re
import unicodedata
import urllib.parse
from typing import Dict, List

import tldextract

# ── Known safe domains (top legitimate domains — whitelist) ───────────────────
_KNOWN_SAFE_DOMAINS = frozenset({
    "google", "youtube", "facebook", "twitter", "instagram", "linkedin",
    "microsoft", "apple", "amazon", "netflix", "github", "stackoverflow",
    "wikipedia", "reddit", "whatsapp", "tiktok", "zoom", "dropbox",
    "salesforce", "adobe", "stripe", "shopify", "wordpress", "cloudflare",
    "mozilla", "python", "nodejs", "docker", "kubernetes", "heroku",
    "aws", "azure", "gcp", "openai", "anthropic", "huggingface",
    "nytimes", "bbc", "cnn", "reuters", "bloomberg", "theguardian",
    "yahoo", "bing", "duckduckgo", "brave", "opera", "firefox",
    "slack", "discord", "telegram", "signal", "skype", "teams",
    "spotify", "soundcloud", "twitch", "vimeo", "dailymotion",
    "paypal", "stripe", "square", "visa", "mastercard", "chase",
    "wellsfargo", "bankofamerica", "citibank", "hsbc", "barclays",
    "ebay", "etsy", "walmart", "target", "bestbuy", "homedepot",
    "fedex", "ups", "usps", "dhl", "airbnb", "booking", "expedia",
})

# Suspicious keywords that frequently appear in phishing URLs
SUSPICIOUS_KEYWORDS: List[str] = [
    "login", "verify", "account", "secure", "update", "banking",
    "password", "confirm", "billing", "payment", "signin", "webscr",
    "paypal", "ebay", "amazon", "apple", "microsoft", "google",
    "support", "help", "service", "wallet", "crypto", "free", "prize",
    "reset", "unlock", "suspended", "alert", "authenticate", "authorize",
    "validate", "urgent", "limited", "expire", "suspend", "winner",
]

SUSPICIOUS_TLDS: set = {
    ".tk", ".ml", ".ga", ".cf", ".gq", ".xyz", ".top", ".club",
    ".work", ".click", ".link", ".live", ".online", ".buzz", ".icu",
    ".vip", ".win", ".bid", ".date", ".loan", ".review", ".stream",
    ".gdn", ".ren", ".kim", ".men", ".download", ".racing",
}

_BRAND_NAMES = [
    "paypal", "apple", "google", "microsoft", "amazon", "netflix",
    "facebook", "instagram", "twitter", "linkedin", "ebay", "chase",
    "wellsfargo", "bankofamerica", "citibank", "dhl", "fedex", "ups",
    "dropbox", "icloud", "outlook", "office365", "onedrive", "yahoo",
    "steam", "roblox", "coinbase", "binance", "blockchain",
]

# ── Homoglyph / Unicode lookalike detection ────────────────────────────────────
# Characters that visually resemble ASCII but are different Unicode codepoints
_HOMOGLYPH_MAP = {
    'а': 'a', 'е': 'e', 'о': 'o', 'р': 'p', 'с': 'c', 'х': 'x',
    'В': 'B', 'С': 'C', 'Е': 'E', 'М': 'M', 'Н': 'H', 'О': 'O',
    'Р': 'P', 'Т': 'T', 'Х': 'X', 'А': 'A', 'К': 'K',
    'ο': 'o', 'ρ': 'p', 'ν': 'v', 'η': 'n', 'Ι': 'I', 'Κ': 'K',
}


def _has_homoglyphs(text: str) -> bool:
    """Detect unicode homoglyph / lookalike characters in domain name."""
    for ch in text:
        if ch in _HOMOGLYPH_MAP or (ord(ch) > 127 and unicodedata.category(ch).startswith('L')):
            return True
    return False


# ── Entropy calculation ───────────────────────────────────────────────────────

def _shannon_entropy(s: str) -> float:
    """Shannon entropy of a string — high entropy indicates random/DGA domain."""
    if not s:
        return 0.0
    freq = {}
    for c in s:
        freq[c] = freq.get(c, 0) + 1
    total = len(s)
    return -sum((v / total) * math.log2(v / total) for v in freq.values())


# ── Private helpers ────────────────────────────────────────────────────────────

def _has_ip_in_host(hostname: str) -> bool:
    try:
        ipaddress.ip_address(hostname)
        return True
    except ValueError:
        return False


def _contains_brand(url_lower: str, hostname_lower: str) -> bool:
    """Return True if a known brand appears in URL but NOT as the registered domain."""
    for brand in _BRAND_NAMES:
        if brand in url_lower and brand not in hostname_lower:
            return True
    return False


def _has_repeated_domain_words(domain: str) -> bool:
    """Detect domain repetition tricks like 'paypal-paypal.com'."""
    parts = re.split(r'[-_.]', domain.lower())
    seen = set()
    for p in parts:
        if len(p) > 3 and p in seen:
            return True
        seen.add(p)
    return False


def _consonant_ratio(s: str) -> float:
    """High consonant ratio in domain indicates randomly generated (DGA) names."""
    consonants = sum(1 for c in s.lower() if c in 'bcdfghjklmnpqrstvwxyz')
    letters = sum(1 for c in s.lower() if c.isalpha())
    return consonants / max(letters, 1)


# ── Main feature extractor ────────────────────────────────────────────────────

def extract_features(url: str) -> Dict[str, float]:
    """
    Extract a flat dictionary of numeric URL features.
    Returns a dict suitable for passing to a sklearn model.
    """
    parsed = urllib.parse.urlparse(url)
    ext = tldextract.extract(url)

    full_url = url
    domain = parsed.netloc or ""
    path = parsed.path or ""
    hostname = ext.domain or ""
    subdomain = ext.subdomain or ""
    suffix = f".{ext.suffix}" if ext.suffix else ""
    registered_domain = ext.registered_domain or ""

    url_length    = len(full_url)
    domain_length = len(domain)
    path_length   = len(path)

    num_dots      = full_url.count(".")
    num_hyphens   = full_url.count("-")
    num_digits    = sum(c.isdigit() for c in full_url)
    num_special   = sum(1 for c in full_url if c in "@!#$%^&*()=+[]{}|;:,<>?~`")
    num_slashes   = full_url.count("/")
    num_at        = full_url.count("@")
    num_question  = full_url.count("?")
    num_equal     = full_url.count("=")
    num_ampersand = full_url.count("&")
    num_percent   = full_url.count("%")

    num_subdomains = len([s for s in subdomain.split(".") if s]) if subdomain else 0
    has_ip         = _has_ip_in_host(parsed.hostname or "")
    has_https      = 1.0 if parsed.scheme.lower() == "https" else 0.0

    url_lower = full_url.lower()
    num_suspicious_keywords = sum(1 for kw in SUSPICIOUS_KEYWORDS if kw in url_lower)
    has_suspicious_tld      = 1.0 if suffix.lower() in SUSPICIOUS_TLDS else 0.0
    contains_brand          = _contains_brand(url_lower, hostname.lower())
    has_double_slash        = 1.0 if "//" in path else 0.0
    has_non_standard_port   = 1.0 if (parsed.port and parsed.port not in (80, 443)) else 0.0

    digit_ratio   = num_digits / max(url_length, 1)
    special_ratio = num_special / max(url_length, 1)
    query_length  = len(parsed.query or "")

    # ── New accuracy-boosting features ────────────────────────────────────────
    # Domain entropy — high entropy = likely DGA / randomly generated domain
    domain_entropy = _shannon_entropy(hostname)

    # Domain-only digit ratio — digits in domain itself (not full URL)
    domain_digits = sum(c.isdigit() for c in hostname)
    domain_digit_ratio = domain_digits / max(len(hostname), 1)

    # Consonant ratio — high value = likely auto-generated domain
    domain_consonant_ratio = _consonant_ratio(hostname)

    # Is registered domain in known-safe whitelist?
    is_known_safe = 1.0 if hostname.lower() in _KNOWN_SAFE_DOMAINS else 0.0

    # Homoglyph detection — unicode lookalike chars in URL (IDN homograph attack)
    has_homoglyphs = 1.0 if _has_homoglyphs(registered_domain) else 0.0

    # Repeated domain words (e.g. paypal-paypal.xyz)
    has_repeated_words = 1.0 if _has_repeated_domain_words(registered_domain) else 0.0

    # Path depth — very deep paths with long params = suspicious
    path_depth = path.count("/")

    # Encoded characters in path (obfuscation)
    num_encoded = url_lower.count("%")

    # Domain has no vowels (possible DGA)
    domain_vowels = sum(1 for c in hostname.lower() if c in 'aeiou')
    domain_has_no_vowels = 1.0 if (len(hostname) > 3 and domain_vowels == 0) else 0.0

    # Subdomain depth — many subdomains is suspicious
    subdomain_depth = num_subdomains

    # TLD length — very long TLD = suspicious
    tld_length = len(ext.suffix) if ext.suffix else 0

    # URL has redirect keywords
    redirect_keywords = ["redirect", "redir", "url=", "link=", "goto=", "r=", "u=", "out="]
    has_redirect_kw = 1.0 if any(kw in url_lower for kw in redirect_keywords) else 0.0

    return {
        # Original features (preserve for model compatibility)
        "url_length":               float(url_length),
        "domain_length":            float(domain_length),
        "path_length":              float(path_length),
        "num_dots":                 float(num_dots),
        "num_hyphens":              float(num_hyphens),
        "num_digits":               float(num_digits),
        "num_special":              float(num_special),
        "num_slashes":              float(num_slashes),
        "num_at":                   float(num_at),
        "num_question":             float(num_question),
        "num_equal":                float(num_equal),
        "num_ampersand":            float(num_ampersand),
        "num_percent":              float(num_percent),
        "num_subdomains":           float(num_subdomains),
        "has_ip":                   float(has_ip),
        "has_https":                float(has_https),
        "num_suspicious_keywords":  float(num_suspicious_keywords),
        "has_suspicious_tld":       float(has_suspicious_tld),
        "contains_brand":           float(contains_brand),
        "has_double_slash":         float(has_double_slash),
        "has_non_standard_port":    float(has_non_standard_port),
        "digit_ratio":              float(digit_ratio),
        "special_ratio":            float(special_ratio),
        "query_length":             float(query_length),
        # New enhanced features
        "domain_entropy":           float(domain_entropy),
        "domain_digit_ratio":       float(domain_digit_ratio),
        "domain_consonant_ratio":   float(domain_consonant_ratio),
        "is_known_safe":            float(is_known_safe),
        "has_homoglyphs":           float(has_homoglyphs),
        "has_repeated_words":       float(has_repeated_words),
        "path_depth":               float(path_depth),
        "domain_has_no_vowels":     float(domain_has_no_vowels),
        "subdomain_depth":          float(subdomain_depth),
        "tld_length":               float(tld_length),
        "has_redirect_kw":          float(has_redirect_kw),
    }


# Defined AFTER helpers and extract_features — called at module import time
FEATURE_NAMES: List[str] = list(extract_features("http://example.com").keys())
