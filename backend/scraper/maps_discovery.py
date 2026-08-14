"""
Stage 1: Google Maps Discovery.

Opens Google Maps search, scrolls the results feed, and extracts
one lightweight record per business card.

The extractor intentionally uses multiple fallback strategies
and conservative validation because Google Maps DOM text contains
icons, status text, ratings, hours and other UI elements mixed
with business data.
"""

import asyncio
import logging
from typing import Callable, List, Optional

from playwright.async_api import (
    async_playwright,
    Page,
    TimeoutError as PWTimeoutError,
)

from backend.config import (
    HEADLESS,
    NAV_TIMEOUT_MS,
    MAPS_SCROLL_PAUSE_MS,
    MAX_SCROLL_ATTEMPTS_WITHOUT_NEW_RESULTS,
)

from backend.utils.validators import (
    looks_like_rating,
    looks_like_phone,
    looks_like_hours,
    is_valid_category,
    clean_category,
    is_google_ad_url,
)

from backend.utils.helpers import (
    normalize_whitespace,
    make_lead_id,
)


logger = logging.getLogger(
    "maps_discovery"
)


RESULTS_FEED_SELECTOR = (
    'div[role="feed"]'
)

CARD_SELECTOR = (
    'div[role="feed"] > div > '
    'div[jsaction] '
    'a[href^="https://www.google.com/maps/place"]'
)


# =============================================================================
# QUERY → CATEGORY FALLBACK
# =============================================================================

CATEGORY_QUERY_MAP = {
    "dentist": "Dental clinic",
    "dentists": "Dental clinic",
    "dental": "Dental clinic",
    "dental clinic": "Dental clinic",

    "doctor": "Doctor",
    "doctors": "Doctor",

    "hospital": "Hospital",
    "hospitals": "Hospital",

    "restaurant": "Restaurant",
    "restaurants": "Restaurant",

    "cafe": "Cafe",
    "cafes": "Cafe",

    "coffee shop": "Coffee shop",
    "coffee": "Coffee shop",

    "salon": "Salon",
    "salons": "Salon",

    "gym": "Gym",
    "gyms": "Gym",

    "pharmacy": "Pharmacy",
    "pharmacies": "Pharmacy",

    "hotel": "Hotel",
    "hotels": "Hotel",

    "school": "School",
    "schools": "School",

    "spa": "Spa",
    "spas": "Spa",

    "laboratory": "Laboratory",
    "laboratories": "Laboratory",
    "lab": "Laboratory",

    "clinic": "Clinic",
    "clinics": "Clinic",

    "store": "Store",
    "stores": "Store",

    "shop": "Shop",
    "shops": "Shop",
}


def infer_category_from_query(
    query: str,
) -> str:
    """
    Infer a safe fallback category from the user's search query.

    Example:
        dentists in Pune
        -> Dental clinic

    This is only used when Google Maps does not expose a clean
    category in the card DOM.
    """

    if not query:
        return ""

    query_lower = query.lower().strip()

    # Prefer the longest matching phrase first.
    # This avoids "coffee" matching before "coffee shop", etc.
    for keyword in sorted(
        CATEGORY_QUERY_MAP.keys(),
        key=len,
        reverse=True,
    ):
        if keyword in query_lower:
            return CATEGORY_QUERY_MAP[
                keyword
            ]

    return ""


# =============================================================================
# CATEGORY CANDIDATE SELECTION
# =============================================================================

def choose_category_candidate(
    candidates: list[str],
    business_name: str,
    query: str,
) -> str:
    """
    Pick the most plausible category from text segments.

    We prefer:
    - short readable text
    - no numbers
    - no hours/status markers
    - no rating/review markers
    - no obvious UI glyphs
    - not the business name
    - common category terminology

    If no trustworthy category can be extracted, fall back
    to the semantic category implied by the search query.
    """

    valid_candidates = []

    for candidate in candidates:

        candidate = normalize_whitespace(
            candidate
        )

        if not candidate:
            continue

        if not is_valid_category(
            candidate,
            business_name,
        ):
            continue

        score = 0

        # ---------------------------------------------------------------------
        # Short categories are generally better.
        # ---------------------------------------------------------------------

        length = len(candidate)

        if length <= 30:
            score += 5

        elif length <= 45:
            score += 2

        else:
            score -= 3

        # ---------------------------------------------------------------------
        # Common category-like wording gets a preference.
        # ---------------------------------------------------------------------

        lowered = candidate.lower()

        category_words = {
            "clinic",
            "dentist",
            "dental",
            "hospital",
            "restaurant",
            "cafe",
            "coffee",
            "salon",
            "store",
            "shop",
            "hotel",
            "gym",
            "school",
            "doctor",
            "pharmacy",
            "laboratory",
            "lab",
            "spa",
            "agency",
            "office",
        }

        if any(
            word in lowered
            for word in category_words
        ):
            score += 10

        valid_candidates.append(
            (
                score,
                candidate,
            )
        )

    # -------------------------------------------------------------------------
    # Use the best validated Maps category if one exists.
    # -------------------------------------------------------------------------

    if valid_candidates:

        valid_candidates.sort(
            key=lambda item: (
                item[0],
                -len(item[1]),
            ),
            reverse=True,
        )

        cleaned = clean_category(
            valid_candidates[0][1],
            business_name,
        )

        if cleaned:
            return cleaned

    # -------------------------------------------------------------------------
    # Safe fallback based on the original user query.
    # -------------------------------------------------------------------------

    return infer_category_from_query(
        query
    )


# =============================================================================
# CARD EXTRACTION
# =============================================================================

async def _extract_card_data(
    card_link,
    query: str,
) -> Optional[dict]:
    """
    Extract one business card using multiple fallback strategies.
    """

    try:

        # ---------------------------------------------------------------------
        # Maps URL
        # ---------------------------------------------------------------------

        maps_url = await card_link.get_attribute(
            "href"
        )

        if not maps_url:
            return None

        # ---------------------------------------------------------------------
        # The clickable <a> wraps the whole card.
        # ---------------------------------------------------------------------

        container = card_link.locator(
            "xpath=ancestor::div[contains(@class,'Nv2PK') "
            "or @role='article'][1]"
        )

        if await container.count() == 0:

            container = card_link.locator(
                "xpath=.."
            )

        # ---------------------------------------------------------------------
        # Business name
        # ---------------------------------------------------------------------

        name = normalize_whitespace(
            await card_link.get_attribute(
                "aria-label"
            )
            or ""
        )

        # ---------------------------------------------------------------------
        # IMPORTANT:
        # Preserve original line structure.
        #
        # Previously the whole inner_text() was normalized into a single
        # string before split("\n"), which made it difficult to distinguish
        # category/address/hours/status text.
        # ---------------------------------------------------------------------

        raw_full_text = ""

        try:

            raw_full_text = await container.first.inner_text()

        except Exception:

            pass

        normalized_full_text = normalize_whitespace(
            raw_full_text
        )

        # ---------------------------------------------------------------------
        # Sponsored detection
        # ---------------------------------------------------------------------

        is_sponsored = (
            "sponsored"
            in normalized_full_text.lower()
            or "ad ·"
            in normalized_full_text.lower()
        )

        # ---------------------------------------------------------------------
        # RATING / REVIEW COUNT
        # ---------------------------------------------------------------------

        rating = ""
        review_count = ""

        try:

            rating_el = (
                container.first.locator(
                    'span[role="img"][aria-label*="star"]'
                )
            )

            if await rating_el.count() > 0:

                aria = (
                    await rating_el.first.get_attribute(
                        "aria-label"
                    )
                    or ""
                )

                parts = (
                    aria
                    .replace(
                        "stars",
                        "",
                    )
                    .replace(
                        "star",
                        "",
                    )
                    .strip()
                )

                tokens = parts.split()

                if (
                    tokens
                    and looks_like_rating(
                        tokens[0]
                    )
                ):

                    rating = tokens[0]

                review_match = [
                    token
                    for token in aria.split()
                    if token.replace(
                        ",",
                        "",
                    ).isdigit()
                ]

                if review_match:

                    review_count = (
                        review_match[-1]
                        .replace(
                            ",",
                            "",
                        )
                    )

        except Exception:

            pass

        # ---------------------------------------------------------------------
        # BASIC FIELDS
        # ---------------------------------------------------------------------

        category = ""
        search_address = ""
        phone_raw = ""
        website = ""

        # ---------------------------------------------------------------------
        # WEBSITE
        # ---------------------------------------------------------------------

        try:

            website_el = container.first.locator(
                'a[data-value="Website"], '
                'a[href*="url?q="]'
            )

            if await website_el.count() > 0:

                href = (
                    await website_el.first.get_attribute(
                        "href"
                    )
                )

                if (
                    href
                    and not is_google_ad_url(
                        href
                    )
                ):

                    website = href

        except Exception:

            pass

        # ---------------------------------------------------------------------
        # TEXT SEGMENTS
        # ---------------------------------------------------------------------

        if raw_full_text:

            # Keep line boundaries.
            lines = [
                normalize_whitespace(
                    line
                )
                for line in raw_full_text.splitlines()
                if normalize_whitespace(
                    line
                )
            ]

            category_candidates = []

            for line in lines:

                if "·" not in line:
                    continue

                segments = [
                    segment.strip()
                    for segment in line.split(
                        "·"
                    )
                    if segment.strip()
                ]

                for segment in segments:

                    segment = normalize_whitespace(
                        segment
                    )

                    if not segment:
                        continue

                    # ---------------------------------------------------------
                    # Phone candidate
                    # ---------------------------------------------------------

                    if (
                        looks_like_phone(
                            segment
                        )
                        and not phone_raw
                    ):

                        phone_raw = segment
                        continue

                    # ---------------------------------------------------------
                    # Rating candidate
                    # ---------------------------------------------------------

                    if looks_like_rating(
                        segment
                    ):

                        continue

                    # ---------------------------------------------------------
                    # Hours candidate
                    # ---------------------------------------------------------

                    if looks_like_hours(
                        segment
                    ):

                        continue

                    # ---------------------------------------------------------
                    # Address candidate
                    # ---------------------------------------------------------

                    if (
                        not search_address
                        and len(segment) > 8
                        and (
                            ","
                            in segment
                            or any(
                                char.isdigit()
                                for char in segment
                            )
                        )
                    ):

                        search_address = segment
                        continue

                    # ---------------------------------------------------------
                    # Potential category candidate
                    # ---------------------------------------------------------

                    category_candidates.append(
                        segment
                    )

            category = choose_category_candidate(
                category_candidates,
                name,
                query,
            )

        # ---------------------------------------------------------------------
        # FINAL CATEGORY FALLBACK
        # ---------------------------------------------------------------------

        if not category:

            category = infer_category_from_query(
                query
            )

        # ---------------------------------------------------------------------
        # RECORD
        # ---------------------------------------------------------------------

        record = {
            "name": name,
            "category": category,
            "search_address": search_address,
            "phone_raw": phone_raw,
            "phone": phone_raw,
            "rating": rating,
            "review_count": review_count,
            "website": website,
            "maps_url": maps_url,
            "is_sponsored": is_sponsored,
        }

        record[
            "lead_id"
        ] = make_lead_id(
            maps_url,
            name,
        )

        return record

    except Exception as exc:

        logger.warning(
            "Card extraction failed: %s",
            exc,
        )

        return None


# =============================================================================
# DISCOVERY
# =============================================================================

async def discover_leads(
    query: str,
    target_leads: int,
    on_progress: Optional[
        Callable[[dict], None]
    ] = None,
    should_stop: Optional[
        Callable[[], bool]
    ] = None,
) -> List[dict]:
    """
    Run the Maps discovery stage.
    """

    results: dict[str, dict] = {}

    async with async_playwright() as p:

        browser = await p.chromium.launch(
            headless=HEADLESS
        )

        page: Page = await browser.new_page()

        page.set_default_timeout(
            NAV_TIMEOUT_MS
        )

        # ---------------------------------------------------------------------
        # Build Google Maps search URL
        # ---------------------------------------------------------------------

        search_url = (
            "https://www.google.com/maps/search/"
            f"{query.replace(' ', '+')}"
        )

        try:

            await page.goto(
                search_url,
                wait_until="domcontentloaded",
            )

        except PWTimeoutError:

            logger.error(
                "Initial navigation to Maps timed out"
            )

            await browser.close()

            return list(
                results.values()
            )

        # ---------------------------------------------------------------------
        # Wait for results feed
        # ---------------------------------------------------------------------

        try:

            await page.wait_for_selector(
                RESULTS_FEED_SELECTOR,
                timeout=NAV_TIMEOUT_MS,
            )

        except PWTimeoutError:

            logger.warning(
                "Results feed never appeared; "
                "query may have returned a single place"
            )

            await browser.close()

            return list(
                results.values()
            )

        stagnant_scrolls = 0

        # ---------------------------------------------------------------------
        # Scroll until target number of unique businesses is reached.
        # ---------------------------------------------------------------------

        while (
            len(results) < target_leads
            and stagnant_scrolls
            < MAX_SCROLL_ATTEMPTS_WITHOUT_NEW_RESULTS
        ):

            if (
                should_stop
                and should_stop()
            ):
                break

            cards = page.locator(
                CARD_SELECTOR
            )

            count = await cards.count()

            new_found = 0

            # -----------------------------------------------------------------
            # Extract visible cards
            # -----------------------------------------------------------------

            for i in range(count):

                if (
                    len(results)
                    >= target_leads
                ):
                    break

                data = await _extract_card_data(
                    cards.nth(i),
                    query,
                )

                if (
                    data
                    and data.get(
                        "maps_url"
                    )
                    and data[
                        "maps_url"
                    ]
                    not in results
                ):

                    results[
                        data[
                            "maps_url"
                        ]
                    ] = data

                    new_found += 1

            # -----------------------------------------------------------------
            # Progress / stagnation
            # -----------------------------------------------------------------

            if new_found > 0:

                stagnant_scrolls = 0

                if on_progress:

                    on_progress(
                        {
                            "discovered": len(
                                results
                            ),
                            "target": target_leads,
                        }
                    )

            else:

                stagnant_scrolls += 1

            # -----------------------------------------------------------------
            # Target reached
            # -----------------------------------------------------------------

            if (
                len(results)
                >= target_leads
            ):
                break

            # -----------------------------------------------------------------
            # Scroll results feed
            # -----------------------------------------------------------------

            try:

                feed = page.locator(
                    RESULTS_FEED_SELECTOR
                )

                await feed.evaluate(
                    "(el) => el.scrollBy(0, el.scrollHeight)"
                )

            except Exception:

                pass

            await asyncio.sleep(
                MAPS_SCROLL_PAUSE_MS / 1000
            )

        await browser.close()

    return list(
        results.values()
    )[:target_leads]