"""
Field validators and normalization helpers.

These validators protect the pipeline from common Google Maps / website
extraction problems:

- rating text mistaken for category/address
- hours/status text mistaken for category
- Google UI glyphs mistaken for category
- placeholder / malformed / encoded emails
- image filenames mistaken for emails
- infrastructure-generated emails
- useless social links
- Google ad URLs
- directory URLs
"""

import re
import unicodedata
from urllib.parse import unquote

from backend.config import (
    PLACEHOLDER_EMAILS,
    IGNORED_SOCIAL_PATTERNS,
    KNOWN_DIRECTORY_DOMAINS,
)


# =============================================================================
# REGEX
# =============================================================================

RATING_RE = re.compile(
    r"^\d(?:\.\d)?$"
)

PHONE_CHARS_RE = re.compile(
    r"[^\d+]"
)

PINCODE_RE = re.compile(
    r"\b(\d{6})\b"
)

EMAIL_RE = re.compile(
    r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}"
)

HOURS_HINT_RE = re.compile(
    r"(am|pm|open|closed|24\s*hours|hours|opening|closes)",
    re.IGNORECASE,
)

REVIEW_HINT_RE = re.compile(
    r"(reviews?|stars?)",
    re.IGNORECASE,
)

URL_LIKE_RE = re.compile(
    r"(https?://|www\.)",
    re.IGNORECASE,
)

EMAIL_PERCENT_ESCAPE_RE = re.compile(
    r"%[0-9a-fA-F]{2}"
)


# =============================================================================
# EMAIL BLOCKLISTS
# =============================================================================

IMAGE_EXTENSIONS = {
    "gif",
    "png",
    "jpg",
    "jpeg",
    "webp",
    "svg",
    "ico",
}

INFRASTRUCTURE_EMAIL_DOMAINS = {
    "sentry.wixpress.com",
    "wixpress.com",
}

INFRASTRUCTURE_LOCAL_PREFIXES = {
    "ajax-loader",
    "loader",
    "noreply",
    "no-reply",
    "donotreply",
    "do-not-reply",
}


# =============================================================================
# CATEGORY FILTERING
# =============================================================================

CATEGORY_GARBAGE = {
    "",
    "·",
    "",
    "",
    "website",
    "directions",
    "book online",
    "send to phone",
    "save",
    "nearby",
    "share",
}

# Words that strongly indicate that a candidate is not a business category.
CATEGORY_REJECT_HINTS = {
    "open",
    "closed",
    "closes",
    "opening",
    "hours",
    "reviews",
    "stars",
    "directions",
    "website",
    "book online",
    "write a review",
    "send to phone",
}


# =============================================================================
# BASIC FIELD CHECKS
# =============================================================================

def looks_like_rating(value: str) -> bool:
    if not value:
        return False

    value = value.strip()

    try:
        return bool(
            RATING_RE.match(value)
        ) and 0 <= float(value) <= 5
    except (ValueError, TypeError):
        return False


def looks_like_phone(value: str) -> bool:
    if not value:
        return False

    digits = re.sub(
        r"\D",
        "",
        value,
    )

    return 7 <= len(digits) <= 15


def looks_like_address(value: str) -> bool:
    """
    Conservative address heuristic.

    Addresses are typically longer and often contain commas, numbers,
    building/unit indicators, or common street/location words.
    """

    if not value:
        return False

    value = value.strip()

    if looks_like_rating(value):
        return False

    if looks_like_hours(value):
        return False

    if looks_like_phone(value) and "," not in value:
        return False

    if len(value) <= 6:
        return False

    return True


def looks_like_hours(value: str) -> bool:
    if not value:
        return False

    return bool(
        HOURS_HINT_RE.search(value)
    )


# =============================================================================
# UNICODE / GOOGLE GLYPH DETECTION
# =============================================================================

def contains_ui_glyphs(value: str) -> bool:
    """
    Reject Google Maps UI/icon glyphs accidentally extracted as text.

    Private-use characters are especially common in icon fonts.
    """

    if not value:
        return False

    for char in value:

        category = unicodedata.category(char)

        # Private-use area / surrogate / unassigned characters.
        if category in {"Co", "Cs", "Cn"}:
            return True

    return False


def has_reasonable_text_content(value: str) -> bool:
    """
    Ensure the value contains real readable text rather than only symbols.
    """

    if not value:
        return False

    letters = 0
    numbers = 0
    other = 0

    for char in value:

        if char.isalpha():
            letters += 1

        elif char.isdigit():
            numbers += 1

        else:
            other += 1

    if letters < 3:
        return False

    total = letters + numbers + other

    if total == 0:
        return False

    # Most of the candidate should be meaningful text.
    if letters / total < 0.35:
        return False

    return True


# =============================================================================
# CATEGORY VALIDATION
# =============================================================================

def _name_token_overlap(
    candidate: str,
    business_name: str,
) -> int:
    """
    Count meaningful words shared by candidate and business name.
    """

    if not candidate or not business_name:
        return 0

    stop_words = {
        "the",
        "and",
        "of",
        "in",
        "for",
        "at",
        "by",
        "a",
        "an",
    }

    candidate_tokens = {
        token
        for token in re.findall(
            r"[a-zA-Z]+",
            candidate.lower(),
        )
        if len(token) >= 3
        and token not in stop_words
    }

    name_tokens = {
        token
        for token in re.findall(
            r"[a-zA-Z]+",
            business_name.lower(),
        )
        if len(token) >= 3
        and token not in stop_words
    }

    return len(
        candidate_tokens.intersection(
            name_tokens
        )
    )


def is_valid_category(
    value: str,
    business_name: str,
) -> bool:
    """
    Validate a business category extracted from a Maps card.

    Examples accepted:
        Dental clinic
        Dentist
        Restaurant
        Coffee shop
        Hospital

    Examples rejected:
        
        Opens 10 am
        City Dental Care City Dental Care 5.0(345)
        exact business name
        long UI/status strings
    """

    if not value:
        return False

    value = " ".join(
        value.strip().split()
    )

    if not value:
        return False

    lowered = value.lower()

    if lowered in CATEGORY_GARBAGE:
        return False

    if contains_ui_glyphs(value):
        return False

    if URL_LIKE_RE.search(value):
        return False

    if looks_like_rating(value):
        return False

    if looks_like_phone(value):
        return False

    if looks_like_hours(value):
        return False

    if REVIEW_HINT_RE.search(value):
        return False

    if any(
        hint in lowered
        for hint in CATEGORY_REJECT_HINTS
    ):
        return False

    # Categories should be concise.
    if len(value) > 55:
        return False

    # Reject text that is mostly punctuation/symbols.
    if not has_reasonable_text_content(value):
        return False

    # A category should not be identical to the business name.
    if business_name:

        name_clean = " ".join(
            business_name.strip().split()
        ).lower()

        if lowered == name_clean:
            return False

    # If the candidate repeats many business-name words, it is probably
    # the business name/card text rather than the category.
    overlap = _name_token_overlap(
        value,
        business_name,
    )

    candidate_tokens = re.findall(
        r"[a-zA-Z]+",
        value,
    )

    if (
        len(candidate_tokens) >= 3
        and overlap >= 3
    ):
        return False

    return True


def clean_category(
    value: str,
    business_name: str = "",
) -> str:
    """
    Normalize a category and return an empty string when it is not trustworthy.
    """

    if not value:
        return ""

    value = " ".join(
        value.strip().split()
    )

    if not is_valid_category(
        value,
        business_name,
    ):
        return ""

    # Avoid accidental trailing separators.
    value = value.strip(" ·|-")

    return value


# =============================================================================
# PHONE
# =============================================================================

def clean_phone(value: str) -> str:
    if not value:
        return ""

    value = value.replace(
        "tel:",
        "",
    )

    cleaned = PHONE_CHARS_RE.sub(
        "",
        value,
    )

    return cleaned.strip()


# =============================================================================
# PINCODE
# =============================================================================

def extract_pincode(
    address: str,
) -> str:

    if not address:
        return ""

    match = PINCODE_RE.search(
        address
    )

    return (
        match.group(1)
        if match
        else ""
    )


# =============================================================================
# GOOGLE / WEBSITE URL VALIDATION
# =============================================================================

def is_google_ad_url(
    url: str,
) -> bool:

    if not url:
        return False

    lowered = url.lower()

    ad_markers = [
        "googleadservices.com",
        "google.com/aclk",
        "gclid=",
        "/aclk?",
    ]

    return any(
        marker in lowered
        for marker in ad_markers
    )


def is_real_business_website(
    url: str,
) -> bool:

    if not url:
        return False

    if is_google_ad_url(url):
        return False

    lowered = url.lower()

    if "google.com/maps" in lowered:
        return False

    if lowered.startswith(
        "https://www.google.com/search"
    ):
        return False

    return (
        url.startswith("http://")
        or url.startswith("https://")
    )


def is_directory_domain(
    url: str,
) -> bool:

    if not url:
        return False

    lowered = url.lower()

    return any(
        domain in lowered
        for domain in KNOWN_DIRECTORY_DOMAINS
    )


# =============================================================================
# EMAIL VALIDATION
# =============================================================================

def normalize_email(
    email: str,
) -> str:
    """
    Decode URL-encoded email values and normalize whitespace/case.

    Example:
        %20laconicdentalstudio@gmail.com
        ->
        laconicdentalstudio@gmail.com
    """

    if not email:
        return ""

    try:
        email = unquote(
            email
        )
    except Exception:
        pass

    email = email.strip()
    email = email.strip(
        " \t\r\n<>\"'()[]{};,:"
    )

    return email.lower()


def is_placeholder_email(
    email: str,
) -> bool:

    normalized = normalize_email(
        email
    )

    if not normalized:
        return True

    if normalized in {
        item.lower()
        for item in PLACEHOLDER_EMAILS
    }:
        return True

    return False


def is_infrastructure_email(
    email: str,
) -> bool:

    normalized = normalize_email(
        email
    )

    if not normalized or "@" not in normalized:
        return True

    local_part, domain = normalized.split(
        "@",
        1,
    )

    if domain in INFRASTRUCTURE_EMAIL_DOMAINS:
        return True

    if any(
        local_part.startswith(prefix)
        for prefix in INFRASTRUCTURE_LOCAL_PREFIXES
    ):
        return True

    # Example:
    # ajax-loader@2x.gif
    domain_tld = (
        domain.rsplit(".", 1)[-1]
        if "." in domain
        else ""
    )

    if domain_tld in IMAGE_EXTENSIONS:
        return True

    # Sentry/Wix generated addresses often contain long hex IDs.
    if (
        "wixpress" in domain
        or "sentry" in domain
    ):
        return True

    return False


def is_valid_email(
    email: str,
) -> bool:

    normalized = normalize_email(
        email
    )

    if not normalized:
        return False

    if is_placeholder_email(
        normalized
    ):
        return False

    if is_infrastructure_email(
        normalized
    ):
        return False

    # Reject obviously encoded/malformed remnants.
    if EMAIL_PERCENT_ESCAPE_RE.search(
        normalized
    ):
        return False

    if normalized.startswith("%"):
        return False

    if normalized.endswith("%"):
        return False

    if not EMAIL_RE.fullmatch(
        normalized
    ):
        return False

    local_part, domain = normalized.split(
        "@",
        1,
    )

    if len(local_part) > 80:
        return False

    if len(domain) > 255:
        return False

    if ".." in normalized:
        return False

    if domain.startswith(".") or domain.endswith("."):
        return False

    if "." not in domain:
        return False

    return True


def extract_emails_from_text(
    text: str,
) -> list:
    """
    Extract, normalize, validate and deduplicate emails.
    """

    if not text:
        return []

    raw_matches = EMAIL_RE.findall(
        text
    )

    cleaned = set()

    for raw_email in raw_matches:

        normalized = normalize_email(
            raw_email
        )

        if is_valid_email(
            normalized
        ):
            cleaned.add(
                normalized
            )

    return sorted(
        cleaned
    )


# =============================================================================
# SOCIAL URL VALIDATION
# =============================================================================

def is_useless_social_url(
    url: str,
) -> bool:

    if not url:
        return True

    lowered = url.lower()

    return any(
        pattern in lowered
        for pattern in IGNORED_SOCIAL_PATTERNS
    )


def classify_social_platform(
    url: str,
) -> str:

    if not url:
        return ""

    lowered = url.lower()

    if "facebook.com" in lowered:
        return "facebook"

    if "instagram.com" in lowered:
        return "instagram"

    if "linkedin.com" in lowered:
        return "linkedin"

    if (
        "twitter.com" in lowered
        or "x.com" in lowered
    ):
        return "twitter"

    if (
        "youtube.com" in lowered
        or "youtu.be" in lowered
    ):
        return "youtube"

    return ""