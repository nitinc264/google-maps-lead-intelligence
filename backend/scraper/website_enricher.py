"""
Stage 3: Website Enrichment.

For businesses with a real website (not a directory / external profile),
fetch a small number of useful pages and extract emails + social links with
provenance and confidence. Uses httpx (fast, no browser needed) with a hard
per-request timeout so one slow site can't stall the pipeline.
"""
import logging
import re
from urllib.parse import urljoin, urlparse

import httpx

from backend.config import WEBSITE_PAGES_TO_INSPECT, MAX_PAGES_PER_SITE, WEBSITE_REQUEST_TIMEOUT
from backend.utils.validators import (
    is_real_business_website, is_directory_domain, extract_emails_from_text,
    is_useless_social_url, classify_social_platform,
)

logger = logging.getLogger("website_enricher")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; LeadIntelBot/1.0; local-demo-prototype)"
}

SOCIAL_HREF_RE = re.compile(
    r'href=["\']([^"\']*(?:facebook|instagram|linkedin|twitter|x\.com|youtube|youtu\.be)[^"\']*)["\']',
    re.IGNORECASE,
)


def _score_email_confidence(email: str, source_path: str) -> str:
    local_part = email.split("@")[0].lower()
    generic_prefixes = {"info", "contact", "hello", "admin", "support", "office"}
    if any(local_part.startswith(p) for p in generic_prefixes):
        return "medium" if "contact" in source_path.lower() else "medium"
    if "contact" in source_path.lower() or "about" in source_path.lower():
        return "high"
    return "medium" if local_part else "low"


async def enrich_website(website_url: str) -> dict:
    """
    Inspect a handful of pages on website_url. Returns emails, socials,
    directories and a status describing what happened.
    """
    result = {
        "email": "", "all_emails": [], "email_confidence": "", "email_sources": [],
        "facebook": "", "instagram": "", "linkedin": "", "twitter": "", "youtube": "",
        "directories": [], "website_status": "NO_WEBSITE", "pages_inspected": [],
    }

    if not website_url:
        return result

    if is_directory_domain(website_url):
        result["directories"].append(website_url)
        result["website_status"] = "EXTERNAL_PROFILE"
        return result

    if not is_real_business_website(website_url):
        result["website_status"] = "EXTERNAL_PROFILE"
        return result

    parsed = urlparse(website_url)
    base = f"{parsed.scheme}://{parsed.netloc}"

    found_emails = {}   # email -> (confidence, source_path)
    socials = {}         # platform -> url
    pages_ok = 0

    async with httpx.AsyncClient(headers=HEADERS, timeout=WEBSITE_REQUEST_TIMEOUT, follow_redirects=True) as client:
        for path in WEBSITE_PAGES_TO_INSPECT[:MAX_PAGES_PER_SITE]:
            url = urljoin(base + "/", path)
            try:
                resp = await client.get(url)
            except httpx.ConnectTimeout:
                if pages_ok == 0:
                    result["website_status"] = "TIMEOUT"
                continue
            except httpx.ConnectError as exc:
                msg = str(exc).lower()
                if pages_ok == 0:
                    result["website_status"] = "DNS_ERROR" if "name or service" in msg or "getaddrinfo" in msg else "CONNECTION_REFUSED"
                continue
            except httpx.TimeoutException:
                if pages_ok == 0:
                    result["website_status"] = "TIMEOUT"
                continue
            except Exception as exc:
                logger.debug("Website fetch failed for %s: %s", url, exc)
                continue

            if resp.status_code >= 400:
                continue

            pages_ok += 1
            result["pages_inspected"].append(path or "/")
            html = resp.text

            for email in extract_emails_from_text(html):
                if email not in found_emails:
                    found_emails[email] = _score_email_confidence(email, path)
                    result["email_sources"].append({"email": email, "page": path or "/"})

            for match in SOCIAL_HREF_RE.findall(html):
                if is_useless_social_url(match):
                    continue
                platform = classify_social_platform(match)
                if platform and platform not in socials:
                    socials[platform] = match

    if pages_ok == 0 and result["website_status"] == "NO_WEBSITE":
        result["website_status"] = "TIMEOUT"
    elif pages_ok > 0:
        result["website_status"] = "ENRICHED" if found_emails or socials else "INSPECTED"

    if found_emails:
        confidence_rank = {"high": 3, "medium": 2, "low": 1}
        best_email = max(found_emails.items(), key=lambda kv: confidence_rank.get(kv[1], 0))
        result["email"] = best_email[0]
        result["email_confidence"] = best_email[1]
        result["all_emails"] = list(found_emails.keys())

    result["facebook"] = socials.get("facebook", "")
    result["instagram"] = socials.get("instagram", "")
    result["linkedin"] = socials.get("linkedin", "")
    result["twitter"] = socials.get("twitter", "")
    result["youtube"] = socials.get("youtube", "")

    return result