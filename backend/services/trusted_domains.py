"""
services/trusted_domains.py
Trusted-domain verification for URL analysis.

Provides proper parsed-hostname matching against a curated list of trusted
registered domains.  Uses tldextract to prevent suffix attacks, subdomain
spoofing, and substring matching mistakes.

A URL is considered "trusted" only when:
  1. Its scheme is HTTPS.
  2. Its *registered domain* (e.g. "google.com") exactly matches an entry in
     TRUSTED_DOMAINS.
  3. No external threats were found (evaluated separately in scoring_service).

This module deliberately does NOT perform live DNS or reputation lookups.
"""

from typing import NamedTuple

import tldextract

# ── Curated trusted registered domains ───────────────────────────────────────
# Format: "registered-domain.tld"  (lowercase, no www or other subdomains)
#
# RULES FOR MAINTAINING THIS LIST:
#   * Match on registered domain only — subdomains (www., mail., ...) are
#     accepted automatically because tldextract strips them.
#   * All entries must be lowercase.
#   * Verify the domain belongs to a well-known, reputable organisation.
#   * Do NOT add user-generated-content hosts (e.g. *.github.io pages).
#
TRUSTED_DOMAINS: frozenset = frozenset({
    # Search & browser vendors
    "google.com",
    "bing.com",
    "duckduckgo.com",
    "yahoo.com",
    "brave.com",

    # Social & communication platforms
    "facebook.com",
    "instagram.com",
    "twitter.com",
    "x.com",
    "linkedin.com",
    "reddit.com",
    "discord.com",
    "slack.com",
    "telegram.org",
    "signal.org",
    "whatsapp.com",
    "skype.com",
    "zoom.us",

    # Developer & tech
    "github.com",
    "gitlab.com",
    "stackoverflow.com",
    "microsoft.com",
    "apple.com",
    "amazon.com",
    "python.org",
    "nodejs.org",
    "docker.com",
    "kubernetes.io",
    "mozilla.org",
    "cloudflare.com",
    "openai.com",
    "anthropic.com",
    "huggingface.co",

    # Media & reference
    "youtube.com",
    "wikipedia.org",
    "bbc.com",
    "bbc.co.uk",
    "reuters.com",
    "nytimes.com",
    "bloomberg.com",
    "theguardian.com",
    "cnn.com",
    "netflix.com",
    "spotify.com",
    "twitch.tv",
    "vimeo.com",

    # E-commerce & payments
    "paypal.com",
    "stripe.com",
    "ebay.com",
    "etsy.com",
    "walmart.com",
    "shopify.com",
    "visa.com",
    "mastercard.com",

    # Productivity & storage
    "dropbox.com",
    "notion.so",
    "atlassian.com",
    "salesforce.com",
    "adobe.com",
    "wordpress.com",
    "medium.com",

    # Finance & banking
    "chase.com",
    "wellsfargo.com",
    "bankofamerica.com",
    "citibank.com",
    "hsbc.com",
    "barclays.co.uk",
    "coinbase.com",
})


# ── Trust verdict ─────────────────────────────────────────────────────────────

class TrustVerdict(NamedTuple):
    is_trusted: bool
    registered_domain: str
    reason: str


def is_trusted_domain(url: str) -> TrustVerdict:
    """
    Determine whether a URL belongs to a verified-trusted registered domain.

    Matching rules
    --------------
    Only HTTPS URLs can receive trusted status.

    Uses tldextract to extract the registered domain component, preventing:
        Suffix attack     ->  google.com.evil.example
                              registered_domain = "evil.example"   NOT trusted
        @ credential      ->  https://google.com@attacker.example
                              hostname = "attacker.example"        NOT trusted
        Substring match   ->  https://notgoogle.com
                              registered_domain = "notgoogle.com"  NOT trusted
        Subdomain allowed ->  https://www.google.com
                              registered_domain = "google.com"     TRUSTED

    Returns a TrustVerdict(is_trusted, registered_domain, reason).
    Never raises -- exceptions are caught and returned as is_trusted=False.
    """
    try:
        url_stripped = url.strip()

        # Require HTTPS (scheme check before expensive tldextract call)
        if not url_stripped.lower().startswith("https://"):
            return TrustVerdict(
                is_trusted=False,
                registered_domain="",
                reason="URL uses HTTP instead of HTTPS -- trusted-domain status requires HTTPS.",
            )

        ext = tldextract.extract(url_stripped)
        registered_domain = (ext.registered_domain or "").lower()

        if not registered_domain:
            return TrustVerdict(
                is_trusted=False,
                registered_domain="",
                reason="Could not extract a registered domain from the URL.",
            )

        if registered_domain in TRUSTED_DOMAINS:
            return TrustVerdict(
                is_trusted=True,
                registered_domain=registered_domain,
                reason=(
                    f"Registered domain '{registered_domain}' matched the trusted-domain list. "
                    "Hostname was parsed with tldextract to prevent suffix and spoofing attacks."
                ),
            )

        return TrustVerdict(
            is_trusted=False,
            registered_domain=registered_domain,
            reason=f"Registered domain '{registered_domain}' is not in the trusted-domain list.",
        )

    except Exception as exc:
        return TrustVerdict(
            is_trusted=False,
            registered_domain="",
            reason=f"Trusted-domain check encountered an error: {exc}",
        )
