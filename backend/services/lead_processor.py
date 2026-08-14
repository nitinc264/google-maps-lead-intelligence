"""
Stage 4 & 5: Lead Processing / Validation and Lead Scoring.

Responsibilities:
- normalize fields
- validate contact information
- conservative deduplication
- normalize social profile representations
- calculate transparent 0-100 lead score
- assign A/B/C/D lead grade
"""

from typing import List

from backend.config import (
    SCORING,
    MAX_SCORE,
    GRADE_BANDS,
)

from backend.utils.helpers import (
    normalize_phone_for_matching,
    normalize_name,
    normalize_url,
)

from backend.utils.validators import (
    is_valid_email,
    normalize_email,
    clean_category,
)


SOCIAL_KEYS = (
    "facebook",
    "instagram",
    "linkedin",
    "twitter",
    "youtube",
)


# =============================================================================
# DEDUPLICATION
# =============================================================================

def _dedup_key(
    lead: dict,
) -> str:
    """
    Secondary matching key.

    Never deduplicate by business name alone.
    """

    phone_key = normalize_phone_for_matching(
        lead.get(
            "phone",
            "",
        )
    )

    name_key = normalize_name(
        lead.get(
            "name",
            "",
        )
    )

    address_key = normalize_name(
        lead.get(
            "full_address"
        )
        or lead.get(
            "search_address",
            "",
        )
    )

    if phone_key:

        return (
            f"phone:{phone_key}|"
            f"{name_key}"
        )

    return (
        f"nameaddr:"
        f"{name_key}|"
        f"{address_key}"
    )


def deduplicate_leads(
    leads: List[dict],
) -> List[dict]:

    # -------------------------------------------------------------------------
    # Primary identity: Maps URL
    # -------------------------------------------------------------------------

    by_maps_url = {}

    for lead in leads:

        maps_url = (
            normalize_url(
                lead.get(
                    "maps_url",
                    "",
                )
            )
            or lead.get(
                "lead_id"
            )
        )

        if maps_url not in by_maps_url:

            by_maps_url[
                maps_url
            ] = lead

    # -------------------------------------------------------------------------
    # Secondary conservative deduplication
    # -------------------------------------------------------------------------

    seen_secondary = {}

    deduped = []

    for lead in by_maps_url.values():

        key = _dedup_key(
            lead
        )

        if key in seen_secondary:

            existing = seen_secondary[
                key
            ]

            if (
                _completeness_score(
                    lead
                )
                >
                _completeness_score(
                    existing
                )
            ):

                seen_secondary[
                    key
                ] = lead

                idx = deduped.index(
                    existing
                )

                deduped[idx] = lead

            continue

        seen_secondary[
            key
        ] = lead

        deduped.append(
            lead
        )

    return deduped


def _completeness_score(
    lead: dict,
) -> int:

    fields = [
        "phone",
        "email",
        "website",
        "full_address",
        "rating",
    ]

    score = sum(
        1
        for field in fields
        if lead.get(field)
    )

    social_profiles = (
        lead.get(
            "social_profiles",
            {},
        )
        or {}
    )

    score += sum(
        1
        for key in SOCIAL_KEYS
        if (
            lead.get(key)
            or social_profiles.get(key)
            or (
                key == "twitter"
                and social_profiles.get(
                    "twitter_x"
                )
            )
        )
    )

    return score


# =============================================================================
# SOCIAL NORMALIZATION
# =============================================================================

def _normalize_social_profiles(
    lead: dict,
) -> None:

    profiles = dict(
        lead.get(
            "social_profiles",
            {},
        )
        or {}
    )

    # Flat -> nested
    for key in (
        "facebook",
        "instagram",
        "linkedin",
        "youtube",
    ):

        if not profiles.get(key):

            profiles[key] = (
                lead.get(key)
                or ""
            )

    twitter_value = (
        profiles.get(
            "twitter_x"
        )
        or profiles.get(
            "twitter"
        )
        or lead.get(
            "twitter_x"
        )
        or lead.get(
            "twitter"
        )
        or ""
    )

    if twitter_value:

        profiles[
            "twitter_x"
        ] = twitter_value

    lead[
        "social_profiles"
    ] = profiles

    # Nested -> flat compatibility fields.

    lead["facebook"] = (
        profiles.get(
            "facebook"
        )
        or ""
    )

    lead["instagram"] = (
        profiles.get(
            "instagram"
        )
        or ""
    )

    lead["linkedin"] = (
        profiles.get(
            "linkedin"
        )
        or ""
    )

    lead["twitter_x"] = (
        profiles.get(
            "twitter_x"
        )
        or profiles.get(
            "twitter"
        )
        or ""
    )

    lead["twitter"] = (
        lead["twitter_x"]
    )

    lead["youtube"] = (
        profiles.get(
            "youtube"
        )
        or ""
    )


# =============================================================================
# NORMALIZATION
# =============================================================================

def normalize_lead(
    lead: dict,
) -> dict:
    """
    Normalize important lead fields.
    """

    # -------------------------------------------------------------------------
    # Category
    # -------------------------------------------------------------------------

    lead["category"] = clean_category(
        lead.get(
            "category",
            "",
        ),
        lead.get(
            "name",
            "",
        ),
    )

    if not lead["category"]:

        lead["category"] = (
            "Business"
        )

    # -------------------------------------------------------------------------
    # Phone
    # -------------------------------------------------------------------------

    lead["phone"] = (
        lead.get(
            "phone"
        )
        or ""
    ).strip()

    # -------------------------------------------------------------------------
    # Email
    # -------------------------------------------------------------------------

    raw_email = (
        lead.get(
            "email"
        )
        or ""
    )

    normalized_email = normalize_email(
        raw_email
    )

    if is_valid_email(
        normalized_email
    ):

        lead["email"] = (
            normalized_email
        )

    else:

        lead["email"] = ""

    # -------------------------------------------------------------------------
    # All emails
    # -------------------------------------------------------------------------

    valid_all_emails = []

    for email in (
        lead.get(
            "all_emails",
            [],
        )
        or []
    ):

        normalized = normalize_email(
            email
        )

        if is_valid_email(
            normalized
        ):

            valid_all_emails.append(
                normalized
            )

    lead[
        "all_emails"
    ] = list(
        dict.fromkeys(
            valid_all_emails
        )
    )

    # If primary email is valid but not in all_emails, include it.
    if (
        lead["email"]
        and lead["email"]
        not in lead["all_emails"]
    ):

        lead["all_emails"].insert(
            0,
            lead["email"],
        )

    # -------------------------------------------------------------------------
    # Website
    # -------------------------------------------------------------------------

    lead["website"] = (
        lead.get(
            "website"
        )
        or ""
    ).strip()

    # -------------------------------------------------------------------------
    # Socials
    # -------------------------------------------------------------------------

    _normalize_social_profiles(
        lead
    )

    # -------------------------------------------------------------------------
    # Directories
    # -------------------------------------------------------------------------

    lead["directories"] = list(
        dict.fromkeys(
            lead.get(
                "directories",
                [],
            )
            or []
        )
    )

    return lead


# =============================================================================
# SCORING
# =============================================================================

def score_lead(
    lead: dict,
) -> dict:

    score = 0
    contact_routes = 0

    # -------------------------------------------------------------------------
    # Phone
    # -------------------------------------------------------------------------

    if lead.get(
        "phone"
    ):

        score += SCORING[
            "phone"
        ]

        contact_routes += 1

    # -------------------------------------------------------------------------
    # Validated email
    # -------------------------------------------------------------------------

    if (
        lead.get(
            "email"
        )
        and is_valid_email(
            lead["email"]
        )
    ):

        score += SCORING[
            "email_validated"
        ]

        contact_routes += 1

        confidence = (
            lead.get(
                "email_confidence"
            )
            or ""
        ).lower()

        if confidence == "high":

            score += SCORING[
                "email_confidence_high"
            ]

        elif confidence == "medium":

            score += SCORING[
                "email_confidence_medium"
            ]

    # -------------------------------------------------------------------------
    # Website
    # -------------------------------------------------------------------------

    if lead.get(
        "website"
    ):

        score += SCORING[
            "website"
        ]

        contact_routes += 1

    # -------------------------------------------------------------------------
    # Social profiles
    # -------------------------------------------------------------------------

    social_profiles = (
        lead.get(
            "social_profiles",
            {},
        )
        or {}
    )

    instagram = (
        lead.get(
            "instagram"
        )
        or social_profiles.get(
            "instagram"
        )
    )

    facebook = (
        lead.get(
            "facebook"
        )
        or social_profiles.get(
            "facebook"
        )
    )

    linkedin = (
        lead.get(
            "linkedin"
        )
        or social_profiles.get(
            "linkedin"
        )
    )

    twitter = (
        lead.get(
            "twitter"
        )
        or lead.get(
            "twitter_x"
        )
        or social_profiles.get(
            "twitter"
        )
        or social_profiles.get(
            "twitter_x"
        )
    )

    youtube = (
        lead.get(
            "youtube"
        )
        or social_profiles.get(
            "youtube"
        )
    )

    if instagram:

        score += SCORING[
            "instagram"
        ]

        contact_routes += 1

    if facebook:

        score += SCORING[
            "facebook"
        ]

        contact_routes += 1

    if linkedin:

        score += SCORING[
            "linkedin"
        ]

        contact_routes += 1

    if twitter:

        score += SCORING[
            "twitter"
        ]

        contact_routes += 1

    if youtube:

        score += SCORING[
            "youtube"
        ]

        contact_routes += 1

    # -------------------------------------------------------------------------
    # Address
    # -------------------------------------------------------------------------

    if lead.get(
        "full_address"
    ):

        score += SCORING[
            "full_address"
        ]

    # -------------------------------------------------------------------------
    # Google Maps rating
    # -------------------------------------------------------------------------

    try:

        rating = lead.get(
            "rating"
        )

        if (
            rating
            and float(rating) >= 4.5
        ):

            score += SCORING[
                "rating_45_plus"
            ]

    except (
        ValueError,
        TypeError,
    ):
        pass

    # -------------------------------------------------------------------------
    # Multiple contact routes
    # -------------------------------------------------------------------------

    if contact_routes >= 3:

        score += SCORING[
            "three_plus_contact_routes"
        ]

    score = min(
        score,
        MAX_SCORE,
    )

    grade = "D"

    for (
        low,
        high,
        letter,
        _label,
    ) in GRADE_BANDS:

        if (
            low
            <= score
            <= high
        ):

            grade = letter
            break

    lead[
        "lead_score"
    ] = score

    lead[
        "lead_grade"
    ] = grade

    return lead


# =============================================================================
# PROCESS
# =============================================================================

def process_leads(
    leads: List[dict],
) -> List[dict]:
    """
    normalize -> deduplicate -> score
    """

    normalized = [
        normalize_lead(
            lead
        )
        for lead in leads
    ]

    deduped = deduplicate_leads(
        normalized
    )

    scored = [
        score_lead(
            lead
        )
        for lead in deduped
    ]

    scored.sort(
        key=lambda lead: lead.get(
            "lead_score",
            0,
        ),
        reverse=True,
    )

    return scored


# =============================================================================
# SUMMARY
# =============================================================================

def summarize_leads(
    leads: List[dict],
) -> dict:

    total = len(
        leads
    )

    grades = {
        "A": 0,
        "B": 0,
        "C": 0,
        "D": 0,
    }

    with_phone = 0
    with_email = 0
    with_website = 0
    with_social = 0

    for lead in leads:

        grade = lead.get(
            "lead_grade",
            "D",
        )

        grades[
            grade
        ] = grades.get(
            grade,
            0,
        ) + 1

        if lead.get(
            "phone"
        ):
            with_phone += 1

        if lead.get(
            "email"
        ):
            with_email += 1

        if lead.get(
            "website"
        ):
            with_website += 1

        social_profiles = (
            lead.get(
                "social_profiles",
                {},
            )
            or {}
        )

        has_social = any(
            [
                lead.get(
                    "facebook"
                ),
                lead.get(
                    "instagram"
                ),
                lead.get(
                    "linkedin"
                ),
                lead.get(
                    "twitter"
                ),
                lead.get(
                    "twitter_x"
                ),
                lead.get(
                    "youtube"
                ),
                social_profiles.get(
                    "facebook"
                ),
                social_profiles.get(
                    "instagram"
                ),
                social_profiles.get(
                    "linkedin"
                ),
                social_profiles.get(
                    "twitter"
                ),
                social_profiles.get(
                    "twitter_x"
                ),
                social_profiles.get(
                    "youtube"
                ),
            ]
        )

        if has_social:
            with_social += 1

    return {
        "total_leads": total,
        "grades": grades,
        "with_phone": with_phone,
        "with_email": with_email,
        "with_website": with_website,
        "with_social": with_social,
    }