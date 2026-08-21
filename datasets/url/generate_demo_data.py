"""
datasets/url/generate_demo_data.py

Synthetic URL dataset generator for pipeline testing.
Produces a CSV with realistic-looking benign and phishing URLs.

This is for PIPELINE TESTING ONLY.
Replace with a real labeled dataset (e.g., PhishTank + Alexa top-1M)
before making any performance claims.

Usage:
    python datasets/url/generate_demo_data.py
"""

import random
import sys
import os
from pathlib import Path

import pandas as pd

OUTPUT_PATH = Path(__file__).parent / "url_dataset.csv"

# ── Seed values ───────────────────────────────────────────────────────────────

BENIGN_DOMAINS = [
    "google.com", "wikipedia.org", "github.com", "stackoverflow.com",
    "amazon.com", "bbc.co.uk", "nytimes.com", "reddit.com", "youtube.com",
    "microsoft.com", "apple.com", "linkedin.com", "twitter.com",
    "openai.com", "python.org", "django-rest-framework.org", "fastapi.tiangolo.com",
]

BENIGN_PATHS = [
    "/", "/about", "/contact", "/products", "/services",
    "/blog/article-123", "/docs/getting-started", "/search?q=python",
    "/news/technology", "/shop/items?page=2",
]

PHISHING_PATTERNS = [
    "http://{brand}-secure-login.{tld}/account/verify",
    "http://{ip}/login?redirect=paypal.com",
    "http://secure-{brand}.{suspicious_tld}/signin.php",
    "http://{subdomain}.{brand}-verification.{tld}/update",
    "http://{brand}.{random_str}.{tld}/login/authenticate",
    "http://{ip}:{port}/verify-account?user=admin&token={token}",
    "http://{brand}-alert-{random_str}.{suspicious_tld}/action",
    "https://www.{brand}@{ip}/secure/login",
]

BRANDS = ["paypal", "apple", "microsoft", "amazon", "netflix", "google", "ebay", "facebook"]
SUSPICIOUS_TLDS = ["tk", "ml", "ga", "cf", "gq", "xyz", "top", "click"]
SAFE_TLDS = ["com", "org", "net", "edu", "gov"]
SUBDOMAINS = ["secure", "login", "verify", "account", "update", "billing", "support"]


def _rand_ip() -> str:
    return f"{random.randint(1,254)}.{random.randint(0,255)}.{random.randint(0,255)}.{random.randint(1,254)}"


def _rand_str(length: int = 8) -> str:
    chars = "abcdefghijklmnopqrstuvwxyz0123456789"
    return "".join(random.choices(chars, k=length))


def _rand_token() -> str:
    return _rand_str(32)


def generate_benign_url() -> str:
    domain = random.choice(BENIGN_DOMAINS)
    path = random.choice(BENIGN_PATHS)
    scheme = random.choice(["https", "https", "https", "http"])
    return f"{scheme}://www.{domain}{path}"


def generate_phishing_url() -> str:
    pattern = random.choice(PHISHING_PATTERNS)
    brand = random.choice(BRANDS)
    tld = random.choice(SAFE_TLDS)
    suspicious_tld = random.choice(SUSPICIOUS_TLDS)
    subdomain = random.choice(SUBDOMAINS)
    ip = _rand_ip()
    port = random.choice([8080, 8443, 4443, 9090])
    random_str = _rand_str()
    token = _rand_token()
    url = pattern.format(
        brand=brand, tld=tld, suspicious_tld=suspicious_tld,
        subdomain=subdomain, ip=ip, port=port,
        random_str=random_str, token=token,
    )
    return url


def generate(n_benign: int = 1500, n_phishing: int = 1500) -> pd.DataFrame:
    random.seed(42)
    benign_urls = [generate_benign_url() for _ in range(n_benign)]
    phishing_urls = [generate_phishing_url() for _ in range(n_phishing)]

    urls = benign_urls + phishing_urls
    labels = [0] * n_benign + [1] * n_phishing

    df = pd.DataFrame({"url": urls, "label": labels})
    df = df.sample(frac=1, random_state=42).reset_index(drop=True)
    return df


if __name__ == "__main__":
    print("[TrustAI] Generating synthetic URL demo dataset …")
    print("[WARN]    This is for pipeline testing only. Use a real dataset for results.")
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    df = generate()
    df.to_csv(OUTPUT_PATH, index=False)
    print(f"[INFO] Saved {len(df)} rows -> {OUTPUT_PATH}")
    print(f"       Benign: {(df['label']==0).sum()} | Phishing: {(df['label']==1).sum()}")
